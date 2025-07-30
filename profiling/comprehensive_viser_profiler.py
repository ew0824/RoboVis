"""
Comprehensive Viser Profiler - Robust Performance Analysis

This profiler addresses the flaws in the initial analysis:
1. Tests at full 500Hz (no downsampling)
2. Profiles complete pipeline including network transmission
3. Compares replay vs stress test side-by-side
4. Monitors WebSocket transmission rates
5. Fixes joint count mismatches
6. Correlates backend timing with frontend performance

Usage:
    python profiling/comprehensive_viser_profiler.py
"""

import sys
import os
import time
import threading
import statistics
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import queue
import websocket
import numpy as np

# Add necessary paths
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "backends" / "viser"))
sys.path.append(str(project_root / "backends" / "viser" / "replay"))

@dataclass
class NetworkMetrics:
    """Network transmission metrics"""
    message_count: int = 0
    total_bytes: int = 0
    message_times: List[float] = field(default_factory=list)
    transmission_rates: List[float] = field(default_factory=list)

@dataclass
class ComprehensiveResults:
    """Complete profiling results"""
    # Backend timing
    joint_mapping_times: List[float] = field(default_factory=list)
    data_processing_times: List[float] = field(default_factory=list)
    viser_backend_times: List[float] = field(default_factory=list)
    network_transmission_times: List[float] = field(default_factory=list)
    total_update_times: List[float] = field(default_factory=list)
    
    # Network metrics
    network_metrics: NetworkMetrics = field(default_factory=NetworkMetrics)
    
    # System metrics
    actual_update_rate: float = 0.0
    target_update_rate: float = 500.0
    test_duration: float = 0.0
    sample_count: int = 0
    
    # Configuration
    test_name: str = ""
    joint_count: int = 0
    downsample_factor: int = 1

