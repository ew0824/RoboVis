"""
URDF Loader Module for Viser Multi-URDF Robot Visualization

This module handles all URDF-related functionality including:
- Loading and parsing URDF files from workcell directories
- ROS package:// URI resolution to local file paths
- Multi-URDF management with smart joint filtering
- Coordinate frame visualization using Viser's built-in frame system
- GUI slider creation for joint control

Key Features:
- Smart joint filtering (excludes auxiliary joints like conveyors, rollers)
- Automatic URDF deduplication (prefers newer versions)
- Built-in coordinate frame visualization
- Mesh loading with package path resolution
- Multi-URDF coordination and synchronization

Usage:
    from urdf_manager import SmartUrdfManager, discover_workcell_urdfs
    
    # Create URDF manager
    urdf_manager = SmartUrdfManager(server)
    
    # Discover and load URDFs
    urdf_configs = discover_workcell_urdfs("workcell_alpha_2")
    for urdf_path, urdf_name in urdf_configs:
        urdf_manager.add_urdf(urdf_path, urdf_name)
"""

from __future__ import annotations

import time
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from yourdfpy import URDF
from scipy.spatial.transform import Rotation

import viser
from viser_urdf import ViserUrdf

from telemetry import publish_telemetry


class PackagePathResolver:
    """
    Resolves ROS package:// URIs to actual file paths in the robot_description folder.
    
    This class handles the common ROS convention of referencing mesh files using
    package:// URIs by building a mapping from package names to actual directory
    paths in the assets/robot_description folder.
    
    Attributes:
        robot_description_path: Path to the robot description directory
        package_map: Mapping from package names to directory paths
    """
    
    def __init__(self, robot_description_path: str = "assets/robot_description"):
        # Ensure path is relative to project root, not current working directory
        if not robot_description_path.startswith('/'):
            # Find project root by looking for .gitignore file
            current_dir = Path.cwd()
            project_root = current_dir
            while project_root.parent != project_root:
                if (project_root / '.gitignore').exists():
                    break
                project_root = project_root.parent
            self.robot_description_path = project_root / robot_description_path
        else:
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
        """
        Convert package://package_name/path to actual file path.
        
        Args:
            package_uri: URI in the format "package://package_name/relative/path"
            
        Returns:
            Resolved file path if successful, None if package not found
            
        Supports fuzzy matching for common package name variations.
        """
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
    """
    Simplified URDF manager using built-in Viser coordinate frames.
    
    This class manages multiple URDF files with intelligent joint filtering
    and coordinate frame visualization. It provides a unified interface for
    controlling multiple robots and workcell components simultaneously.
    
    Key Features:
    - Smart joint filtering (excludes auxiliary joints like conveyors)
    - Multi-URDF coordination with unified joint naming
    - Built-in coordinate frame visualization
    - Mesh loading with automatic path resolution
    - Performance-optimized joint updates
    
    Attributes:
        server: Viser server instance
        path_resolver: Package path resolver for mesh files
        viser_urdfs: List of loaded ViserUrdf instances
        urdf_configs: List of URDF configuration dictionaries
        coordinate_frames: Mapping from URDF name to coordinate frames
        filtered_joint_limits: Joint limits for meaningful joints only
        filtered_joint_names: Names of meaningful joints in "urdf::joint" format
    """
    
    def __init__(self, server: viser.ViserServer):
        self.server = server
        self.path_resolver = PackagePathResolver()
        self.viser_urdfs: List[ViserUrdf] = []
        self.urdf_configs: List[Dict] = []
        self.coordinate_frames: Dict[str, Dict[str, viser.FrameHandle]] = {}  # urdf_name -> {joint_name -> frame}
        self.filtered_joint_limits: Dict[str, Tuple[float, float]] = {}
        self.filtered_joint_names: List[str] = []
        
    def _patch_urdf_mesh_paths(self, urdf_content: str) -> str:
        """
        Replace package:// URIs with resolved file paths in URDF content.
        
        Args:
            urdf_content: Raw URDF XML content
            
        Returns:
            Patched URDF content with resolved file paths
        """
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
        """
        Determine if a joint should have a slider (is meaningful for visualization).
        
        Args:
            joint_name: Name of the joint
            joint_type: Type of joint (revolute, prismatic, continuous, fixed, etc.)
            joint_limits: Tuple of (lower_limit, upper_limit)
            
        Returns:
            True if joint should be controllable, False if auxiliary/fixed
            
        This method filters out auxiliary joints like conveyors, rollers, and belts
        that are not meaningful for robot visualization and control.
        """
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
        """
        Create a shorter, more readable joint name for GUI display.
        
        Args:
            full_joint_name: Original joint name from URDF
            
        Returns:
            Shortened, more readable joint name
            
        This method removes common prefixes and applies formatting to make
        joint names more readable in the GUI while keeping them lowercase
        to match the scene tree display.
        """
        # Remove common prefixes
        name = full_joint_name
        prefixes_to_remove = [
            "band_separator_", "robot_gantry_", "scara_", "infeed_", "gantry_"
        ]
        
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
                
        # Replace underscores with spaces but keep lowercase
        name = name.replace("_", " ")
        
        # Shorten common terms (keeping lowercase)
        replacements = {
            " to ": " → ",
            "base to": "",
        }
        
        for old, new in replacements.items():
            name = name.replace(old, new)
            
        return name.strip()
        
    def add_urdf(self, urdf_path: str, name: str, load_meshes: bool = True, 
                 load_collision_meshes: bool = True):
        """
        Add a URDF with smart path resolution and coordinate frames.
        
        Args:
            urdf_path: Path to the URDF file
            name: Display name for this URDF
            load_meshes: Whether to load visual meshes
            load_collision_meshes: Whether to load collision meshes
            
        This method loads a URDF file, patches package:// URIs, creates
        a ViserUrdf instance, adds coordinate frames, and registers
        meaningful joints for control.
        """
        try:
            print(f"[SMART-URDF] Loading {name} from {urdf_path}")
            
            # Convert to absolute path if needed
            if not urdf_path.startswith('/'):
                # Find project root by looking for .gitignore file
                current_dir = Path.cwd()
                project_root = current_dir
                while project_root.parent != project_root:
                    if (project_root / '.gitignore').exists():
                        break
                    project_root = project_root.parent
                urdf_path = str(project_root / urdf_path)
            
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
            
            # Create standard ViserUrdf instance
            viser_urdf = ViserUrdf(
                self.server,
                urdf_or_path=urdf,
                load_meshes=load_meshes,
                load_collision_meshes=load_collision_meshes,
                collision_mesh_color_override=(1.0, 0.0, 0.0, 0.5),
                root_node_name=f"/{name}",
            )
            
            # Add coordinate frames using built-in Viser system
            frames = add_urdf_coordinate_frames(self.server, urdf, name, scale=1.0)
            
            # Store configuration
            config = {
                "name": name,
                "path": urdf_path,
                "urdf": urdf,
                "viser_urdf": viser_urdf
            }
            
            self.viser_urdfs.append(viser_urdf)
            self.urdf_configs.append(config)
            self.coordinate_frames[name] = frames
            
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
            print(f"  📐 Total coordinate frames: {len(frames)}")
            
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
        """
        Update all URDF configurations and coordinate frames with provided joint values.
        
        Args:
            joint_values: Array of joint values for all meaningful joints
            
        This is the main update method that distributes joint values to the
        appropriate URDFs and updates their coordinate frames. It's called
        during both manual control and robot replay.
        """
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
        
        # Update each ViserUrdf instance and coordinate frames
        for config in self.urdf_configs:
            urdf_name = config["name"]
            urdf = config["urdf"]
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
                    
                    # Update coordinate frames
                    if urdf_name in self.coordinate_frames:
                        update_urdf_coordinate_frames(urdf, self.coordinate_frames[urdf_name], scale=1.0)
                    
    def get_initial_configuration(self) -> np.ndarray:
        """
        Get initial joint configuration for meaningful joints only.
        
        Returns:
            Array of initial joint positions
            
        This method calculates reasonable initial positions for all joints,
        typically centering them in their range or using zero if the range
        includes zero.
        """
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


