"""
Robot Replay Module for Viser Backend Robot Data Playback

This module provides robot data replay functionality for playing back
recorded robot motion data. It integrates with the robot data parser
and joint mapper to provide smooth playback of real robot trajectories
with full GUI controls and timeline scrubbing capabilities.

Features:
- Offline robot data replay from JSON files
- Play/pause/reset controls with timeline scrubbing
- Progress tracking with time and percentage display
- Configurable downsampling for performance optimization
- Unified slider system integration for seamless control
- Enhanced monitoring with real-time status updates

Usage:
    from robot_replay import RobotReplayManager
    
    # Create replay manager
    replay_manager = RobotReplayManager(server, urdf_manager, robot_data=1)
    
    # Connect to slider system
    replay_manager.set_slider_handles(slider_handles, joint_names)
    
    # Add GUI controls
    replay_manager.add_replay_controls()
"""

from __future__ import annotations

import sys
import os
import time
import threading
from typing import Dict, List, Optional

import numpy as np
import viser

# Add replay directory to path for robot data modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'replay'))

try:
    from robot_data_parser import RobotDataParser
    from joint_mapper import JointMapper
    from replay_controller import SimpleReplayController
except ImportError as e:
    print(f"[ROBOT_REPLAY] Warning: Could not import robot data modules: {e}")
    print("[ROBOT_REPLAY] Robot replay functionality will be disabled")
    RobotDataParser = None
    JointMapper = None
    SimpleReplayController = None


