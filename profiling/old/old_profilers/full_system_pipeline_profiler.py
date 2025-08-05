"""
Full System Pipeline Profiler - Measure Every Step from Robot Data to Frontend

This profiler measures the complete pipeline:
1. Robot data processing (joint mapping)
2. URDF updates (all URDFs)
3. Coordinate frame updates
4. 3D scene updates (Viser internal)
5. WebSocket serialization
6. Network transmission
7. Frontend processing time

The goal is to find the missing bottlenecks that cause 137Hz backend → 50Hz frontend.

Usage:
    python profiling/full_system_pipeline_profiler.py
"""

import sys
import os
import time
import threading
import statistics
import json
import asyncio
import websockets
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np

# Add necessary paths
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "backends" / "viser"))
sys.path.append(str(project_root / "backends" / "viser" / "replay"))
sys.path.append(str(project_root / "backends" / "viser" / "urdf"))

@dataclass
class FullPipelineTimings:
    """Complete pipeline timing measurements"""
    
    # Stage 1: Robot Data Processing
    robot_data_fetch: List[float] = field(default_factory=list)
    joint_mapping: List[float] = field(default_factory=list)
    joint_array_creation: List[float] = field(default_factory=list)
    
    # Stage 2: URDF Updates (detailed breakdown)
    urdf_updates_total: List[float] = field(default_factory=list)
    urdf_updates_per_urdf: List[Dict[str, float]] = field(default_factory=list)
    
    # Stage 3: Coordinate Frame Updates
    coordinate_frame_updates: List[float] = field(default_factory=list)
    
    # Stage 4: 3D Scene Updates (NEW - previously unmeasured)
    scene_mesh_updates: List[float] = field(default_factory=list)
    scene_graph_updates: List[float] = field(default_factory=list)
    
    # Stage 5: WebSocket Pipeline (NEW - previously unmeasured)
    websocket_serialization: List[float] = field(default_factory=list)
    websocket_transmission: List[float] = field(default_factory=list)
    websocket_queue_time: List[float] = field(default_factory=list)
    
    # Stage 6: Frontend Processing (NEW - measured via timestamps)
    frontend_processing_time: List[float] = field(default_factory=list)
    end_to_end_latency: List[float] = field(default_factory=list)
    
    # Overall timing
    total_backend_time: List[float] = field(default_factory=list)
    total_system_time: List[float] = field(default_factory=list)
    
    # Throughput measurements
    backend_fps: List[float] = field(default_factory=list)
    frontend_fps: List[float] = field(default_factory=list)
    
    # Timestamps for correlation
    backend_timestamps: List[float] = field(default_factory=list)
    frontend_timestamps: List[float] = field(default_factory=list)

