"""
Unified Robot Replay System

This module provides a centralized system for managing both streaming and offline
robot replay functionality with a clean, unified GUI interface.

The system coordinates:
- Streaming replay: Real-time processing with some latency
- Offline replay: Pre-processed data for lag-free playback
- Unified GUI controls in a single folder
- Proper lifecycle management and cleanup

Usage:
    from backends.viser.replay.replay import UnifiedReplaySystem
    
    replay_system = UnifiedReplaySystem(server, urdf_manager)
    replay_system.setup(
        robot_data=1, 
        streaming_downsample=10, 
        offline_downsample=5
    )
"""

from __future__ import annotations

from typing import Optional
import viser

from .streaming import create_streaming_manager
from .offline import create_offline_manager


class UnifiedReplaySystem:
    """
    Manages the unified robot replay system with both streaming and offline capabilities.
    
    This class provides a single point of control for the robot replay functionality,
    creating a clean unified GUI and managing the lifecycle of both streaming and
    offline replay managers.
    
    Attributes:
        server: Viser server instance
        urdf_manager: SmartUrdfManager instance
        streaming_manager: StreamingManager instance (optional)
        offline_manager: OfflineManager instance (optional)
        replay_folder: GUI folder handle for unified controls
    """
    
    def __init__(self, server: viser.ViserServer, urdf_manager):
        """
        Initialize the unified replay system.
        
        Args:
            server: Viser server instance
            urdf_manager: SmartUrdfManager instance for robot control
        """
        self.server = server
        self.urdf_manager = urdf_manager
        self.streaming_manager = None
        self.offline_manager = None
        self.replay_folder = None
        
        print("[REPLAY] Unified replay system initialized")
    
    def setup(
        self, 
        robot_data: int = 1, 
        streaming_downsample: int = 10, 
        offline_downsample: int = 5,
        slider_handles: Optional[list] = None,
        joint_names: Optional[list] = None
    ) -> bool:
        """
        Set up the unified replay system with both streaming and offline capabilities.
        
        Args:
            robot_data: Robot data file number (1 or 2)
            streaming_downsample: Downsampling factor for streaming replay
            offline_downsample: Downsampling factor for offline replay  
            slider_handles: List of GUI slider handles for unified control
            joint_names: List of joint names corresponding to sliders
            
        Returns:
            True if setup was successful, False otherwise
        """
        print("[REPLAY] Setting up unified robot replay system...")
        
        success = False
        
        # Initialize streaming replay
        print("[REPLAY] Setting up streaming replay...")
        self.streaming_manager = create_streaming_manager(
            self.server, self.urdf_manager, robot_data, streaming_downsample
        )
        if self.streaming_manager is not None:
            if slider_handles and joint_names:
                self.streaming_manager.set_slider_handles(slider_handles, joint_names)
            print(f"[REPLAY] ✅ Streaming replay ready (data file: {robot_data}, downsample: {streaming_downsample}x)")
            success = True
        else:
            print("[REPLAY] ❌ Streaming replay failed to initialize")
        
        # Initialize offline replay
        print("[REPLAY] Setting up offline replay...")
        self.offline_manager = create_offline_manager(
            self.server, self.urdf_manager, robot_data, offline_downsample
        )
        if self.offline_manager is not None:
            if slider_handles and joint_names:
                self.offline_manager.set_slider_handles(slider_handles, joint_names)
            
            # Configure for unified mode
            self.offline_manager.unified_server = self.server
            
            print(f"[REPLAY] ✅ Offline replay ready (data file: {robot_data}, downsample: {offline_downsample}x)")
            print(f"[REPLAY] 🔄 Processing will start when user clicks 'Process Data' button")
            success = True
        else:
            print("[REPLAY] ❌ Offline replay failed to initialize")
        
        # Create unified GUI if we have at least one working manager
        if success and (self.streaming_manager or self.offline_manager):
            self._create_unified_gui()
            
            # Enable GUI interactions for offline manager AFTER everything is set up
            if self.offline_manager:
                self.offline_manager.gui_ready = True
                print("[REPLAY] 🔓 Offline GUI interactions enabled")
                
            print("[REPLAY] ✅ Unified replay system ready")
            return True
        else:
            print("[REPLAY] ❌ Failed to initialize any replay managers")
            return False
    
    def _create_unified_gui(self):
        """Create the unified GUI controls for both streaming and offline replay."""
        print("[REPLAY] Creating unified replay GUI...")
        
        # Create the main replay folder
        self.replay_folder = self.server.gui.add_folder("🎬 Robot Replay")
        
        with self.replay_folder:
            # Streaming Replay Section
            if self.streaming_manager:
                self.server.gui.add_markdown("## 🔄 Streaming Replay")
                self.server.gui.add_markdown("*Real-time processing with some latency*")
                
                self._create_streaming_controls()
            
            # Add separator if both systems are available
            if self.streaming_manager and self.offline_manager:
                self.server.gui.add_markdown("---")
            
            # Offline Replay Section  
            if self.offline_manager:
                self.server.gui.add_markdown("## ⚡ Offline Replay")
                self.server.gui.add_markdown("*Pre-process data for lag-free playback*")
                
                self._create_offline_controls()
        
        print("[REPLAY] Unified GUI created successfully")
    
    def _create_streaming_controls(self):
        """Create streaming controls within the unified folder."""
        if not self.streaming_manager or not self.streaming_manager.streaming_controller:
            self.server.gui.add_text("Streaming Error", "Streaming controller not available")
            return
        
        # Get timeline info for initial display
        info = self.streaming_manager.streaming_controller.get_timeline_info()
        total_entries = info['total_entries']
        duration = info['duration_seconds']
        
        # Create controls and store in streaming manager for callbacks
        self.streaming_manager.play_button = self.server.gui.add_button("▶️ Play")
        self.streaming_manager.pause_button = self.server.gui.add_button("⏸️ Pause")
        self.streaming_manager.reset_button = self.server.gui.add_button("🔄 Reset")
        
        # Timeline scrubber
        self.streaming_manager.timeline_slider = self.server.gui.add_slider(
            "Timeline",
            min=0,
            max=max(1, total_entries - 1),
            step=1,
            initial_value=0
        )
        
        # Status displays
        self.streaming_manager.status_text = self.server.gui.add_text(
            "Status",
            "Ready - Click Play to start streaming"
        )
        
        self.streaming_manager.time_progress_text = self.server.gui.add_text(
            "Time",
            f"0.0s / {duration:.1f}s"
        )
        
        self.streaming_manager.progress_percentage_text = self.server.gui.add_text(
            "Progress",
            "0.0%"
        )
        
        # Wire up callbacks
        self.streaming_manager.play_button.on_click(self.streaming_manager._on_play_button_click)
        self.streaming_manager.pause_button.on_click(self.streaming_manager._on_pause_button_click)
        self.streaming_manager.reset_button.on_click(self.streaming_manager._on_reset_button_click)
        self.streaming_manager.timeline_slider.on_update(self.streaming_manager._on_timeline_change)
        
        print("[REPLAY] Streaming controls integrated successfully")
    
    def _create_offline_controls(self):
        """Create offline controls within the unified folder."""
        if not self.offline_manager:
            self.server.gui.add_text("Offline Error", "Offline manager not available")
            return
        
        # Store the unified folder reference for later use when processing completes
        self.offline_manager.unified_folder = self.replay_folder
        
        # Create initial "Process Data" button - user controls when to start
        self.offline_manager.gui_elements['process_button'] = self.server.gui.add_button("🔄 Process Data")
        self.offline_manager.gui_elements['status_text'] = self.server.gui.add_text(
            "Status",
            "Ready to process - Click 'Process Data' to begin"
        )
        
        # Wire up the process button callback
        self.offline_manager.gui_elements['process_button'].on_click(self.offline_manager._on_process_button_click)
        
        print("[REPLAY] Offline controls integrated successfully")
    
    def _add_offline_playback_controls(self):
        """Add offline playback controls after processing completes."""
        if not self.offline_manager or not self.offline_manager.controller:
            return
            
        # Add a separator before offline controls
        self.server.gui.add_markdown("### Offline Playback Controls")
        
        # Primary playback controls
        self.offline_manager.gui_elements['play_button'] = self.server.gui.add_button("▶️ Play")
        self.offline_manager.gui_elements['pause_button'] = self.server.gui.add_button("⏸️ Pause")  
        self.offline_manager.gui_elements['stop_button'] = self.server.gui.add_button("🛑 Reset")
        
        # Advanced controls
        self.offline_manager.gui_elements['step_backward'] = self.server.gui.add_button("⏪ Step Back")
        self.offline_manager.gui_elements['step_forward'] = self.server.gui.add_button("⏩ Step Forward")
        
        # Frame-perfect seeking
        max_frames = self.offline_manager.processor.get_total_frames()
        self.offline_manager.gui_elements['frame_slider'] = self.server.gui.add_slider(
            "Frame", 
            min=0, 
            max=max(1, max_frames - 1), 
            step=1, 
            initial_value=0
        )
        
        # Variable speed control  
        self.offline_manager.gui_elements['speed_slider'] = self.server.gui.add_slider(
            "Speed", 
            min=0.1, 
            max=5.0, 
            step=0.1, 
            initial_value=1.0
        )
        
        # Status displays
        self.offline_manager.gui_elements['status_text'] = self.server.gui.add_text(
            "Playback Status",
            "Ready for lag-free playback"
        )
        
        self.offline_manager.gui_elements['progress_text'] = self.server.gui.add_text(
            "Playback Progress", 
            "0.0% (Frame 0)"
        )
        
        self.offline_manager.gui_elements['time_text'] = self.server.gui.add_text(
            "Playback Time",
            f"0.0s / {self.offline_manager.processor.get_duration_seconds():.1f}s"
        )
        
        # Wire up callbacks (using the manager's existing methods)
        self.offline_manager._setup_gui_callbacks()
        
        print("[REPLAY] Offline playback controls added to unified GUI")
    
    def cleanup(self):
        """Clean up the replay system resources."""
        print("[REPLAY] Cleaning up unified replay resources...")
        
        if self.streaming_manager:
            self.streaming_manager.cleanup()
        
        if self.offline_manager:
            self.offline_manager.cleanup()
        
        print("[REPLAY] Cleanup complete")
    
    def get_status(self) -> dict:
        """Get the current status of the replay system."""
        return {
            "streaming_available": self.streaming_manager is not None,
            "offline_available": self.offline_manager is not None,
            "streaming_status": self.streaming_manager.get_streaming_status() if self.streaming_manager else None,
            "offline_status": self.offline_manager.get_playback_info() if self.offline_manager else None,
        }


def create_unified_replay_system(server: viser.ViserServer, urdf_manager) -> UnifiedReplaySystem:
    """
    Factory function to create a UnifiedReplaySystem instance.
    
    Args:
        server: Viser server instance
        urdf_manager: SmartUrdfManager instance
        
    Returns:
        UnifiedReplaySystem instance
    """
    return UnifiedReplaySystem(server, urdf_manager)
