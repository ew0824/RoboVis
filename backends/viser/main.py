"""
Viser Multi-URDF Robot Visualization System

This is the main entry point for the Viser-based robot visualization system.
It coordinates multiple specialized modules to provide a comprehensive
robot visualization and control platform with the following features:

- Multi-URDF robot loading and visualization
- Real-time telemetry and performance monitoring
- High-frequency stress testing capabilities
- Robot data streaming functionality
- Coordinate frame visualization
- Smart joint filtering and control

The system is designed to be modular and extensible, with each major
functionality contained in its own module:

- telemetry.py: WebSocket-based performance monitoring
- urdf_manager.py: URDF loading and multi-robot management
- stress_test.py: High-frequency performance stress testing
- robot_streaming.py: Robot data playback and streaming

Usage:
    # Basic multi-URDF visualization
    python backends/viser/viser.py --workcell workcell_alpha_2
    
    # With stress testing
    python backends/viser/viser.py --workcell workcell_alpha_2 --stress
    
    # With robot streaming
    python backends/viser/viser.py --workcell workcell_alpha_2 --streaming --robot_data 1
    
    # Combined functionality
    python backends/viser/viser.py --workcell workcell_alpha_2 --stress --streaming
"""

from __future__ import annotations

import sys
import os
import time
from typing import Optional

import tyro
import viser

# Add project root to Python path for absolute imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import our refactored modules
from backends.viser.telemetry import start_telemetry_server
from backends.viser.urdf.urdf_manager import (
    SmartUrdfManager,
    discover_workcell_urdfs,
    deduplicate_urdfs,
    create_smart_control_sliders
)
from backends.viser.stress_test import StressTestManager
from backends.viser.streaming.streaming import create_streaming_manager


