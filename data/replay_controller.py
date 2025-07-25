"""
Simple Replay Controller for Robot Demo
Manages timeline, play/pause, and sequence ID navigation
"""

import time
import threading
from typing import Dict, List, Optional, Callable
from robot_data_parser import RobotDataParser
from joint_mapper import JointMapper

class SimpleReplayController:
    """Simple replay controller for demo purposes"""
    
    def __init__(self, json_file: str = "data/robot_status_beta.data.json"):
        self.parser = RobotDataParser(json_file)
        self.mapper = JointMapper()
        
        # Replay state
        self.current_index = 0
        self.is_playing = False
        self.playback_speed = 1.0
        self.update_callback = None
        
        # Threading
        self.play_thread = None
        self.stop_event = threading.Event()
        
        # Initialize data
        self.parser.load_data()
        self.parser.parse_data(downsample_factor=1)
        
        print(f"[REPLAY] Initialized with {len(self.parser.parsed_data)} entries")
        
    def set_update_callback(self, callback: Callable[[Dict], None]) -> None:
        """Set callback function that gets called with joint updates"""
        self.update_callback = callback
        
    def get_total_entries(self) -> int:
        """Get total number of entries in timeline"""
        return len(self.parser.parsed_data)
    
    def get_current_entry(self) -> Optional[Dict]:
        """Get current timeline entry"""
        if 0 <= self.current_index < len(self.parser.parsed_data):
            return self.parser.parsed_data[self.current_index]
        return None
    
    def get_current_sequence_id(self) -> Optional[int]:
        """Get current sequence ID"""
        entry = self.get_current_entry()
        return entry['sequence_id'] if entry else None
    
    def goto_sequence_id(self, sequence_id: int) -> bool:
        """Jump to specific sequence ID"""
        for i, entry in enumerate(self.parser.parsed_data):
            if entry['sequence_id'] == sequence_id:
                self.current_index = i
                self._update_visualization()
                print(f"[REPLAY] Jumped to sequence ID {sequence_id} (index {i})")
                return True
        
        print(f"[REPLAY] Sequence ID {sequence_id} not found")
        return False
    
    def goto_index(self, index: int) -> bool:
        """Jump to specific index"""
        if 0 <= index < len(self.parser.parsed_data):
            self.current_index = index
            self._update_visualization()
            entry = self.get_current_entry()
            seq_id = entry['sequence_id'] if entry else None
            print(f"[REPLAY] Jumped to index {index} (sequence ID {seq_id})")
            return True
        
        print(f"[REPLAY] Index {index} out of range")
        return False
    
    def play(self) -> None:
        """Start playback"""
        if self.is_playing:
            print("[REPLAY] Already playing")
            return
        
        self.is_playing = True
        self.stop_event.clear()
        
        # Start playback thread
        self.play_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.play_thread.start()
        
        print(f"[REPLAY] Started playback from index {self.current_index}")
    
    def pause(self) -> None:
        """Pause playback"""
        if not self.is_playing:
            print("[REPLAY] Not currently playing")
            return
        
        self.is_playing = False
        self.stop_event.set()
        
        if self.play_thread:
            self.play_thread.join(timeout=1.0)
        
        print(f"[REPLAY] Paused at index {self.current_index}")
    
    def stop(self) -> None:
        """Stop playback and reset to beginning"""
        self.pause()
        self.current_index = 0
        self._update_visualization()
        print("[REPLAY] Stopped and reset to beginning")
    
    def set_playback_speed(self, speed: float) -> None:
        """Set playback speed multiplier"""
        self.playback_speed = max(0.1, min(5.0, speed))  # Clamp between 0.1x and 5x
        print(f"[REPLAY] Playback speed set to {self.playback_speed:.1f}x")
    
    def _playback_loop(self) -> None:
        """Main playback loop (runs in separate thread)"""
        target_fps = 50  # Target 50 FPS for smooth playback
        frame_time = 1.0 / target_fps
        
        while self.is_playing and not self.stop_event.is_set():
            start_time = time.time()
            
            # Update current entry
            self._update_visualization()
            
            # Advance to next entry
            self.current_index += 1
            
            # Check if we reached the end
            if self.current_index >= len(self.parser.parsed_data):
                print("[REPLAY] Reached end of timeline - auto-resetting")
                self.is_playing = False
                self.current_index = 0  # Auto-reset to beginning
                self._update_visualization()  # Update visualization to show reset position
                break
            
            # Sleep to maintain target FPS (adjusted by playback speed)
            elapsed = time.time() - start_time
            sleep_time = (frame_time / self.playback_speed) - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _update_visualization(self) -> None:
        """Update visualization with current data"""
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
    
    def get_timeline_info(self) -> Dict:
        """Get timeline information"""
        info = self.parser.get_timeline_info()
        info.update({
            'current_index': self.current_index,
            'current_sequence_id': self.get_current_sequence_id(),
            'is_playing': self.is_playing,
            'playback_speed': self.playback_speed
        })
        return info
    
    def print_status(self) -> None:
        """Print current status"""
        info = self.get_timeline_info()
        status = "PLAYING" if self.is_playing else "PAUSED"
        
        print(f"\n[REPLAY] === STATUS ===")
        print(f"Status: {status}")
        print(f"Index: {info['current_index']}/{info['total_entries']}")
        print(f"Sequence ID: {info['current_sequence_id']}")
        print(f"Speed: {info['playback_speed']:.1f}x")
        print(f"Duration: {info['duration_seconds']:.1f}s")


def test_replay_controller():
    """Test the replay controller"""
    print("=== TESTING REPLAY CONTROLLER ===")
    
    # Create controller
    controller = SimpleReplayController()
    
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
    print("\n[REPLAY] Test completed successfully!")


if __name__ == "__main__":
    test_replay_controller()
