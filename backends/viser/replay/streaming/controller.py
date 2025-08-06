"""
Streaming Controller for Robot Replay System

Refactored to use BaseController for standardized interface and
eliminate code duplication. This controller handles real-time
processing of robot data with some latency.
"""

import time
import threading
from typing import Dict, List, Optional, Callable
from ..parser import DataParser
from ..joint_mapper import JointMapper
from ..shared.base_controller import BaseController

class StreamingController(BaseController):
    """
    Streaming controller for real-time robot data replay.
    
    This controller inherits from BaseController and provides
    real-time processing of robot data with configurable downsampling.
    """
    
    def __init__(self, json_file: str = "data/robot_status_beta.data.json", downsample_factor: int = 5):
        """Initialize streaming controller with data file."""
        super().__init__()
        
        self.json_file = json_file
        self.downsample_factor = downsample_factor
        
        # Data processing components
        self.parser = DataParser(json_file)
        self.mapper = JointMapper()
        
        # Initialize data
        if not self._initialize_data(json_file, downsample_factor=downsample_factor):
            raise RuntimeError(f"Failed to initialize streaming data from {json_file}")
        
        print(f"[STREAMING] Initialized with {self.total_frames} frames")
        print(f"[STREAMING] Downsampling: {downsample_factor}x (500Hz → {500/downsample_factor:.0f}Hz)")
    
    # ================= IMPLEMENT ABSTRACT METHODS =================
    
    def _initialize_data(self, data_source: str, **kwargs) -> bool:
        """Initialize streaming data from JSON file."""
        try:
            downsample_factor = kwargs.get('downsample_factor', 5)
            
            # Load and parse data
            self.parser.load_data()
            self.parser.parse_data(downsample_factor=downsample_factor)
            
            # Set base controller properties
            self.total_frames = len(self.parser.parsed_data)
            timeline_info = self.parser.get_timeline_info()
            self.duration_seconds = timeline_info['duration_seconds']
            
            return True
        except Exception as e:
            print(f"[STREAMING] Error initializing data: {e}")
            return False
            
    def _update_visualization(self) -> None:
        """Update visualization with current data (BaseController interface)."""
        entry = self.get_current_entry()
        if entry and self.update_callback:
            # Create joint configurations for each URDF
            joint_configs = {}
            
            for urdf_name in self.mapper.get_all_urdf_names():
                joint_config = self.mapper.create_joint_config_for_urdf(urdf_name, entry)
                if joint_config:  # Only add if we have joint data
                    joint_configs[urdf_name] = joint_config
            
            # Call the update callback with joint configurations
            self.update_callback(joint_configs)
            
    def _playback_loop(self) -> None:
        """Main playback loop (BaseController interface)."""
        # Calculate real-time frame rate based on downsampling
        original_rate = 500.0  # Original robot controller rate (500Hz)
        effective_rate = original_rate / self.downsample_factor
        frame_time = 1.0 / effective_rate / self.playback_speed  # Account for speed
        
        print(f"[STREAMING] Real-time playback at {effective_rate:.1f}Hz (speed: {self.playback_speed}x)")
        
        while self.is_playing and not self.stop_event.is_set():
            start_time = time.time()
            
            # Update current frame
            self._update_visualization()
            
            # Advance to next frame
            self.current_frame += 1
            
            # Check if we reached the end
            if self.current_frame >= self.total_frames:
                print("[STREAMING] Reached end of timeline - auto-resetting")
                self.is_playing = False
                self.current_frame = 0  # Auto-reset to beginning
                self._update_visualization()  # Update visualization to show reset position
                break
            
            # Sleep to maintain real-time rate
            elapsed = time.time() - start_time
            sleep_time = frame_time - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _find_frame_by_sequence_id(self, sequence_id: int) -> Optional[int]:
        """Find frame index by sequence ID (optimized for streaming)."""
        for i, entry in enumerate(self.parser.parsed_data):
            if entry['sequence_id'] == sequence_id:
                return i
        return None
        
    def _get_current_sequence_id(self) -> Optional[int]:
        """Get sequence ID of current frame."""
        entry = self.get_current_entry()
        return entry['sequence_id'] if entry else None
    
    # ================= LEGACY COMPATIBILITY METHODS =================
    
    def get_total_entries(self) -> int:
        """Get total number of entries in timeline"""
        return self.total_frames
    
    def get_current_entry(self) -> Optional[Dict]:
        """Get current timeline entry"""
        if 0 <= self.current_frame < len(self.parser.parsed_data):
            return self.parser.parsed_data[self.current_frame]
        return None
    
    def goto_index(self, index: int) -> bool:
        """Jump to specific index (legacy compatibility)"""
        return self.goto_frame(index)
    
    def get_timeline_info(self) -> Dict:
        """Get timeline information (legacy compatibility)"""
        info = self.parser.get_timeline_info()
        info.update({
            'current_index': self.current_frame,  # Use BaseController's current_frame
            'current_sequence_id': self._get_current_sequence_id(),
            'is_playing': self.is_playing
        })
        return info
    
    def print_status(self) -> None:
        """Print current status (legacy compatibility)"""
        info = self.get_timeline_info()
        status = "PLAYING" if self.is_playing else "PAUSED"
        
        print(f"\n[STREAMING] === STATUS ===")
        print(f"Status: {status}")
        print(f"Frame: {info['current_index']}/{info['total_entries']}")
        print(f"Sequence ID: {info['current_sequence_id']}")
        print(f"Duration: {info['duration_seconds']:.1f}s")


def test_streaming_controller():
    """Test the streaming controller"""
    print("=== TESTING streaming CONTROLLER ===")
    
    # Create controller
    controller = StreamingController()
    
    # Set up a simple update callback
    def update_callback(joint_configs):
        print(f"[CALLBACK] Updated {len(joint_configs)} URDFs")
        for urdf_name, config in joint_configs.items():
            if config:  # Only show non-empty configs
                joint_count = len(config)
                print(f"  {urdf_name}: {joint_count} joints")
    
    controller.set_update_callback(update_callback)
    
    # Test initial state
    controller.print_status()
    
    # Test jumping to sequence ID
    print("\n=== TESTING SEQUENCE ID NAVIGATION ===")
    sequence_ids = controller.parser.get_sequence_ids()
    if len(sequence_ids) > 5:
        test_seq_id = sequence_ids[5]
        controller.goto_sequence_id(test_seq_id)
        controller.print_status()
    
    # Test manual step
    print("\n=== TESTING MANUAL STEP ===")
    controller.goto_index(0)
    controller._update_visualization()
    
    # Test playback for a few seconds
    print("\n=== TESTING PLAYBACK ===")
    controller.play()
    time.sleep(2.0)  # Play for 2 seconds
    controller.pause()
    
    controller.print_status()
    print("\n[streaming] Test completed successfully!")


if __name__ == "__main__":
    test_streaming_controller()
