"""
Offline Manager - The Orchestrator of Two-Phase Offline Replay System

This module coordinates the entire offline replay system, handling both
Phase 1 (processing) and Phase 2 (playback) with comprehensive GUI integration.

The manager:
1. Orchestrates OfflineProcessor for Phase 1 heavy lifting
2. Creates OfflineController for Phase 2 lag-free playback
3. Provides async initialization with progress feedback
4. Creates comprehensive GUI controls after processing
5. Integrates with URDF manager and slider system
6. Handles all user interactions and status updates

Usage:
    offline_manager = OfflineManager(server, urdf_manager, robot_data=1)
    await offline_manager.initialize_async(downsample=5)
    
    # After initialization, provides lag-free playback with full GUI controls
"""

import asyncio
import threading
import time
from typing import Optional, List, Callable

import numpy as np
import viser

from .processor import OfflineProcessor
from .controller import OfflineController


class OfflineManager:
    """
    Orchestrates the complete two-phase offline replay system.
    
    This manager handles the entire offline replay workflow:
    1. Shows processing progress during Phase 1
    2. Creates ultra-fast controller for Phase 2  
    3. Provides comprehensive GUI controls
    4. Integrates with existing slider system
    5. Handles all status updates and monitoring
    
    Attributes:
        server: Viser server instance for GUI controls
        urdf_manager: SmartUrdfManager for robot control
        robot_data: Robot data file number to load
        downsample: Downsampling factor for data reduction
        processor: OfflineProcessor instance (Phase 1)
        controller: OfflineController instance (Phase 2) 
        slider_handles: GUI slider handles for unified control
        joint_names: Joint names corresponding to sliders
        processing_complete: Flag indicating Phase 1 completion
        gui_elements: Dictionary of GUI control handles
    """
    
    def __init__(self, server: viser.ViserServer, urdf_manager, robot_data: int = 1, downsample: int = 5):
        """
        Initialize the offline replay manager.
        
        Args:
            server: Viser server instance
            urdf_manager: SmartUrdfManager instance
            robot_data: Robot data file number (1 or 2)
            downsample: Downsampling factor for performance
        """
        self.server = server
        self.urdf_manager = urdf_manager
        self.robot_data = robot_data
        self.downsample = downsample
        
        # Two-phase components
        self.processor = None
        self.controller = None
        
        # Integration with slider system
        self.slider_handles = None
        self.joint_names = None
        
        # State tracking
        self.processing_complete = False
        self.initialization_complete = False
        
        # GUI elements (created dynamically)
        self.gui_elements = {}
        
        # Monitoring
        self.monitor_thread = None
        self.monitor_running = False
        
        print(f"🚀 [OFFLINE] Initializing offline replay system...")
        print(f"📊 Data file: {robot_data}, Downsample: {downsample}x")
        
    def set_slider_handles(self, slider_handles: List, joint_names: List[str]):
        """
        Connect to the unified slider system.
        
        Args:
            slider_handles: List of GUI slider handles
            joint_names: List of joint names corresponding to sliders
        """
        self.slider_handles = slider_handles
        self.joint_names = joint_names
        print(f"🎯 [OFFLINE] Connected to {len(slider_handles)} sliders for unified control")
        
    async def initialize_async(self, downsample: Optional[int] = None):
        """
        Asynchronously initialize the offline replay system with progress feedback.
        
        Args:
            downsample: Override downsample factor (optional)
            
        This method handles both Phase 1 and Phase 2 initialization:
        1. Creates processor and starts heavy computation in background
        2. Shows real-time progress feedback to user
        3. Creates controller after processing completes
        4. Sets up comprehensive GUI controls
        5. Starts monitoring systems
        """
        if downsample is not None:
            self.downsample = downsample
            
        print(f"🔄 [OFFLINE] Starting async initialization (downsample={self.downsample}x)")
        
        # Phase 1: Create initial GUI with processing status
        self._create_processing_gui()
        
        # Phase 1: Start intensive processing in background thread
        await self._start_background_processing()
        
        # Phase 2: Create controller and full GUI after processing
        if self.processing_complete:
            self._create_controller()
            self._create_playback_gui()
            self._start_monitoring()
            self.initialization_complete = True
            
            print(f"✅ [OFFLINE] Async initialization complete!")
            print(f"🎬 Ready for lag-free playback with full controls")
        else:
            print(f"❌ [OFFLINE] Initialization failed during processing phase")
            
    def _create_processing_gui(self):
        """Create initial GUI showing processing progress."""
        with self.server.gui.add_folder("🔄 Offline Replay (Processing...)"):
            self.gui_elements['processing_status'] = self.server.gui.add_text(
                "Status", 
                "🔄 Initializing processor..."
            )
            
            self.gui_elements['processing_progress'] = self.server.gui.add_text(
                "Progress",
                "⏳ Starting data processing..."
            )
            
            self.gui_elements['processing_details'] = self.server.gui.add_text(
                "Details", 
                "📊 Preparing for lag-free playback..."
            )
            
    async def _start_background_processing(self):
        """Start intensive processing in background with progress updates."""
        
        # Create data file path
        data_file = f"data/robot_status{self.robot_data}.data.json"
        
        # Update status
        self.gui_elements['processing_status'].value = "🏗️ Creating processor..."
        
        try:
            # Create processor
            self.processor = OfflineProcessor(data_file, self.urdf_manager)
            self.gui_elements['processing_status'].value = "⚡ Processing all data..."
            
            # Run intensive processing in background
            processing_future = asyncio.create_task(self._run_processing_in_background())
            
            # Monitor progress while processing
            while not processing_future.done():
                await asyncio.sleep(0.1)  # Check every 100ms
                
            # Get processing results
            stats = await processing_future
            
            if stats:
                self.processing_complete = True
                
                # Update GUI with completion status
                self.gui_elements['processing_status'].value = (
                    f"✅ Processing Complete!"
                )
                self.gui_elements['processing_progress'].value = (
                    f"📊 {stats['total_frames']} frames in {stats['processing_time']:.1f}s"
                )
                self.gui_elements['processing_details'].value = (
                    f"💾 {stats['memory_usage_mb']:.1f}MB ready for lag-free playback"
                )
                
                print(f"✅ [OFFLINE] Background processing completed successfully")
                
            else:
                self.gui_elements['processing_status'].value = "❌ Processing failed"
                
        except Exception as e:
            print(f"❌ [OFFLINE] Processing error: {e}")
            self.gui_elements['processing_status'].value = f"❌ Error: {str(e)}"
            
    async def _run_processing_in_background(self):
        """Run the intensive processing in a background thread."""
        
        def process():
            try:
                return self.processor.process_all_data(self.downsample)
            except Exception as e:
                print(f"❌ [OFFLINE] Background processing error: {e}")
                return None
                
        # Run in thread pool to avoid blocking async event loop
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(None, process)
        return stats
        
    def _create_controller(self):
        """Create the ultra-fast controller after processing completes."""
        if not self.processing_complete or self.processor is None:
            print("❌ [OFFLINE] Cannot create controller - processing not complete")
            return
            
        try:
            self.controller = OfflineController(self.processor)
            self.controller.set_update_callback(self._on_config_update)
            print(f"🎬 [OFFLINE] Controller created successfully")
        except Exception as e:
            print(f"❌ [OFFLINE] Error creating controller: {e}")
            
    def _create_playback_gui(self):
        """Create comprehensive playback controls after processing."""
        if not self.controller:
            return
            
        with self.server.gui.add_folder("🎬 Offline Replay Controls"):
            
            # Primary playback controls
            self.gui_elements['play_button'] = self.server.gui.add_button("▶️ Play")
            self.gui_elements['pause_button'] = self.server.gui.add_button("⏸️ Pause")
            self.gui_elements['stop_button'] = self.server.gui.add_button("🛑 Reset")
            
            # Advanced controls
            self.gui_elements['step_backward'] = self.server.gui.add_button("⏪ Step Back")
            self.gui_elements['step_forward'] = self.server.gui.add_button("⏩ Step Forward")
            
            # Frame-perfect seeking
            max_frames = self.processor.get_total_frames()
            self.gui_elements['frame_slider'] = self.server.gui.add_slider(
                "Frame", 
                min=0, 
                max=max(1, max_frames - 1), 
                step=1, 
                initial_value=0
            )
            
            # Variable speed control  
            self.gui_elements['speed_slider'] = self.server.gui.add_slider(
                "Speed", 
                min=0.1, 
                max=5.0, 
                step=0.1, 
                initial_value=1.0
            )
            
            # Playback direction
            self.gui_elements['reverse_checkbox'] = self.server.gui.add_checkbox(
                "Reverse Playback", 
                initial_value=False
            )
            
            # Status displays
            self.gui_elements['status_text'] = self.server.gui.add_text(
                "Status",
                "Ready for lag-free playback"
            )
            
            self.gui_elements['progress_text'] = self.server.gui.add_text(
                "Progress", 
                "0.0% (Frame 0)"
            )
            
            self.gui_elements['time_text'] = self.server.gui.add_text(
                "Time",
                f"0.0s / {self.processor.get_duration_seconds():.1f}s"
            )
            
            # Wire up callbacks
            self._setup_gui_callbacks()
            
        print(f"🎛️ [OFFLINE] Comprehensive GUI controls created")
        
    def _setup_gui_callbacks(self):
        """Set up all GUI control callbacks."""
        
        # Primary controls
        self.gui_elements['play_button'].on_click(self._on_play_click)
        self.gui_elements['pause_button'].on_click(self._on_pause_click)
        self.gui_elements['stop_button'].on_click(self._on_stop_click)
        
        # Advanced controls
        self.gui_elements['step_backward'].on_click(lambda _: self.controller.step_frame(-1))
        self.gui_elements['step_forward'].on_click(lambda _: self.controller.step_frame(1))
        
        # Seeking and speed
        self.gui_elements['frame_slider'].on_update(self._on_frame_slider_change)
        self.gui_elements['speed_slider'].on_update(self._on_speed_change)
        
    def _on_play_click(self, _):
        """Handle play button click."""
        if not self.controller:
            return
            
        speed = self.gui_elements['speed_slider'].value
        direction = -1 if self.gui_elements['reverse_checkbox'].value else 1
        
        self.controller.play(speed=speed, direction=direction)
        
    def _on_pause_click(self, _):
        """Handle pause button click."""
        if self.controller:
            self.controller.pause()
            
    def _on_stop_click(self, _):
        """Handle stop/reset button click."""
        if self.controller:
            self.controller.stop()
            
    def _on_frame_slider_change(self, _):
        """Handle frame slider changes for seeking."""
        if not self.controller:
            return
            
        frame_idx = int(self.gui_elements['frame_slider'].value)
        self.controller.goto_frame(frame_idx)
        
    def _on_speed_change(self, _):
        """Handle speed slider changes."""
        # Speed changes take effect on next play() call
        pass
        
    def _on_config_update(self, joint_config: np.ndarray):
        """
        Handle ultra-fast joint configuration updates.
        
        Args:
            joint_config: Pre-computed joint configuration array
        """
        # Direct update to URDF manager - bypasses all parsing!
        self.urdf_manager.update_all_configurations(joint_config)
        
        # Update unified slider system for display consistency
        if self.slider_handles:
            for i, slider in enumerate(self.slider_handles):
                if i < len(joint_config):
                    slider.value = float(joint_config[i])
                    
    def _start_monitoring(self):
        """Start continuous status monitoring."""
        if self.monitor_running or not self.controller:
            return
            
        self.monitor_running = True
        
        def monitor():
            while self.monitor_running and self.controller:
                try:
                    info = self.controller.get_playback_info()
                    
                    # Update status displays
                    if self.gui_elements.get('status_text'):
                        status = "Playing" if info['is_playing'] else "Paused"
                        direction = "Reverse" if info['playback_direction'] < 0 else "Forward"
                        speed = info['playback_speed']
                        self.gui_elements['status_text'].value = f"{status} ({direction} {speed}x)"
                        
                    if self.gui_elements.get('progress_text'):
                        self.gui_elements['progress_text'].value = (
                            f"{info['progress_percentage']:.1f}% (Frame {info['current_frame']})"
                        )
                        
                    if self.gui_elements.get('time_text'):
                        self.gui_elements['time_text'].value = (
                            f"{info['current_time_seconds']:.1f}s / {info['total_duration_seconds']:.1f}s"
                        )
                        
                    # Update frame slider position during playback
                    if self.gui_elements.get('frame_slider'):
                        self.gui_elements['frame_slider'].value = info['current_frame']
                    
                    time.sleep(0.1)  # Update at 10Hz
                    
                except Exception as e:
                    print(f"❌ [OFFLINE] Monitor error: {e}")
                    time.sleep(0.5)
                    
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        
        print(f"📊 [OFFLINE] Status monitoring started")
        
    def _stop_monitoring(self):
        """Stop status monitoring."""
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        print(f"📊 [OFFLINE] Status monitoring stopped")
        
    def get_playback_info(self) -> dict:
        """Get current playback information."""
        if not self.controller:
            return {
                'available': False,
                'processing_complete': self.processing_complete
            }
            
        info = self.controller.get_playback_info()
        info.update({
            'available': True,
            'processing_complete': self.processing_complete,
            'initialization_complete': self.initialization_complete,
            'data_file': f"robot_status{self.robot_data}.data.json"
        })
        
        return info
        
    def cleanup(self):
        """Clean up resources."""
        print(f"🧹 [OFFLINE] Cleaning up offline replay resources")
        
        self._stop_monitoring()
        
        if self.controller:
            self.controller.pause()
            
        print(f"🧹 [OFFLINE] Cleanup complete")


def create_offline_manager(server: viser.ViserServer, urdf_manager, robot_data: int = 1, downsample: int = 5) -> Optional[OfflineManager]:
    """
    Factory function to create an OfflineManager instance.
    
    Args:
        server: Viser server instance
        urdf_manager: SmartUrdfManager instance
        robot_data: Robot data file number (1 or 2)
        downsample: Downsampling factor for performance optimization
        
    Returns:
        OfflineManager instance if successful, None if error
        
    This factory provides a convenient way to create an offline manager
    while handling errors gracefully.
    """
    try:
        return OfflineManager(server, urdf_manager, robot_data, downsample)
    except Exception as e:
        print(f"❌ [OFFLINE] Error creating offline manager: {e}")
        return None


def test_offline_manager():
    """Test the offline manager."""
    print("=== TESTING OFFLINE MANAGER ===")
    print("⚠️  This test requires integration with Viser server and URDF manager")
    print("   Use through main.py for full functionality")


if __name__ == "__main__":
    test_offline_manager()
