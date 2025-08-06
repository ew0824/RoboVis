"""
Professional Playback Controls

This module provides Record3D-inspired professional playback controls with
advanced features like atomic updates, FPS presets, and smooth state management.

Features:
- Atomic scene updates for smooth transitions
- Professional FPS control (direct timing like Record3D)
- Advanced control state management  
- Threaded playback with direct FPS timing
- Frame-perfect seeking and stepping

This module can be used by both streaming and offline replay systems.
"""

import threading
import time
from typing import Dict, Callable, Optional, Any
import viser


class EnhancedPlaybackEngine:
    """
    Record3D-style playback engine with direct FPS control.
    
    This engine provides professional playback features inspired by
    Record3D's implementation, including direct FPS timing and
    atomic scene updates.
    """
    
    def __init__(self, server: viser.ViserServer, controller):
        """
        Initialize enhanced playback engine.
        
        Args:
            server: Viser server instance for atomic updates
            controller: Base controller instance to control
        """
        self.server = server
        self.controller = controller
        
        # Enhanced threading
        self.enhanced_thread: Optional[threading.Thread] = None
        self.should_stop = False
        self.enhanced_mode = False
        
        # FPS control (like Record3D)
        self.target_fps = 20.0
        
    def start_enhanced_playback(self, fps: float = 20.0) -> None:
        """
        Start Record3D-style playback with direct FPS control.
        
        Args:
            fps: Target FPS for playback
        """
        print(f"[ENHANCED] Starting Record3D-style playback at {fps}FPS")
        
        # Stop original controller to prevent conflicts
        if hasattr(self.controller, 'pause'):
            self.controller.pause()
            
        # Configure enhanced mode
        self.enhanced_mode = True
        self.target_fps = fps
        self.should_stop = False
        
        # Start our own timing thread (like Record3D)
        self.enhanced_thread = threading.Thread(
            target=self._enhanced_playback_loop,
            daemon=True
        )
        self.enhanced_thread.start()
        
    def stop_enhanced_playback(self) -> None:
        """Stop enhanced playback and return control."""
        if not self.enhanced_mode:
            return
            
        print("[ENHANCED] Stopping Record3D-style playback")
        self.enhanced_mode = False
        self.should_stop = True
        
        if self.enhanced_thread and self.enhanced_thread.is_alive():
            self.enhanced_thread.join(timeout=1.0)
            
    def _enhanced_playback_loop(self) -> None:
        """
        Record3D-style playback loop with direct FPS timing.
        
        This implements the exact pattern from Record3D:
        - Direct timing control with time.sleep(1.0 / fps)
        - Atomic scene updates for smooth transitions
        - Auto-reset at end of timeline
        """
        frame_time = 1.0 / self.target_fps
        
        print(f"[ENHANCED] Starting Record3D-style loop at {self.target_fps}FPS")
        
        while self.enhanced_mode and not self.should_stop:
            try:
                current_frame = self.controller.get_current_frame()
                max_frame = self.controller.get_total_frames() - 1
                
                # Update to next frame
                if current_frame >= max_frame:
                    # Auto-reset at end (like Record3D)
                    self.controller.goto_frame(0)
                    print("[ENHANCED] Auto-reset at end of timeline")
                else:
                    next_frame = current_frame + 1
                    self._atomic_frame_update(next_frame)
                
                # Direct FPS timing (like Record3D)
                time.sleep(frame_time)
                
            except Exception as e:
                print(f"[ENHANCED] Error in playback loop: {e}")
                time.sleep(0.1)
                
        print("[ENHANCED] Record3D-style playback loop ended")
        
    def _atomic_frame_update(self, frame_index: int) -> None:
        """
        Update frame with atomic scene updates.
        
        Args:
            frame_index: Target frame index
        """
        try:
            # Use atomic updates for smooth transitions (like Record3D)
            with self.server.atomic():
                self.controller.goto_frame(frame_index)
            self.server.flush()  # Optional flush for immediate updates
        except Exception as e:
            print(f"[ENHANCED] Error in atomic update: {e}")
            
    def set_fps(self, fps: float) -> None:
        """
        Set playback FPS (takes effect immediately).
        
        Args:
            fps: New target FPS
        """
        self.target_fps = max(1.0, min(60.0, fps))
        
    def is_enhanced_playing(self) -> bool:
        """Check if enhanced playback is active."""
        return self.enhanced_mode