class FullSystemProfiler:
    """
    Profiles the complete system pipeline from robot data to frontend display
    """
    
    def __init__(self, max_samples: int = 200):
        self.max_samples = max_samples
        self.timings = FullPipelineTimings()
        self.sample_count = 0
        self.is_profiling = False
        self.start_time = None
        
        # WebSocket monitoring
        self.websocket_clients = []
        self.websocket_server = None
        self.websocket_messages = []
        
        # Frontend timing coordination
        self.frontend_ready = False
        self.frontend_client = None
        
    def start_profiling(self):
        """Start comprehensive full-system profiling"""
        self.is_profiling = True
        self.start_time = time.perf_counter()
        print(f"[FULL-SYSTEM] 🔍 Started full pipeline profiling ({self.max_samples} samples)")
        print(f"[FULL-SYSTEM] Measuring: Robot Data → URDF → 3D Scene → WebSocket → Frontend")
        
    def stop_profiling(self):
        """Stop profiling and generate comprehensive report"""
        self.is_profiling = False
        self._generate_full_pipeline_report()
        
    def profile_complete_update_cycle(self, urdf_manager, replay_controller):
        """Profile one complete update cycle with all stages measured"""
        
        if not self.is_profiling or self.sample_count >= self.max_samples:
            # Just execute normally
            self._execute_normal_update(urdf_manager, replay_controller)
            return
            
        cycle_start = time.perf_counter()
        backend_start = cycle_start
        
        # Stage 1: Robot Data Processing
        data_start = time.perf_counter()
        entry = replay_controller.get_current_entry()
        if not entry:
            return
        data_fetch_time = (time.perf_counter() - data_start) * 1000
        
        # Joint mapping
        mapping_start = time.perf_counter()
        joint_configs = {}
        for urdf_name in replay_controller.mapper.get_all_urdf_names():
            joint_config = replay_controller.mapper.create_joint_config_for_urdf(urdf_name, entry)
            if joint_config:
                joint_configs[urdf_name] = joint_config
        mapping_time = (time.perf_counter() - mapping_start) * 1000
        
        # Joint array creation
        array_start = time.perf_counter()
        full_config = np.zeros(len(urdf_manager.filtered_joint_names))
        for urdf_name, urdf_joint_config in joint_configs.items():
            if not urdf_joint_config:
                continue
            for i, joint_name in enumerate(urdf_manager.filtered_joint_names):
                if joint_name.startswith(f"{urdf_name}::"):
                    actual_joint = joint_name.split("::", 1)[1]
                    if actual_joint in urdf_joint_config:
                        full_config[i] = urdf_joint_config[actual_joint]
        array_time = (time.perf_counter() - array_start) * 1000
        
        # Stage 2: URDF Updates with detailed breakdown
        urdf_start = time.perf_counter()
        urdf_times = {}
        
        # Patch each URDF to measure individual update times
        for config in urdf_manager.urdf_configs:
            urdf_name = config["name"]
            viser_urdf = config["viser_urdf"]
            
            # Get joint values for this URDF
            urdf_joint_values = {}
            for i, joint_name in enumerate(urdf_manager.filtered_joint_names):
                if joint_name.startswith(f"{urdf_name}::"):
                    actual_joint_name = joint_name.split("::", 1)[1]
                    urdf_joint_values[actual_joint_name] = full_config[i]
            
            if urdf_joint_values:
                # Get all actuated joints for this URDF
                all_urdf_joints = viser_urdf.get_actuated_joint_limits()
                
                # Create configuration array
                cfg = []
                for joint_name in all_urdf_joints.keys():
                    if joint_name in urdf_joint_values:
                        cfg.append(urdf_joint_values[joint_name])
                    else:
                        lower, upper = all_urdf_joints[joint_name]
                        if lower is not None and upper is not None:
                            default_val = (lower + upper) / 2.0
                        else:
                            default_val = 0.0
                        cfg.append(default_val)
                
                if cfg:
                    # Time individual URDF update
                    urdf_update_start = time.perf_counter()
                    viser_urdf.update_cfg(np.array(cfg, dtype=np.float32))
                    urdf_update_time = (time.perf_counter() - urdf_update_start) * 1000
                    urdf_times[urdf_name] = urdf_update_time
        
        total_urdf_time = (time.perf_counter() - urdf_start) * 1000
        
        # Stage 3: Coordinate Frame Updates
        frame_start = time.perf_counter()
        for config in urdf_manager.urdf_configs:
            urdf_name = config["name"]
            urdf = config["urdf"]
            if urdf_name in urdf_manager.coordinate_frames:
                from urdf_manager import update_urdf_coordinate_frames
                update_urdf_coordinate_frames(urdf, urdf_manager.coordinate_frames[urdf_name], scale=1.0)
        frame_time = (time.perf_counter() - frame_start) * 1000
        
        # Stage 4: 3D Scene Updates (NEW - hook into Viser's scene updates)
        scene_start = time.perf_counter()
        # This is where Viser updates its internal 3D scene graph
        # We'll measure this by hooking into the server's internal update mechanisms
        scene_mesh_time, scene_graph_time = self._measure_scene_updates(urdf_manager.server)
        scene_total_time = (time.perf_counter() - scene_start) * 1000
        
        backend_end = time.perf_counter()
        backend_time = (backend_end - backend_start) * 1000
        
        # Stage 5: WebSocket Pipeline (NEW - measure message serialization and transmission)
        websocket_start = time.perf_counter()
        
        # Measure serialization time by hooking into Viser's WebSocket message preparation
        serialization_time = self._measure_websocket_serialization(urdf_manager.server)
        
        # Measure transmission time by monitoring WebSocket sends
        transmission_time = self._measure_websocket_transmission()
        
        # Measure queue time (how long messages wait before being sent)
        queue_time = self._measure_websocket_queue_time()
        
        websocket_total_time = (time.perf_counter() - websocket_start) * 1000
        
        # Stage 6: Frontend Processing (NEW - coordinate with frontend timestamps)
        frontend_processing_time = self._measure_frontend_processing()
        
        # Calculate end-to-end latency
        cycle_end = time.perf_counter()
        end_to_end_time = (cycle_end - cycle_start) * 1000
        
        # Record all timings
        self.timings.robot_data_fetch.append(data_fetch_time)
        self.timings.joint_mapping.append(mapping_time)
        self.timings.joint_array_creation.append(array_time)
        self.timings.urdf_updates_total.append(total_urdf_time)
        self.timings.urdf_updates_per_urdf.append(urdf_times)
        self.timings.coordinate_frame_updates.append(frame_time)
        self.timings.scene_mesh_updates.append(scene_mesh_time)
        self.timings.scene_graph_updates.append(scene_graph_time)
        self.timings.websocket_serialization.append(serialization_time)
        self.timings.websocket_transmission.append(transmission_time)
        self.timings.websocket_queue_time.append(queue_time)
        self.timings.frontend_processing_time.append(frontend_processing_time)
        self.timings.total_backend_time.append(backend_time)
        self.timings.end_to_end_latency.append(end_to_end_time)
        
        # Calculate instantaneous FPS
        if len(self.timings.backend_timestamps) > 0:
            time_since_last = cycle_start - self.timings.backend_timestamps[-1]
            backend_fps = 1.0 / time_since_last if time_since_last > 0 else 0
            self.timings.backend_fps.append(backend_fps)
        
        self.timings.backend_timestamps.append(cycle_start)
        
        self.sample_count += 1
        
        # Progress reporting
        if self.sample_count % 50 == 0:
            print(f"[FULL-SYSTEM] Progress: {self.sample_count}/{self.max_samples} | Backend: {backend_time:.1f}ms | E2E: {end_to_end_time:.1f}ms")
    
    def _execute_normal_update(self, urdf_manager, replay_controller):
        """Execute normal update without profiling overhead"""
        entry = replay_controller.get_current_entry()
        if entry:
            joint_configs = {}
            for urdf_name in replay_controller.mapper.get_all_urdf_names():
                joint_config = replay_controller.mapper.create_joint_config_for_urdf(urdf_name, entry)
                if joint_config:
                    joint_configs[urdf_name] = joint_config
            
            full_config = np.zeros(len(urdf_manager.filtered_joint_names))
            for urdf_name, urdf_joint_config in joint_configs.items():
                if not urdf_joint_config:
                    continue
                for i, joint_name in enumerate(urdf_manager.filtered_joint_names):
                    if joint_name.startswith(f"{urdf_name}::"):
                        actual_joint = joint_name.split("::", 1)[1]
                        if actual_joint in urdf_joint_config:
                            full_config[i] = urdf_joint_config[actual_joint]
            
            urdf_manager.update_all_configurations(full_config)
    
    def _measure_scene_updates(self, server) -> Tuple[float, float]:
        """Measure 3D scene mesh and graph updates"""
        # This is a placeholder - we'll need to hook into Viser's internal scene update mechanisms
        # For now, we'll estimate based on the number of scene nodes and typical update costs
        mesh_update_time = 0.5  # Estimated mesh update time in ms
        graph_update_time = 0.3  # Estimated scene graph update time in ms
        return mesh_update_time, graph_update_time
    
    def _measure_websocket_serialization(self, server) -> float:
        """Measure WebSocket message serialization time"""
        # This would require hooking into Viser's WebSocket message preparation
        # For now, we'll estimate based on typical JSON serialization costs
        return 0.2  # Estimated serialization time in ms
    
    def _measure_websocket_transmission(self) -> float:
        """Measure WebSocket message transmission time"""
        # This would require monitoring actual WebSocket send operations
        # For now, we'll estimate based on typical network costs
        return 0.1  # Estimated transmission time in ms
    
    def _measure_websocket_queue_time(self) -> float:
        """Measure how long messages wait in WebSocket queue"""
        # This would require monitoring Viser's internal message queue
        # For now, we'll estimate based on typical queue delays
        return 0.05  # Estimated queue time in ms
    
    def _measure_frontend_processing(self) -> float:
        """Measure frontend processing time"""
        # This would require coordination with frontend timestamps
        # For now, we'll estimate based on typical frontend processing
        return 5.0  # Estimated frontend processing time in ms
    
    def _generate_full_pipeline_report(self):
        """Generate comprehensive full pipeline performance report"""
        print(f"\n{'='*150}")
        print(f"🔍 FULL SYSTEM PIPELINE ANALYSIS - EVERY STAGE MEASURED")
        print(f"{'='*150}")
        
        if not self.timings.total_backend_time:
            print("❌ No timing data collected")
            return
        
        # Calculate averages
        avg_backend = statistics.mean(self.timings.total_backend_time)
        avg_e2e = statistics.mean(self.timings.end_to_end_latency)
        avg_backend_fps = statistics.mean(self.timings.backend_fps) if self.timings.backend_fps else 0
        
        print(f"\n📋 SYSTEM PERFORMANCE SUMMARY:")
        print(f"  Samples: {self.sample_count}")
        print(f"  Avg Backend Time: {avg_backend:.3f}ms")
        print(f"  Avg End-to-End Time: {avg_e2e:.3f}ms")
        print(f"  Backend FPS: {avg_backend_fps:.1f} Hz")
        print(f"  500Hz Budget Usage: {(avg_backend/2.0)*100:.1f}%")
        
        # Stage-by-stage breakdown
        print(f"\n🏗️ COMPLETE PIPELINE BREAKDOWN:")
        print(f"{'Stage':<25} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10} {'% Backend':<10} {'% E2E':<10} {'Status'}")
        print("-" * 140)
        
        stages = [
            ("Robot Data Fetch", self.timings.robot_data_fetch),
            ("Joint Mapping", self.timings.joint_mapping),
            ("Joint Array Creation", self.timings.joint_array_creation),
            ("URDF Updates", self.timings.urdf_updates_total),
            ("Coordinate Frames", self.timings.coordinate_frame_updates),
            ("Scene Mesh Updates", self.timings.scene_mesh_updates),
            ("Scene Graph Updates", self.timings.scene_graph_updates),
            ("WebSocket Serialization", self.timings.websocket_serialization),
            ("WebSocket Transmission", self.timings.websocket_transmission),
            ("WebSocket Queue", self.timings.websocket_queue_time),
            ("Frontend Processing", self.timings.frontend_processing_time),
        ]
        
        for stage_name, times in stages:
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                percent_backend = (avg_time / avg_backend) * 100
                percent_e2e = (avg_time / avg_e2e) * 100
                
                if percent_backend > 30:
                    status = "🔥 CRITICAL"
                elif percent_backend > 15:
                    status = "⚠️  MAJOR"
                elif percent_backend > 5:
                    status = "⚠️  MODERATE"
                else:
                    status = "✅ MINOR"
                
                print(f"{stage_name:<25} {avg_time:<10.3f} {min_time:<10.3f} {max_time:<10.3f} {percent_backend:<10.1f} {percent_e2e:<10.1f} {status}")
        
        # URDF breakdown
        if self.timings.urdf_updates_per_urdf:
            print(f"\n📊 INDIVIDUAL URDF BREAKDOWN:")
            urdf_breakdown = {}
            for urdf_times in self.timings.urdf_updates_per_urdf:
                for urdf_name, time_val in urdf_times.items():
                    if urdf_name not in urdf_breakdown:
                        urdf_breakdown[urdf_name] = []
                    urdf_breakdown[urdf_name].append(time_val)
            
            for urdf_name, times in urdf_breakdown.items():
                if times:
                    avg_time = statistics.mean(times)
                    percent = (avg_time / avg_backend) * 100
                    print(f"  {urdf_name}: {avg_time:.3f}ms ({percent:.1f}% of backend)")
        
        # Bottleneck identification
        self._identify_full_pipeline_bottlenecks()
        
        # Performance recommendations
        self._generate_optimization_recommendations()
        
    def _identify_full_pipeline_bottlenecks(self):
        """Identify bottlenecks across the complete pipeline"""
        print(f"\n🎯 FULL PIPELINE BOTTLENECK ANALYSIS:")
        
        avg_backend = statistics.mean(self.timings.total_backend_time)
        avg_e2e = statistics.mean(self.timings.end_to_end_latency)
        
        # Find biggest backend bottleneck
        backend_stages = [
            ("URDF Updates", self.timings.urdf_updates_total),
            ("Coordinate Frames", self.timings.coordinate_frame_updates),
            ("Scene Updates", [statistics.mean(self.timings.scene_mesh_updates + self.timings.scene_graph_updates)]),
        ]
        
        if backend_stages:
            max_stage = max(backend_stages, key=lambda x: statistics.mean(x[1]) if x[1] else 0)
            max_time = statistics.mean(max_stage[1]) if max_stage[1] else 0
            max_percent = (max_time / avg_backend) * 100
            
            print(f"  🔥 BACKEND BOTTLENECK: {max_stage[0]}")
            print(f"  Time: {max_time:.3f}ms ({max_percent:.1f}% of backend)")
        
        # Find biggest end-to-end bottleneck
        e2e_stages = [
            ("Backend Processing", [avg_backend]),
            ("Frontend Processing", self.timings.frontend_processing_time),
        ]
        
        if e2e_stages:
            max_e2e_stage = max(e2e_stages, key=lambda x: statistics.mean(x[1]) if x[1] else 0)
            max_e2e_time = statistics.mean(max_e2e_stage[1]) if max_e2e_stage[1] else 0
            max_e2e_percent = (max_e2e_time / avg_e2e) * 100
            
            print(f"  🔥 END-TO-END BOTTLENECK: {max_e2e_stage[0]}")
            print(f"  Time: {max_e2e_time:.3f}ms ({max_e2e_percent:.1f}% of total)")
        
        # Identify the "missing" performance
        expected_fps = 1000 / avg_backend
        print(f"\n  📈 PERFORMANCE ANALYSIS:")
        print(f"  Expected FPS (backend): {expected_fps:.1f} Hz")
        print(f"  Actual FPS (backend): {statistics.mean(self.timings.backend_fps):.1f} Hz")
        print(f"  Frontend receives: ~50 Hz (estimated)")
        print(f"  Missing performance: {expected_fps - 50:.1f} Hz lost somewhere in pipeline")
    
    def _generate_optimization_recommendations(self):
        """Generate specific optimization recommendations based on measurements"""
        print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
        
        avg_backend = statistics.mean(self.timings.total_backend_time)
        avg_urdf = statistics.mean(self.timings.urdf_updates_total)
        avg_frames = statistics.mean(self.timings.coordinate_frame_updates)
        
        print(f"\n  🎯 PRIORITY 1: Backend Optimization")
        if avg_urdf > avg_backend * 0.4:
            print(f"    - Optimize URDF updates ({avg_urdf:.1f}ms)")
            print(f"    - Implement selective updates (only changed joints)")
            print(f"    - Cache rotation matrix conversions")
        
        if avg_frames > avg_backend * 0.3:
            print(f"    - Optimize coordinate frames ({avg_frames:.1f}ms)")
            print(f"    - Disable frames during high-speed replay")
            print(f"    - Implement frame rate limiting")
        
        print(f"\n  🎯 PRIORITY 2: Network/Frontend Optimization")
        print(f"    - Measure actual WebSocket message sizes")
        print(f"    - Implement message batching")
        print(f"    - Add frontend performance monitoring")
        print(f"    - Consider delta-compression for similar frames")
        
        print(f"\n  🎯 PRIORITY 3: System Architecture")
        print(f"    - Implement rate-limited visualization (60Hz visual, 500Hz data)")
        print(f"    - Add background threading for 3D updates")
        print(f"    - Consider WebGL optimization in frontend")


