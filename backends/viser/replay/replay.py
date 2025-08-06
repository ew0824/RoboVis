"""
Robot Replay System Coordinator

Clean replay coordinator that eliminates redundancy and focuses solely on 
GUI creation and coordination. All business logic has been moved to the 
appropriate controllers and shared components.

The coordinator's only job:
1. Create the unified GUI structure  
2. Initialize controllers using BaseController interface
3. Wire GUI callbacks to controller methods
4. Manage lifecycle and cleanup
"""

from typing import Optional, List
import viser

from .streaming.controller import StreamingController
from .offline.controller import OfflineController
from .offline.processor import OfflineProcessor
from .shared.gui_components import create_unified_controls
from .shared.pro_controls import create_record3d_controls


class ReplayCoordinator:
    """
    Clean coordinator that just creates GUI and manages lifecycle.
    
    This class eliminates all the redundant GUI and callback code
    by delegating to standardized shared components and controllers.
    """
    
    def __init__(self, server: viser.ViserServer, urdf_manager):
        """
        Initialize the replay coordinator.
        
        Args:
            server: Viser server instance
            urdf_manager: SmartUrdfManager instance
        """
        self.server = server
        self.urdf_manager = urdf_manager
        
        # Controllers (BaseController interface)
        self.streaming_controller: Optional[StreamingController] = None
        self.offline_controller: Optional[OfflineController] = None
        
        # GUI components
        self.replay_folder = None
        self.streaming_controls = None
        self.offline_controls = None
        
        print("[REPLAY] Replay coordinator initialized")
    
    def setup(
        self, 
        robot_data: int = 1, 
        streaming_downsample: int = 1, 
        offline_downsample: int = 1,
        enable_record3d: bool = True
    ) -> bool:
        """
        Set up the complete replay system with clean separation.
        
        Args:
            robot_data: Robot data file number (1 or 2)
            streaming_downsample: Downsampling for streaming
            offline_downsample: Downsampling for offline
            enable_record3d: Whether to use Record3D-style controls
            
        Returns:
            True if setup successful
        """
        print("[REPLAY] Setting up replay system...")
        
        success = False
        
        # Create controllers using standardized interface
        if self._create_streaming_controller(robot_data, streaming_downsample):
            success = True
            
        if self._create_offline_system(robot_data, offline_downsample):
            success = True
            
        # Create GUI if we have at least one controller
        if success:
            self._create_unified_gui(enable_record3d)
            print("[REPLAY] ✅ Replay system ready")
            return True
        else:
            print("[REPLAY] ❌ Failed to initialize any controllers")
            return False
    
    def _create_streaming_controller(self, robot_data: int, downsample: int) -> bool:
        """Create streaming controller using BaseController interface."""
        try:
            from pathlib import Path
            data_file = f"data/robot_status{robot_data}.data.json"
            
            print(f"[DEBUG] ReplayCoordinator._create_streaming_controller() called with:")
            print(f"[DEBUG]   robot_data: {robot_data}")
            print(f"[DEBUG]   downsample: {downsample}")
            print(f"[DEBUG]   data_file: {data_file}")
            
            self.streaming_controller = StreamingController(data_file, downsample)
            self.streaming_controller.set_update_callback(self._on_streaming_update)
            
            print(f"[REPLAY] ✅ Streaming controller ready")
            return True
        except Exception as e:
            print(f"[REPLAY] ❌ Streaming controller failed: {e}")
            return False
    
    def _create_offline_system(self, robot_data: int, downsample: int) -> bool:
        """Create offline processor and controller."""
        try:
            data_file = f"data/robot_status{robot_data}.data.json"
            
            # Create processor
            processor = OfflineProcessor(data_file, self.urdf_manager)
            
            # Process data (this will be done when user clicks process)
            # For now, just prepare the system
            self.processor = processor
            
            print(f"[REPLAY] ✅ Offline system ready (processing on-demand)")
            return True
        except Exception as e:
            print(f"[REPLAY] ❌ Offline system failed: {e}")
            return False
    
    def _create_unified_gui(self, enable_record3d: bool):
        """Create clean unified GUI using shared components."""
        print("[REPLAY] Creating unified GUI...")
        
        # Create main folder
        self.replay_folder = self.server.gui.add_folder("🎬 Robot Replay")
        
        with self.replay_folder:
            # Streaming section
            if self.streaming_controller:
                self.server.gui.add_markdown("## 🔄 Streaming Replay")
                self.server.gui.add_markdown("*Real-time processing with some latency*")
                
                if enable_record3d:
                    # Use Record3D-style controls
                    self.streaming_controls = create_record3d_controls(
                        self.server, self.streaming_controller, "streaming"
                    )
                else:
                    # Use standard controls
                    total_frames = self.streaming_controller.get_total_frames()
                    self.streaming_controls = create_unified_controls(
                        self.server, "streaming", total_frames
                    )
                    self._wire_streaming_callbacks()
            
            # Separator
            if self.streaming_controller and self.processor:
                self.server.gui.add_markdown("---")
            
            # Offline section
            if self.processor:
                self.server.gui.add_markdown("## ⚡ Offline Replay")
                self.server.gui.add_markdown("*Pre-process data for lag-free playback*")
                
                # Process button (user-initiated)
                self.process_button = self.server.gui.add_button("🔄 Process Data")
                self.process_status = self.server.gui.add_text(
                    "Status", 
                    "Ready to process - Click 'Process Data' to begin"
                )
                
                self.process_button.on_click(self._on_process_data)
        
        print("[REPLAY] Unified GUI created")
    
    def _wire_streaming_callbacks(self):
        """Wire streaming callbacks using standardized interface."""
        if not self.streaming_controls:
            return
            
        # Map GUI controls to controller methods (BaseController interface)
        callback_map = {
            'play': lambda _: self.streaming_controller.play(),
            'pause': lambda _: self.streaming_controller.pause(), 
            'stop': lambda _: self.streaming_controller.stop(),
            'reset': lambda _: self.streaming_controller.stop(),
            'prev_frame': lambda _: self.streaming_controller.step_frame(-1),
            'next_frame': lambda _: self.streaming_controller.step_frame(1),
            'timeline_slider': lambda _: self._on_timeline_change(),
            'speed_presets': lambda _: self._on_speed_preset()
        }
        
        # Wire all callbacks
        self.streaming_controls.wire_all_callbacks(callback_map)
    
    def _on_process_data(self, _):
        """Handle offline data processing (user-initiated)."""
        print("[REPLAY] Starting offline data processing...")
        
        # Update status
        self.process_status.value = "🔄 Processing data..."
        
        # Process data (this could be moved to a background thread)
        try:
            stats = self.processor.process_all_data(downsample=5)
            
            if stats:
                # Create offline controller after processing
                self.offline_controller = OfflineController(self.processor)
                self.offline_controller.set_update_callback(self._on_offline_update)
                
                # Add offline controls
                self._add_offline_controls()
                
                self.process_status.value = f"✅ Ready! Processed {stats['total_frames']} frames"
                print("[REPLAY] ✅ Offline processing complete")
            else:
                self.process_status.value = "❌ Processing failed"
                
        except Exception as e:
            print(f"[REPLAY] ❌ Processing error: {e}")
            self.process_status.value = f"❌ Error: {str(e)}"
    
    def _add_offline_controls(self):
        """Add offline controls after processing is complete."""
        with self.replay_folder:
            # Add separator
            self.server.gui.add_markdown("### 🎮 Offline Controls")
            
            # Create Record3D-style controls for offline
            self.offline_controls = create_record3d_controls(
                self.server, self.offline_controller, "offline"
            )
    
    def _on_timeline_change(self):
        """Handle timeline slider changes."""
        if self.streaming_controls and hasattr(self.streaming_controls, 'controls'):
            frame_index = int(self.streaming_controls.controls['timeline_slider'].value)
            self.streaming_controller.goto_frame(frame_index)
    
    def _on_speed_preset(self):
        """Handle speed preset selection."""
        if self.streaming_controls and hasattr(self.streaming_controls, 'speed_controls'):
            # Speed changes take effect on next play
            pass
    
    def _on_streaming_update(self, joint_configs):
        """Handle streaming controller updates (efficient per-URDF approach)."""
        # Use the new efficient update method from URDF manager
        for urdf_name, joint_config in joint_configs.items():
            if joint_config:
                self.urdf_manager.update_specific_urdf(urdf_name, joint_config)
    
    def _on_offline_update(self, joint_config):
        """Handle offline controller updates (pre-computed array)."""
        # Update robot with pre-computed configuration using unified array approach
        if joint_config is not None:
            self.urdf_manager.update_all_configurations(joint_config)
    
    def get_status(self) -> dict:
        """Get system status (standardized interface)."""
        return {
            "streaming_available": self.streaming_controller is not None,
            "offline_available": self.offline_controller is not None,
            "streaming_status": self.streaming_controller.get_status() if self.streaming_controller else None,
            "offline_status": self.offline_controller.get_status() if self.offline_controller else None,
        }
    
    def cleanup(self):
        """Clean up all resources."""
        print("[REPLAY] Cleaning up replay system...")
        
        # Cleanup controllers
        if self.streaming_controller:
            self.streaming_controller.cleanup()
        if self.offline_controller:
            self.offline_controller.cleanup()
        
        # Cleanup GUI controls
        if self.streaming_controls:
            self.streaming_controls.cleanup()
        if self.offline_controls:
            self.offline_controls.cleanup()
        
        print("[REPLAY] Cleanup complete")


def create_replay_system(server: viser.ViserServer, urdf_manager) -> ReplayCoordinator:
    """
    Factory function to create the replay system.
    
    Args:
        server: Viser server instance
        urdf_manager: SmartUrdfManager instance
        
    Returns:
        ReplayCoordinator instance
    """
    return ReplayCoordinator(server, urdf_manager)
