"""
Reusable GUI Components for Robot Replay System

This module provides standardized, reusable GUI components that are shared
between streaming and offline replay systems. This eliminates duplicate
GUI creation code and ensures consistent user experience.

Components provided:
- PlaybackControls: Standard play/pause/stop buttons
- TimelineControls: Slider and frame step buttons  
- StatusDisplays: Progress, time, and frame counters
- SpeedControls: Speed slider and presets
- EnhancedControls: Record3D-inspired features

All components are configurable and can be customized per replay mode.
"""

from typing import Dict, List, Optional, Callable, Any
import viser


class PlaybackControls:
    """
    Standard playback control buttons (play/pause/stop/reset).
    
    Provides the core transport controls that are common to both
    streaming and offline replay modes.
    """
    
    def __init__(self, server: viser.ViserServer, mode: str = "replay"):
        """
        Initialize playback controls.
        
        Args:
            server: Viser server instance
            mode: Mode identifier for button labels (e.g., "streaming", "offline")
        """
        self.server = server
        self.mode = mode
        self.buttons: Dict[str, Any] = {}
        
    def create(self) -> Dict[str, Any]:
        """
        Create standard playback buttons.
        
        Returns:
            Dictionary of button handles
        """
        self.buttons = {
            'play': self.server.gui.add_button("▶️ Play"),
            'pause': self.server.gui.add_button("⏸️ Pause"),
            'stop': self.server.gui.add_button("🛑 Stop"),
            'reset': self.server.gui.add_button("🔄 Reset")
        }
        
        return self.buttons
        
    def wire_callbacks(self, callbacks: Dict[str, Callable]):
        """
        Wire button callbacks.
        
        Args:
            callbacks: Dictionary mapping button names to callback functions
        """
        for button_name, callback in callbacks.items():
            if button_name in self.buttons:
                self.buttons[button_name].on_click(callback)
                
    def set_enabled_state(self, is_playing: bool):
        """
        Update button enabled states based on playback state.
        
        Args:
            is_playing: Whether playback is currently active
        """
        # Disable certain controls during playback
        if 'reset' in self.buttons:
            self.buttons['reset'].disabled = is_playing


class TimelineControls:
    """
    Timeline scrubber and frame step controls.
    
    Provides timeline navigation including slider scrubbing and
    frame-by-frame stepping controls.
    """
    
    def __init__(self, server: viser.ViserServer):
        """Initialize timeline controls."""
        self.server = server
        self.controls: Dict[str, Any] = {}
        
    def create(self, total_frames: int) -> Dict[str, Any]:
        """
        Create timeline navigation controls.
        
        Args:
            total_frames: Total number of frames for slider range
            
        Returns:
            Dictionary of control handles
        """
        self.controls = {
            # Frame step buttons
            'prev_frame': self.server.gui.add_button("⏮️ Previous Frame"),
            'next_frame': self.server.gui.add_button("⏭️ Next Frame"),
            
            # Timeline scrubber
            'timeline_slider': self.server.gui.add_slider(
                "Timeline",
                min=0,
                max=max(1, total_frames - 1),
                step=1,
                initial_value=0
            )
        }
        
        return self.controls
        
    def wire_callbacks(self, callbacks: Dict[str, Callable]):
        """Wire timeline control callbacks."""
        for control_name, callback in callbacks.items():
            if control_name in self.controls:
                if control_name == 'timeline_slider':
                    self.controls[control_name].on_update(callback)
                else:
                    self.controls[control_name].on_click(callback)
                    
    def set_enabled_state(self, is_playing: bool):
        """
        Update control enabled states.
        
        Args:
            is_playing: Whether playback is currently active
        """
        # Disable frame step controls when playing (Record3D style)
        if 'prev_frame' in self.controls:
            self.controls['prev_frame'].disabled = is_playing
        if 'next_frame' in self.controls:
            self.controls['next_frame'].disabled = is_playing
        if 'timeline_slider' in self.controls:
            self.controls['timeline_slider'].disabled = is_playing
            
    def update_position(self, current_frame: int):
        """
        Update timeline slider position.
        
        Args:
            current_frame: Current frame index
        """
        if 'timeline_slider' in self.controls:
            self.controls['timeline_slider'].value = current_frame


class StatusDisplays:
    """
    Status information displays (progress, time, frame counters).
    
    Provides comprehensive status information about playback state
    in a standardized format across replay modes.
    """
    
    def __init__(self, server: viser.ViserServer):
        """Initialize status displays."""
        self.server = server
        self.displays: Dict[str, Any] = {}
        
    def create(self, initial_status: str = "Ready") -> Dict[str, Any]:
        """
        Create status display elements.
        
        Args:
            initial_status: Initial status message
            
        Returns:
            Dictionary of display handles
        """
        self.displays = {
            'status': self.server.gui.add_text("Status", initial_status),
            'frame_counter': self.server.gui.add_text("Frame", "0 / 0"),
            'time_display': self.server.gui.add_text("Time", "0:00 / 0:00"),
            'progress': self.server.gui.add_text("Progress", "0.0%")
        }
        
        return self.displays
        
    def update(self, status_info: Dict[str, Any]):
        """
        Update all status displays.
        
        Args:
            status_info: Dictionary with current status information
        """
        # Update status text
        if 'status' in self.displays and 'status_text' in status_info:
            self.displays['status'].value = status_info['status_text']
            
        # Update frame counter
        if 'frame_counter' in self.displays:
            current = status_info.get('current_frame', 0)
            total = status_info.get('total_frames', 0)
            self.displays['frame_counter'].value = f"{current} / {total}"
            
        # Update time display (mm:ss format like Record3D)
        if 'time_display' in self.displays:
            current_time = status_info.get('current_time_seconds', 0)
            total_time = status_info.get('total_duration_seconds', 0)
            self.displays['time_display'].value = self._format_time_display(current_time, total_time)
            
        # Update progress percentage
        if 'progress' in self.displays:
            progress = status_info.get('progress_percentage', 0)
            self.displays['progress'].value = f"{progress:.1f}%"
            
    def _format_time_display(self, current_seconds: float, total_seconds: float) -> str:
        """Format time display in mm:ss format like Record3D."""
        def format_seconds(seconds):
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        
        return f"{format_seconds(current_seconds)} / {format_seconds(total_seconds)}"


