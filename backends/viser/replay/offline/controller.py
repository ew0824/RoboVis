"""
Offline Controller - Ultra-Fast Pre-Processed Robot Replay

Refactored to use BaseController for standardized interface and
eliminate code duplication. This controller provides zero-latency
playback of pre-processed robot data.
"""

import time
import threading
from typing import Callable, Optional

import numpy as np

from .processor import OfflineProcessor
from ..shared.base_controller import BaseController


class OfflineController(BaseController):
    """
    Ultra-fast offline controller for pre-processed robot data replay.
    
    This controller inherits from BaseController and provides instant
    access to any frame without parsing or mapping overhead. All operations
    are just NumPy array indexing for maximum speed.
    
    Attributes:
        processor: OfflineProcessor with pre-computed data
        playback_direction: 1 for forward, -1 for reverse playback
        target_fps: Target FPS for smooth playback (60fps default)
    """
    
    def __init__(self, processor: OfflineProcessor):
        """
        Initialize the offline controller with pre-processed data.
        
        Args:
            processor: OfflineProcessor instance with processed data
        """
        super().__init__()
        
        self.processor = processor
        
        if not processor.is_processed:
            raise ValueError("Processor must have processed data before creating controller")
        
        # Offline-specific attributes
        self.playback_direction = 1  # 1 for forward, -1 for reverse
        self.target_fps = 60  # Smooth 60fps playback
        
        # Initialize base controller properties
        if not self._initialize_data("processor", processor=processor):
            raise RuntimeError("Failed to initialize offline controller")
        
        print(f"🎬 [OFFLINE] Controller initialized for {self.total_frames} frames")
    
    # ================= IMPLEMENT ABSTRACT METHODS =================
    
    def _initialize_data(self, data_source: str, **kwargs) -> bool:
        """Initialize offline controller with processor."""
        try:
            processor = kwargs.get('processor')
            if not processor or not processor.is_processed:
                return False
                
            # Set base controller properties from processor
            self.total_frames = processor.get_total_frames()
            self.duration_seconds = processor.get_duration_seconds()
            
            return True
        except Exception as e:
            print(f"[OFFLINE] Error initializing data: {e}")
            return False
    
    def _update_visualization(self) -> None:
        """Zero-latency visualization update - just array indexing!"""
        if self.update_callback is None:
            return
            
        # INSTANT: Pre-computed configuration lookup (nanoseconds!)
        joint_config = self.processor.get_frame_config(self.current_frame)
        
        if joint_config is not None:
            # Direct callback with pre-computed NumPy array
            self.update_callback(joint_config)
            
    def _playback_loop(self) -> None:
        """Ultra-fast playback loop - just array indexing!"""
        frame_time = (1.0 / self.target_fps) / abs(self.playback_speed)
        
        while self.is_playing and not self.stop_event.is_set():
            start_time = time.time()
            
            # ZERO-LATENCY UPDATE: Just array lookup!
            self._update_visualization()
            
            # Advance frame based on speed and direction
            self.current_frame += self.playback_direction
            
            # Handle boundaries
            if self.playback_direction > 0:
                if self.current_frame >= self.total_frames:
                    # Forward playback reached end
                    self.is_playing = False
                    self.current_frame = self.total_frames - 1
                    self._update_visualization()  # Show final frame
                    print("🏁 [OFFLINE] Reached end of timeline")
                    break
            else:
                if self.current_frame < 0:
                    # Reverse playback reached beginning
                    self.is_playing = False
                    self.current_frame = 0
                    self._update_visualization()  # Show first frame
                    print("🏁 [OFFLINE] Reached beginning of timeline")
                    break
            
            # High-precision timing for smooth playback
            elapsed = time.time() - start_time
            sleep_time = frame_time - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    def _find_frame_by_sequence_id(self, sequence_id: int) -> Optional[int]:
        """Find frame index by sequence ID (optimized for offline)."""
        return self.processor.find_frame_by_sequence_id(sequence_id)
        
    def _get_current_sequence_id(self) -> Optional[int]:
        """Get sequence ID of current frame."""
        return self.processor.get_frame_sequence_id(self.current_frame)
        
    # ================= ENHANCED OFFLINE METHODS =================
    
    def play_with_direction(self, speed: float = 1.0, direction: int = 1):
        """
        Start ultra-fast playback with variable speed and direction.
        
        Args:
            speed: Playback speed multiplier (0.1 to 5.0)
            direction: 1 for forward, -1 for reverse
        """
        self.playback_direction = 1 if direction >= 0 else -1
        
        # Use base controller's play method
        super().play(speed)
        
        direction_text = "forward" if self.playback_direction > 0 else "reverse"
        print(f"🎬 [OFFLINE] Started lag-free {direction_text} playback at {self.playback_speed}x speed")
        
    # ================= LEGACY COMPATIBILITY METHODS =================
    
    def get_current_frame(self) -> int:
        """Get current frame index (legacy compatibility)."""
        return self.current_frame
        
    def get_total_frames(self) -> int:
        """Get total number of frames (legacy compatibility)."""
        return self.total_frames
        
    def get_current_timestamp(self) -> Optional[int]:
        """Get timestamp of current frame."""
        return self.processor.get_frame_timestamp(self.current_frame)
        
    def get_current_sequence_id(self) -> Optional[int]:
        """Get sequence ID of current frame."""
        return self.processor.get_frame_sequence_id(self.current_frame)
        
    def get_progress_percentage(self) -> float:
        """Get playback progress as percentage (0-100)."""
        total = self.processor.get_total_frames()
        if total <= 1:
            return 0.0
        return (self.current_frame / (total - 1)) * 100
        
    def get_current_time_seconds(self) -> float:
        """Get current playback time in seconds."""
        total_duration = self.processor.get_duration_seconds()
        total_frames = self.processor.get_total_frames()
        
        if total_frames <= 1:
            return 0.0
            
        return (self.current_frame / (total_frames - 1)) * total_duration
        
    def get_playback_info(self) -> dict:
        """Get comprehensive playback status information."""
        return {
            'current_frame': self.current_frame,
            'total_frames': self.processor.get_total_frames(),
            'is_playing': self.is_playing,
            'playback_speed': self.playback_speed,
            'playback_direction': self.playback_direction,
            'progress_percentage': self.get_progress_percentage(),
            'current_time_seconds': self.get_current_time_seconds(),
            'total_duration_seconds': self.processor.get_duration_seconds(),
            'current_timestamp': self.get_current_timestamp(),
            'current_sequence_id': self.get_current_sequence_id()
        }
        
    def print_status(self):
        """Print current playback status."""
        info = self.get_playback_info()
        status = "PLAYING" if info['is_playing'] else "PAUSED"
        direction = "FORWARD" if info['playback_direction'] > 0 else "REVERSE"
        
        print(f"\n🎬 [OFFLINE] === PLAYBACK STATUS ===")
        print(f"Status: {status} ({direction} at {info['playback_speed']:.1f}x)")
        print(f"Frame: {info['current_frame']}/{info['total_frames']}")
        print(f"Time: {info['current_time_seconds']:.1f}s / {info['total_duration_seconds']:.1f}s")
        print(f"Progress: {info['progress_percentage']:.1f}%")
        print(f"Sequence ID: {info['current_sequence_id']}")
        print("="*40)


def test_offline_controller():
    """Test the offline controller independently."""
    print("=== TESTING OFFLINE CONTROLLER ===")
    
    # This would need a processed OfflineProcessor for testing
    # In actual usage, processor comes from OfflineManager
    print("⚠️  This test requires integration with OfflineProcessor")
    print("   Use through OfflineManager for full functionality")


if __name__ == "__main__":
    test_offline_controller()
