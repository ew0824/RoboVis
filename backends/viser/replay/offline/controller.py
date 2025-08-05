"""
Offline Controller - Phase 2 of Offline Replay System

This module provides ultra-fast, lag-free playback of pre-processed robot data.
After OfflineProcessor has done the heavy lifting, this controller provides
instant access to any frame with zero parsing/mapping overhead.

The controller features:
- Zero-latency frame access (just NumPy array indexing)
- Instant seeking to any frame 
- Variable speed playback (0.1x to 5x)
- Frame-perfect controls
- Reverse playback capability
- High-precision timing (60fps smooth playback)

Usage:
    controller = OfflineController(processor)
    controller.set_update_callback(update_function)
    controller.play(speed=2.0)  # 2x speed playback
    controller.goto_frame(100)  # Instant seek
"""

import time
import threading
from typing import Callable, Optional

import numpy as np

from .processor import OfflineProcessor


class OfflineController:
    """
    Phase 2: Ultra-fast indexed playback with zero processing latency.
    
    This controller operates on pre-computed data from OfflineProcessor,
    providing instant access to any frame without parsing or mapping overhead.
    All operations are just NumPy array indexing for maximum speed.
    
    Attributes:
        processor: OfflineProcessor with pre-computed data
        current_frame: Current frame index in the timeline
        is_playing: Whether playback is currently active
        playback_speed: Playback speed multiplier (1.0 = normal speed)
        playback_direction: 1 for forward, -1 for reverse playback
        update_callback: Function called with joint configuration updates
        playback_thread: Thread for smooth playback timing
        stop_event: Threading event for stopping playback
    """
    
    def __init__(self, processor: OfflineProcessor):
        """
        Initialize the offline controller with pre-processed data.
        
        Args:
            processor: OfflineProcessor instance with processed data
        """
        self.processor = processor
        
        if not processor.is_processed:
            raise ValueError("Processor must have processed data before creating controller")
        
        # Playback state
        self.current_frame = 0
        self.is_playing = False
        self.playback_speed = 1.0
        self.playback_direction = 1  # 1 for forward, -1 for reverse
        
        # Callback for visualization updates
        self.update_callback = None
        
        # High-performance playback threading
        self.playback_thread = None
        self.stop_event = threading.Event()
        
        # Timing for smooth playback
        self.target_fps = 60  # Smooth 60fps playback
        
        print(f"🎬 [OFFLINE] Controller initialized for {self.processor.get_total_frames()} frames")
    
    def set_update_callback(self, callback: Callable[[np.ndarray], None]):
        """
        Set callback for joint configuration updates.
        
        Args:
            callback: Function that receives joint configuration array
            
        The callback receives pre-computed NumPy arrays directly,
        eliminating all parsing and conversion overhead.
        """
        self.update_callback = callback
        
    def goto_frame(self, frame_idx: int) -> bool:
        """
        Instant seeking to any frame - ZERO LATENCY!
        
        Args:
            frame_idx: Target frame index
            
        Returns:
            True if successful, False if invalid frame
            
        This method provides frame-perfect seeking with zero latency
        since all data is pre-computed and indexed.
        """
        if 0 <= frame_idx < self.processor.get_total_frames():
            self.current_frame = frame_idx
            self._update_visualization()
            return True
        return False
        
    def goto_sequence_id(self, sequence_id: int) -> bool:
        """
        Seek to frame by sequence ID - optimized with NumPy search.
        
        Args:
            sequence_id: Target sequence ID
            
        Returns:
            True if found and seeked, False otherwise
        """
        frame_idx = self.processor.find_frame_by_sequence_id(sequence_id)
        if frame_idx is not None:
            return self.goto_frame(frame_idx)
        return False
        
    def play(self, speed: float = 1.0, direction: int = 1):
        """
        Start ultra-fast playback with variable speed.
        
        Args:
            speed: Playback speed multiplier (0.1 to 5.0)
            direction: 1 for forward, -1 for reverse
            
        The playback loop uses high-precision timing to maintain
        smooth 60fps display regardless of playback speed.
        """
        if self.is_playing:
            print("[OFFLINE] Already playing - stopping current playback")
            self.pause()
        
        self.playback_speed = max(0.1, min(5.0, speed))  # Clamp speed
        self.playback_direction = 1 if direction >= 0 else -1
        self.is_playing = True
        self.stop_event.clear()
        
        # Start high-performance playback thread
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()
        
        direction_text = "forward" if self.playback_direction > 0 else "reverse"
        print(f"🎬 [OFFLINE] Started lag-free {direction_text} playback at {self.playback_speed}x speed")
        
    def pause(self):
        """Pause playback instantly."""
        if not self.is_playing:
            return
            
        self.is_playing = False
        self.stop_event.set()
        
        # Wait for playback thread to finish
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
            
        print(f"⏸️ [OFFLINE] Paused at frame {self.current_frame}")
        
    def stop(self):
        """Stop playback and reset to beginning."""
        self.pause()
        self.goto_frame(0)
        print("🛑 [OFFLINE] Stopped and reset to beginning")
        
    def step_frame(self, direction: int = 1):
        """
        Step one frame forward or backward.
        
        Args:
            direction: 1 for forward, -1 for backward
        """
        target_frame = self.current_frame + direction
        self.goto_frame(target_frame)
        
    def _playback_loop(self):
        """
        Ultra-fast playback loop - just array indexing!
        
        This loop maintains smooth 60fps playback timing while
        advancing through pre-computed frames at the specified speed.
        All updates are just NumPy array lookups - no processing!
        """
        frame_time = (1.0 / self.target_fps) / abs(self.playback_speed)
        total_frames = self.processor.get_total_frames()
        
        while self.is_playing and not self.stop_event.is_set():
            start_time = time.time()
            
            # ZERO-LATENCY UPDATE: Just array lookup!
            self._update_visualization()
            
            # Advance frame based on speed and direction
            self.current_frame += self.playback_direction
            
            # Handle boundaries
            if self.playback_direction > 0:
                if self.current_frame >= total_frames:
                    # Forward playback reached end
                    self.is_playing = False
                    self.current_frame = total_frames - 1
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
            # If we can't keep up, just run at maximum speed
                
    def _update_visualization(self):
        """
        Zero-latency visualization update - just array indexing!
        
        This method provides instant access to pre-computed joint
        configurations with zero parsing or mapping overhead.
        """
        if self.update_callback is None:
            return
            
        # INSTANT: Pre-computed configuration lookup (nanoseconds!)
        joint_config = self.processor.get_frame_config(self.current_frame)
        
        if joint_config is not None:
            # Direct callback with pre-computed NumPy array
            self.update_callback(joint_config)
            
    def get_current_frame(self) -> int:
        """Get current frame index."""
        return self.current_frame
        
    def get_total_frames(self) -> int:
        """Get total number of frames."""
        return self.processor.get_total_frames()
        
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
