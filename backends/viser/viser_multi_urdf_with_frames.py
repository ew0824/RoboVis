"""
Enhanced Multi-URDF Viser system with individual coordinate frame controls.
Each joint and link gets its own coordinate frame toggle button in the GUI.

Launch:
    python backends/viser/viser_multi_urdf_with_frames.py --workcell workcell_alpha_2 --stress --stress-hz 200
"""

from __future__ import annotations

import time
import asyncio
import threading
import websockets
from typing import Dict, List, Optional, Set, Tuple
import msgpack
import os
import re
from pathlib import Path

import numpy as np
import tyro
from yourdfpy import URDF

import viser

# Import our extended ViserUrdf class
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from viser_urdf_extended import ViserUrdfExtended

# Global telemetry counter and timing
seq_counter = 0
last_telemetry_time = time.perf_counter()

# WebSocket telemetry clients
telemetry_clients: Set[websockets.WebSocketServerProtocol] = set()

class PackagePathResolver:
    """Resolves ROS package:// URIs to actual file paths in the robot_description folder."""
    
    def __init__(self, robot_description_path: str = "assets/robot_description"):
        self.robot_description_path = Path(robot_description_path)
        self.package_map = self._build_package_map()
        
    def _build_package_map(self) -> Dict[str, Path]:
        """Build a mapping from ROS package names to actual directories."""
        package_map = {}
        
        if not self.robot_description_path.exists():
            print(f"[PATH_RESOLVER] Warning: {self.robot_description_path} does not exist")
            return package_map
            
        # Map each subdirectory as a potential ROS package
        for subdir in self.robot_description_path.iterdir():
            if subdir.is_dir():
                package_map[subdir.name] = subdir
                
        print(f"[PATH_RESOLVER] Found {len(package_map)} packages:")
        for pkg_name, pkg_path in package_map.items():
            print(f"  - {pkg_name} → {pkg_path}")
            
        return package_map
        
    def resolve_package_uri(self, package_uri: str) -> Optional[str]:
        """Convert package://package_name/path to actual file path."""
        if not package_uri.startswith("package://"):
            return package_uri
            
        # Extract package name and relative path
        uri_parts = package_uri[10:].split("/", 1)  # Remove "package://"
        if len(uri_parts) < 2:
            return None
            
        package_name, relative_path = uri_parts
        
        if package_name not in self.package_map:
            # Try fuzzy matching for common variations
            for pkg_name in self.package_map.keys():
                if package_name in pkg_name or pkg_name in package_name:
                    print(f"[PATH_RESOLVER] Fuzzy match: {package_name} → {pkg_name}")
                    package_name = pkg_name
                    break
            else:
                print(f"[PATH_RESOLVER] Package not found: {package_name}")
                return None
                
        resolved_path = self.package_map[package_name] / relative_path
        
        if resolved_path.exists():
            return str(resolved_path)
        else:
            print(f"[PATH_RESOLVER] File not found: {resolved_path}")
            return None


