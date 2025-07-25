"""
Viser Multi-URDF System with Robot Replay
Integrates robot replay functionality into the existing Viser system
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))

from viser_multi_urdf import *
from robot_data_parser import RobotDataParser
from joint_mapper import JointMapper
from replay_controller import SimpleReplayController

class ViserRobotReplaySystem:
    """Integrates robot replay with Viser multi-URDF system"""
    
    def __init__(self, server: viser.ViserServer, urdf_manager: SmartUrdfManager, robot_data: int = 1):
        self.server = server
        self.urdf_manager = urdf_manager
        self.robot_data = robot_data
        self.replay_controller = None
        self.replay_mode = False
        
        # GUI handles
        self.replay_controls = None
        self.play_button = None
        self.pause_button = None
        self.reset_button = None
        self.status_text = None
        self.frame_progress_text = None
        self.time_progress_text = None
        self.progress_percentage_text = None
        self.replay_mode_text = None
        self.monitor_thread = None
        self.monitor_running = False
        
        # Slider handles for unified control
        self.slider_handles = None
        self.joint_names = None
        
        # Initialize replay controller
        self._initialize_replay_controller()
        
    def set_slider_handles(self, slider_handles, joint_names):
        """Set slider handles for unified control"""
        self.slider_handles = slider_handles
        self.joint_names = joint_names
        print(f"[REPLAY_SYSTEM] Connected to {len(slider_handles)} sliders for unified control")
        
    def _initialize_replay_controller(self):
        """Initialize the replay controller"""
        try:
            print(f"[REPLAY_SYSTEM] Initializing robot replay controller with data file {self.robot_data}...")
            
            # Construct data file path
            data_file = f"data/robot_status{self.robot_data}.data.json"
            self.replay_controller = SimpleReplayController(data_file)
            
            # Set up update callback
            self.replay_controller.set_update_callback(self._on_replay_update)
            
            print(f"[REPLAY_SYSTEM] Robot replay controller initialized successfully with {data_file}")
            
        except Exception as e:
            print(f"[REPLAY_SYSTEM] Error initializing replay controller: {e}")
            self.replay_controller = None
    
    def _on_replay_update(self, joint_configs: Dict[str, Dict[str, float]]):
        """Handle updates from replay controller - UNIFIED SLIDER SYSTEM"""
        if not self.replay_mode or not self.slider_handles:
            return
            
        try:
            # Create full configuration array for all joints
            full_config = np.zeros(len(self.urdf_manager.filtered_joint_names))
            
            # Process each URDF's joint configuration
            for urdf_name, urdf_joint_config in joint_configs.items():
                if not urdf_joint_config:
                    continue
                    
                # Find joints for this URDF in the filtered joint names
                for i, joint_name in enumerate(self.urdf_manager.filtered_joint_names):
                    # Joint names are in format "urdf_name::actual_joint_name"
                    if joint_name.startswith(f"{urdf_name}::"):
                        actual_joint = joint_name.split("::", 1)[1]
                        
                        # Get the value from the joint config
                        if actual_joint in urdf_joint_config:
                            full_config[i] = urdf_joint_config[actual_joint]
                        # else: keep default value (0.0)
            
            # 🎯 UNIFIED SYSTEM: Update sliders, which will trigger robot updates
            for i, slider in enumerate(self.slider_handles):
                if i < len(full_config):
                    # Update slider value - this will trigger the slider callback
                    slider.value = float(full_config[i])
            
            # Note: No direct urdf_manager update - sliders handle it via callbacks!
            
        except Exception as e:
            print(f"[REPLAY_SYSTEM] Error in unified replay update: {e}")
            import traceback
            traceback.print_exc()
    
    def add_replay_controls(self):
        """Add enhanced replay controls positioned at bottom-left"""
        if self.replay_controller is None:
            print("[REPLAY_SYSTEM] Cannot add controls - replay controller not initialized")
            return
        
        # Get timeline info for initial display
        info = self.replay_controller.get_timeline_info()
        total_entries = info['total_entries']
        duration = info['duration_seconds']
        
        # Create replay controls in main GUI (will be positioned at bottom-left)
        # Using a more compact layout
        replay_folder = self.server.gui.add_folder("🎬 Robot Replay")
        
        with replay_folder:
            # Control buttons - compact icons for better layout
            self.play_button = self.server.gui.add_button("▶️ Play")
            self.pause_button = self.server.gui.add_button("⏸️ Pause")  
            self.reset_button = self.server.gui.add_button("🔄 Reset")
            
            # Replay mode toggle
            replay_mode_checkbox = self.server.gui.add_checkbox(
                "Replay Mode",
                initial_value=False
            )
            
            # Enhanced status information
            self.status_text = self.server.gui.add_text(
                "Status",
                initial_value="Ready - Toggle Replay Mode and click Play"
            )
            
            self.replay_mode_text = self.server.gui.add_text(
                "Mode",
                initial_value="DISABLED - Manual control active"
            )
            
            self.frame_progress_text = self.server.gui.add_text(
                "Frame",
                initial_value=f"0 / {total_entries}"
            )
            
            self.time_progress_text = self.server.gui.add_text(
                "Time",
                initial_value=f"0.0s / {duration:.1f}s"
            )
            
            self.progress_percentage_text = self.server.gui.add_text(
                "Progress",
                initial_value="0.0%"
            )
            
            # Wire up callbacks
            self.play_button.on_click(self._on_play_button_click)
            self.pause_button.on_click(self._on_pause_button_click)
            self.reset_button.on_click(self._on_reset_button_click)
            replay_mode_checkbox.on_update(self._on_replay_mode_change)
            
            # Start continuous monitoring for enhanced info
            self._start_enhanced_monitoring()
            
            print("[REPLAY_SYSTEM] Enhanced replay controls added to GUI")
    
    def _on_play_button_click(self, _):
        """Handle play button click"""
        if self.replay_controller is None:
            return
            
        if not self.replay_controller.is_playing:
            # Play
            self.replay_controller.play()
            self.status_text.value = "Playing..."
            
            # Start monitoring playback status
            self._monitor_playback_status()
    
    def _on_pause_button_click(self, _):
        """Handle pause button click"""
        if self.replay_controller is None:
            return
            
        if self.replay_controller.is_playing:
            # Pause
            self.replay_controller.pause()
            self.status_text.value = "Paused"
    
    def _on_reset_button_click(self, _):
        """Handle reset button click"""
        if self.replay_controller is None:
            return
            
        # Stop any playing playback and reset to beginning
        self.replay_controller.stop()
        self.status_text.value = "Ready - Click Play to start replay"
        
        print("[REPLAY_SYSTEM] Reset to beginning")
    
    def _monitor_playback_status(self):
        """Monitor playback status and update GUI"""
        def monitor():
            import time
            while self.replay_controller and self.replay_controller.is_playing:
                time.sleep(0.1)
            
            # Playback finished
            if self.replay_controller and not self.replay_controller.is_playing:
                info = self.replay_controller.get_timeline_info()
                if info['current_index'] == 0:
                    # Reset to beginning after completion
                    self.status_text.value = "Ready - Click Play to start replay"
                elif info['current_index'] >= info['total_entries']:
                    self.status_text.value = "Playback Complete"
                else:
                    self.status_text.value = "Paused"
        
        # Start monitoring in a separate thread
        import threading
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def _on_sequence_change(self, _):
        """Handle sequence ID input change"""
        if self.replay_controller is None:
            return
            
        sequence_id = int(self.sequence_input.value)
        success = self.replay_controller.goto_sequence_id(sequence_id)
        
        if success:
            self.status_text.value = f"Jumped to sequence {sequence_id}"
        else:
            self.status_text.value = f"Sequence {sequence_id} not found"
    
    def _on_replay_mode_change(self, _):
        """Handle replay mode toggle"""
        self.replay_mode = not self.replay_mode
        
        if self.replay_mode:
            self.status_text.value = "Replay mode ENABLED - Robot will follow recorded motion"
            self.replay_mode_text.value = "ENABLED - Robot follows recorded motion"
        else:
            self.status_text.value = "Replay mode DISABLED - Manual control active"
            self.replay_mode_text.value = "DISABLED - Manual control active"
        
        print(f"[REPLAY_SYSTEM] Replay mode: {'ENABLED' if self.replay_mode else 'DISABLED'}")
    
    def _start_enhanced_monitoring(self):
        """Start continuous monitoring for enhanced information display"""
        if self.monitor_running:
            return
            
        self.monitor_running = True
        
        def enhanced_monitor():
            import time
            while self.monitor_running and self.replay_controller:
                try:
                    # Get current timeline info
                    info = self.replay_controller.get_timeline_info()
                    current_index = info['current_index']
                    total_entries = info['total_entries']
                    duration_seconds = info['duration_seconds']
                    
                    # Calculate current time and progress
                    if total_entries > 0:
                        progress_percentage = (current_index / total_entries) * 100
                        current_time = (current_index / total_entries) * duration_seconds
                    else:
                        progress_percentage = 0.0
                        current_time = 0.0
                    
                    # Update GUI fields
                    if self.frame_progress_text:
                        self.frame_progress_text.value = f"{current_index} / {total_entries}"
                    
                    if self.time_progress_text:
                        self.time_progress_text.value = f"{current_time:.1f}s / {duration_seconds:.1f}s"
                    
                    if self.progress_percentage_text:
                        self.progress_percentage_text.value = f"{progress_percentage:.1f}%"
                    
                    # Update status based on controller state
                    if self.replay_controller.is_playing:
                        if self.status_text.value != "Playing...":
                            self.status_text.value = "Playing..."
                    else:
                        if current_index >= total_entries:
                            if self.status_text.value != "Playback Complete":
                                self.status_text.value = "Playback Complete"
                        elif current_index > 0:
                            if self.status_text.value not in ["Paused", "Playback Complete"]:
                                self.status_text.value = "Paused"
                    
                    # Sleep for a short time to avoid overloading the GUI
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"[REPLAY_SYSTEM] Error in enhanced monitor: {e}")
                    time.sleep(0.5)
        
        # Start monitoring in a separate thread
        import threading
        self.monitor_thread = threading.Thread(target=enhanced_monitor, daemon=True)
        self.monitor_thread.start()
        
        print("[REPLAY_SYSTEM] Enhanced monitoring started")
    
    def _stop_enhanced_monitoring(self):
        """Stop the enhanced monitoring thread"""
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        print("[REPLAY_SYSTEM] Enhanced monitoring stopped")


def main_with_replay(
    workcell: str = "workcell_beta",
    robot_data: int = 1,
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
    **kwargs
) -> None:
    """
    Main function with robot replay functionality
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
    
    # Initialize URDF manager
    urdf_manager = SmartUrdfManager(server)
    
    # Discover and load URDFs
    urdf_configs = discover_workcell_urdfs(workcell)
    if not urdf_configs:
        print(f"[MAIN] No URDFs found in {workcell}")
        return
    
    urdf_configs = deduplicate_urdfs(urdf_configs)
    print(f"[MAIN] Loading {len(urdf_configs)} URDFs")
    
    # Load URDFs
    for urdf_path, urdf_name in urdf_configs:
        urdf_manager.add_urdf(
            urdf_path, 
            urdf_name, 
            load_meshes=load_meshes,
            load_collision_meshes=load_collision_meshes
        )
    
    meaningful_dof = urdf_manager.get_total_meaningful_dof()
    print(f"[MAIN] System loaded with {meaningful_dof} meaningful DOF")
    
    # Initialize robot replay system
    replay_system = ViserRobotReplaySystem(server, urdf_manager, robot_data)
    
    # Create manual control sliders
    with server.gui.add_folder("Manual Joint Control"):
        (slider_handles, joint_names, initial_config) = create_smart_control_sliders(
            server, urdf_manager
        )
    
    # Connect sliders to replay system for unified control
    replay_system.set_slider_handles(slider_handles, joint_names)
    
    # Add replay controls
    replay_system.add_replay_controls()
    
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
    
    # Add grid
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
    
    print(f"\n[MAIN] 🎬 Robot Replay System Ready!")
    print(f"[MAIN] Loaded {len(urdf_configs)} URDFs with {meaningful_dof} DOF")
    print(f"[MAIN] Robot replay data: 469 entries, 9.4 seconds")
    print(f"[MAIN] View at: http://localhost:8080")
    print(f"[MAIN] 📋 Instructions:")
    print(f"[MAIN]   1. Toggle 'Replay Mode' to enable robot replay")
    print(f"[MAIN]   2. Click 'Play' to start recorded motion")
    print(f"[MAIN]   3. Click 'Pause' to pause playback")
    print(f"[MAIN]   4. Use manual sliders when replay mode is disabled")
    
    # Run forever
    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    tyro.cli(main_with_replay)
