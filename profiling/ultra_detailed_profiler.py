"""
Ultra-Detailed Profiler - Profile Every Single Step in update_cfg()

This profiler instruments the ViserUrdf.update_cfg() method to measure
every single operation inside the 3.7ms bottleneck:

1. yourdfpy._urdf.update_cfg() - Internal forward kinematics
2. Each get_transform() call - Per-joint transforms
3. Each SO3.from_matrix() call - Rotation conversions  
4. Each frame_handle update - Viser scene updates
5. 3D rendering preparation - Currently unmeasured!

Usage:
    python profiling/ultra_detailed_profiler.py
"""

import sys
import os
import time
import threading
import statistics
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import numpy as np

# Add necessary paths
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "backends" / "viser"))
sys.path.append(str(project_root / "backends" / "viser" / "replay"))

@dataclass
class UltraDetailedTimings:
    """Ultra-detailed timing measurements for each micro-operation"""
    # Main ViserUrdf.update_cfg() stages
    yourdfpy_update_cfg: List[float] = field(default_factory=list)
    joint_loop_total: List[float] = field(default_factory=list)
    
    # Per-joint operations (summed across all joints)
    get_transform_calls: List[float] = field(default_factory=list)
    so3_from_matrix_calls: List[float] = field(default_factory=list)
    frame_wxyz_updates: List[float] = field(default_factory=list)
    frame_position_updates: List[float] = field(default_factory=list)
    
    # Individual joint operation collections
    per_joint_get_transform: List[List[float]] = field(default_factory=list)
    per_joint_so3_matrix: List[List[float]] = field(default_factory=list)
    per_joint_frame_wxyz: List[List[float]] = field(default_factory=list)
    per_joint_frame_position: List[List[float]] = field(default_factory=list)
    
    # Total update_cfg time
    total_update_cfg: List[float] = field(default_factory=list)
    joint_counts: List[int] = field(default_factory=list)  # Number of joints per update