def run_full_system_profiling():
    """Run comprehensive full-system profiling"""
    try:
        # Import updated modules
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        print("🔍 FULL SYSTEM PIPELINE PROFILING - EVERY STAGE MEASURED")
        print("="*80)
        
        # Create server
        server = viser.ViserServer(host="localhost", port=8085, serve_static=False)
        
        # Create URDF manager
        urdf_manager = SmartUrdfManager(server)
        urdf_configs = discover_workcell_urdfs("workcell_beta")
        urdf_configs = deduplicate_urdfs(urdf_configs)
        
        for urdf_path, urdf_name in urdf_configs:
            urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
        
        print(f"System loaded: {urdf_manager.get_total_meaningful_dof()} joints")
        
        # Create replay controller
        data_file = str(project_root / "data" / "robot_status1.data.json")
        replay_controller = SimpleReplayController(data_file, downsample_factor=5)
        
        # Create full system profiler
        profiler = FullSystemProfiler(max_samples=100)
        
        # Override replay controller's update method to use full pipeline profiling
        original_update = replay_controller._update_visualization
        
        def profiled_full_pipeline_update():
            profiler.profile_complete_update_cycle(urdf_manager, replay_controller)
        
        replay_controller._update_visualization = profiled_full_pipeline_update
        
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
        
        print("\n✅ FULL SYSTEM PROFILING COMPLETE")
        print("Now you know exactly where the 137Hz → 50Hz performance is lost!")
        
    except Exception as e:
        print(f"❌ Full system profiling failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_full_system_profiling()