class SmartUrdfManager:
    """Enhanced URDF manager with individual coordinate frame controls."""
    
    def __init__(self, server: viser.ViserServer):
        self.server = server
        self.path_resolver = PackagePathResolver()
        self.viser_urdfs: List[ViserUrdfExtended] = []
        self.urdf_configs: List[Dict] = []
        self.filtered_joint_limits: Dict[str, Tuple[float, float]] = {}
        self.filtered_joint_names: List[str] = []
        
        # Note: Individual coordinate frame management is now handled by ViserUrdfExtended
        
    def _patch_urdf_mesh_paths(self, urdf_content: str) -> str:
        """Replace package:// URIs with resolved file paths in URDF content."""
        def replace_package_uri(match):
            package_uri = match.group(1)
            resolved_path = self.path_resolver.resolve_package_uri(package_uri)
            if resolved_path:
                return f'filename="{resolved_path}"'
            else:
                print(f"[URDF_PATCHER] Could not resolve: {package_uri}")
                return match.group(0)  # Return original if can't resolve
                
        # Replace all package:// URIs in mesh filename attributes
        pattern = r'filename="(package://[^"]+)"'
        patched_content = re.sub(pattern, replace_package_uri, urdf_content)
        
        return patched_content
        
    def _is_meaningful_joint(self, joint_name: str, joint_type: str, joint_limits: Tuple[Optional[float], Optional[float]]) -> bool:
        """Determine if a joint should have a slider (is meaningful for visualization)."""
        lower, upper = joint_limits
        
        # Skip continuous joints that are typically for conveyors/wheels
        if joint_type == "continuous":
            # Exception: wrist joints might be continuous but are meaningful
            if any(keyword in joint_name.lower() for keyword in ["wrist", "eoat", "tool"]):
                return True
            return False
            
        # Skip fixed joints
        if joint_type == "fixed":
            return False
            
        # Skip joints with no meaningful range
        if lower is not None and upper is not None and abs(upper - lower) < 1e-6:
            return False
            
        # Skip joints that are clearly auxiliary (like rollers, belts)
        auxiliary_keywords = ["roller", "belt", "conveyor", "hardstop"]
        if any(keyword in joint_name.lower() for keyword in auxiliary_keywords):
            return False
            
        return True
        
    def _get_short_joint_name(self, full_joint_name: str) -> str:
        """Create a shorter, more readable joint name."""
        # Remove common prefixes
        name = full_joint_name
        prefixes_to_remove = [
            "band_separator_", "robot_gantry_", "scara_", "infeed_", "gantry_"
        ]
        
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
                
        # Replace underscores with spaces and title case
        name = name.replace("_", " ").title()
        
        # Shorten common terms
        replacements = {
            "To": "→",
            "Base To": "",
            "Stage": "Stage",
            "Arm 1": "Arm1",
            "Arm 2": "Arm2",
        }
        
        for old, new in replacements.items():
            name = name.replace(old, new)
            
        return name.strip()
    
    def _compute_joint_poses(self) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Compute world poses for all joints using forward kinematics."""
        joint_poses = {}
        
        for config in self.urdf_configs:
            urdf_name = config["name"]
            urdf = config["urdf"]
            viser_urdf = config["viser_urdf"]
            
            try:
                # Get current joint configuration
                actuated_joints = viser_urdf.get_actuated_joint_limits()
                joint_angles = {}
                
                # Build joint angles dictionary
                for joint_name in actuated_joints.keys():
                    unique_name = f"{urdf_name}::{joint_name}"
                    if unique_name in self.filtered_joint_names:
                        idx = self.filtered_joint_names.index(unique_name)
                        # This will be set by the calling function
                        joint_angles[joint_name] = 0.0
                    else:
                        # Use default for auxiliary joints
                        lower, upper = actuated_joints[joint_name]
                        if lower is not None and upper is not None:
                            joint_angles[joint_name] = (lower + upper) / 2.0
                        else:
                            joint_angles[joint_name] = 0.0
                
                # Compute forward kinematics for all links
                fk = urdf.link_fk(cfg=joint_angles)
                
                # Extract poses for joints (which connect links)
                for joint in urdf.robot.joints:
                    if joint.child in fk:
                        # Get the transform matrix
                        transform = fk[joint.child]
                        position = transform[:3, 3]
                        
                        # Convert rotation matrix to quaternion (w, x, y, z)
                        rotation_matrix = transform[:3, :3]
                        r = Rotation.from_matrix(rotation_matrix)
                        quat_wxyz = r.as_quat()  # Returns [x, y, z, w]
                        quat_wxyz = np.array([quat_wxyz[3], quat_wxyz[0], quat_wxyz[1], quat_wxyz[2]])  # Convert to [w, x, y, z]
                        
                        frame_name = f"{urdf_name}_{joint.name}"
                        joint_poses[frame_name] = (position, quat_wxyz)
                        
            except Exception as e:
                print(f"[FRAMES] Error computing poses for {urdf_name}: {e}")
                
        return joint_poses
    
        
    def add_urdf(self, urdf_path: str, name: str, load_meshes: bool = True, 
                 load_collision_meshes: bool = True):
        """Add a URDF with smart path resolution and joint filtering."""
        try:
            print(f"[SMART-URDF] Loading {name} from {urdf_path}")
            
            # Read and patch URDF content
            with open(urdf_path, 'r') as f:
                urdf_content = f.read()
                
            patched_content = self._patch_urdf_mesh_paths(urdf_content)
            
            # Write patched URDF to temp file
            temp_urdf_path = f"/tmp/patched_{name}_{int(time.time())}.urdf"
            with open(temp_urdf_path, 'w') as f:
                f.write(patched_content)
            
            # Load patched URDF
            urdf = URDF.load(
                temp_urdf_path,
                load_meshes=load_meshes,
                build_scene_graph=load_meshes,
                load_collision_meshes=load_collision_meshes,
                build_collision_scene_graph=load_collision_meshes,
            )
            
            # Create ViserUrdfExtended instance with individual coordinate frame controls
            viser_urdf = ViserUrdfExtended(
                self.server,
                urdf_or_path=urdf,
                load_meshes=load_meshes,
                load_collision_meshes=load_collision_meshes,
                collision_mesh_color_override=(1.0, 0.0, 0.0, 0.5),
                root_node_name=f"/{name}",
                frame_scale=0.1,
            )
            
            # Store configuration
            config = {
                "name": name,
                "path": urdf_path,
                "urdf": urdf,
                "viser_urdf": viser_urdf
            }
            
            self.viser_urdfs.append(viser_urdf)
            self.urdf_configs.append(config)
            
            # Get ALL joint information from URDF
            all_joints = {}  # joint_name -> (type, limits)
            for joint in urdf.robot.joints:
                if hasattr(joint, 'limit') and joint.limit:
                    limits = (joint.limit.lower, joint.limit.upper)
                else:
                    limits = (None, None)
                all_joints[joint.name] = (joint.type, limits)
            
            # Filter meaningful joints
            actuated_joints = viser_urdf.get_actuated_joint_limits()
            meaningful_joints = {}
            
            for joint_name, limits in actuated_joints.items():
                if joint_name in all_joints:
                    joint_type, _ = all_joints[joint_name]
                    if self._is_meaningful_joint(joint_name, joint_type, limits):
                        meaningful_joints[joint_name] = limits
                        
            print(f"[SMART-URDF] {name}: {len(actuated_joints)} actuated joints, {len(meaningful_joints)} meaningful")
            
            for joint_name in meaningful_joints.keys():
                joint_type = all_joints[joint_name][0] if joint_name in all_joints else "unknown" 
                print(f"  ✅ {joint_name} ({joint_type})")
                
            filtered_count = len(actuated_joints) - len(meaningful_joints)
            if filtered_count > 0:
                print(f"  🚫 Filtered out {filtered_count} auxiliary joints (conveyors, fixed, etc.)")
            
            # Count total joints for coordinate frames
            total_joints = len(urdf.robot.joints)
            print(f"  📐 Total joints for coordinate frames: {total_joints}")
            
            # Add to global joint collection with unique naming
            for joint_name, limits in meaningful_joints.items():
                unique_name = f"{name}::{joint_name}"
                self.filtered_joint_limits[unique_name] = limits
                self.filtered_joint_names.append(unique_name)
                
            # Clean up temp file
            try:
                os.unlink(temp_urdf_path)
            except:
                pass
                
        except Exception as e:
            print(f"[SMART-URDF] Error loading {name}: {e}")
            import traceback
            traceback.print_exc()
            
    def get_total_meaningful_dof(self) -> int:
        """Get total meaningful degrees of freedom (excluding auxiliary joints)."""
        return len(self.filtered_joint_limits)
        
    def update_all_configurations(self, joint_values: np.ndarray):
        """Update all URDF configurations and coordinate frames with provided joint values."""
        if len(joint_values) != len(self.filtered_joint_names):
            print(f"[SMART-URDF] Warning: Expected {len(self.filtered_joint_names)} joint values, got {len(joint_values)}")
            return
            
        # Group joint values by URDF
        urdf_joint_values = {}
        
        for i, joint_name in enumerate(self.filtered_joint_names):
            urdf_name, actual_joint_name = joint_name.split("::", 1)
            if urdf_name not in urdf_joint_values:
                urdf_joint_values[urdf_name] = {}
            urdf_joint_values[urdf_name][actual_joint_name] = joint_values[i]
        
        # Update each ViserUrdf instance
        for config in self.urdf_configs:
            urdf_name = config["name"]
            viser_urdf = config["viser_urdf"]
            
            if urdf_name in urdf_joint_values:
                # Get ALL actuated joint limits for this URDF (including filtered ones)
                all_urdf_joints = viser_urdf.get_actuated_joint_limits()
                
                # Create configuration array in correct order
                cfg = []
                for joint_name in all_urdf_joints.keys():
                    if joint_name in urdf_joint_values[urdf_name]:
                        cfg.append(urdf_joint_values[urdf_name][joint_name])
                    else:
                        # Use default value for auxiliary joints we don't control
                        lower, upper = all_urdf_joints[joint_name]
                        if lower is not None and upper is not None:
                            default_val = (lower + upper) / 2.0
                        else:
                            default_val = 0.0
                        cfg.append(default_val)
                
                if cfg:  # Only update if there are actuated joints
                    viser_urdf.update_cfg(np.array(cfg, dtype=np.float32))
                    
    def get_initial_configuration(self) -> np.ndarray:
        """Get initial joint configuration for meaningful joints only."""
        initial_config = []
        
        for joint_name in self.filtered_joint_names:
            urdf_name, actual_joint_name = joint_name.split("::", 1)
            lower, upper = self.filtered_joint_limits[joint_name]
            
            # Set reasonable initial position
            if lower is None:
                lower = -np.pi
            if upper is None:
                upper = np.pi
                
            initial_pos = 0.0 if lower < -0.1 and upper > 0.1 else (lower + upper) / 2.0
            initial_config.append(initial_pos)
            
        return np.array(initial_config, dtype=np.float32)

def deduplicate_urdfs(urdf_configs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Remove duplicate URDFs, preferring newer versions."""
    
    # Group by component name
    grouped = {}
    for urdf_path, component_name in urdf_configs:
        if component_name not in grouped:
            grouped[component_name] = []
        grouped[component_name].append((urdf_path, component_name))
    
    deduped = []
    for component_name, versions in grouped.items():
        if len(versions) == 1:
            deduped.extend(versions)
        else:
            # Pick the best version based on naming patterns
            print(f"[DEDUP] Found {len(versions)} versions of {component_name}:")
            for path, name in versions:
                print(f"  - {path}")
            
            # Prefer versions with dates (newer), then avoid "testing" versions
            scored_versions = []
            for path, name in versions:
                score = 0
                path_lower = path.lower()
                
                # Prefer versions with dates
                if re.search(r'\d{8}', path):  # YYYYMMDD format
                    score += 100
                if re.search(r'v\d+', path):   # Version numbers
                    score += 50
                    
                # Avoid testing versions
                if 'testing' in path_lower:
                    score -= 200
                if 'dynamics_only' in path_lower:
                    score -= 100
                    
                # Prefer shorter, simpler names (likely the main version)
                score -= len(path) * 0.1
                
                scored_versions.append((score, path, name))
            
            # Pick the highest scoring version
            scored_versions.sort(key=lambda x: x[0], reverse=True)
            best_version = scored_versions[0]
            deduped.append((best_version[1], best_version[2]))
            print(f"[DEDUP] Selected: {best_version[1]} (score: {best_version[0]:.1f})")
    
    return deduped