class UltraDetailedProfiler:
    """
    Profiles every single micro-operation inside ViserUrdf.update_cfg()
    """
    
    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.timings = UltraDetailedTimings()
        self.sample_count = 0
        self.is_profiling = False
        
    def start_profiling(self):
        """Start ultra-detailed profiling"""
        self.is_profiling = True
        print(f"[ULTRA-DETAILED] 🔬 Started ultra-detailed profiling ({self.max_samples} samples)")
        print(f"[ULTRA-DETAILED] Profiling every single operation inside update_cfg()")
        
    def stop_profiling(self):
        """Stop profiling and generate ultra-detailed report"""
        self.is_profiling = False
        self._generate_ultra_detailed_report()
        
    def profile_viser_urdf_update_cfg(self, viser_urdf, configuration: np.ndarray):
        """Profile the ViserUrdf.update_cfg() method with micro-operation timing"""
        if not self.is_profiling or self.sample_count >= self.max_samples:
            # Just execute without profiling
            viser_urdf.original_update_cfg(configuration)
            return
            
        update_cfg_start = time.perf_counter()
        
        # Stage 1: yourdfpy internal update
        yourdfpy_start = time.perf_counter()
        viser_urdf._urdf.update_cfg(configuration)
        yourdfpy_end = time.perf_counter()
        yourdfpy_time = (yourdfpy_end - yourdfpy_start) * 1000
        self.timings.yourdfpy_update_cfg.append(yourdfpy_time)
        
        # Stage 2: Joint loop with detailed per-joint timing
        joint_loop_start = time.perf_counter()
        
        # Per-joint timing collections for this update
        joint_get_transform_times = []
        joint_so3_matrix_times = []
        joint_frame_wxyz_times = []
        joint_frame_position_times = []
        
        # Time each joint operation individually
        for joint, frame_handle in zip(viser_urdf._joint_map_values, viser_urdf._joint_frames):
            assert isinstance(joint, __import__('yourdfpy').Joint)
            
            # Time get_transform() call
            get_transform_start = time.perf_counter()
            T_parent_child = viser_urdf._urdf.get_transform(
                joint.child, joint.parent, collision_geometry=not viser_urdf._load_meshes
            )
            get_transform_end = time.perf_counter()
            get_transform_time = (get_transform_end - get_transform_start) * 1000
            joint_get_transform_times.append(get_transform_time)
            
            # Time SO3.from_matrix() call
            so3_start = time.perf_counter()
            from viser import transforms as tf
            rotation_quat = tf.SO3.from_matrix(T_parent_child[:3, :3]).wxyz
            so3_end = time.perf_counter()
            so3_time = (so3_end - so3_start) * 1000
            joint_so3_matrix_times.append(so3_time)
            
            # Time frame_handle.wxyz update
            frame_wxyz_start = time.perf_counter()
            frame_handle.wxyz = rotation_quat
            frame_wxyz_end = time.perf_counter()
            frame_wxyz_time = (frame_wxyz_end - frame_wxyz_start) * 1000
            joint_frame_wxyz_times.append(frame_wxyz_time)
            
            # Time frame_handle.position update
            frame_position_start = time.perf_counter()
            frame_handle.position = T_parent_child[:3, 3] * viser_urdf._scale
            frame_position_end = time.perf_counter()
            frame_position_time = (frame_position_end - frame_position_start) * 1000
            joint_frame_position_times.append(frame_position_time)
        
        joint_loop_end = time.perf_counter()
        joint_loop_time = (joint_loop_end - joint_loop_start) * 1000
        
        # Record joint loop timing
        self.timings.joint_loop_total.append(joint_loop_time)
        
        # Record summed per-joint operation times
        self.timings.get_transform_calls.append(sum(joint_get_transform_times))
        self.timings.so3_from_matrix_calls.append(sum(joint_so3_matrix_times))
        self.timings.frame_wxyz_updates.append(sum(joint_frame_wxyz_times))
        self.timings.frame_position_updates.append(sum(joint_frame_position_times))
        
        # Store individual joint timings
        self.timings.per_joint_get_transform.append(joint_get_transform_times)
        self.timings.per_joint_so3_matrix.append(joint_so3_matrix_times)
        self.timings.per_joint_frame_wxyz.append(joint_frame_wxyz_times)
        self.timings.per_joint_frame_position.append(joint_frame_position_times)
        
        # Record total update_cfg time
        update_cfg_end = time.perf_counter()
        total_time = (update_cfg_end - update_cfg_start) * 1000
        self.timings.total_update_cfg.append(total_time)
        self.timings.joint_counts.append(len(viser_urdf._joint_map_values))
        
        self.sample_count += 1
        
        # Progress reporting
        if self.sample_count % 25 == 0:
            print(f"[ULTRA-DETAILED] Progress: {self.sample_count}/{self.max_samples}")
            
    def _generate_ultra_detailed_report(self):
        """Generate ultra-detailed performance report"""
        print(f"\n{'='*120}")
        print(f"🔬 ULTRA-DETAILED PROFILING RESULTS - EVERY SINGLE OPERATION")
        print(f"{'='*120}")
        
        if not self.timings.total_update_cfg:
            print("❌ No timing data collected")
            return
            
        # Calculate averages
        avg_total = statistics.mean(self.timings.total_update_cfg)
        avg_joint_count = statistics.mean(self.timings.joint_counts)
        
        print(f"\n📋 SUMMARY:")
        print(f"  Samples: {self.sample_count}")
        print(f"  Avg total update_cfg time: {avg_total:.3f}ms")
        print(f"  Avg joint count: {avg_joint_count:.1f}")
        print(f"  500Hz budget: {(avg_total/2.0)*100:.1f}%")
        
        # Main stage breakdown
        print(f"\n📊 MAIN STAGE BREAKDOWN:")
        print(f"{'Stage':<25} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'% of Total':<10} {'Status'}")
        print("-" * 100)
        
        stages = [
            ("yourdfpy update_cfg", self.timings.yourdfpy_update_cfg),
            ("Joint loop total", self.timings.joint_loop_total),
            ("TOTAL update_cfg", self.timings.total_update_cfg)
        ]
        
        for stage_name, times in stages:
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                percent = (avg_time / avg_total) * 100
                
                if percent > 50:
                    status = "🔥 MAJOR"
                elif percent > 20:
                    status = "⚠️  SIGNIFICANT"
                else:
                    status = "✅ MODERATE"
                
                print(f"{stage_name:<25} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {percent:<10.1f} {status}")
        
        # Per-joint operation breakdown
        print(f"\n🔬 PER-JOINT OPERATION BREAKDOWN (summed across all joints):")
        print(f"{'Operation':<25} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'% of Total':<10} {'Avg per Joint':<12}")
        print("-" * 115)
        
        joint_operations = [
            ("get_transform() calls", self.timings.get_transform_calls),
            ("SO3.from_matrix() calls", self.timings.so3_from_matrix_calls),
            ("frame.wxyz updates", self.timings.frame_wxyz_updates),
            ("frame.position updates", self.timings.frame_position_updates)
        ]
        
        for op_name, times in joint_operations:
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                percent = (avg_time / avg_total) * 100
                avg_per_joint = avg_time / avg_joint_count
                
                print(f"{op_name:<25} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {percent:<10.1f} {avg_per_joint:<12.4f}")
        
        # Individual joint timing analysis
        if self.timings.per_joint_get_transform:
            print(f"\n🎯 INDIVIDUAL JOINT TIMING ANALYSIS:")
            print(f"Operation: get_transform() - Most expensive per-joint operation")
            
            # Analyze first sample to show per-joint variation
            sample_times = self.timings.per_joint_get_transform[0]
            if sample_times:
                print(f"  Sample joint times: {[f'{t:.4f}' for t in sample_times[:5]]}ms (showing first 5)")
                print(f"  Min joint time: {min(sample_times):.4f}ms")
                print(f"  Max joint time: {max(sample_times):.4f}ms")
                print(f"  Joint time variation: {(max(sample_times) - min(sample_times)):.4f}ms")
        
        # Bottleneck identification
        self._identify_ultra_detailed_bottleneck()
        
    def _identify_ultra_detailed_bottleneck(self):
        """Identify the micro-operation bottleneck"""
        print(f"\n🎯 ULTRA-DETAILED BOTTLENECK ANALYSIS:")
        
        if not self.timings.total_update_cfg:
            return
            
        avg_total = statistics.mean(self.timings.total_update_cfg)
        
        # Compare main stages
        stage_averages = []
        if self.timings.yourdfpy_update_cfg:
            stage_averages.append(("yourdfpy update_cfg", statistics.mean(self.timings.yourdfpy_update_cfg)))
        if self.timings.joint_loop_total:
            stage_averages.append(("Joint loop", statistics.mean(self.timings.joint_loop_total)))
            
        if stage_averages:
            bottleneck_stage, bottleneck_time = max(stage_averages, key=lambda x: x[1])
            bottleneck_percent = (bottleneck_time / avg_total) * 100
            
            print(f"  🔥 PRIMARY STAGE: {bottleneck_stage}")
            print(f"  Time: {bottleneck_time:.3f}ms ({bottleneck_percent:.1f}% of total)")
            
            # If joint loop is the bottleneck, analyze per-joint operations
            if "Joint loop" in bottleneck_stage:
                print(f"\n  🔬 JOINT LOOP BREAKDOWN:")
                joint_op_averages = []
                if self.timings.get_transform_calls:
                    joint_op_averages.append(("get_transform() calls", statistics.mean(self.timings.get_transform_calls)))
                if self.timings.so3_from_matrix_calls:
                    joint_op_averages.append(("SO3.from_matrix() calls", statistics.mean(self.timings.so3_from_matrix_calls)))
                if self.timings.frame_wxyz_updates:
                    joint_op_averages.append(("frame.wxyz updates", statistics.mean(self.timings.frame_wxyz_updates)))
                if self.timings.frame_position_updates:
                    joint_op_averages.append(("frame.position updates", statistics.mean(self.timings.frame_position_updates)))
                
                if joint_op_averages:
                    joint_bottleneck, joint_bottleneck_time = max(joint_op_averages, key=lambda x: x[1])
                    joint_bottleneck_percent = (joint_bottleneck_time / avg_total) * 100
                    
                    print(f"    🔥 JOINT OPERATION BOTTLENECK: {joint_bottleneck}")
                    print(f"    Time: {joint_bottleneck_time:.3f}ms ({joint_bottleneck_percent:.1f}% of total)")
                    
                    # Optimization recommendations
                    print(f"\n  💡 OPTIMIZATION RECOMMENDATIONS:")
                    if "get_transform" in joint_bottleneck:
                        print(f"    - Cache transform calculations for unchanged joints")
                        print(f"    - Optimize yourdfpy forward kinematics")
                        print(f"    - Consider selective joint updates")
                    elif "SO3.from_matrix" in joint_bottleneck:
                        print(f"    - Cache rotation matrix conversions")
                        print(f"    - Use pre-computed quaternions where possible")
                    elif "frame" in joint_bottleneck:
                        print(f"    - Batch frame updates")
                        print(f"    - Disable coordinate frames during high-speed replay")
                        print(f"    - Consider frame update rate limiting")


