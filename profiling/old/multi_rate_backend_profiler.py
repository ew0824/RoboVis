"""
Multi-Rate Backend Profiler - Test Different Downsampling Factors

Tests backend send timing consistency at multiple downsampling rates
to identify the optimal rate for smooth visualization.

Usage:
    python multi_rate_backend_profiler.py
"""

import sys
import time
import threading
import statistics
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Add necessary paths
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "backends" / "viser"))
sys.path.append(str(project_root / "backends" / "viser" / "replay"))
sys.path.append(str(project_root / "backends" / "viser" / "urdf"))

@dataclass
class MultiRateResults:
    """Results from multiple downsampling rate tests"""
    downsampling_factor: int
    effective_rate_hz: float
    target_interval_ms: float
    
    # Timing measurements
    avg_interval_ms: float
    std_interval_ms: float
    min_interval_ms: float
    max_interval_ms: float
    consistency_percent: float
    
    # Processing measurements  
    avg_processing_ms: float
    avg_cycle_ms: float
    avg_urdf_ms: float
    
    # Data collection
    sample_count: int
    duration_seconds: float
    

class MultiRateBackendProfiler:
    """
    Tests backend consistency at multiple downsampling rates
    """
    
    def __init__(self, target_duration_seconds: float = 20.0):
        self.target_duration = target_duration_seconds
        self.results = []
        
    def run_comprehensive_test(self, downsampling_factors: List[int] = [1, 3, 5, 10]):
        """Run backend profiling at multiple downsampling rates"""
        
        print(f"🎯 MULTI-RATE BACKEND PROFILING - {self.target_duration}s per test")
        print(f"Testing downsampling factors: {downsampling_factors}")
        print("="*80)
        
        for i, factor in enumerate(downsampling_factors):
            print(f"\n🔍 TEST {i+1}/{len(downsampling_factors)}: Downsampling {factor}x")
            print(f"   Expected rate: {500/factor:.1f}Hz ({(factor/500)*1000:.1f}ms intervals)")
            
            try:
                result = self._run_single_test(factor)
                self.results.append(result)
                
                print(f"   ✅ Completed: {result.consistency_percent:.1f}% consistency, "
                      f"{result.effective_rate_hz:.1f}Hz effective")
                      
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                continue
        
        # Generate comprehensive analysis
        self._generate_comparative_analysis()
        self._export_multi_rate_data()
        
    def _run_single_test(self, downsampling_factor: int) -> MultiRateResults:
        """Run a single backend profiling test"""
        
        # Import here to avoid issues with multiple imports
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        # Use different port for each test to avoid conflicts
        port = 8090 + downsampling_factor
        server = viser.ViserServer(host="localhost", port=port, serve_static=False)
        
        # Create URDF manager
        urdf_manager = SmartUrdfManager(server)
        urdf_configs = discover_workcell_urdfs("workcell_beta")
        urdf_configs = deduplicate_urdfs(urdf_configs)
        
        for urdf_path, urdf_name in urdf_configs:
            urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
        
        # Create replay controller with specified downsampling
        data_file = str(project_root / "data" / "robot_status1.data.json")
        replay_controller = SimpleReplayController(data_file, downsample_factor=downsampling_factor)
        
        # Calculate target sample count for desired duration
        target_rate = 500.0 / downsampling_factor
        target_samples = int(self.target_duration * target_rate * 1.2)  # 20% extra to ensure duration
        
        # Create custom profiler for this test
        profiler = SingleRateProfiler(max_samples=target_samples, target_duration=self.target_duration)
        
        # Hook profiler into replay controller
        profiler.hook_into_controller(urdf_manager, replay_controller)
        
        # Run the test
        profiler.start_profiling()
        replay_controller.play()
        
        # Wait for completion or timeout
        start_time = time.time()
        while (profiler.is_profiling and 
               profiler.sample_count < target_samples and
               (time.time() - start_time) < (self.target_duration + 5)):
            time.sleep(0.1)
            
            # Restart replay if it stops before we're done
            if not replay_controller.is_playing and profiler.is_profiling:
                replay_controller.stop()
                replay_controller.play()
        
        # Stop and collect results
        replay_controller.pause()
        profiler.stop_profiling()
        
        # Calculate results
        return self._calculate_results(profiler, downsampling_factor)
        
    def _calculate_results(self, profiler, downsampling_factor: int) -> MultiRateResults:
        """Calculate results from profiler data"""
        
        if not profiler.send_intervals:
            raise ValueError("No timing data collected")
            
        # Basic statistics
        avg_interval = statistics.mean(profiler.send_intervals)
        std_interval = statistics.stdev(profiler.send_intervals) if len(profiler.send_intervals) > 1 else 0
        min_interval = min(profiler.send_intervals)
        max_interval = max(profiler.send_intervals)
        
        # Consistency calculation
        consistency = max(0, 100 - (std_interval / avg_interval * 100)) if avg_interval > 0 else 0
        
        # Processing statistics
        avg_processing = statistics.mean(profiler.processing_times) if profiler.processing_times else 0
        avg_cycle = statistics.mean(profiler.cycle_times) if profiler.cycle_times else 0
        avg_urdf = statistics.mean(profiler.urdf_times) if profiler.urdf_times else 0
        
        return MultiRateResults(
            downsampling_factor=downsampling_factor,
            effective_rate_hz=1000.0 / avg_interval,
            target_interval_ms=(downsampling_factor / 500.0) * 1000,
            avg_interval_ms=avg_interval,
            std_interval_ms=std_interval,
            min_interval_ms=min_interval,
            max_interval_ms=max_interval,
            consistency_percent=consistency,
            avg_processing_ms=avg_processing,
            avg_cycle_ms=avg_cycle,
            avg_urdf_ms=avg_urdf,
            sample_count=profiler.sample_count,
            duration_seconds=profiler.actual_duration
        )
    
    def _generate_comparative_analysis(self):
        """Generate comprehensive comparative analysis"""
        
        print(f"\n{'='*100}")
        print(f"🎯 MULTI-RATE BACKEND ANALYSIS - COMPREHENSIVE RESULTS")
        print(f"{'='*100}")
        
        if not self.results:
            print("❌ No results to analyze")
            return
            
        # Summary table
        print(f"\n📊 CONSISTENCY COMPARISON:")
        print(f"{'Factor':<8} {'Target':<12} {'Actual':<12} {'Consistency':<12} {'Variance':<12} {'Verdict'}")
        print("-" * 80)
        
        for result in self.results:
            target_hz = 500 / result.downsampling_factor
            verdict = self._get_verdict(result.consistency_percent)
            
            print(f"{result.downsampling_factor}x"
                  f"{target_hz:>11.1f}Hz"
                  f"{result.effective_rate_hz:>11.1f}Hz"
                  f"{result.consistency_percent:>11.1f}%"
                  f"{result.std_interval_ms:>11.2f}ms"
                  f"  {verdict}")
        
        # Detailed breakdown
        print(f"\n📈 DETAILED TIMING BREAKDOWN:")
        print(f"{'Factor':<8} {'Duration':<10} {'Samples':<8} {'Avg Cycle':<12} {'URDF Time':<12} {'Processing':<12}")
        print("-" * 80)
        
        for result in self.results:
            print(f"{result.downsampling_factor}x"
                  f"{result.duration_seconds:>9.1f}s"
                  f"{result.sample_count:>7d}"
                  f"{result.avg_cycle_ms:>11.2f}ms"
                  f"{result.avg_urdf_ms:>11.2f}ms"
                  f"{result.avg_processing_ms:>11.2f}ms")
        
        # Key insights
        self._generate_insights()
        
    def _get_verdict(self, consistency: float) -> str:
        """Get verdict string based on consistency"""
        if consistency >= 90:
            return "🟢 EXCELLENT"
        elif consistency >= 80:
            return "🟡 GOOD"
        elif consistency >= 70:
            return "🟠 ACCEPTABLE"
        else:
            return "🔴 POOR"
    
    def _generate_insights(self):
        """Generate key insights from the multi-rate test"""
        
        print(f"\n🎯 KEY INSIGHTS:")
        
        if not self.results:
            return
            
        # Find best consistency
        best_result = max(self.results, key=lambda r: r.consistency_percent)
        worst_result = min(self.results, key=lambda r: r.consistency_percent)
        
        print(f"\n✅ BEST PERFORMANCE:")
        print(f"  Downsampling: {best_result.downsampling_factor}x ({best_result.effective_rate_hz:.1f}Hz)")
        print(f"  Consistency: {best_result.consistency_percent:.1f}%")
        print(f"  Variance: ±{best_result.std_interval_ms:.2f}ms")
        
        print(f"\n❌ WORST PERFORMANCE:")
        print(f"  Downsampling: {worst_result.downsampling_factor}x ({worst_result.effective_rate_hz:.1f}Hz)")
        print(f"  Consistency: {worst_result.consistency_percent:.1f}%")
        print(f"  Variance: ±{worst_result.std_interval_ms:.2f}ms")
        
        # Trend analysis
        print(f"\n📈 TREND ANALYSIS:")
        consistencies = [r.consistency_percent for r in self.results]
        factors = [r.downsampling_factor for r in self.results]
        
        if len(consistencies) >= 2:
            if consistencies[-1] > consistencies[0]:
                print(f"  📊 Consistency IMPROVES with higher downsampling (lower rates)")
                print(f"  📊 {factors[0]}x: {consistencies[0]:.1f}% → {factors[-1]}x: {consistencies[-1]:.1f}%")
            else:
                print(f"  📊 Consistency DEGRADES with higher downsampling")
        
        # Recommendation
        recommended = [r for r in self.results if r.consistency_percent >= 85]
        if recommended:
            best_rec = max(recommended, key=lambda r: r.effective_rate_hz)
            print(f"\n💡 RECOMMENDATION:")
            print(f"  Best balance: {best_rec.downsampling_factor}x downsampling ({best_rec.effective_rate_hz:.1f}Hz)")
            print(f"  Provides {best_rec.consistency_percent:.1f}% consistency with good responsiveness")
        else:
            print(f"\n⚠️  WARNING: No downsampling factor achieved >85% consistency!")
            print(f"  Consider system optimization or lower target rates")
    
    def _export_multi_rate_data(self):
        """Export comprehensive multi-rate data"""
        
        export_data = {
            "multi_rate_analysis": {
                "test_duration_seconds": self.target_duration,
                "test_timestamp": time.time(),
                "results_summary": {
                    "best_consistency": max(r.consistency_percent for r in self.results) if self.results else 0,
                    "worst_consistency": min(r.consistency_percent for r in self.results) if self.results else 0,
                    "recommended_factor": self._get_recommended_factor()
                }
            },
            "detailed_results": []
        }
        
        # Add detailed results
        for result in self.results:
            export_data["detailed_results"].append({
                "downsampling_factor": result.downsampling_factor,
                "effective_rate_hz": result.effective_rate_hz,
                "target_rate_hz": 500 / result.downsampling_factor,
                "consistency_percent": result.consistency_percent,
                "avg_interval_ms": result.avg_interval_ms,
                "std_interval_ms": result.std_interval_ms,
                "sample_count": result.sample_count,
                "duration_seconds": result.duration_seconds,
                "avg_processing_ms": result.avg_processing_ms,
                "avg_cycle_ms": result.avg_cycle_ms
            })
        
        # Save to file
        timestamp = int(time.time())
        filename = f"multi_rate_backend_analysis_{timestamp}.json"
        filepath = Path(__file__).parent / filename
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"\n📁 Multi-rate analysis exported to: {filename}")
        
        # Also save as latest
        latest_filepath = Path(__file__).parent / "latest_multi_rate_analysis.json"
        with open(latest_filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
            
    def _get_recommended_factor(self):
        """Get recommended downsampling factor"""
        if not self.results:
            return None
            
        # Find factors with >80% consistency
        good_results = [r for r in self.results if r.consistency_percent >= 80]
        
        if good_results:
            # Among good results, prefer higher rate (lower factor)
            return min(good_results, key=lambda r: r.downsampling_factor).downsampling_factor
        else:
            # If none are good, return best available
            return max(self.results, key=lambda r: r.consistency_percent).downsampling_factor


class SingleRateProfiler:
    """Single rate profiler for multi-rate testing"""
    
    def __init__(self, max_samples: int, target_duration: float):
        self.max_samples = max_samples
        self.target_duration = target_duration
        
        # Timing data
        self.send_intervals = []
        self.processing_times = []
        self.cycle_times = []
        self.urdf_times = []
        
        # State
        self.sample_count = 0
        self.is_profiling = False
        self.start_time = None
        self.actual_duration = 0
        self.last_send_time = 0
        
        # Original method reference
        self.original_update_method = None
        
    def hook_into_controller(self, urdf_manager, replay_controller):
        """Hook profiler into replay controller"""
        self.urdf_manager = urdf_manager
        self.replay_controller = replay_controller
        
        # Store original method
        self.original_update_method = replay_controller._update_visualization
        
        # Hook our profiler
        replay_controller._update_visualization = self._profile_update_cycle
        
    def start_profiling(self):
        """Start profiling"""
        self.is_profiling = True
        self.start_time = time.perf_counter()
        
    def stop_profiling(self):
        """Stop profiling"""
        self.is_profiling = False
        if self.start_time:
            self.actual_duration = time.perf_counter() - self.start_time
            
    def _profile_update_cycle(self):
        """Profile one update cycle"""
        if not self.is_profiling or self.sample_count >= self.max_samples:
            return self.original_update_method()
            
        # Check duration limit
        if self.start_time and (time.perf_counter() - self.start_time) > self.target_duration:
            return self.original_update_method()
            
        cycle_start = time.perf_counter()
        
        # Get robot data
        entry = self.replay_controller.get_current_entry()
        if not entry:
            return
            
        # Process joint configurations
        processing_start = time.perf_counter()
        joint_configs = {}
        for urdf_name in self.replay_controller.mapper.get_all_urdf_names():
            joint_config = self.replay_controller.mapper.create_joint_config_for_urdf(urdf_name, entry)
            if joint_config:
                joint_configs[urdf_name] = joint_config
        
        # Create full configuration
        full_config = self._create_full_configuration(joint_configs)
        processing_end = time.perf_counter()
        processing_time = (processing_end - processing_start) * 1000
        
        # Update URDFs
        urdf_start = time.perf_counter()
        self.urdf_manager.update_all_configurations(full_config)
        urdf_end = time.perf_counter()
        urdf_time = (urdf_end - urdf_start) * 1000
        
        cycle_end = time.perf_counter()
        cycle_time = (cycle_end - cycle_start) * 1000
        
        # Record timing data
        now = time.perf_counter()
        
        # Calculate send intervals
        if self.last_send_time > 0:
            send_interval = (now - self.last_send_time) * 1000
            self.send_intervals.append(send_interval)
        
        self.processing_times.append(processing_time)
        self.cycle_times.append(cycle_time)
        self.urdf_times.append(urdf_time)
        
        self.last_send_time = now
        self.sample_count += 1
        
    def _create_full_configuration(self, joint_configs):
        """Create full joint configuration array"""
        import numpy as np
        
        if not self.urdf_manager.filtered_joint_names:
            return None
            
        full_config = np.zeros(len(self.urdf_manager.filtered_joint_names))
        
        for urdf_name, urdf_joint_config in joint_configs.items():
            if not urdf_joint_config:
                continue
            for i, joint_name in enumerate(self.urdf_manager.filtered_joint_names):
                if joint_name.startswith(f"{urdf_name}::"):
                    actual_joint = joint_name.split("::", 1)[1]
                    if actual_joint in urdf_joint_config:
                        full_config[i] = urdf_joint_config[actual_joint]
        
        return full_config


if __name__ == "__main__":
    # Run comprehensive multi-rate test
    profiler = MultiRateBackendProfiler(target_duration_seconds=20.0)
    profiler.run_comprehensive_test([1, 3, 5, 10])