async def handle_telemetry_client(websocket):
    """Handle new telemetry WebSocket connections and ping/pong for latency measurement."""
    connect_time = time.perf_counter()
    telemetry_clients.add(websocket)
    print(f"[TELEMETRY] Client connected from {websocket.remote_address}, total clients: {len(telemetry_clients)}")
    
    try:
        async for message in websocket:
            try:
                data = msgpack.unpackb(message)
                if isinstance(data, dict) and data.get("type") == "ping":
                    pong_response = {
                        "type": "pong",
                        "client_timestamp": data.get("client_timestamp"),
                        "server_timestamp": time.perf_counter_ns()
                    }
                    pong_bytes = msgpack.packb(pong_response, use_bin_type=True)
                    await websocket.send(pong_bytes)
            except Exception as e:
                print(f"[TELEMETRY] Error processing message: {e}")
                
    except websockets.exceptions.ConnectionClosed as e:
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        print(f"[TELEMETRY] Client {websocket.remote_address} disconnected after {duration:.1f}s")
    except Exception as e:
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        print(f"[TELEMETRY] Client {websocket.remote_address} error: {e}")
    finally:
        telemetry_clients.discard(websocket)
        print(f"[TELEMETRY] Removed client, remaining: {len(telemetry_clients)}")

def start_telemetry_server():
    """Start the telemetry WebSocket server in a background thread."""
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def server_main():
            print("[TELEMETRY] Starting WebSocket server on ws://0.0.0.0:8081")
            async with websockets.serve(handle_telemetry_client, "0.0.0.0", 8081):
                print("[TELEMETRY] WebSocket server ready for connections")
                await asyncio.Future()  # Run forever
        
        try:
            loop.run_until_complete(server_main())
        except Exception as e:
            print(f"[TELEMETRY] WebSocket server error: {e}")
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(0.1)