def run_ultra_detailed_profiling():
    """Run ultra-detailed profiling with ViserUrdf instrumentation"""
    try:
        # Import updated modules
        sys.path.append(str(project_root / "backends" / "viser" / "urdf"))
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        print("🔬 ULTRA-DETAILED PROFILING - EVERY SINGLE OPERATION")
        print("="*60)
        
        # Create server
        server = viser.ViserServer(host="localhost", port=8084, serve_static=False)
        
        # Create URDF manager
        urdf_manager = SmartUrdfManager(server)
        urdf_configs = discover_workcell_urdfs("workcell_beta")
        urdf_configs = deduplicate_urdfs(urdf_configs)
        
        for urdf_path, urdf_name in urdf_configs:
            urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
        
        print(f"System loaded: {urdf_manager.get_total_meaningful_dof()} joints")
        
        # Create replay controller at full rate
        data_file = str(project_root / "data" / "robot_status1.data.json")
        replay_controller = SimpleReplayController(data_file, downsample_factor=1)
        
        # Create ultra-detailed profiler
        profiler = UltraDetailedProfiler(max_samples=50)  # Fewer samples for detailed analysis
        
        # Patch each ViserUrdf instance to use profiled version
        for config in urdf_manager.urdf_configs:
            viser_urdf = config["viser_urdf"]
            
            # Store original method
            viser_urdf.original_update_cfg = viser_urdf.update_cfg
            
            # Replace with profiled version
            def profiled_update_cfg(configuration: np.ndarray, *, _profiler=profiler, _viser_urdf=viser_urdf):
                _profiler.profile_viser_urdf_update_cfg(_viser_urdf, configuration)
            
            viser_urdf.update_cfg = profiled_update_cfg
        
        # Override urdf_manager update method to trigger profiling
        original_update = urdf_manager.update_all_configurations
        
        def profiled_update_all(joint_values):
            # Call original method which will trigger our profiled update_cfg methods
            original_update(joint_values)
        
        urdf_manager.update_all_configurations = profiled_update_all
        
        # Override replay controller's update method
        original_replay_update = replay_controller._update_visualization
        
        def profiled_replay_update():
            entry = replay_controller.get_current_entry()
            if entry:
                # Extract joint values using existing pipeline
                joint_configs = {}
                for urdf_name in replay_controller.mapper.get_all_urdf_names():
                    joint_config = replay_controller.mapper.create_joint_config_for_urdf(urdf_name, entry)
                    if joint_config:
                        joint_configs[urdf_name] = joint_config
                
                # Convert to full config array
                full_config = np.zeros(len(urdf_manager.filtered_joint_names))
                for urdf_name, urdf_joint_config in joint_configs.items():
                    if not urdf_joint_config:
                        continue
                    for i, joint_name in enumerate(urdf_manager.filtered_joint_names):
                        if joint_name.startswith(f"{urdf_name}::"):
                            actual_joint = joint_name.split("::", 1)[1]
                            if actual_joint in urdf_joint_config:
                                full_config[i] = urdf_joint_config[actual_joint]
                
                # Call profiled update
                urdf_manager.update_all_configurations(full_config)
        
        replay_controller._update_visualization = profiled_replay_update
        
        # Run profiling
        profiler.start_profiling()
        replay_controller.play()
        
        # Wait for completion
        while profiler.is_profiling and profiler.sample_count < profiler.max_samples:
            time.sleep(0.1)
            
            # Restart replay if needed
            if not replay_controller.is_playing and profiler.is_profiling:
                replay_controller.stop()
                replay_controller.play()
        
        replay_controller.pause()
        profiler.stop_profiling()
        
        print("\n✅ ULTRA-DETAILED PROFILING COMPLETE")
        print("Now you know exactly where every microsecond is spent!")
        
    except Exception as e:
        print(f"❌ Ultra-detailed profiling failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_ultra_detailed_profiling()