def main(
    workcell: str = "workcell_beta",
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
    stress: bool = False,
    stress_hz: float = 200.0,
    stress_amplitude: float = 0.3,
    stress_wave_freq: float = 0.3,
    stress_joints: Optional[int] = None,
    streaming: bool = False,
    robot_data: int = 1,
    downsample: int = 10,
) -> None:
    """
    Main entry point for the Viser Multi-URDF Robot Visualization System.
    
    Args:
        workcell: Workcell configuration to load (e.g., "workcell_alpha_2")
        load_meshes: Whether to load visual meshes
        load_collision_meshes: Whether to load collision meshes
        stress: Enable stress testing functionality
        stress_hz: Stress test frequency in Hz
        stress_amplitude: Stress test amplitude in radians
        stress_wave_freq: Stress test wave frequency
        stress_joints: Number of joints to stress test (None = all)
        streaming: Enable robot streaming functionality
        robot_data: Robot data file number (1 or 2)
        downsample: Downsampling factor for streaming data
    """
    
    print("🚀 [VISER] Starting Viser Multi-URDF Robot Visualization System")
    print(f"[VISER] Workcell: {workcell}")
    print(f"[VISER] Features: Stress={stress}, streaming={streaming}")
    
    # Initialize Viser server
    server = viser.ViserServer(
        host="0.0.0.0",
        port=8080,
        serve_static=False,
    )
    
    # Initialize telemetry system (always available for debugging)
    start_telemetry_server()
    print("[VISER] Telemetry system initialized")
    
    # Initialize URDF management system
    print("[VISER] Initializing URDF management system...")
    urdf_manager = SmartUrdfManager(server)
    
    # Discover and load URDFs
    urdf_configs = discover_workcell_urdfs(workcell)
    if not urdf_configs:
        print(f"[VISER] ❌ No URDFs found in {workcell}")
        return
    
    # Deduplicate URDFs to avoid conflicts
    urdf_configs = deduplicate_urdfs(urdf_configs)
    print(f"[VISER] Loading {len(urdf_configs)} URDFs after deduplication")
    
    # Load all URDFs
    for urdf_path, urdf_name in urdf_configs:
        urdf_manager.add_urdf(
            urdf_path, 
            urdf_name, 
            load_meshes=load_meshes,
            load_collision_meshes=load_collision_meshes
        )
    
    meaningful_dof = urdf_manager.get_total_meaningful_dof()
    print(f"[VISER] ✅ System loaded with {meaningful_dof} meaningful DOF")
    
    if meaningful_dof == 0:
        print("[VISER] ❌ No meaningful joints found - check URDF loading")
        return
    
    # Create manual control sliders (always available)
    print("[VISER] Creating joint control interface...")
    with server.gui.add_folder("Joint Control"):
        (slider_handles, joint_names, initial_config) = create_smart_control_sliders(
            server, urdf_manager
        )
    
    # Set initial configuration
    urdf_manager.update_all_configurations(initial_config)
    
    # Initialize optional modules based on command line flags
    stress_manager = None
    streaming_manager = None
    
    # Initialize stress testing if requested
    if stress:
        print("[VISER] Initializing stress testing system...")
        stress_manager = StressTestManager(server, urdf_manager, initial_config)
        stress_manager.stress_hz = stress_hz
        stress_manager.stress_amplitude = stress_amplitude
        stress_manager.stress_wave_freq = stress_wave_freq
        stress_manager.set_stress_joints(stress_joints)
        stress_manager.add_stress_controls()
        print(f"[VISER] ✅ Stress testing system ready ({stress_hz:.1f}Hz)")
    
    # Initialize robot streaming if requested
    if streaming:
        print("[VISER] Initializing robot streaming system...")
        streaming_manager = create_streaming_manager(server, urdf_manager, robot_data, downsample)
        if streaming_manager is not None:
            streaming_manager.set_slider_handles(slider_handles, joint_names)
            streaming_manager.add_streaming_controls()
            print(f"[VISER] ✅ Robot streaming system ready (data file: {robot_data})")
        else:
            print("[VISER] ❌ Robot streaming system failed to initialize")
    
    # Add visibility controls
    print("[VISER] Adding visibility controls...")
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
    
    # Add scene grid for reference
    server.scene.add_grid(
        "/grid",
        width=4,
        height=4,
        position=(0.0, 0.0, 0.0),
    )
    
    # Create reset button for joint positions
    reset_button = server.gui.add_button("Reset All Joints")
    @reset_button.on_click
    def _(_):
        for s, init_val in zip(slider_handles, initial_config):
            s.value = init_val
        print("[VISER] Reset all joints to initial positions")
    
    # Print system summary
    print("\n" + "="*60)
    print("🎉 [VISER] System Ready!")
    print("="*60)
    print(f"📊 System Summary:")
    print(f"  - URDFs loaded: {len(urdf_configs)}")
    print(f"  - Meaningful DOF: {meaningful_dof}")
    print(f"  - Workcell: {workcell}")
    print(f"  - Visual meshes: {'✅' if load_meshes else '❌'}")
    print(f"  - Collision meshes: {'✅' if load_collision_meshes else '❌'}")
    print(f"  - Stress testing: {'✅' if stress else '❌'}")
    print(f"  - Robot streaming: {'✅' if streaming and streaming_manager else '❌'}")
    print(f"  - Telemetry: ✅ (port 8081)")
    print(f"  - Coordinate frames: ✅ (toggle in scene tree)")
    print()
    print(f"🌐 Access the system at: http://localhost:8080")
    print(f"📡 Telemetry available at: ws://localhost:8081")
    print()
    
    # Print usage instructions
    print("📋 Usage Instructions:")
    print("  1. Use joint sliders for manual robot control")
    print("  2. Toggle coordinate frames in the scene tree")
    print("  3. Use visibility controls to show/hide meshes")
    if stress:
        print("  4. Enable stress testing for performance analysis")
    if streaming and streaming_manager:
        print("  5. Use robot streaming controls for data playback")
    print("  6. Monitor performance via telemetry WebSocket")
    print()
    
    # Print module status
    print("🔧 Module Status:")
    print(f"  - telemetry.py: ✅ Active")
    print(f"  - urdf_manager.py: ✅ Active")
    print(f"  - stress_test.py: {'✅ Active' if stress else '⚪ Available'}")
    print(f"  - robot_streaming.py: {'✅ Active' if streaming and streaming_manager else '⚪ Available'}")
    print("="*60)
    
    # Main execution loop
    try:
        print("[VISER] System running - press Ctrl+C to stop")
        while True:
            time.sleep(10.0)
    except KeyboardInterrupt:
        print("\n[VISER] Shutting down...")
        
        # Clean up modules
        if stress_manager:
            stress_manager.cleanup()
        if streaming_manager:
            streaming_manager.cleanup()
            
        print("[VISER] Goodbye! 👋")


if __name__ == "__main__":
    tyro.cli(main)