def send_telemetry_to_clients(payload_bytes: bytes):
    """Send telemetry data to all connected WebSocket clients."""
    if not telemetry_clients:
        return
    
    disconnected = set()
    for client in telemetry_clients.copy():
        try:
            def send_task(client_ref=client, data=payload_bytes):
                asyncio.create_task(client_ref.send(data))
            
            if hasattr(client, 'loop') and client.loop:
                client.loop.call_soon_threadsafe(send_task)
            else:
                disconnected.add(client)
        except Exception as e:
            print(f"[TELEMETRY] Error sending to client {client.remote_address}: {e}")
            disconnected.add(client)
    
    if disconnected:
        telemetry_clients.difference_update(disconnected)

def publish_telemetry(cfg: np.ndarray) -> None:
    """Publish telemetry with performance metrics."""
    global seq_counter, last_telemetry_time
    seq_counter += 1
    
    current_time = time.perf_counter()
    timestamp_ns = time.perf_counter_ns()
    
    dt = current_time - last_telemetry_time
    hz = 1.0 / dt if dt > 0 else 0.0
    last_telemetry_time = current_time
    
    payload = {
        "seq": seq_counter,
        "ns": timestamp_ns,
        "nq": int(cfg.shape[0]),
        "hz": round(hz, 1),
    }
    
    try:
        packed = msgpack.packb(payload, use_bin_type=True)
    except Exception as e:
        print(f"[TELEMETRY] Msgpack encoding error: {e}")
        return
    
    send_telemetry_to_clients(packed)
    
    if seq_counter % 50 == 0 or hz < 10:
        print(f"[TELEMETRY] seq={seq_counter}, nq={cfg.shape[0]}, rate={hz:.1f}Hz, bytes={len(packed)}")

