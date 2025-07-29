"""
Simplified Multi-URDF Viser system using built-in coordinate frames.
Uses standard viser.extras.ViserUrdf + simple frame helpers + enhanced scene tree.

Launch:
    python backends/viser/viser_multi_urdf_simplified.py --workcell workcell_alpha_2 --stress --stress-hz 200
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
from scipy.spatial.transform import Rotation

import viser
from viser.extras import ViserUrdf
from telemetry import start_telemetry_server, publish_telemetry, send_telemetry_to_clients, handle_telemetry_client

# Global telemetry counter and timing
seq_counter = 0
last_telemetry_time = time.perf_counter()

# WebSocket telemetry clients
telemetry_clients: Set[websockets.WebSocketServerProtocol] = set()









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



def main(
    workcell: str = "workcell_beta",
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
    stress: bool = False,
    stress_hz: float = 200.0,
    stress_amplitude: float = 0.3,
    stress_wave_freq: float = 0.3,
    stress_joints: Optional[int] = None,
) -> None:
    """
    Simplified Multi-URDF system with built-in coordinate frame visualization.
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
    
    # Initialize simplified URDF manager
    urdf_manager = SmartUrdfManager(server)
    
    # Discover and deduplicate URDFs
    urdf_configs = discover_workcell_urdfs(workcell)
    
    if not urdf_configs:
        print(f"[MAIN] No URDFs found in {workcell}")
        return
    
    # Deduplicate URDFs
    urdf_configs = deduplicate_urdfs(urdf_configs)
    print(f"[MAIN] After deduplication: {len(urdf_configs)} URDFs")
    
    # Load all URDFs with coordinate frames
    for urdf_path, urdf_name in urdf_configs:
        urdf_manager.add_urdf(
            urdf_path, 
            urdf_name, 
            load_meshes=load_meshes,
            load_collision_meshes=load_collision_meshes
        )
    
    meaningful_dof = urdf_manager.get_total_meaningful_dof()
    print(f"\n[MAIN] 🎯 Simplified System Summary:")
    print(f"  - Total URDFs: {len(urdf_configs)}")
    print(f"  - Meaningful DOF: {meaningful_dof}")
    print(f"  - Workcell: {workcell}")
    print(f"  - Built-in coordinate frames: ✅")
    print(f"  - Scene tree integration: ✅")
    
    if meaningful_dof == 0:
        print("[MAIN] No meaningful joints found!")
        return
    
    # Create smart control sliders
    with server.gui.add_folder("Joint Control"):
        (slider_handles, joint_names, initial_config) = create_smart_control_sliders(
            server, urdf_manager
        )
    
    # Add visibility controls
    with server.gui.add_folder("Visibility"):
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
    
    # Add smart stress testing
    if stress:
        nq = stress_joints if stress_joints is not None else meaningful_dof
        nq = min(nq, meaningful_dof)
        
        with server.gui.add_folder("Stress Testing"):
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
            print(f"🚀 [SMART-STRESS] Starting simplified multi-URDF stress test:")
            print(f"   Total URDFs: {len(urdf_configs)}")
            print(f"   Meaningful DOF: {meaningful_dof}")
            print(f"   Stress joints: {nq}")
            print(f"   Initial frequency: {current_stress_hz:.1f} Hz")
            print(f"   Initial amplitude: ±{current_stress_amplitude:.2f} rad")
            print(f"   Built-in coordinate frames: ✅ Toggle in scene tree")
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
                    print(f"🔥 [SMART-STRESS] {msg_count:,} updates | {elapsed:.1f}s | {avg_hz:.1f} Hz avg | Target: {hz:.1f} Hz | {nq}/{meaningful_dof} DOF | Frames: Built-in scene tree")
                    last_stats = loop_start
                
                # Sleep to maintain frequency
                period = 1.0 / hz if hz > 0 else 1.0
                loop_end = time.perf_counter()
                sleep_time = period - (loop_end - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            print("⏹️ [SMART-STRESS] Simplified stress testing stopped")
        
        @stress_enabled_cb.on_update
        def _(_):
            nonlocal stress_thread
            if stress_enabled_cb.value and stress_thread is None:
                stress_running.set()
                stress_thread = threading.Thread(target=run_stress_testing_in_thread, daemon=True)
                stress_thread.start()
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints"
                print(f"🚀 [SMART-STRESS] Started simplified stress testing: {current_stress_hz:.1f}Hz")
                
            elif not stress_enabled_cb.value and stress_thread is not None:
                stress_running.clear()
                stress_thread = None
                stress_info.value = "Disabled"
                print("⏹️ [SMART-STRESS] Stopped simplified stress testing")
        
        print(f"[SMART-STRESS] Simplified stress testing available")
        print(f"[SMART-STRESS] Config: {stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints, ±{stress_amplitude:.2f}rad")
    
    print(f"\n[MAIN] 🎉 Simplified Multi-URDF System Ready!")
    print(f"[MAIN] Ready for visualization with {meaningful_dof} meaningful DOF")
    print(f"[MAIN] 📐 Coordinate frames available in scene tree (Configuration & Diagnostics tab)")
    print(f"[TELEMETRY] WebSocket telemetry available on port 8081")
    print(f"[MAIN] View at: http://localhost:8080")
    
    # Run forever
    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    tyro.cli(main)