class RobotReplayManager:
    """
    Manages robot data replay functionality for the Viser backend.
    
    This class integrates recorded robot motion data with the Viser visualization
    system, providing smooth playback with comprehensive GUI controls. It handles
    the complex mapping between robot data joint names and URDF joint names,
    and provides a unified interface with the manual slider system.
    
    Attributes:
        server: Viser server instance for GUI controls
        urdf_manager: SmartUrdfManager instance for robot control
        robot_data: Robot data file number to load
        downsample: Downsampling factor for replay data
        replay_controller: SimpleReplayController instance for data playback
        slider_handles: List of GUI slider handles for unified control
        joint_names: List of joint names corresponding to sliders
        monitor_thread: Thread for continuous status monitoring
        monitor_running: Flag to control monitoring thread execution
    """
    
    def __init__(self, server: viser.ViserServer, urdf_manager, robot_data: int = 1, downsample: int = 10):
        """
        Initialize the robot replay manager.
        
        Args:
            server: Viser server instance
            urdf_manager: SmartUrdfManager instance
            robot_data: Robot data file number (1 or 2)
            downsample: Downsampling factor for replay data optimization
        """
        self.server = server
        self.urdf_manager = urdf_manager
        self.robot_data = robot_data
        self.downsample = downsample
        self.replay_controller = None
        
        # GUI handles
        self.play_button = None
        self.pause_button = None
        self.reset_button = None
        self.timeline_slider = None
        self.status_text = None
        self.time_progress_text = None
        self.progress_percentage_text = None
        
        # Monitoring thread
        self.monitor_thread = None
        self.monitor_running = False
        
        # Timeline slider state
        self.updating_timeline_slider = False  # Flag to prevent callback loops
        
        # Slider handles for unified control
        self.slider_handles = None
        self.joint_names = None
        
        # Initialize replay controller
        self._initialize_replay_controller()
        
        print(f"[ROBOT_REPLAY] Robot replay manager initialized (data file: {robot_data}, downsample: {downsample}x)")
        
    def _initialize_replay_controller(self):
        """
        Initialize the replay controller with robot data.
        
        This method loads the specified robot data file and creates a
        SimpleReplayController instance. It handles missing dependencies
        gracefully and provides informative error messages.
        """
        if SimpleReplayController is None:
            print("[ROBOT_REPLAY] Error: Robot data modules not available")
            print("[ROBOT_REPLAY] Please ensure robot_data_parser.py, joint_mapper.py, and replay_controller.py are available")
            return
            
        try:
            print(f"[ROBOT_REPLAY] Initializing robot replay controller with data file {self.robot_data}...")
            
            # Construct data file path relative to project root
            from pathlib import Path
            current_dir = Path.cwd()
            project_root = current_dir
            while project_root.parent != project_root:
                if (project_root / '.gitignore').exists():
                    break
                project_root = project_root.parent
            data_file = str(project_root / f"data/robot_status{self.robot_data}.data.json")
            self.replay_controller = SimpleReplayController(data_file, downsample_factor=self.downsample)
            
            # Set up update callback
            self.replay_controller.set_update_callback(self._on_replay_update)
            
            print(f"[ROBOT_REPLAY] Robot replay controller initialized successfully with {data_file}")
            print(f"[ROBOT_REPLAY] Using downsample factor: {self.downsample}x")
            
        except Exception as e:
            print(f"[ROBOT_REPLAY] Error initializing replay controller: {e}")
            self.replay_controller = None
            
    def set_slider_handles(self, slider_handles: List, joint_names: List[str]):
        """
        Set slider handles for unified control integration.
        
        Args:
            slider_handles: List of GUI slider handles
            joint_names: List of joint names corresponding to sliders
            
        This method connects the robot replay system with the manual slider
        system, enabling seamless switching between replay and manual control.
        """
        self.slider_handles = slider_handles
        self.joint_names = joint_names
        print(f"[ROBOT_REPLAY] Connected to {len(slider_handles)} sliders for unified control")
        
    def _on_replay_update(self, joint_configs: Dict[str, Dict[str, float]]):
        """
        Handle updates from the replay controller using the unified slider system.
        
        Args:
            joint_configs: Dictionary mapping URDF names to joint configurations
            
        This method processes replay data and updates the robot visualization
        through the unified slider system. This ensures consistency between
        replay and manual control modes.
        """
        if not self.slider_handles:
            print("[ROBOT_REPLAY] Warning: No slider handles connected")
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
            
            # 🎯 UNIFIED SYSTEM: Update sliders, which will trigger robot updates
            for i, slider in enumerate(self.slider_handles):
                if i < len(full_config):
                    # Update slider value - this will trigger the slider callback
                    slider.value = float(full_config[i])
                    
        except Exception as e:
            print(f"[ROBOT_REPLAY] Error in unified replay update: {e}")
            import traceback
            traceback.print_exc()
            
    def add_replay_controls(self):
        """
        Add robot replay controls to the Viser GUI.
        
        Creates a comprehensive set of controls including:
        - Play/pause/reset buttons
        - Timeline scrubber slider
        - Status and progress displays
        - Real-time monitoring information
        
        The controls are positioned in a dedicated folder and provide
        intuitive access to all replay functionality.
        """
        if self.replay_controller is None:
            print("[ROBOT_REPLAY] Cannot add controls - replay controller not initialized")
            return
        
        # Get timeline info for initial display
        info = self.replay_controller.get_timeline_info()
        total_entries = info['total_entries']
        duration = info['duration_seconds']
        
        # Create replay controls
        with self.server.gui.add_folder("Robot Replay"):
            # Control buttons with intuitive icons
            self.play_button = self.server.gui.add_button("▶️ Play")
            self.pause_button = self.server.gui.add_button("⏸️ Pause")  
            self.reset_button = self.server.gui.add_button("🔄 Reset")
            
            # Timeline scrubber slider
            self.timeline_slider = self.server.gui.add_slider(
                "Timeline",
                min=0,
                max=max(1, total_entries - 1),
                step=1,
                initial_value=0
            )
            
            # Status information displays
            self.status_text = self.server.gui.add_text(
                "Status",
                initial_value="Ready - Click Play to start replay"
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
            self.timeline_slider.on_update(self._on_timeline_change)
            
        # Start continuous monitoring for enhanced info
        self._start_enhanced_monitoring()
        
        print("[ROBOT_REPLAY] Robot replay controls added to GUI")
        print(f"[ROBOT_REPLAY] Loaded {total_entries} data points spanning {duration:.1f}s")
        
    def _on_play_button_click(self, _):
        """Handle play button click to start/resume replay."""
        if self.replay_controller is None:
            return
            
        if not self.replay_controller.is_playing:
            # Start playing
            self.replay_controller.play()
            self.status_text.value = "Playing..."
            
            # Start monitoring playback status
            self._monitor_playback_status()
            
            print("[ROBOT_REPLAY] Playback started")
    
    def _on_pause_button_click(self, _):
        """Handle pause button click to pause replay."""
        if self.replay_controller is None:
            return
            
        if self.replay_controller.is_playing:
            # Pause playback
            self.replay_controller.pause()
            self.status_text.value = "Paused"
            
            print("[ROBOT_REPLAY] Playback paused")
    
    def _on_reset_button_click(self, _):
        """Handle reset button click to return to beginning."""
        if self.replay_controller is None:
            return
            
        # Stop any playing playback and reset to beginning
        self.replay_controller.stop()
        self.status_text.value = "Ready - Click Play to start replay"
        
        print("[ROBOT_REPLAY] Playback reset to beginning")
    
    def _on_timeline_change(self, _):
        """
        Handle timeline scrubber slider changes for seeking.
        
        This method allows users to scrub through the timeline by dragging
        the slider. It automatically pauses playback during scrubbing to
        provide responsive seeking behavior.
        """
        if self.replay_controller is None:
            return
            
        # Avoid callback loops when we're updating the slider programmatically
        if self.updating_timeline_slider:
            return
            
        # Pause playback when user scrubs the timeline
        was_playing = self.replay_controller.is_playing
        if was_playing:
            self.replay_controller.pause()
        
        # Jump to the selected frame
        frame_index = int(self.timeline_slider.value)
        self.replay_controller.goto_index(frame_index)
        
        # Update status
        if was_playing:
            self.status_text.value = "Paused (scrubbing)"
        else:
            self.status_text.value = "Paused"
        
        print(f"[ROBOT_REPLAY] Timeline scrubbed to frame {frame_index}")
        
    def _monitor_playback_status(self):
        """
        Monitor playback status and update GUI when playback finishes.
        
        This method runs in a separate thread to monitor the playback state
        and update the GUI status when playback completes naturally.
        """
        def monitor():
            while self.replay_controller and self.replay_controller.is_playing:
                time.sleep(0.1)
            
            # Playback finished - update status based on position
            if self.replay_controller and not self.replay_controller.is_playing:
                info = self.replay_controller.get_timeline_info()
                if info['current_index'] == 0:
                    # Reset to beginning after completion
                    self.status_text.value = "Ready - Click Play to start replay"
                elif info['current_index'] >= info['total_entries'] - 1:
                    self.status_text.value = "Playback Complete"
                else:
                    self.status_text.value = "Paused"
        
        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        
    def _start_enhanced_monitoring(self):
        """
        Start continuous monitoring for enhanced information display.
        
        This method starts a background thread that continuously updates
        the GUI with current playback information including time progress,
        percentage complete, and timeline slider position.
        """
        if self.monitor_running:
            return
            
        self.monitor_running = True
        
        def enhanced_monitor():
            while self.monitor_running and self.replay_controller:
                try:
                    # Get current timeline info
                    info = self.replay_controller.get_timeline_info()
                    current_index = info['current_index']
                    total_entries = info['total_entries']
                    duration_seconds = info['duration_seconds']
                    
                    # Calculate current time and progress
                    if total_entries > 0:
                        progress_percentage = (current_index / max(1, total_entries - 1)) * 100
                        current_time = (current_index / max(1, total_entries - 1)) * duration_seconds
                    else:
                        progress_percentage = 0.0
                        current_time = 0.0
                    
                    # Update GUI fields
                    if self.time_progress_text:
                        self.time_progress_text.value = f"{current_time:.1f}s / {duration_seconds:.1f}s"
                    
                    if self.progress_percentage_text:
                        self.progress_percentage_text.value = f"{progress_percentage:.1f}%"
                    
                    # Update timeline slider position during playback
                    if self.timeline_slider:
                        self.updating_timeline_slider = True
                        self.timeline_slider.value = current_index
                        self.updating_timeline_slider = False
                    
                    # Update status based on controller state
                    if self.replay_controller.is_playing:
                        if self.status_text and self.status_text.value != "Playing...":
                            self.status_text.value = "Playing..."
                    else:
                        if current_index >= total_entries - 1:
                            if self.status_text and self.status_text.value != "Playback Complete":
                                self.status_text.value = "Playback Complete"
                        elif current_index > 0:
                            if self.status_text and self.status_text.value not in ["Paused", "Playback Complete", "Paused (scrubbing)"]:
                                self.status_text.value = "Paused"
                    
                    # Sleep for a short time to avoid overloading the GUI
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"[ROBOT_REPLAY] Error in enhanced monitor: {e}")
                    time.sleep(0.5)
        
        # Start monitoring in a separate thread
        self.monitor_thread = threading.Thread(target=enhanced_monitor, daemon=True)
        self.monitor_thread.start()
        
        print("[ROBOT_REPLAY] Enhanced monitoring started")
        
    def _stop_enhanced_monitoring(self):
        """Stop the enhanced monitoring thread."""
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        print("[ROBOT_REPLAY] Enhanced monitoring stopped")
        
    def get_replay_status(self) -> dict:
        """
        Get current replay status information.
        
        Returns:
            Dictionary with replay status including:
            - is_available: Whether replay functionality is available
            - is_playing: Whether replay is currently playing
            - current_time: Current playback time in seconds
            - total_time: Total duration in seconds
            - progress: Progress percentage (0-100)
            - data_file: Robot data file being used
        """
        if self.replay_controller is None:
            return {
                "is_available": False,
                "is_playing": False,
                "current_time": 0.0,
                "total_time": 0.0,
                "progress": 0.0,
                "data_file": f"robot_status{self.robot_data}.data.json"
            }
            
        info = self.replay_controller.get_timeline_info()
        current_index = info['current_index']
        total_entries = info['total_entries']
        duration_seconds = info['duration_seconds']
        
        if total_entries > 0:
            progress_percentage = (current_index / max(1, total_entries - 1)) * 100
            current_time = (current_index / max(1, total_entries - 1)) * duration_seconds
        else:
            progress_percentage = 0.0
            current_time = 0.0
        
        return {
            "is_available": True,
            "is_playing": self.replay_controller.is_playing,
            "current_time": current_time,
            "total_time": duration_seconds,
            "progress": progress_percentage,
            "data_file": f"robot_status{self.robot_data}.data.json",
            "total_entries": total_entries,
            "current_index": current_index
        }
        
    def cleanup(self):
        """
        Clean up resources and stop monitoring.
        
        This method should be called when shutting down to ensure
        all threads are properly terminated and resources are cleaned up.
        """
        print("[ROBOT_REPLAY] Cleaning up robot replay resources")
        self._stop_enhanced_monitoring()
        
        if self.replay_controller:
            self.replay_controller.stop()


def create_robot_replay_manager(server: viser.ViserServer, urdf_manager, robot_data: int = 1, downsample: int = 10) -> Optional[RobotReplayManager]:
    """
    Factory function to create a RobotReplayManager instance.
    
    Args:
        server: Viser server instance
        urdf_manager: SmartUrdfManager instance
        robot_data: Robot data file number (1 or 2)
        downsample: Downsampling factor for performance optimization
        
    Returns:
        RobotReplayManager instance if successful, None if dependencies missing
        
    This factory function provides a convenient way to create a robot replay
    manager while handling missing dependencies gracefully.
    """
    if SimpleReplayController is None:
        print("[ROBOT_REPLAY] Cannot create robot replay manager - dependencies missing")
        return None
        
    try:
        return RobotReplayManager(server, urdf_manager, robot_data, downsample)
    except Exception as e:
        print(f"[ROBOT_REPLAY] Error creating robot replay manager: {e}")
        return None
