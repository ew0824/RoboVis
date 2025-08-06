"""
Base Controller for Robot Replay System

This module provides a standardized interface and common functionality
for both streaming and offline replay controllers, eliminating code
duplication and ensuring consistent behavior.

The BaseController defines the standard replay interface:
- play() / pause() / stop()
- goto_frame() / goto_sequence_id() 
- get_status()
- Standard callback system
- Common state management

All replay controllers inherit from this base to ensure consistency.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable, Union
import threading
import time


class BaseController(ABC):
    """
    Abstract base class for all replay controllers.
    
    This class defines the standard interface that all replay controllers
    must implement, ensuring consistency between streaming and offline modes.
    
    Attributes:
        current_frame: Current frame index in the timeline
        is_playing: Whether playback is currently active
        playback_speed: Speed multiplier for playback
        update_callback: Function called with joint configuration updates
        total_frames: Total number of frames in the timeline
        duration_seconds: Total duration of the timeline in seconds
    """
    
    def __init__(self):
        """Initialize base controller state."""
        # Standard playback state
        self.current_frame = 0
        self.is_playing = False
        self.playback_speed = 1.0
        
        # Callback for visualization updates
        self.update_callback: Optional[Callable] = None
        
        # Timeline info (set by subclasses)
        self.total_frames = 0
        self.duration_seconds = 0.0
        
        # Threading for playback
        self.playback_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
    # ================= ABSTRACT METHODS (Must be implemented) =================
    
    @abstractmethod
    def _initialize_data(self, data_source: str, **kwargs) -> bool:
        """
        Initialize data source (file, processor, etc.).
        
        Args:
            data_source: Path to data file or data source identifier
            **kwargs: Additional initialization parameters
            
        Returns:
            True if initialization successful, False otherwise
        """
        pass
        
    @abstractmethod
    def _update_visualization(self) -> None:
        """Update robot visualization with current frame data."""
        pass
        
    @abstractmethod
    def _playback_loop(self) -> None:
        """Main playback loop implementation (runs in separate thread)."""
        pass
        
    # ================= STANDARD INTERFACE (Common implementation) =================
    
    def set_update_callback(self, callback: Callable) -> None:
        """
        Set callback function for joint configuration updates.
        
        Args:
            callback: Function that receives joint configuration data
        """
        self.update_callback = callback
        
    def goto_frame(self, frame_index: int) -> bool:
        """
        Seek to specific frame index.
        
        Args:
            frame_index: Target frame index
            
        Returns:
            True if successful, False if invalid frame
        """
        if 0 <= frame_index < self.total_frames:
            self.current_frame = frame_index
            self._update_visualization()
            return True
        return False
        
    def goto_sequence_id(self, sequence_id: int) -> bool:
        """
        Seek to frame by sequence ID.
        
        Args:
            sequence_id: Target sequence ID
            
        Returns:
            True if found and seeked, False otherwise
        """
        # Default implementation - subclasses can override for optimization
        frame_index = self._find_frame_by_sequence_id(sequence_id)
        if frame_index is not None:
            return self.goto_frame(frame_index)
        return False
        
    def play(self, speed: float = 1.0) -> None:
        """
        Start playback at specified speed.
        
        Args:
            speed: Playback speed multiplier (0.1 to 5.0)
        """
        if self.is_playing:
            print(f"[CONTROLLER] Already playing - stopping current playback")
            self.pause()
        
        self.playback_speed = max(0.1, min(5.0, speed))  # Clamp speed
        self.is_playing = True
        self.stop_event.clear()
        
        # Start playback thread
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()
        
        print(f"[CONTROLLER] Started playback at {self.playback_speed}x speed")
        
    def pause(self) -> None:
        """Pause playback."""
        if not self.is_playing:
            return
            
        self.is_playing = False
        self.stop_event.set()
        
        # Wait for playback thread to finish
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
            
        print(f"[CONTROLLER] Paused at frame {self.current_frame}")
        
    def stop(self) -> None:
        """Stop playback and reset to beginning."""
        self.pause()
        self.goto_frame(0)
        print(f"[CONTROLLER] Stopped and reset to beginning")
        
    def step_frame(self, direction: int = 1) -> bool:
        """
        Step one frame forward or backward.
        
        Args:
            direction: 1 for forward, -1 for backward
            
        Returns:
            True if step successful, False if at boundary
        """
        target_frame = self.current_frame + direction
        return self.goto_frame(target_frame)
        
    def get_status(self) -> Dict:
        """
        Get standardized status information.
        
        Returns:
            Dictionary with current playback status
        """
        progress_percentage = 0.0
        current_time = 0.0
        
        if self.total_frames > 1:
            progress_percentage = (self.current_frame / (self.total_frames - 1)) * 100
            current_time = (self.current_frame / (self.total_frames - 1)) * self.duration_seconds
            
        return {
            'current_frame': self.current_frame,
            'total_frames': self.total_frames,
            'is_playing': self.is_playing,
            'playback_speed': self.playback_speed,
            'progress_percentage': progress_percentage,
            'current_time_seconds': current_time,
            'total_duration_seconds': self.duration_seconds,
            'current_sequence_id': self._get_current_sequence_id()
        }
        
    def print_status(self) -> None:
        """Print current status in standardized format."""
        status = self.get_status()
        state = "PLAYING" if status['is_playing'] else "PAUSED"
        
        print(f"\n[CONTROLLER] === STATUS ===")
        print(f"State: {state} (at {status['playback_speed']:.1f}x speed)")
        print(f"Frame: {status['current_frame']}/{status['total_frames']}")
        print(f"Time: {status['current_time_seconds']:.1f}s / {status['total_duration_seconds']:.1f}s")
        print(f"Progress: {status['progress_percentage']:.1f}%")
        print(f"Sequence ID: {status['current_sequence_id']}")
        print("="*30)
        
    # ================= HELPER METHODS (Can be overridden) =================
    
    def _find_frame_by_sequence_id(self, sequence_id: int) -> Optional[int]:
        """
        Find frame index by sequence ID (default implementation).
        
        Args:
            sequence_id: Target sequence ID
            
        Returns:
            Frame index if found, None otherwise
            
        Note: Subclasses should override this for better performance
        """
        # This is a fallback implementation
        # Subclasses with optimized data structures should override
        return None
        
    def _get_current_sequence_id(self) -> Optional[int]:
        """
        Get sequence ID of current frame (default implementation).
        
        Returns:
            Current sequence ID if available, None otherwise
            
        Note: Subclasses should override this
        """
        return None
        
    def get_current_frame(self) -> int:
        """Get current frame index."""
        return self.current_frame
        
    def get_total_frames(self) -> int:
        """Get total number of frames."""
        return self.total_frames
        
    def get_duration_seconds(self) -> float:
        """Get total duration in seconds."""
        return self.duration_seconds
        
    def cleanup(self) -> None:
        """Clean up resources."""
        print(f"[CONTROLLER] Cleaning up base controller resources")
        self.pause()
        
        
class PlaybackError(Exception):
    """Exception raised for playback-related errors."""
    pass