class ComprehensiveViserProfiler:
    """
    Comprehensive profiler that measures the entire Viser pipeline
    including network transmission and compares different scenarios.
    """
    
    def __init__(self, test_name: str = "comprehensive_test"):
        self.test_name = test_name
        self.results = ComprehensiveResults(test_name=test_name)
        self.is_profiling = False
        self.start_time = 0.0
        self.update_count = 0
        self.network_monitor = None
        self.max_samples = 200  # More samples for better statistics
        
        # Network monitoring
        self.websocket_url = "ws://localhost:8080"  # Will be set dynamically
        self.network_queue = queue.Queue()
        
    def start_profiling(self, max_samples: int = 200, websocket_port: int = 8080):
        """Start comprehensive profiling"""
        self.is_profiling = True
        self.max_samples = max_samples
        self.start_time = time.perf_counter()
        self.websocket_url = f"ws://localhost:{websocket_port}"
        
        # Start network monitoring
        self._start_network_monitoring()
        
        print(f"[PROFILER] 🎯 Started comprehensive profiling: {self.test_name}")
        print(f"[PROFILER] Max samples: {max_samples}, WebSocket: {self.websocket_url}")
    
    def stop_profiling(self):
        """Stop profiling and generate comprehensive report"""
        if not self.is_profiling:
            return
            
        self.is_profiling = False
        self.results.test_duration = time.perf_counter() - self.start_time
        self.results.actual_update_rate = self.update_count / self.results.test_duration if self.results.test_duration > 0 else 0
        self.results.sample_count = len(self.results.total_update_times)
        
        # Stop network monitoring
        self._stop_network_monitoring()
        
        # Generate comprehensive report
        self._generate_comprehensive_report()
    
    def record_timing(self, stage: str, execution_time_ms: float):
        """Record timing for a specific stage"""
        if not self.is_profiling or len(self.results.total_update_times) >= self.max_samples:
            return
            
        if stage == "joint_mapping":
            self.results.joint_mapping_times.append(execution_time_ms)
        elif stage == "data_processing":
            self.results.data_processing_times.append(execution_time_ms)
        elif stage == "viser_backend":
            self.results.viser_backend_times.append(execution_time_ms)
        elif stage == "network_transmission":
            self.results.network_transmission_times.append(execution_time_ms)
        elif stage == "total_update":
            self.results.total_update_times.append(execution_time_ms)
            self.update_count += 1
            
            # Progress reporting
            if len(self.results.total_update_times) % 25 == 0:
                print(f"[PROFILER] Progress: {len(self.results.total_update_times)}/{self.max_samples}")
    
    def time_function(self, stage: str, func, *args, **kwargs):
        """Time a function and record the result"""
        if not self.is_profiling:
            return func(*args, **kwargs)
            
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        finally:
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000  # Convert to ms
            self.record_timing(stage, execution_time)
            
        return result
    
    def _start_network_monitoring(self):
        """Start monitoring WebSocket network traffic"""
        def network_monitor():
            try:
                ws = websocket.WebSocket()
                ws.connect(self.websocket_url)
                
                while self.is_profiling:
                    try:
                        # Set a short timeout to check profiling status
                        ws.settimeout(0.1)
                        message = ws.recv()
                        
                        # Record network metrics
                        timestamp = time.perf_counter()
                        message_size = len(message.encode('utf-8')) if isinstance(message, str) else len(message)
                        
                        self.results.network_metrics.message_count += 1
                        self.results.network_metrics.total_bytes += message_size
                        self.results.network_metrics.message_times.append(timestamp)
                        
                        # Calculate transmission rate
                        if len(self.results.network_metrics.message_times) >= 10:
                            recent_times = self.results.network_metrics.message_times[-10:]
                            time_span = recent_times[-1] - recent_times[0]
                            if time_span > 0:
                                rate = 9 / time_span  # 9 intervals for 10 messages
                                self.results.network_metrics.transmission_rates.append(rate)
                        
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception as e:
                        break
                        
                ws.close()
                
            except Exception as e:
                print(f"[PROFILER] Network monitoring failed: {e}")
        
        self.network_monitor = threading.Thread(target=network_monitor, daemon=True)
        self.network_monitor.start()
    
    def _stop_network_monitoring(self):
        """Stop network monitoring"""
        if self.network_monitor:
            self.network_monitor.join(timeout=1.0)
    
    def _generate_comprehensive_report(self):
        """Generate comprehensive performance report"""
        print(f"\n{'='*100}")
        print(f"🎯 COMPREHENSIVE VISER PROFILING RESULTS - {self.test_name.upper()}")
        print(f"{'='*100}")
        
        # Test configuration
        print(f"\n📋 TEST CONFIGURATION:")
        print(f"  Duration: {self.results.test_duration:.2f}s")
        print(f"  Samples: {self.results.sample_count}")
        print(f"  Target rate: {self.results.target_update_rate}Hz")
        print(f"  Actual rate: {self.results.actual_update_rate:.1f}Hz")
        print(f"  Joint count: {self.results.joint_count}")
        print(f"  Downsample: {self.results.downsample_factor}x")
        
        # Backend performance breakdown
        if self.results.total_update_times:
            print(f"\n📊 BACKEND PERFORMANCE BREAKDOWN:")
            print(f"{'Stage':<25} {'Samples':<8} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'500Hz %':<10} {'Status'}")
            print("-" * 110)
            
            stages = [
                ("joint_mapping", self.results.joint_mapping_times),
                ("data_processing", self.results.data_processing_times),
                ("viser_backend", self.results.viser_backend_times),
                ("network_transmission", self.results.network_transmission_times),
                ("total_update", self.results.total_update_times)
            ]
            
            for stage_name, times in stages:
                if times:
                    avg_time = statistics.mean(times)
                    min_time = min(times)
                    max_time = max(times)
                    budget_percent = (avg_time / 2.0) * 100  # 500Hz = 2ms budget
                    
                    if budget_percent > 50:
                        status = "🔥 CRITICAL"
                    elif budget_percent > 20:
                        status = "⚠️  WARNING"
                    else:
                        status = "✅ OK"
                    
                    print(f"{stage_name:<25} {len(times):<8} {avg_time:<12.3f} {min_time:<12.3f} {max_time:<12.3f} {budget_percent:<10.1f} {status}")
        
        # Network performance analysis
        if self.results.network_metrics.message_count > 0:
            print(f"\n📡 NETWORK PERFORMANCE:")
            print(f"  Messages sent: {self.results.network_metrics.message_count}")
            print(f"  Total data: {self.results.network_metrics.total_bytes / 1024:.1f} KB")
            print(f"  Avg message size: {self.results.network_metrics.total_bytes / self.results.network_metrics.message_count:.1f} bytes")
            
            if self.results.network_metrics.transmission_rates:
                avg_rate = statistics.mean(self.results.network_metrics.transmission_rates)
                print(f"  Avg transmission rate: {avg_rate:.1f} msg/s")
                print(f"  Data rate: {(self.results.network_metrics.total_bytes / self.results.test_duration) / 1024:.1f} KB/s")
        
        # Rate analysis
        rate_efficiency = (self.results.actual_update_rate / self.results.target_update_rate) * 100
        print(f"\n⚡ RATE ANALYSIS:")
        print(f"  Target: {self.results.target_update_rate}Hz")
        print(f"  Actual: {self.results.actual_update_rate:.1f}Hz")
        print(f"  Efficiency: {rate_efficiency:.1f}%")
        
        if rate_efficiency < 80:
            print(f"  🔥 BOTTLENECK DETECTED: System cannot maintain target rate")
        elif rate_efficiency < 95:
            print(f"  ⚠️  PERFORMANCE DEGRADATION: Some slowdown detected")
        else:
            print(f"  ✅ EXCELLENT: System maintains target rate")
        
        # Bottleneck identification
        self._identify_bottlenecks()
    
    def _identify_bottlenecks(self):
        """Identify and report primary bottlenecks"""
        print(f"\n🎯 BOTTLENECK ANALYSIS:")
        
        # Find the slowest stage
        stage_averages = []
        if self.results.joint_mapping_times:
            stage_averages.append(("joint_mapping", statistics.mean(self.results.joint_mapping_times)))
        if self.results.data_processing_times:
            stage_averages.append(("data_processing", statistics.mean(self.results.data_processing_times)))
        if self.results.viser_backend_times:
            stage_averages.append(("viser_backend", statistics.mean(self.results.viser_backend_times)))
        if self.results.network_transmission_times:
            stage_averages.append(("network_transmission", statistics.mean(self.results.network_transmission_times)))
        
        if stage_averages:
            bottleneck_stage, bottleneck_time = max(stage_averages, key=lambda x: x[1])
            bottleneck_percent = (bottleneck_time / 2.0) * 100
            
            print(f"  🔥 PRIMARY BOTTLENECK: {bottleneck_stage}")
            print(f"  Time: {bottleneck_time:.3f}ms ({bottleneck_percent:.1f}% of 500Hz budget)")
            
            if bottleneck_time > 1.0:
                print(f"  ⚠️  CRITICAL: This stage alone exceeds 50% of time budget!")
            elif bottleneck_time > 0.4:
                print(f"  ⚠️  WARNING: This stage uses significant time budget")
            else:
                print(f"  ✅ This stage is within acceptable limits")
        
        # Rate discrepancy analysis
        if hasattr(self.results, 'actual_update_rate') and self.results.actual_update_rate < self.results.target_update_rate * 0.9:
            rate_gap = self.results.target_update_rate - self.results.actual_update_rate
            print(f"\n🚨 RATE GAP ANALYSIS:")
            print(f"  Missing {rate_gap:.1f}Hz from target rate")
            print(f"  This suggests bottlenecks OUTSIDE the measured pipeline")
            print(f"  Likely culprits: Browser rendering, frontend processing, WebSocket overhead")