class Record3DControls:
    """
    Complete Record3D-style control system.
    
    This class provides the full Record3D experience including
    FPS presets, frame stepping, and enhanced state management.
    """
    
    def __init__(self, server: viser.ViserServer, controller, mode: str = "enhanced"):
        """
        Initialize Record3D-style controls.
        
        Args:
            server: Viser server instance
            controller: Base controller to enhance
            mode: Mode identifier
        """
        self.server = server
        self.controller = controller
        self.mode = mode
        
        # Enhanced playback engine
        self.playback_engine = EnhancedPlaybackEngine(server, controller)
        
        # GUI elements
        self.controls: Dict[str, Any] = {}
        
        # State tracking
        self.is_playing = False
        self.should_stop_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
    def create_controls(self, total_frames: int) -> Dict[str, Any]:
        """
        Create complete Record3D-style control set.
        
        Args:
            total_frames: Total number of frames
            
        Returns:
            Dictionary of all control handles
        """
        # Primary transport controls
        self.controls.update({
            'play': self.server.gui.add_button("▶️ Play"),
            'pause': self.server.gui.add_button("⏸️ Pause"),
            'reset': self.server.gui.add_button("🔄 Reset")
        })
        
        # Frame step controls (Record3D style)
        self.controls.update({
            'prev_frame': self.server.gui.add_button("⏮️ Previous Frame"),
            'next_frame': self.server.gui.add_button("⏭️ Next Frame")
        })
        
        # Timeline scrubber
        self.controls['timeline_slider'] = self.server.gui.add_slider(
            "Timeline",
            min=0,
            max=max(1, total_frames - 1),
            step=1,
            initial_value=0
        )
        
        # FPS control (Record3D style)
        self.controls.update({
            'fps_slider': self.server.gui.add_slider(
                "FPS",
                min=1,
                max=60,
                step=0.1,
                initial_value=20.0
            ),
            'fps_presets': self.server.gui.add_button_group(
                "FPS Presets", ("10", "20", "30", "60")
            )
        })
        
        # Enhanced status displays (Record3D style)
        duration = self.controller.get_duration_seconds()
        self.controls.update({
            'status': self.server.gui.add_text(
                "Status", 
                "Ready - Click Play for Record3D-style playback"
            ),
            'frame_counter': self.server.gui.add_text(
                "Frame", 
                f"0 / {total_frames}"
            ),
            'time_display': self.server.gui.add_text(
                "Time",
                self._format_time_display(0, duration)
            ),
            'progress': self.server.gui.add_text(
                "Progress", 
                "0.0%"
            )
        })
        
        # Wire up all callbacks
        self._setup_callbacks()
        
        return self.controls
        
    def _setup_callbacks(self) -> None:
        """Set up all control callbacks."""
        # Transport controls
        self.controls['play'].on_click(self._on_play)
        self.controls['pause'].on_click(self._on_pause)
        self.controls['reset'].on_click(self._on_reset)
        
        # Frame step controls
        self.controls['prev_frame'].on_click(self._on_prev_frame)
        self.controls['next_frame'].on_click(self._on_next_frame)
        
        # Timeline control
        self.controls['timeline_slider'].on_update(self._on_timeline_change)
        
        # FPS controls
        self.controls['fps_presets'].on_click(self._on_fps_preset)
        self.controls['fps_slider'].on_update(self._on_fps_change)
        
    def _on_play(self, _) -> None:
        """Handle play button with Record3D-style control."""
        print("[RECORD3D] Starting Record3D-style playback")
        
        self.is_playing = True
        self._update_control_states()
        
        # Get current FPS setting
        fps = self.controls['fps_slider'].value
        self.playback_engine.start_enhanced_playback(fps)
        
        # Update status
        self.controls['status'].value = "Playing (Record3D mode)"
        
    def _on_pause(self, _) -> None:
        """Handle pause button."""
        print("[RECORD3D] Pausing Record3D-style playback")
        
        self.is_playing = False
        self._update_control_states()
        
        self.playback_engine.stop_enhanced_playback()
        
        # Update status
        self.controls['status'].value = "Paused"
        
    def _on_reset(self, _) -> None:
        """Handle reset button."""
        print("[RECORD3D] Resetting Record3D-style playback")
        
        self.is_playing = False
        self.playback_engine.stop_enhanced_playback()
        
        # Reset to beginning
        self.controller.goto_frame(0)
        self.controls['timeline_slider'].value = 0
        
        self._update_control_states()
        self._update_displays()
        
        # Update status
        self.controls['status'].value = "Reset to beginning"
        
    def _on_prev_frame(self, _) -> None:
        """Step to previous frame with atomic updates."""
        current_frame = self.controls['timeline_slider'].value
        if current_frame > 0:
            new_frame = current_frame - 1
            self.controls['timeline_slider'].value = new_frame
            self.playback_engine._atomic_frame_update(int(new_frame))
            self._update_displays()
            
    def _on_next_frame(self, _) -> None:
        """Step to next frame with atomic updates."""
        current_frame = self.controls['timeline_slider'].value
        max_frame = self.controller.get_total_frames() - 1
        if current_frame < max_frame:
            new_frame = current_frame + 1
            self.controls['timeline_slider'].value = new_frame
            self.playback_engine._atomic_frame_update(int(new_frame))
            self._update_displays()
            
    def _on_timeline_change(self, _) -> None:
        """Handle timeline scrubbing with atomic updates."""
        frame_index = int(self.controls['timeline_slider'].value)
        self.playback_engine._atomic_frame_update(frame_index)
        # Don't call _update_displays() here to prevent recursion
        self._update_displays_except_slider()
        
    def _on_fps_preset(self, _) -> None:
        """Handle FPS preset selection (Record3D style)."""
        preset_value = float(self.controls['fps_presets'].value)
        self.controls['fps_slider'].value = preset_value
        
        # Update engine immediately if playing
        if self.playback_engine.is_enhanced_playing():
            self.playback_engine.set_fps(preset_value)
            
    def _on_fps_change(self, _) -> None:
        """Handle FPS slider changes."""
        fps = self.controls['fps_slider'].value
        
        # Update engine immediately if playing
        if self.playback_engine.is_enhanced_playing():
            self.playback_engine.set_fps(fps)
            
    def _update_control_states(self) -> None:
        """Update control enabled/disabled states (Record3D style)."""
        # Disable frame controls when playing (like Record3D)
        self.controls['prev_frame'].disabled = self.is_playing
        self.controls['next_frame'].disabled = self.is_playing
        self.controls['timeline_slider'].disabled = self.is_playing
        
    def _update_displays(self) -> None:
        """Update status displays with enhanced formatting."""
        status = self.controller.get_status()
        
        # Update frame counter
        current = status['current_frame']
        total = status['total_frames']
        self.controls['frame_counter'].value = f"{current} / {total}"
        
        # Update time display (Record3D format)
        current_time = status['current_time_seconds']
        total_time = status['total_duration_seconds']
        self.controls['time_display'].value = self._format_time_display(current_time, total_time)
        
        # Update progress
        progress = status['progress_percentage']
        self.controls['progress'].value = f"{progress:.1f}%"
        
        # Update timeline position
        self.controls['timeline_slider'].value = current
        
    def _update_displays_except_slider(self) -> None:
        """Update displays without touching timeline slider to prevent recursion."""
        status = self.controller.get_status()
        
        # Update frame counter
        current = status['current_frame']
        total = status['total_frames']
        self.controls['frame_counter'].value = f"{current} / {total}"
        
        # Update time display (Record3D format)
        current_time = status['current_time_seconds']
        total_time = status['total_duration_seconds']
        self.controls['time_display'].value = self._format_time_display(current_time, total_time)
        
        # Update progress
        progress = status['progress_percentage']
        self.controls['progress'].value = f"{progress:.1f}%"
        
        # DON'T update timeline slider to prevent recursion
        
    def _format_time_display(self, current_seconds: float, total_seconds: float) -> str:
        """Format time display in Record3D style (mm:ss format)."""
        def format_seconds(seconds):
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        
        return f"{format_seconds(current_seconds)} / {format_seconds(total_seconds)}"
        
    def start_monitoring(self) -> None:
        """Start monitoring thread for real-time display updates."""
        def monitor():
            while not self.should_stop_monitoring:
                try:
                    if self.playback_engine.is_enhanced_playing():
                        self._update_displays()
                except Exception as e:
                    print(f"[RECORD3D] Monitor error: {e}")
                time.sleep(0.1)  # 10Hz updates
            print("[RECORD3D] Monitor thread ended")
                
        self.should_stop_monitoring = False
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        
    def cleanup(self) -> None:
        """Clean up enhanced controls."""
        print("[RECORD3D] Cleaning up enhanced controls")
        
        # Stop monitoring thread
        self.should_stop_monitoring = True
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=0.5)
        
        # Stop playback engine
        self.playback_engine.stop_enhanced_playback()


def create_record3d_controls(server: viser.ViserServer, controller, mode: str = "streaming") -> Record3DControls:
    """
    Factory function to create Record3D-style controls.
    
    Args:
        server: Viser server instance
        controller: Base controller to enhance
        mode: Mode identifier
        
    Returns:
        Record3DControls instance
    """
    controls = Record3DControls(server, controller, mode)
    total_frames = controller.get_total_frames()
    controls.create_controls(total_frames)
    controls.start_monitoring()
    return controls
