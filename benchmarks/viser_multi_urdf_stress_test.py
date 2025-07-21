"""
Multi-URDF Viser stress testing benchmark with telemetry support.
Loads multiple URDFs from a workcell and treats them as separate ViserUrdf instances,
but coordinates their joint updates for comprehensive stress testing.

Launch:
    # workcell_alpha_2 (7 DOF total):
    python benchmarks/viser_multi_urdf_stress_test.py --workcell workcell_alpha_2 --stress --stress-hz 200
    
    # workcell_beta (more DOF):
    python benchmarks/viser_multi_urdf_stress_test.py --workcell workcell_beta --stress --stress-hz 150
"""

from __future__ import annotations

import time
import asyncio
import threading
import websockets
from typing import Dict, List, Optional, Set, Tuple
import msgpack
import os
from pathlib import Path

import numpy as np
import tyro
from yourdfpy import URDF

import viser
from viser.extras import ViserUrdf

# Global telemetry counter and timing
seq_counter = 0
last_telemetry_time = time.perf_counter()

# WebSocket telemetry clients
telemetry_clients: Set[websockets.WebSocketServerProtocol] = set()

class MultiUrdfManager:
    """Manager for multiple ViserUrdf instances with coordinated control."""
    
    def __init__(self, server: viser.ViserServer):
        self.server = server
        self.viser_urdfs: List[ViserUrdf] = []
        self.urdf_configs: List[Dict] = []
        self.all_joint_limits: Dict[str, Tuple[float, float]] = {}
        self.all_joint_names: List[str] = []
        
    def add_urdf(self, urdf_path: str, name: str, load_meshes: bool = True, 
                 load_collision_meshes: bool = True):
        """Add a URDF to the multi-URDF setup."""
        try:
            print(f"[MULTI-URDF] Loading {name} from {urdf_path}")
            
            # Load URDF
            urdf = URDF.load(
                urdf_path,
                load_meshes=load_meshes,
                build_scene_graph=load_meshes,
                load_collision_meshes=load_collision_meshes,
                build_collision_scene_graph=load_collision_meshes,
            )
            
            # Create ViserUrdf instance
            viser_urdf = ViserUrdf(
                self.server,
                urdf_or_path=urdf,
                load_meshes=load_meshes,
                load_collision_meshes=load_collision_meshes,
                collision_mesh_color_override=(1.0, 0.0, 0.0, 0.5),
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
            
            # Collect actuated joints
            joint_limits = viser_urdf.get_actuated_joint_limits()
            actuated_count = len(joint_limits)
            
            print(f"[MULTI-URDF] {name}: {actuated_count} actuated joints")
            for joint_name in joint_limits.keys():
                print(f"  - {joint_name}")
            
            # Add to global joint collection with unique naming
            for joint_name, limits in joint_limits.items():
                unique_name = f"{name}::{joint_name}"
                self.all_joint_limits[unique_name] = limits
                self.all_joint_names.append(unique_name)
                
        except Exception as e:
            print(f"[MULTI-URDF] Error loading {name}: {e}")
            
    def get_total_dof(self) -> int:
        """Get total degrees of freedom across all URDFs."""
        return len(self.all_joint_limits)
        
    def update_all_configurations(self, joint_values: np.ndarray):
        """Update all URDF configurations with provided joint values."""
        if len(joint_values) != len(self.all_joint_names):
            print(f"[MULTI-URDF] Warning: Expected {len(self.all_joint_names)} joint values, got {len(joint_values)}")
            return
            
        # Group joint values by URDF
        urdf_joint_values = {}
        
        for i, joint_name in enumerate(self.all_joint_names):
            urdf_name, actual_joint_name = joint_name.split("::", 1)
            if urdf_name not in urdf_joint_values:
                urdf_joint_values[urdf_name] = {}
            urdf_joint_values[urdf_name][actual_joint_name] = joint_values[i]
        
        # Update each ViserUrdf instance
        for config in self.urdf_configs:
            urdf_name = config["name"]
            viser_urdf = config["viser_urdf"]
            
            if urdf_name in urdf_joint_values:
                # Get joint limits for this URDF
                urdf_joint_limits = viser_urdf.get_actuated_joint_limits()
                
                # Create configuration array in correct order
                cfg = []
                for joint_name in urdf_joint_limits.keys():
                    if joint_name in urdf_joint_values[urdf_name]:
                        cfg.append(urdf_joint_values[urdf_name][joint_name])
                    else:
                        cfg.append(0.0)  # Default value
                
                if cfg:  # Only update if there are actuated joints
                    viser_urdf.update_cfg(np.array(cfg, dtype=np.float32))
                    
    def get_initial_configuration(self) -> np.ndarray:
        """Get initial joint configuration for all URDFs."""
        initial_config = []
        
        for joint_name in self.all_joint_names:
            urdf_name, actual_joint_name = joint_name.split("::", 1)
            lower, upper = self.all_joint_limits[joint_name]
            
            # Set reasonable initial position
            if lower is None:
                lower = -np.pi
            if upper is None:
                upper = np.pi
                
            initial_pos = 0.0 if lower < -0.1 and upper > 0.1 else (lower + upper) / 2.0
            initial_config.append(initial_pos)
            
        return np.array(initial_config, dtype=np.float32)

async def handle_telemetry_client(websocket):
    """Handle new telemetry WebSocket connections and ping/pong for latency measurement."""
    connect_time = time.perf_counter()
    telemetry_clients.add(websocket)
    print(f"[TELEMETRY] Client connected from {websocket.remote_address}, total clients: {len(telemetry_clients)}")
    
    try:
        # Listen for ping messages from client for latency measurement
        async for message in websocket:
            try:
                # Try to decode as msgpack ping message
                data = msgpack.unpackb(message)
                
                if isinstance(data, dict) and data.get("type") == "ping":
                    # Echo back the ping as a pong with the same client timestamp
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
    
    # Only print occasionally to avoid console flooding
    if seq_counter % 50 == 0 or hz < 10:
        print(f"[TELEMETRY] seq={seq_counter}, nq={cfg.shape[0]}, rate={hz:.1f}Hz, bytes={len(packed)}")

def create_multi_urdf_control_sliders(
    server: viser.ViserServer, urdf_manager: MultiUrdfManager
) -> Tuple[List[viser.GuiInputHandle[float]], List[str], np.ndarray]:
    """Create sliders for all joints across all URDFs."""
    slider_handles: List[viser.GuiInputHandle[float]] = []
    joint_names: List[str] = []
    initial_config = urdf_manager.get_initial_configuration()
    
    # Group sliders by URDF for better organization
    urdf_groups = {}
    
    # Group joints by URDF
    for joint_name in urdf_manager.all_joint_names:
        urdf_name, actual_joint_name = joint_name.split("::", 1)
        if urdf_name not in urdf_groups:
            urdf_groups[urdf_name] = []
        urdf_groups[urdf_name].append(joint_name)
    
    # Create sliders grouped by URDF
    for urdf_name, urdf_joint_names in urdf_groups.items():
        with server.gui.add_folder(f"{urdf_name} joints"):
            for joint_name in urdf_joint_names:
                i = urdf_manager.all_joint_names.index(joint_name)
                actual_joint_name = joint_name.split("::", 1)[1]
                lower, upper = urdf_manager.all_joint_limits[joint_name]
                
                # Handle None limits
                if lower is None:
                    lower = -np.pi
                if upper is None:
                    upper = np.pi
                    
                slider = server.gui.add_slider(
                    label=actual_joint_name,
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
        print(f"[MULTI-URDF] Warning: {base_path} does not exist")
        return urdf_configs
    
    # Look for URDF files in subdirectories
    for subdir in base_path.iterdir():
        if subdir.is_dir():
            for urdf_file in subdir.glob("*.urdf"):
                # Skip files with certain patterns (like xacro intermediates)
                if any(pattern in urdf_file.name.lower() for pattern in ["macro", "testing", "dynamics_only"]):
                    continue
                    
                relative_path = str(urdf_file.relative_to(Path(".")))
                urdf_configs.append((relative_path, subdir.name))
                
    print(f"[MULTI-URDF] Discovered URDFs in {workcell_name}:")
    for path, name in urdf_configs:
        print(f"  - {name}: {path}")
        
    return urdf_configs

def main(
    workcell: str = "workcell_alpha_2",
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
    # Stress testing options
    stress: bool = False,
    stress_hz: float = 200.0,
    stress_amplitude: float = 0.3,
    stress_wave_freq: float = 0.3,
    stress_joints: Optional[int] = None,
) -> None:
    """
    Multi-URDF stress testing with coordinated control.
    
    Args:
        workcell: Workcell name (workcell_alpha_2, workcell_beta)
        load_meshes: Whether to load visual meshes
        load_collision_meshes: Whether to load collision meshes
        stress: Enable automated stress testing
        stress_hz: Stress testing frequency (Hz)
        stress_amplitude: Joint movement amplitude (radians)
        stress_wave_freq: Frequency of sine wave motion (Hz)
        stress_joints: Number of joints to drive (None = use all)
    """
    
    # Start Viser server
    server = viser.ViserServer(
        host="0.0.0.0",
        port=8080,
        serve_static=False,
    )
    
    # Initialize telemetry system
    start_telemetry_server()
    print("[TELEMETRY] Telemetry system initialized with WebSocket server")
    
    # Initialize multi-URDF manager
    urdf_manager = MultiUrdfManager(server)
    
    # Discover and load URDFs
    urdf_configs = discover_workcell_urdfs(workcell)
    
    if not urdf_configs:
        print(f"[MULTI-URDF] No URDFs found in {workcell}")
        return
    
    # Load all URDFs
    for urdf_path, urdf_name in urdf_configs:
        urdf_manager.add_urdf(
            urdf_path, 
            urdf_name, 
            load_meshes=load_meshes,
            load_collision_meshes=load_collision_meshes
        )
    
    total_dof = urdf_manager.get_total_dof()
    print(f"\n[MULTI-URDF] Summary:")
    print(f"  - Total URDFs: {len(urdf_configs)}")
    print(f"  - Total DOF: {total_dof}")
    print(f"  - Workcell: {workcell}")
    
    if total_dof == 0:
        print("[MULTI-URDF] No actuated joints found!")
        return
    
    # Create control sliders
    with server.gui.add_folder("Multi-URDF Joint Control"):
        (slider_handles, joint_names, initial_config) = create_multi_urdf_control_sliders(
            server, urdf_manager
        )
    
    # Add visibility controls
    with server.gui.add_folder("Visibility"):
        show_meshes_cb = server.gui.add_checkbox("Show meshes", load_meshes)
        show_collision_meshes_cb = server.gui.add_checkbox("Show collision meshes", load_collision_meshes)
    
    @show_meshes_cb.on_update
    def _(_):
        for viser_urdf in urdf_manager.viser_urdfs:
            viser_urdf.show_visual = show_meshes_cb.value
    
    @show_collision_meshes_cb.on_update
    def _(_):
        for viser_urdf in urdf_manager.viser_urdfs:
            viser_urdf.show_collision = show_collision_meshes_cb.value
    
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
    reset_button = server.gui.add_button("Reset All Joints")
    @reset_button.on_click
    def _(_):
        for s, init_val in zip(slider_handles, initial_config):
            s.value = init_val
    
    # Add stress testing if enabled
    if stress:
        nq = stress_joints if stress_joints is not None else total_dof
        nq = min(nq, total_dof)  # Don't exceed available joints
        
        with server.gui.add_folder("Multi-URDF Stress Testing"):
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
        
        # Shared variables for dynamic control
        current_stress_hz = stress_hz
        current_stress_amplitude = stress_amplitude
        
        @stress_hz_slider.on_update
        def _(_):
            nonlocal current_stress_hz
            current_stress_hz = stress_hz_slider.value
            if stress_thread is not None:
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{total_dof} joints"
        
        @stress_amplitude_slider.on_update
        def _(_):
            nonlocal current_stress_amplitude
            current_stress_amplitude = stress_amplitude_slider.value
            if stress_thread is not None:
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{total_dof} joints, ±{current_stress_amplitude:.2f}rad"
        
        def run_stress_testing_in_thread():
            """Run multi-URDF stress testing loop."""
            print(f"🚀 [MULTI-STRESS] Starting coordinated multi-URDF stress test:")
            print(f"   Total URDFs: {len(urdf_configs)}")
            print(f"   Total DOF: {total_dof}")
            print(f"   Stress joints: {nq}")
            print(f"   Initial frequency: {current_stress_hz:.1f} Hz")
            print(f"   Initial amplitude: ±{current_stress_amplitude:.2f} rad")
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
                
                # Update all URDFs
                urdf_manager.update_all_configurations(full_config)
                publish_telemetry(full_config)
                msg_count += 1
                
                # Print statistics
                if loop_start - last_stats >= 10.0:
                    elapsed = loop_start - t0
                    avg_hz = msg_count / elapsed if elapsed > 0 else 0
                    print(f"🔥 [MULTI-STRESS] {msg_count:,} updates | {elapsed:.1f}s | {avg_hz:.1f} Hz avg | Target: {hz:.1f} Hz | {nq}/{total_dof} DOF")
                    last_stats = loop_start
                
                # Sleep to maintain frequency
                period = 1.0 / hz if hz > 0 else 1.0
                loop_end = time.perf_counter()
                sleep_time = period - (loop_end - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            print("⏹️ [MULTI-STRESS] Coordinated stress testing stopped")
        
        @stress_enabled_cb.on_update
        def _(_):
            nonlocal stress_thread
            if stress_enabled_cb.value and stress_thread is None:
                stress_running.set()
                stress_thread = threading.Thread(target=run_stress_testing_in_thread, daemon=True)
                stress_thread.start()
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{total_dof} joints"
                print(f"🚀 [MULTI-STRESS] Started coordinated stress testing: {current_stress_hz:.1f}Hz")
                
            elif not stress_enabled_cb.value and stress_thread is not None:
                stress_running.clear()
                stress_thread = None
                stress_info.value = "Disabled"
                print("⏹️ [MULTI-STRESS] Stopped coordinated stress testing")
        
        print(f"[MULTI-STRESS] Multi-URDF stress testing available")
        print(f"[MULTI-STRESS] Config: {stress_hz:.1f}Hz, {nq}/{total_dof} joints, ±{stress_amplitude:.2f}rad")
    
    print(f"\n[MULTI-URDF] {workcell} loaded successfully!")
    print(f"[MULTI-URDF] Ready for stress testing with {total_dof} total DOF")
    print(f"[TELEMETRY] WebSocket telemetry available on port 8081")
    
    # Run forever
    while True:
        time.sleep(10.0)

if __name__ == "__main__":
    tyro.cli(main)