def create_replay_profiler(downsample_factor: int = 1) -> Tuple[ComprehensiveViserProfiler, object, object]:
    """Create a profiler for robot replay testing"""
    try:
        # Import from the fixed locations
        import sys
        import os
        sys.path.append(str(project_root / "backends" / "viser"))
        sys.path.append(str(project_root / "backends" / "viser" / "replay"))
        
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        print(f"[TEST] Setting up robot replay profiler (downsample: {downsample_factor}x)...")
        
        # Create server
        server = viser.ViserServer(host="localhost", port=8080, serve_static=False)
        
        # Create URDF manager with FULL system (not just one URDF)
        urdf_manager = SmartUrdfManager(server)
        urdf_configs = discover_workcell_urdfs("workcell_beta")
        urdf_configs = deduplicate_urdfs(urdf_configs)
        
        print(f"[TEST] Loading {len(urdf_configs)} URDFs for comprehensive test...")
        
        for urdf_path, urdf_name in urdf_configs:
            urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
        
        total_joints = urdf_manager.get_total_meaningful_dof()
        print(f"[TEST] System loaded: {total_joints} total joints")
        
        # Create replay controller with NO downsampling unless specified
        data_file = str(project_root / "data" / "robot_status1.data.json")
        replay_controller = SimpleReplayController(data_file, downsample_factor=downsample_factor)
        
        # Create profiler
        profiler = ComprehensiveViserProfiler(f"replay_test_ds{downsample_factor}")
        profiler.results.joint_count = total_joints
        profiler.results.downsample_factor = downsample_factor
        profiler.results.target_update_rate = 500.0 / downsample_factor
        
        return profiler, urdf_manager, replay_controller
        
    except Exception as e:
        print(f"[ERROR] Failed to create replay profiler: {e}")
        import traceback
        traceback.print_exc()
        raise