class SpeedControls:
    """
    Speed control slider and presets.
    
    Provides playback speed control with both a continuous slider
    and discrete preset buttons for common speeds.
    """
    
    def __init__(self, server: viser.ViserServer):
        """Initialize speed controls."""
        self.server = server
        self.controls: Dict[str, Any] = {}
        
    def create(self, initial_speed: float = 1.0) -> Dict[str, Any]:
        """
        Create speed control elements.
        
        Args:
            initial_speed: Initial speed value
            
        Returns:
            Dictionary of control handles
        """
        self.controls = {
            'speed_slider': self.server.gui.add_slider(
                "Speed",
                min=0.1,
                max=5.0,
                step=0.1,
                initial_value=initial_speed
            ),
            'speed_presets': self.server.gui.add_button_group(
                "Speed Presets", ("0.5x", "1x", "2x", "5x")
            )
        }
        
        return self.controls
        
    def wire_callbacks(self, callbacks: Dict[str, Callable]):
        """Wire speed control callbacks."""
        for control_name, callback in callbacks.items():
            if control_name in self.controls:
                if control_name == 'speed_presets':
                    self.controls[control_name].on_click(callback)
                else:
                    self.controls[control_name].on_update(callback)
                    
    def get_current_speed(self) -> float:
        """Get current speed value."""
        return self.controls['speed_slider'].value if 'speed_slider' in self.controls else 1.0
        
    def set_speed(self, speed: float):
        """Set speed value."""
        if 'speed_slider' in self.controls:
            self.controls['speed_slider'].value = max(0.1, min(5.0, speed))


class EnhancedControls:
    """
    Record3D-inspired enhanced controls.
    
    Provides advanced playback features inspired by the Record3D example,
    including FPS control and enhanced display formatting.
    """
    
    def __init__(self, server: viser.ViserServer, mode: str = "enhanced"):
        """
        Initialize enhanced controls.
        
        Args:
            server: Viser server instance  
            mode: Control mode identifier
        """
        self.server = server
        self.mode = mode
        self.controls: Dict[str, Any] = {}
        
    def create(self, total_frames: int) -> Dict[str, Any]:
        """
        Create enhanced control set.
        
        Args:
            total_frames: Total number of frames
            
        Returns:
            Dictionary of all enhanced controls
        """
        # Create all component groups
        playback = PlaybackControls(self.server, self.mode)
        timeline = TimelineControls(self.server)
        status = StatusDisplays(self.server)
        speed = SpeedControls(self.server)
        
        # Combine all controls
        self.controls = {
            **playback.create(),
            **timeline.create(total_frames),
            **status.create(f"Ready for {self.mode} playback"),
            **speed.create()
        }
        
        # Store component instances for later use
        self.playback_controls = playback
        self.timeline_controls = timeline
        self.status_displays = status
        self.speed_controls = speed
        
        return self.controls
        
    def wire_all_callbacks(self, callback_map: Dict[str, Callable]):
        """
        Wire all callbacks using a single callback map.
        
        Args:
            callback_map: Dictionary mapping control names to callbacks
        """
        # Distribute callbacks to appropriate component groups
        playback_callbacks = {k: v for k, v in callback_map.items() 
                            if k in ['play', 'pause', 'stop', 'reset']}
        timeline_callbacks = {k: v for k, v in callback_map.items()
                            if k in ['prev_frame', 'next_frame', 'timeline_slider']}
        speed_callbacks = {k: v for k, v in callback_map.items()
                         if k in ['speed_slider', 'speed_presets']}
        
        # Wire each component group
        self.playback_controls.wire_callbacks(playback_callbacks)
        self.timeline_controls.wire_callbacks(timeline_callbacks)
        self.speed_controls.wire_callbacks(speed_callbacks)
        
    def update_state(self, is_playing: bool):
        """
        Update all control states based on playback state.
        
        Args:
            is_playing: Whether playback is currently active
        """
        self.playback_controls.set_enabled_state(is_playing)
        self.timeline_controls.set_enabled_state(is_playing)
        
    def update_displays(self, status_info: Dict[str, Any]):
        """
        Update all status displays.
        
        Args:
            status_info: Current status information
        """
        self.status_displays.update(status_info)
        self.timeline_controls.update_position(status_info.get('current_frame', 0))


def create_unified_controls(server: viser.ViserServer, mode: str, total_frames: int) -> EnhancedControls:
    """
    Factory function to create a complete set of unified controls.
    
    Args:
        server: Viser server instance
        mode: Control mode identifier (e.g., "streaming", "offline")
        total_frames: Total number of frames
        
    Returns:
        EnhancedControls instance with all components
    """
    controls = EnhancedControls(server, mode)
    controls.create(total_frames)
    return controls