def create_smart_control_sliders(
    server: viser.ViserServer, urdf_manager: SmartUrdfManager
) -> Tuple[List[viser.GuiInputHandle[float]], List[str], np.ndarray]:
    """Create well-organized sliders for meaningful joints only."""
    slider_handles: List[viser.GuiInputHandle[float]] = []
    joint_names: List[str] = []
    initial_config = urdf_manager.get_initial_configuration()
    
    # Group joints by URDF for better organization
    urdf_groups = {}
    
    for joint_name in urdf_manager.filtered_joint_names:
        urdf_name, actual_joint_name = joint_name.split("::", 1)
        if urdf_name not in urdf_groups:
            urdf_groups[urdf_name] = []
        urdf_groups[urdf_name].append(joint_name)
    
    # Create organized sliders
    for urdf_name, urdf_joint_names in urdf_groups.items():
        joint_count = len(urdf_joint_names)
        with server.gui.add_folder(f"🤖 {urdf_name.title()} ({joint_count} DOF)"):
            for joint_name in urdf_joint_names:
                i = urdf_manager.filtered_joint_names.index(joint_name)
                actual_joint_name = joint_name.split("::", 1)[1]
                lower, upper = urdf_manager.filtered_joint_limits[joint_name]
                
                # Handle None limits
                if lower is None:
                    lower = -np.pi
                if upper is None:
                    upper = np.pi
                
                # Create readable label
                short_name = urdf_manager._get_short_joint_name(actual_joint_name)
                units = "°" if abs(upper - lower) > 6 else "m"  # Rough guess for units
                range_str = f"[{lower:.2f}, {upper:.2f}]{units}"
                label = f"{short_name} {range_str}"
                
                slider = server.gui.add_slider(
                    label=label,
                    min=lower,
                    max=upper,
                    step=1e-3,
                    initial_value=initial_config[i],
                )
                
                def _on_update(_: object, *, _slider_handles=slider_handles, _urdf_manager=urdf_manager) -> None:
                    cfg = np.array([s.value for s in _slider_handles], dtype=np.float32)
                    _urdf_manager.update_all_configurations(cfg)
                    publish_telemetry(cfg)
                    
                slider.on_update(_on_update)
                slider_handles.append(slider)
                joint_names.append(joint_name)
    
    return slider_handles, joint_names, initial_config