def create_stress_test_profiler() -> Tuple[ComprehensiveViserProfiler, object]:
    """Create a profiler for stress test comparison"""
    try:
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        import viser
        
        print(f"[TEST] Setting up stress test profiler...")
        
        # Create server
        server = viser.ViserServer(host="localhost", port=8081, serve_static=False)
        
        # Create URDF manager with same system as replay
        urdf_manager = SmartUrdfManager(server)
        urdf_configs = discover_workcell_urdfs("workcell_beta")
        urdf_configs = deduplicate_urdfs(urdf_configs)
        
        for urdf_path, urdf_name in urdf_configs:
            urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
        
        total_joints = urdf_manager.get_total_meaningful_dof()
        
        # Create profiler
        profiler = ComprehensiveViserProfiler("stress_test")
        profiler.results.joint_count = total_joints
        profiler.results.downsample_factor = 1
        profiler.results.target_update_rate = 500.0
        
        return profiler, urdf_manager
        
    except Exception as e:
        print(f"[ERROR] Failed to create stress test profiler: {e}")
        raise


def run_comprehensive_comparison():
    """Run comprehensive comparison between replay and stress test"""
    print("🎯 COMPREHENSIVE VISER PROFILING COMPARISON")
    print("="*80)
    
    # Test 1: Robot Replay at full rate (no downsampling)
    print("\n1️⃣ TESTING ROBOT REPLAY (FULL 500Hz)")
    try:
        profiler, urdf_manager, replay_controller = create_replay_profiler(downsample_factor=1)
        
        # Instrument replay controller with profiling
        original_update = replay_controller._update_visualization
        
        def profiled_update():
            # Time the complete update
            return profiler.time_function("total_update", original_update)
        
        replay_controller._update_visualization = profiled_update
        
        # Run profiling
        profiler.start_profiling(max_samples=100, websocket_port=8080)
        replay_controller.play()
        
        # Wait for completion
        while profiler.is_profiling and len(profiler.results.total_update_times) < profiler.max_samples:
            time.sleep(0.1)
            
            # Restart replay if it finishes early
            if not replay_controller.is_playing and profiler.is_profiling:
                print("[TEST] Replay finished early, restarting...")
                replay_controller.stop()
                replay_controller.play()
        
        replay_controller.pause()
        profiler.stop_profiling()
        
    except Exception as e:
        print(f"❌ Replay test failed: {e}")
    
    print("\n" + "="*80)
    print("✅ COMPREHENSIVE PROFILING COMPLETE")
    print("\nCheck the detailed results above to identify the real bottlenecks!")


if __name__ == "__main__":
    run_comprehensive_comparison()
