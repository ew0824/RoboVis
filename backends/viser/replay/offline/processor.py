"""
Offline Processor - Phase 1 of Offline Replay System

This module handles the heavy lifting of pre-processing ALL robot data upfront.
It pays the computational cost once during initialization to enable lag-free
playback with zero parsing/mapping latency during replay.

The processor:
1. Loads and parses all robot data from JSON files
2. Pre-computes joint configurations for every single frame
3. Maps robot data to URDF joint indices 
4. Stores everything in high-performance NumPy arrays
5. Provides statistics about memory usage and processing time

Usage:
    processor = OfflineProcessor(data_file, urdf_manager)
    stats = processor.process_all_data(downsample=5)
    
    # After processing, data is instantly accessible:
    frame_config = processor.frame_configs[frame_index]  # Zero latency!
"""

import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..parser import DataParser  
from ..joint_mapper import JointMapper


class OfflineProcessor:
    """
    Phase 1: Pre-processes ALL robot data for lag-free replay.
    
    This class performs intensive computation upfront to eliminate all
    processing latency during playback. It converts robot data into
    pre-computed NumPy arrays that can be accessed instantly.
    
    Attributes:
        data_file: Path to robot data JSON file
        urdf_manager: SmartUrdfManager for joint configuration
        parser: DataParser instance for robot data parsing
        mapper: JointMapper for robot-to-URDF joint mapping
        frame_configs: Pre-computed joint configurations [frame_idx] -> config
        frame_timestamps: Frame timestamps [frame_idx] -> timestamp_ns  
        frame_sequence_ids: Frame sequence IDs [frame_idx] -> sequence_id
        processing_stats: Dictionary with processing statistics
    """
    
    def __init__(self, data_file: str, urdf_manager):
        """
        Initialize the offline processor.
        
        Args:
            data_file: Path to robot data JSON file  
            urdf_manager: SmartUrdfManager instance for joint mapping
        """
        self.data_file = data_file
        self.urdf_manager = urdf_manager
        
        # Initialize shared components
        self.parser = DataParser(self._resolve_data_file(data_file))
        self.mapper = JointMapper()
        
        # Pre-computed arrays (the magic!)
        self.frame_configs = None        # [frame_idx] -> full_joint_config
        self.frame_timestamps = None     # [frame_idx] -> timestamp_ns
        self.frame_sequence_ids = None   # [frame_idx] -> sequence_id
        
        # Processing statistics
        self.processing_stats = {}
        self.is_processed = False
        
    def _resolve_data_file(self, data_file: str) -> str:
        """Resolve data file path relative to project root."""
        if data_file.startswith('/'):
            return data_file
            
        # Find project root by looking for .gitignore file
        current_dir = Path.cwd()
        project_root = current_dir
        while project_root.parent != project_root:
            if (project_root / '.gitignore').exists():
                break
            project_root = project_root.parent
            
        return str(project_root / data_file)
        
    def process_all_data(self, downsample: int = 1) -> Dict:
        """
        Phase 1: Pre-compute EVERYTHING upfront for lag-free playback.
        
        Args:
            downsample: Downsampling factor for data reduction
            
        Returns:
            Dictionary with processing statistics
            
        This method performs intensive computation upfront:
        - Parses all robot data from JSON
        - Pre-computes joint configurations for every frame  
        - Maps robot joints to URDF joint indices
        - Stores everything in NumPy arrays for maximum speed
        
        The upfront cost enables zero-latency playback later.
        """
        print(f"🔄 [OFFLINE] Phase 1: Processing all data (downsample={downsample}x)")
        print("⏳ This may take 30+ seconds but enables lag-free playback...")
        
        start_time = time.time()
        
        # Step 1: Load and parse raw robot data
        print("📖 [OFFLINE] Step 1: Loading raw robot data...")
        self.parser.load_data()
        self.parser.parse_data(downsample_factor=downsample)
        
        total_frames = len(self.parser.parsed_data)
        if total_frames == 0:
            raise ValueError("No robot data found - check data file path")
            
        print(f"🔢 [OFFLINE] Processing {total_frames} frames...")
        
        # Step 2: Pre-allocate arrays for maximum performance
        num_joints = len(self.urdf_manager.filtered_joint_names)
        if num_joints == 0:
            raise ValueError("No joints found in URDF manager")
            
        print(f"🎯 [OFFLINE] Pre-allocating arrays for {num_joints} joints...")
        
        # Pre-allocate NumPy arrays
        self.frame_configs = np.zeros((total_frames, num_joints), dtype=np.float32)
        self.frame_timestamps = np.zeros(total_frames, dtype=np.int64)
        self.frame_sequence_ids = np.zeros(total_frames, dtype=np.int32)
        
        # Step 3: Pre-compute EVERY frame (the heavy lifting!)
        print("⚡ [OFFLINE] Step 3: Pre-computing all joint configurations...")
        
        # Track progress
        last_progress = 0
        progress_interval = max(1, total_frames // 20)  # Show progress every 5%
        
        for i, entry in enumerate(self.parser.parsed_data):
            # Show progress
            if i % progress_interval == 0 or i == total_frames - 1:
                progress = (i / total_frames) * 100
                if progress >= last_progress + 5:  # Update every 5%
                    print(f"⚡ [OFFLINE] Processing: {progress:.0f}% ({i+1}/{total_frames})")
                    last_progress = progress
            
            # Pre-compute joint configuration for this frame
            frame_config = np.zeros(num_joints, dtype=np.float32)
            
            # Process each URDF's joints
            for urdf_name in self.mapper.get_all_urdf_names():
                joint_config = self.mapper.create_joint_config_for_urdf(urdf_name, entry)
                
                if joint_config:
                    # Map robot joints to global URDF joint indices
                    for j, joint_name in enumerate(self.urdf_manager.filtered_joint_names):
                        if joint_name.startswith(f"{urdf_name}::"):
                            actual_joint = joint_name.split("::", 1)[1]
                            if actual_joint in joint_config:
                                frame_config[j] = joint_config[actual_joint]
            
            # Store pre-computed data
            self.frame_configs[i] = frame_config
            self.frame_timestamps[i] = entry['timestamp_ns']
            self.frame_sequence_ids[i] = entry['sequence_id']
        
        processing_time = time.time() - start_time
        
        # Calculate statistics
        memory_usage_mb = self.frame_configs.nbytes / (1024 * 1024)
        duration_seconds = (self.frame_timestamps[-1] - self.frame_timestamps[0]) / 1e9 if total_frames > 1 else 0
        effective_fps = total_frames / duration_seconds if duration_seconds > 0 else 0
        
        self.processing_stats = {
            'total_frames': total_frames,
            'num_joints': num_joints,
            'duration_seconds': duration_seconds,
            'processing_time': processing_time,
            'memory_usage_mb': memory_usage_mb,
            'downsample_factor': downsample,
            'effective_fps': effective_fps,
            'original_data_points': len(self.parser.raw_data) if hasattr(self.parser, 'raw_data') else total_frames * downsample
        }
        
        self.is_processed = True
        
        print(f"✅ [OFFLINE] Phase 1 Complete!")
        print(f"📊 Processed {total_frames} frames in {processing_time:.1f}s")
        print(f"🎯 Ready for lag-free playback ({memory_usage_mb:.1f}MB memory)")
        print(f"⚡ Effective rate: {effective_fps:.1f} fps over {duration_seconds:.1f}s duration")
        
        return self.processing_stats
        
    def get_frame_config(self, frame_index: int) -> Optional[np.ndarray]:
        """
        Get pre-computed joint configuration for a frame - ZERO LATENCY!
        
        Args:
            frame_index: Frame index to retrieve
            
        Returns:
            Pre-computed joint configuration array, or None if invalid index
            
        This method provides instant access to pre-computed data with
        zero parsing or mapping overhead - just array indexing.
        """
        if not self.is_processed:
            print("[OFFLINE] Warning: Data not processed yet - call process_all_data() first")
            return None
            
        if 0 <= frame_index < len(self.frame_configs):
            return self.frame_configs[frame_index]
        return None
        
    def get_frame_timestamp(self, frame_index: int) -> Optional[int]:
        """Get timestamp for a frame."""
        if not self.is_processed or frame_index < 0 or frame_index >= len(self.frame_timestamps):
            return None
        return self.frame_timestamps[frame_index]
        
    def get_frame_sequence_id(self, frame_index: int) -> Optional[int]:
        """Get sequence ID for a frame."""
        if not self.is_processed or frame_index < 0 or frame_index >= len(self.frame_sequence_ids):
            return None
        return self.frame_sequence_ids[frame_index]
        
    def get_total_frames(self) -> int:
        """Get total number of processed frames."""
        return len(self.frame_configs) if self.frame_configs is not None else 0
        
    def get_duration_seconds(self) -> float:
        """Get total duration in seconds."""
        return self.processing_stats.get('duration_seconds', 0.0) if self.is_processed else 0.0
        
    def find_frame_by_sequence_id(self, sequence_id: int) -> Optional[int]:
        """
        Find frame index by sequence ID - optimized with NumPy.
        
        Args:
            sequence_id: Sequence ID to find
            
        Returns:
            Frame index if found, None otherwise
        """
        if not self.is_processed:
            return None
            
        # Use NumPy's optimized search
        matches = np.where(self.frame_sequence_ids == sequence_id)[0]
        return int(matches[0]) if len(matches) > 0 else None
        
    def get_memory_info(self) -> Dict:
        """Get detailed memory usage information."""
        if not self.is_processed:
            return {}
            
        return {
            'frame_configs_mb': self.frame_configs.nbytes / (1024 * 1024),
            'frame_timestamps_mb': self.frame_timestamps.nbytes / (1024 * 1024),  
            'frame_sequence_ids_mb': self.frame_sequence_ids.nbytes / (1024 * 1024),
            'total_memory_mb': self.processing_stats['memory_usage_mb'],
            'memory_per_frame_kb': (self.processing_stats['memory_usage_mb'] * 1024) / self.get_total_frames() if self.get_total_frames() > 0 else 0
        }
        
    def print_stats(self):
        """Print detailed processing statistics."""
        if not self.is_processed:
            print("[OFFLINE] No processing statistics available")
            return
            
        stats = self.processing_stats
        memory = self.get_memory_info()
        
        print("\n" + "="*60)
        print("📊 OFFLINE PROCESSING STATISTICS")
        print("="*60)
        print(f"📁 Data file: {self.data_file}")
        print(f"🔢 Total frames: {stats['total_frames']:,}")
        print(f"🎯 Joints: {stats['num_joints']}")
        print(f"📉 Downsample factor: {stats['downsample_factor']}x")
        print(f"⏱️  Processing time: {stats['processing_time']:.1f}s")
        print(f"🎬 Duration: {stats['duration_seconds']:.1f}s")
        print(f"📊 Effective FPS: {stats['effective_fps']:.1f}")
        print(f"💾 Memory usage: {stats['memory_usage_mb']:.1f}MB")
        print(f"🗂️  Memory per frame: {memory['memory_per_frame_kb']:.2f}KB")
        print(f"📈 Original data points: {stats['original_data_points']:,}")
        print("="*60)


def test_offline_processor():
    """Test the offline processor independently."""
    print("=== TESTING OFFLINE PROCESSOR ===")
    
    # This would need a mock urdf_manager for testing
    # In actual usage, urdf_manager comes from the main system
    print("⚠️  This test requires integration with URDF manager")
    print("   Use through OfflineManager for full functionality")


if __name__ == "__main__":
    test_offline_processor()
