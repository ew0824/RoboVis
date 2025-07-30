"""
Detailed Pipeline Profiler - Measure Each Stage of the Update Pipeline

This profiler instruments each stage of the robot update pipeline to identify
exactly where the performance bottleneck occurs:

1. Joint Mapping (robot data → joint configs)
2. Data Processing (joint configs → arrays)
3. Viser Backend (URDF updates)
4. Network Transmission (WebSocket)
5. Timing between updates (rate limiting)

Usage:
    python profiling/detailed_pipeline_profiler.py
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
class DetailedTimings:
    """Detailed timing measurements for each pipeline stage"""
    joint_mapping: List[float] = field(default_factory=list)
    data_processing: List[float] = field(default_factory=list)
    viser_backend: List[float] = field(default_factory=list)
    network_transmission: List[float] = field(default_factory=list)
    total_pipeline: List[float] = field(default_factory=list)
    update_intervals: List[float] = field(default_factory=list)
    
class DetailedPipelineProfiler:
    """
    Profiles each stage of the robot update pipeline in detail
    """
    
    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.timings = DetailedTimings()
        self.sample_count = 0
        self.is_profiling = False
        self.last_update_time = 0.0
        self.start_time = 0.0
        
    def start_profiling(self):
        """Start detailed profiling"""
        self.is_profiling = True
        self.start_time = time.perf_counter()
        self.last_update_time = self.start_time
        print(f"[DETAILED] 🎯 Started detailed pipeline profiling ({self.max_samples} samples)")
        
    def stop_profiling(self):
        """Stop profiling and generate report"""
        self.is_profiling = False
        total_duration = time.perf_counter() - self.start_time
        self._generate_detailed_report(total_duration)
        
    def profile_update(self, joint_mapping_func, data_processing_func, viser_backend_func, network_func, *args):
        """Profile a complete update through all pipeline stages"""
        if not self.is_profiling or self.sample_count >= self.max_samples:
            # Just execute without profiling
            joint_configs = joint_mapping_func(*args)
            arrays = data_processing_func(joint_configs)
            viser_backend_func(arrays)
            network_func()
            return
            
        pipeline_start = time.perf_counter()
        
        # Record interval since last update
        if self.last_update_time > 0:
            interval = (pipeline_start - self.last_update_time) * 1000
            self.timings.update_intervals.append(interval)
        
        # Stage 1: Joint Mapping
        stage_start = time.perf_counter()
        joint_configs = joint_mapping_func(*args)
        stage_end = time.perf_counter()
        self.timings.joint_mapping.append((stage_end - stage_start) * 1000)
        
        # Stage 2: Data Processing 
        stage_start = time.perf_counter()
        arrays = data_processing_func(joint_configs)
        stage_end = time.perf_counter()
        self.timings.data_processing.append((stage_end - stage_start) * 1000)
        
        # Stage 3: Viser Backend
        stage_start = time.perf_counter()
        viser_backend_func(arrays)
        stage_end = time.perf_counter()
        self.timings.viser_backend.append((stage_end - stage_start) * 1000)
        
        # Stage 4: Network Transmission
        stage_start = time.perf_counter()
        network_func()
        stage_end = time.perf_counter()
        self.timings.network_transmission.append((stage_end - stage_start) * 1000)
        
        # Total pipeline time
        pipeline_end = time.perf_counter()
        self.timings.total_pipeline.append((pipeline_end - pipeline_start) * 1000)
        
        self.sample_count += 1
        self.last_update_time = pipeline_end
        
        # Progress reporting
        if self.sample_count % 25 == 0:
            print(f"[DETAILED] Progress: {self.sample_count}/{self.max_samples}")
            
    def _generate_detailed_report(self, total_duration: float):
        """Generate comprehensive detailed report"""
        print(f"\n{'='*100}")
        print(f"🎯 DETAILED PIPELINE PROFILING RESULTS")
        print(f"{'='*100}")
        
        actual_rate = self.sample_count / total_duration if total_duration > 0 else 0
        
        print(f"\n📋 TEST SUMMARY:")
        print(f"  Duration: {total_duration:.2f}s")
        print(f"  Samples: {self.sample_count}")
        print(f"  Target rate: 500Hz")
        print(f"  Actual rate: {actual_rate:.1f}Hz")
        print(f"  Efficiency: {(actual_rate/500)*100:.1f}%")
        
        # Detailed stage analysis
        print(f"\n📊 DETAILED STAGE BREAKDOWN:")
        print(f"{'Stage':<25} {'Samples':<8} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'Total %':<8} {'500Hz %':<8} {'Status'}")
        print("-" * 120)
        
        stages = [
            ("Joint Mapping", self.timings.joint_mapping),
            ("Data Processing", self.timings.data_processing), 
            ("Viser Backend", self.timings.viser_backend),
            ("Network Transmission", self.timings.network_transmission),
            ("TOTAL PIPELINE", self.timings.total_pipeline)
        ]
        
        total_avg = statistics.mean(self.timings.total_pipeline) if self.timings.total_pipeline else 0
        
        for stage_name, times in stages:
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                total_percent = (avg_time / total_avg * 100) if total_avg > 0 else 0
                budget_percent = (avg_time / 2.0) * 100  # 500Hz = 2ms budget
                
                if budget_percent > 50:
                    status = "🔥 CRITICAL"
                elif budget_percent > 20:
                    status = "⚠️  WARNING" 
                elif budget_percent > 5:
                    status = "📊 MODERATE"
                else:
                    status = "✅ OK"
                
                print(f"{stage_name:<25} {len(times):<8} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {total_percent:<8.1f} {budget_percent:<8.1f} {status}")
        
        # Update interval analysis
        if self.timings.update_intervals:
            print(f"\n⏱️  UPDATE INTERVAL ANALYSIS:")
            avg_interval = statistics.mean(self.timings.update_intervals)
            min_interval = min(self.timings.update_intervals)
            max_interval = max(self.timings.update_intervals)
            
            print(f"  Avg interval: {avg_interval:.3f}ms (target: 2.0ms for 500Hz)")
            print(f"  Min interval: {min_interval:.3f}ms")
            print(f"  Max interval: {max_interval:.3f}ms")
            print(f"  Interval efficiency: {(2.0/avg_interval)*100:.1f}%")
            
            if avg_interval > 2.5:
                print(f"  🔥 INTERVAL BOTTLENECK: Updates are spaced too far apart!")
                print(f"  Actual rate: {1000/avg_interval:.1f}Hz vs target 500Hz")
            
        # Bottleneck identification
        self._identify_detailed_bottleneck()
        
    def _identify_detailed_bottleneck(self):
        """Identify the primary bottleneck in the pipeline"""
        print(f"\n🎯 DETAILED BOTTLENECK ANALYSIS:")
        
        if not self.timings.total_pipeline:
            print("  ❌ No pipeline data collected")
            return
            
        # Find slowest stage
        stage_averages = []
        if self.timings.joint_mapping:
            stage_averages.append(("Joint Mapping", statistics.mean(self.timings.joint_mapping)))
        if self.timings.data_processing:
            stage_averages.append(("Data Processing", statistics.mean(self.timings.data_processing)))
        if self.timings.viser_backend:
            stage_averages.append(("Viser Backend", statistics.mean(self.timings.viser_backend)))
        if self.timings.network_transmission:
            stage_averages.append(("Network Transmission", statistics.mean(self.timings.network_transmission)))
            
        if stage_averages:
            bottleneck_stage, bottleneck_time = max(stage_averages, key=lambda x: x[1])
            total_pipeline_avg = statistics.mean(self.timings.total_pipeline)
            bottleneck_percent = (bottleneck_time / total_pipeline_avg) * 100
            
            print(f"  🔥 PIPELINE BOTTLENECK: {bottleneck_stage}")
            print(f"  Time: {bottleneck_time:.3f}ms ({bottleneck_percent:.1f}% of pipeline)")
            print(f"  500Hz budget: {(bottleneck_time/2.0)*100:.1f}%")
            
        # Rate limiting analysis
        if self.timings.update_intervals:
            avg_interval = statistics.mean(self.timings.update_intervals)
            total_pipeline_avg = statistics.mean(self.timings.total_pipeline)
            
            print(f"\n🕒 RATE LIMITING ANALYSIS:")
            print(f"  Pipeline time: {total_pipeline_avg:.3f}ms")
            print(f"  Update interval: {avg_interval:.3f}ms")
            print(f"  Gap time: {avg_interval - total_pipeline_avg:.3f}ms ({((avg_interval - total_pipeline_avg)/avg_interval)*100:.1f}% of interval)")
            
            if (avg_interval - total_pipeline_avg) > total_pipeline_avg:
                print(f"  🔥 RATE LIMITING DETECTED: Gap time > pipeline time!")
                print(f"  This suggests external rate limiting (threading, GUI, etc.)")


def run_detailed_profiling():
    """Run detailed pipeline profiling with working replay system"""
    try:
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        print("🎯 DETAILED PIPELINE PROFILING")
        print("="*50)
        
        # Create server
        server = viser.ViserServer(host="localhost", port=8082, serve_static=False)
        
        # Create URDF manager
        urdf_manager = SmartUrdfManager(server)
        urdf_configs = discover_workcell_urdfs("workcell_beta")
        urdf_configs = deduplicate_urdfs(urdf_configs)
        
        for urdf_path, urdf_name in urdf_configs:
            urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
        
        # Create replay controller at full rate
        data_file = str(project_root / "data" / "robot_status1.data.json")
        replay_controller = SimpleReplayController(data_file, downsample_factor=1)
        
        # Create detailed profiler
        profiler = DetailedPipelineProfiler(max_samples=100)
        
        # Define pipeline stages for profiling
        def joint_mapping_stage(entry):
            """Stage 1: Map robot data to joint configs"""
            joint_configs = {}
            for urdf_name in replay_controller.mapper.get_all_urdf_names():
                joint_config = replay_controller.mapper.create_joint_config_for_urdf(urdf_name, entry)
                if joint_config:
                    joint_configs[urdf_name] = joint_config
            return joint_configs
            
        def data_processing_stage(joint_configs):
            """Stage 2: Process joint configs to arrays"""
            full_config = np.zeros(len(urdf_manager.filtered_joint_names))
            for urdf_name, urdf_joint_config in joint_configs.items():
                if not urdf_joint_config:
                    continue
                for i, joint_name in enumerate(urdf_manager.filtered_joint_names):
                    if joint_name.startswith(f"{urdf_name}::"):
                        actual_joint = joint_name.split("::", 1)[1]
                        if actual_joint in urdf_joint_config:
                            full_config[i] = urdf_joint_config[actual_joint]
            return full_config
            
        def viser_backend_stage(config_array):
            """Stage 3: Update Viser backend"""
            urdf_manager.update_all_configurations(config_array)
            
        def network_stage():
            """Stage 4: Network transmission (placeholder)"""
            # This would measure actual WebSocket transmission if we could instrument it
            pass
        
        # Override replay controller's update method with profiled version
        original_update = replay_controller._update_visualization
        
        def profiled_update():
            entry = replay_controller.get_current_entry()
            if entry:
                profiler.profile_update(
                    joint_mapping_stage, 
                    data_processing_stage,
                    viser_backend_stage,
                    network_stage,
                    entry
                )
        
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
        
        print("\n✅ DETAILED PROFILING COMPLETE")
        
    except Exception as e:
        print(f"❌ Detailed profiling failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_detailed_profiling()