def discover_workcell_urdfs(workcell_name: str) -> List[Tuple[str, str]]:
    """
    Discover all URDF files in a workcell directory.
    
    Args:
        workcell_name: Name of the workcell (e.g., "workcell_alpha_2")
        
    Returns:
        List of tuples (urdf_path, component_name)
        
    This function scans the workcell directory structure and finds all
    available URDF files, excluding macro files which are not complete URDFs.
    """
    # Find project root by looking for .gitignore file
    current_dir = Path.cwd()
    project_root = current_dir
    while project_root.parent != project_root:
        if (project_root / '.gitignore').exists():
            break
        project_root = project_root.parent
    
    base_path = project_root / f"assets/robot_description/{workcell_name}/urdf"
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
                    
                relative_path = str(urdf_file.relative_to(project_root))
                urdf_configs.append((relative_path, subdir.name))
                
    print(f"[URDF_DISCOVERY] Discovered {len(urdf_configs)} URDFs in {workcell_name}:")
    for path, name in urdf_configs:
        print(f"  - {name}: {path}")
        
    return urdf_configs


def deduplicate_urdfs(urdf_configs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Remove duplicate URDFs, preferring newer versions.
    
    Args:
        urdf_configs: List of (urdf_path, component_name) tuples
        
    Returns:
        Deduplicated list with preferred versions
        
    This function handles cases where multiple versions of the same component
    exist, using heuristics to select the best version (newest, non-testing, etc.).
    """
    
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


def add_urdf_coordinate_frames(server: viser.ViserServer, urdf: URDF, urdf_name: str, scale: float = 1.0) -> Dict[str, viser.FrameHandle]:
    """
    Add coordinate frames for all joints in a URDF using Viser's built-in frame system.
    
    Args:
        server: Viser server instance
        urdf: Loaded URDF object
        urdf_name: Name of the URDF for frame naming
        scale: Scale factor for frame positions
        
    Returns:
        Dictionary mapping joint names to frame handles
        
    This function creates coordinate frames for all joints in the URDF,
    making them visible in the scene tree under the "frames" folder.
    """
    frames = {}
    
    print(f"[FRAMES] Adding coordinate frames for {urdf_name}")
    
    for joint in urdf.robot.joints:
        # Create frame name that will appear nicely in scene tree
        frame_name = f"/{urdf_name}/frames/{joint.name}"
        
        try:
            # Get initial transform for this joint
            T_parent_child = urdf.get_transform(joint.child, joint.parent)
            position = T_parent_child[:3, 3] * scale
            rotation_matrix = T_parent_child[:3, :3]
            
            # Convert rotation matrix to quaternion (w, x, y, z)
            r = Rotation.from_matrix(rotation_matrix)
            quat_xyzw = r.as_quat()  # Returns [x, y, z, w]
            quat_wxyz = np.array([quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]])  # Convert to [w, x, y, z]
            
            # Create coordinate frame using Viser's built-in system
            frame = server.scene.add_frame(
                frame_name,
                show_axes=False,  # Start hidden, user can toggle in scene tree
                axes_length=0.1,
                axes_radius=0.005,
                position=tuple(position),
                wxyz=tuple(quat_wxyz),
            )
            
            frames[joint.name] = frame
            
        except Exception as e:
            print(f"[FRAMES] Warning: Could not create frame for joint {joint.name}: {e}")
    
    print(f"[FRAMES] Created {len(frames)} coordinate frames for {urdf_name}")
    return frames


def update_urdf_coordinate_frames(urdf: URDF, frames: Dict[str, viser.FrameHandle], scale: float = 1.0) -> None:
    """
    Update coordinate frame positions based on current joint configuration.
    
    Args:
        urdf: URDF object with current joint configuration
        frames: Dictionary of frame handles to update
        scale: Scale factor for frame positions
        
    This function is called after joint updates to move the coordinate
    frames to their new positions based on the current joint configuration.
    """
    for joint_name, frame in frames.items():
        try:
            # Find the joint
            joint = None
            for j in urdf.robot.joints:
                if j.name == joint_name:
                    joint = j
                    break
            
            if joint is None:
                continue
                
            # Get current transform for this joint
            T_parent_child = urdf.get_transform(joint.child, joint.parent)
            position = T_parent_child[:3, 3] * scale
            rotation_matrix = T_parent_child[:3, :3]
            
            # Convert rotation matrix to quaternion (w, x, y, z)
            r = Rotation.from_matrix(rotation_matrix)
            quat_xyzw = r.as_quat()  # Returns [x, y, z, w]
            quat_wxyz = np.array([quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2]])  # Convert to [w, x, y, z]
            
            # Update frame pose
            frame.position = tuple(position)
            frame.wxyz = tuple(quat_wxyz)
            
        except Exception as e:
            print(f"[FRAMES] Warning: Could not update frame for joint {joint_name}: {e}")


def create_smart_control_sliders(
    server: viser.ViserServer, urdf_manager: SmartUrdfManager
) -> Tuple[List[viser.GuiInputHandle[float]], List[str], np.ndarray]:
    """
    Create well-organized sliders for meaningful joints only.
    
    Args:
        server: Viser server instance
        urdf_manager: SmartUrdfManager with loaded URDFs
        
    Returns:
        Tuple of (slider_handles, joint_names, initial_config)
        
    This function creates GUI sliders organized by URDF, with clean naming
    and automatic telemetry integration. Only meaningful joints get sliders.
    """
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
        with server.gui.add_folder(f"{urdf_name} ({joint_count} DOF)"):
            for joint_name in urdf_joint_names:
                i = urdf_manager.filtered_joint_names.index(joint_name)
                actual_joint_name = joint_name.split("::", 1)[1]
                lower, upper = urdf_manager.filtered_joint_limits[joint_name]
                
                # Handle None limits
                if lower is None:
                    lower = -np.pi
                if upper is None:
                    upper = np.pi
                
                # Create clean, compact label (no range info - it's shown on slider)
                short_name = urdf_manager._get_short_joint_name(actual_joint_name)
                label = short_name
                
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
