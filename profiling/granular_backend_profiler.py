"""
Granular Backend Profiler - Break Down the 6.122ms Bottleneck

This profiler instruments the internals of urdf_manager.update_all_configurations()
to identify exactly where the 6.122ms per update is being spent:

1. Joint Processing (grouping, array creation)
2. Viser URDF Updates (viser_urdf.update_cfg calls)
3. Coordinate Frame Updates (frame position updates)
4. System Overhead (loops, memory allocation)

Usage:
    python profiling/granular_backend_profiler.py
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
class GranularTimings:
    """Detailed timing measurements for each sub-operation"""
    joint_processing: List[float] = field(default_factory=list)
    viser_urdf_updates: List[float] = field(default_factory=list)
    coordinate_frame_updates: List[float] = field(default_factory=list)
    system_overhead: List[float] = field(default_factory=list)
    total_update: List[float] = field(default_factory=list)
    
    # Per-URDF breakdown
    individual_urdf_updates: Dict[str, List[float]] = field(default_factory=dict)
    individual_frame_updates: Dict[str, List[float]] = field(default_factory=dict)

class GranularBackendProfiler:
    """
    Profiles the internal components of update_all_configurations()
    """
    
    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.timings = GranularTimings()
        self.sample_count = 0
        self.is_profiling = False
        
    def start_profiling(self):
        """Start granular profiling"""
        self.is_profiling = True
        print(f"[GRANULAR] 🔬 Started granular backend profiling ({self.max_samples} samples)")
        
    def stop_profiling(self):
        """Stop profiling and generate detailed report"""
        self.is_profiling = False
        self._generate_granular_report()
        
    def profile_update_all_configurations(self, urdf_manager, joint_values: np.ndarray):
        """Profile the complete update_all_configurations method with internal timing"""
        if not self.is_profiling or self.sample_count >= self.max_samples:
            # Just execute without profiling
            urdf_manager.original_update_all_configurations(joint_values)
            return
            
        total_start = time.perf_counter()
        
        # Validate input
        if len(joint_values) != len(urdf_manager.filtered_joint_names):
            print(f"[GRANULAR] Warning: Expected {len(urdf_manager.filtered_joint_names)} joint values, got {len(joint_values)}")
            return
            
        # Stage 1: Joint Processing
        processing_start = time.perf_counter()
        
        # Group joint values by URDF (from original method)
        urdf_joint_values = {}
        for i, joint_name in enumerate(urdf_manager.filtered_joint_names):
            urdf_name, actual_joint_name = joint_name.split("::", 1)
            if urdf_name not in urdf_joint_values:
                urdf_joint_values[urdf_name] = {}
            urdf_joint_values[urdf_name][actual_joint_name] = joint_values[i]
            
        processing_end = time.perf_counter()
        self.timings.joint_processing.append((processing_end - processing_start) * 1000)
        
        # Stage 2: Viser URDF Updates
        viser_updates_start = time.perf_counter()
        
        for config in urdf_manager.urdf_configs:
            urdf_name = config["name"]
            urdf = config["urdf"]
            viser_urdf = config["viser_urdf"]
            
            if urdf_name in urdf_joint_values:
                # Get ALL actuated joint limits for this URDF
                all_urdf_joints = viser_urdf.get_actuated_joint_limits()
                
                # Create configuration array in correct order
                cfg = []
                for joint_name in all_urdf_joints.keys():
                    if joint_name in urdf_joint_values[urdf_name]:
                        cfg.append(urdf_joint_values[urdf_name][joint_name])
                    else:
                        # Use default value for auxiliary joints
                        lower, upper = all_urdf_joints[joint_name]
                        if lower is not None and upper is not None:
                            default_val = (lower + upper) / 2.0
                        else:
                            default_val = 0.0
                        cfg.append(default_val)
                
                if cfg:  # Only update if there are actuated joints
                    # Time individual URDF update
                    urdf_update_start = time.perf_counter()
                    viser_urdf.update_cfg(np.array(cfg, dtype=np.float32))
                    urdf_update_end = time.perf_counter()
                    
                    # Record individual URDF timing
                    if urdf_name not in self.timings.individual_urdf_updates:
                        self.timings.individual_urdf_updates[urdf_name] = []
                    self.timings.individual_urdf_updates[urdf_name].append(
                        (urdf_update_end - urdf_update_start) * 1000
                    )
        
        viser_updates_end = time.perf_counter() 
        self.timings.viser_urdf_updates.append((viser_updates_end - viser_updates_start) * 1000)
        
        # Stage 3: Coordinate Frame Updates
        frames_start = time.perf_counter()
        
        for config in urdf_manager.urdf_configs:
            urdf_name = config["name"]
            urdf = config["urdf"]
            
            if urdf_name in urdf_joint_values and urdf_name in urdf_manager.coordinate_frames:
                # Time individual frame update
                frame_update_start = time.perf_counter()
                from urdf_manager import update_urdf_coordinate_frames
                update_urdf_coordinate_frames(urdf, urdf_manager.coordinate_frames[urdf_name], scale=1.0)
                frame_update_end = time.perf_counter()
                
                # Record individual frame timing
                if urdf_name not in self.timings.individual_frame_updates:
                    self.timings.individual_frame_updates[urdf_name] = []
                self.timings.individual_frame_updates[urdf_name].append(
                    (frame_update_end - frame_update_start) * 1000
                )
        
        frames_end = time.perf_counter()
        self.timings.coordinate_frame_updates.append((frames_end - frames_start) * 1000)
        
        # Total time and overhead calculation
        total_end = time.perf_counter()
        total_time = (total_end - total_start) * 1000
        
        # System overhead = total - (processing + viser + frames)
        measured_time = (
            self.timings.joint_processing[-1] + 
            self.timings.viser_urdf_updates[-1] + 
            self.timings.coordinate_frame_updates[-1]
        )
        overhead = total_time - measured_time
        
        self.timings.total_update.append(total_time)
        self.timings.system_overhead.append(overhead)
        
        self.sample_count += 1
        
        # Progress reporting
        if self.sample_count % 25 == 0:
            print(f"[GRANULAR] Progress: {self.sample_count}/{self.max_samples}")
            
    def _generate_granular_report(self):
        """Generate comprehensive granular report"""
        print(f"\n{'='*100}")
        print(f"🔬 GRANULAR BACKEND PROFILING RESULTS")
        print(f"{'='*100}")
        
        if not self.timings.total_update:
            print("❌ No timing data collected")
            return
            
        total_avg = statistics.mean(self.timings.total_update)
        
        print(f"\n📋 SUMMARY:")
        print(f"  Samples: {self.sample_count}")
        print(f"  Avg total time: {total_avg:.3f}ms")
        print(f"  500Hz budget: {(total_avg/2.0)*100:.1f}%")
        
        # Main component breakdown
        print(f"\n📊 MAIN COMPONENT BREAKDOWN:")
        print(f"{'Component':<25} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'% of Total':<10} {'Status'}")
        print("-" * 100)
        
        components = [
            ("Joint Processing", self.timings.joint_processing),
            ("Viser URDF Updates", self.timings.viser_urdf_updates),
            ("Coordinate Frames", self.timings.coordinate_frame_updates),
            ("System Overhead", self.timings.system_overhead),
        ]
        
        for comp_name, times in components:
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                percent = (avg_time / total_avg) * 100
                
                if percent > 50:
                    status = "🔥 MAJOR"
                elif percent > 20:
                    status = "⚠️  SIGNIFICANT"
                elif percent > 5:
                    status = "📊 MODERATE"
                else:
                    status = "✅ MINOR"
                
                print(f"{comp_name:<25} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {percent:<10.1f} {status}")
        
        # Individual URDF breakdown
        if self.timings.individual_urdf_updates:
            print(f"\n🤖 INDIVIDUAL URDF UPDATE BREAKDOWN:")
            print(f"{'URDF Name':<25} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'% of Total':<10}")
            print("-" * 85)
            
            for urdf_name, times in self.timings.individual_urdf_updates.items():
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                percent = (avg_time / total_avg) * 100
                print(f"{urdf_name:<25} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {percent:<10.1f}")
        
        # Individual frame update breakdown
        if self.timings.individual_frame_updates:
            print(f"\n📐 INDIVIDUAL FRAME UPDATE BREAKDOWN:")
            print(f"{'URDF Name':<25} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'% of Total':<10}")
            print("-" * 85)
            
            for urdf_name, times in self.timings.individual_frame_updates.items():
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                percent = (avg_time / total_avg) * 100
                print(f"{urdf_name:<25} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {percent:<10.1f}")
        
        # Bottleneck identification
        self._identify_granular_bottleneck()
        
    def _identify_granular_bottleneck(self):
        """Identify the specific bottleneck within update_all_configurations"""
        print(f"\n🎯 GRANULAR BOTTLENECK ANALYSIS:")
        
        if not self.timings.total_update:
            return
            
        total_avg = statistics.mean(self.timings.total_update)
        
        # Find the biggest time consumer
        component_times = []
        if self.timings.joint_processing:
            component_times.append(("Joint Processing", statistics.mean(self.timings.joint_processing)))
        if self.timings.viser_urdf_updates:
            component_times.append(("Viser URDF Updates", statistics.mean(self.timings.viser_urdf_updates)))
        if self.timings.coordinate_frame_updates:
            component_times.append(("Coordinate Frame Updates", statistics.mean(self.timings.coordinate_frame_updates)))
        if self.timings.system_overhead:
            component_times.append(("System Overhead", statistics.mean(self.timings.system_overhead)))
            
        if component_times:
            bottleneck_name, bottleneck_time = max(component_times, key=lambda x: x[1])
            bottleneck_percent = (bottleneck_time / total_avg) * 100
            
            print(f"  🔥 PRIMARY BOTTLENECK: {bottleneck_name}")
            print(f"  Time: {bottleneck_time:.3f}ms ({bottleneck_percent:.1f}% of total)")
            print(f"  500Hz impact: {(bottleneck_time/2.0)*100:.1f}% of time budget")
            
            # Specific recommendations based on bottleneck
            if "Viser URDF" in bottleneck_name:
                print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
                print(f"  - Focus on viser_urdf.update_cfg() performance")
                print(f"  - Consider selective updates (only changed joints)")
                print(f"  - Investigate mesh complexity reduction")
                print(f"  - Test impact of disabling collision meshes")
                
                # Find slowest URDF
                if self.timings.individual_urdf_updates:
                    slowest_urdf = None
                    slowest_time = 0
                    for urdf_name, times in self.timings.individual_urdf_updates.items():
                        avg_time = statistics.mean(times)
                        if avg_time > slowest_time:
                            slowest_time = avg_time
                            slowest_urdf = urdf_name
                    
                    if slowest_urdf:
                        print(f"  - Slowest URDF: {slowest_urdf} ({slowest_time:.3f}ms)")
                        
            elif "Coordinate Frame" in bottleneck_name:
                print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
                print(f"  - Consider disabling coordinate frame updates during high-speed replay")
                print(f"  - Implement frame update rate limiting")
                print(f"  - Cache transform calculations where possible")
                
            elif "Joint Processing" in bottleneck_name:
                print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
                print(f"  - Optimize joint value grouping algorithm")
                print(f"  - Pre-compute joint mappings")
                print(f"  - Use more efficient data structures")


def run_granular_profiling():
    """Run granular profiling of update_all_configurations internals"""
    try:
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        print("🔬 GRANULAR BACKEND PROFILING")
        print("="*50)
        
        # Create server
        server = viser.ViserServer(host="localhost", port=8083, serve_static=False)
        
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
        
        # Create granular profiler
        profiler = GranularBackendProfiler(max_samples=100)
        
        # Patch urdf_manager to use profiled version
        urdf_manager.original_update_all_configurations = urdf_manager.update_all_configurations
        
        def profiled_update_all_configurations(joint_values: np.ndarray):
            profiler.profile_update_all_configurations(urdf_manager, joint_values)
        
        urdf_manager.update_all_configurations = profiled_update_all_configurations
        
        # Override replay controller's update method
        original_update = replay_controller._update_visualization
        
        def profiled_update():
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
        
        replay_controller._update_visualization = profiled_update
        
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
        
        print("\n✅ GRANULAR PROFILING COMPLETE")
        
    except Exception as e:
        print(f"❌ Granular profiling failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_granular_profiling()