def discover_workcell_urdfs(workcell_name: str) -> List[Tuple[str, str]]:
    """Discover all URDF files in a workcell directory."""
    base_path = Path(f"assets/urdf/{workcell_name}/urdf")
    urdf_configs = []
    
    if not base_path.exists():
        print(f"[URDF_DISCOVERY] Warning: {base_path} does not exist")
        return urdf_configs
    
    # Look for URDF files in subdirectories
    for subdir in base_path.iterdir():
        if subdir.is_dir():
            for urdf_file in subdir.glob("*.urdf"):
                # Skip macro files (they're not complete URDFs)
                if "macro" in urdf_file.name.lower():
                    continue
                    
                relative_path = str(urdf_file.relative_to(Path(".")))
                urdf_configs.append((relative_path, subdir.name))
                
    print(f"[URDF_DISCOVERY] Discovered {len(urdf_configs)} URDFs in {workcell_name}:")
    for path, name in urdf_configs:
        print(f"  - {name}: {path}")
        
    return urdf_configs

def main(
    workcell: str = "workcell_alpha_2",
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
    stress: bool = False,
    stress_hz: float = 200.0,
    stress_amplitude: float = 0.3,
    stress_wave_freq: float = 0.3,
    stress_joints: Optional[int] = None,
) -> None:
    """
    Enhanced Multi-URDF system with coordinate frame visualization.
    """
    
    # Start Viser server
    server = viser.ViserServer(
        host="0.0.0.0",
        port=8080,
        serve_static=False,
    )
    
    # Initialize telemetry system
    start_telemetry_server()
    print("[TELEMETRY] Telemetry system initialized")
    
    # Initialize smart URDF manager with coordinate frames
    urdf_manager = SmartUrdfManager(server)
    
    # Discover and deduplicate URDFs
    urdf_configs = discover_workcell_urdfs(workcell)
    
    if not urdf_configs:
        print(f"[MAIN] No URDFs found in {workcell}")
        return
    
    # Deduplicate URDFs
    urdf_configs = deduplicate_urdfs(urdf_configs)
    print(f"[MAIN] After deduplication: {len(urdf_configs)} URDFs")
    
    # Load all URDFs with smart processing
    for urdf_path, urdf_name in urdf_configs:
        urdf_manager.add_urdf(
            urdf_path, 
            urdf_name, 
            load_meshes=load_meshes,
            load_collision_meshes=load_collision_meshes
        )
    
    meaningful_dof = urdf_manager.get_total_meaningful_dof()
    print(f"\n[MAIN] 🎯 Smart Loading Summary:")
    print(f"  - Total URDFs: {len(urdf_configs)}")
    print(f"  - Meaningful DOF: {meaningful_dof}")
    print(f"  - Workcell: {workcell}")
    print(f"  - Meshes resolved: ✅")
    print(f"  - Coordinate frames: ✅")
    
    if meaningful_dof == 0:
        print("[MAIN] No meaningful joints found!")
        return
    
    # Create smart control sliders
    with server.gui.add_folder("🎛️ Smart Joint Control"):
        (slider_handles, joint_names, initial_config) = create_smart_control_sliders(
            server, urdf_manager
        )
    
    # Add visibility controls
    with server.gui.add_folder("👁️ Visibility"):
        show_meshes_cb = server.gui.add_checkbox("Show visual meshes", load_meshes)
        show_collision_meshes_cb = server.gui.add_checkbox("Show collision meshes", load_collision_meshes)
    
    @show_meshes_cb.on_update
    def _(_):
        for viser_urdf in urdf_manager.viser_urdfs:
            viser_urdf.show_visual = show_meshes_cb.value
    
    @show_collision_meshes_cb.on_update
    def _(_):
        for viser_urdf in urdf_manager.viser_urdfs:
            viser_urdf.show_collision = show_collision_meshes_cb.value
    
    # Note: Individual coordinate frame controls are now handled by ViserUrdfExtended
    # Each URDF gets its own coordinate frame toggle buttons in the GUI automatically
    
    # Set initial configuration
    urdf_manager.update_all_configurations(initial_config)
    publish_telemetry(initial_config)
    
    # Create grid
    server.scene.add_grid(
        "/grid",
        width=4,
        height=4,
        position=(0.0, 0.0, 0.0),
    )
    
    # Create reset button
    reset_button = server.gui.add_button("🔄 Reset All Joints")
    @reset_button.on_click
    def _(_):
        for s, init_val in zip(slider_handles, initial_config):
            s.value = init_val
    
    # Add smart stress testing
    if stress:
        nq = stress_joints if stress_joints is not None else meaningful_dof
        nq = min(nq, meaningful_dof)
        
        with server.gui.add_folder("🔥 Smart Stress Testing"):
            stress_enabled_cb = server.gui.add_checkbox("Enable Stress Testing", False)
            stress_hz_slider = server.gui.add_slider(
                "Frequency (Hz)",
                min=1.0,
                max=500.0,
                step=1.0,
                initial_value=stress_hz,
            )
            stress_amplitude_slider = server.gui.add_slider(
                "Amplitude (rad)",
                min=0.1,
                max=1.5,
                step=0.1,
                initial_value=stress_amplitude,
            )
            stress_info = server.gui.add_text("Status", "Disabled")
        
        stress_thread = None
        stress_running = threading.Event()
        current_stress_hz = stress_hz
        current_stress_amplitude = stress_amplitude
        
        @stress_hz_slider.on_update
        def _(_):
            nonlocal current_stress_hz
            current_stress_hz = stress_hz_slider.value
            if stress_thread is not None:
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints"
        
        @stress_amplitude_slider.on_update
        def _(_):
            nonlocal current_stress_amplitude
            current_stress_amplitude = stress_amplitude_slider.value
            if stress_thread is not None:
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints, ±{current_stress_amplitude:.2f}rad"
        
        def run_stress_testing_in_thread():
            """Run smart stress testing loop with coordinate frame updates."""
            print(f"🚀 [SMART-STRESS] Starting intelligent multi-URDF stress test with coordinate frames:")
            print(f"   Total URDFs: {len(urdf_configs)}")
            print(f"   Meaningful DOF: {meaningful_dof}")
            print(f"   Stress joints: {nq}")
            print(f"   Initial frequency: {current_stress_hz:.1f} Hz")
            print(f"   Initial amplitude: ±{current_stress_amplitude:.2f} rad")
            print(f"   Individual coordinate frames: ✅ Available via GUI buttons")
            print()
            
            phases = np.linspace(0, 2*np.pi, nq, endpoint=False)
            t0 = time.perf_counter()
            msg_count = 0
            last_stats = t0
            
            while stress_running.is_set():
                loop_start = time.perf_counter()
                
                # Get current parameters
                hz = current_stress_hz
                amplitude = current_stress_amplitude
                
                # Generate sinusoidal motion for selected joints
                t = loop_start - t0
                stress_values = amplitude * np.sin(2*np.pi*stress_wave_freq*t + phases)
                
                # Create full configuration (stress values + initial values for other joints)
                full_config = initial_config.copy()
                full_config[:nq] = stress_values
                
                # Update all URDFs and coordinate frames
                urdf_manager.update_all_configurations(full_config)
                publish_telemetry(full_config)
                msg_count += 1
                
                # Print statistics
                if loop_start - last_stats >= 10.0:
                    elapsed = loop_start - t0
                    avg_hz = msg_count / elapsed if elapsed > 0 else 0
                    print(f"🔥 [SMART-STRESS] {msg_count:,} updates | {elapsed:.1f}s | {avg_hz:.1f} Hz avg | Target: {hz:.1f} Hz | {nq}/{meaningful_dof} DOF | Individual frames available via GUI")
                    last_stats = loop_start
                
                # Sleep to maintain frequency
                period = 1.0 / hz if hz > 0 else 1.0
                loop_end = time.perf_counter()
                sleep_time = period - (loop_end - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            print("⏹️ [SMART-STRESS] Intelligent stress testing stopped")
        
        @stress_enabled_cb.on_update
        def _(_):
            nonlocal stress_thread
            if stress_enabled_cb.value and stress_thread is None:
                stress_running.set()
                stress_thread = threading.Thread(target=run_stress_testing_in_thread, daemon=True)
                stress_thread.start()
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints"
                print(f"🚀 [SMART-STRESS] Started intelligent stress testing: {current_stress_hz:.1f}Hz")
                
            elif not stress_enabled_cb.value and stress_thread is not None:
                stress_running.clear()
                stress_thread = None
                stress_info.value = "Disabled"
                print("⏹️ [SMART-STRESS] Stopped intelligent stress testing")
        
        print(f"[SMART-STRESS] Intelligent stress testing available")
        print(f"[SMART-STRESS] Config: {stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints, ±{stress_amplitude:.2f}rad")
    
    print(f"\n[MAIN] 🎉 Enhanced Multi-URDF System with Coordinate Frames Ready!")
    print(f"[MAIN] Ready for visualization with {meaningful_dof} meaningful DOF")
    print(f"[MAIN] 📐 Coordinate frame visualization available")
    print(f"[TELEMETRY] WebSocket telemetry available on port 8081")
    print(f"[MAIN] View at: http://localhost:8080")
    
    # Run forever
    while True:
        time.sleep(10.0)

if __name__ == "__main__":
    tyro.cli(main)
