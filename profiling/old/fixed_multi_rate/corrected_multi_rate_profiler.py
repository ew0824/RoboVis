"""
Corrected Multi-Rate Backend Profiler - Fixed Data File Approach

This corrected version eliminates replay restart overhead by using complete data files
and focusing on measuring actual processing consistency.

Usage:
    python fixed_multi_rate/corrected_multi_rate_profiler.py
"""

import sys
import time
import statistics
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# Add necessary paths
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "backends" / "viser"))
sys.path.append(str(project_root / "backends" / "viser" / "replay"))
sys.path.append(str(project_root / "backends" / "viser" / "urdf"))

@dataclass
class CorrectedRateResults:
    """Results from corrected single-rate test"""
    downsampling_factor: int
    target_rate_hz: float
    
    # Actual measurements
    actual_rate_hz: float
    avg_interval_ms: float
    std_interval_ms: float
    min_interval_ms: float
    max_interval_ms: float
    
    # Robust consistency metrics
    consistency_percent: float
    interval_regularity: float
    timing_stability: float
    
    # Processing metrics
    avg_processing_ms: float
    avg_urdf_ms: float
    sample_count: int
    data_file: str


class CorrectedMultiRateProfiler:
    """
    Corrected multi-rate profiler that eliminates replay restart artifacts
    by using complete data file runs
    """
    
    def __init__(self, data_files: List[str]):
        self.data_files = data_files
        self.results = []
        
    def run_corrected_analysis(self, downsampling_factors: List[int] = [1, 3, 5, 10]):
        """Run corrected multi-rate analysis"""
        
        print(f"🔧 CORRECTED MULTI-RATE BACKEND PROFILING")
        print(f"Data files: {self.data_files}")
        print(f"Testing downsampling factors: {downsampling_factors}")
        print("="*80)
        
        for factor in downsampling_factors:
            print(f"\n🔍 TESTING {factor}x DOWNSAMPLING (Target: {500/factor:.1f}Hz)")
            
            # Test with each data file
            factor_results = []
            for data_file in self.data_files:
                try:
                    result = self._run_single_data_file_test(factor, data_file)
                    factor_results.append(result)
                    print(f"   📊 {data_file}: {result.consistency_percent:.1f}% consistency, "
                          f"{result.actual_rate_hz:.1f}Hz actual")
                except Exception as e:
                    print(f"   ❌ {data_file} failed: {e}")
                    
            # Aggregate results from multiple data files
            if factor_results:
                aggregated_result = self._aggregate_factor_results(factor, factor_results)
                self.results.append(aggregated_result)
                print(f"   ✅ Combined: {aggregated_result.consistency_percent:.1f}% consistency")
        
        # Generate corrected analysis
        self._generate_corrected_analysis()
        self._export_corrected_data()
        
    def _run_single_data_file_test(self, downsampling_factor: int, data_file: str) -> CorrectedRateResults:
        """Run single test with one data file"""
        
        from urdf_manager import SmartUrdfManager, discover_workcell_urdfs, deduplicate_urdfs
        from replay_controller import SimpleReplayController
        import viser
        
        # Use unique port
        port = 8200 + downsampling_factor + hash(data_file) % 10
        server = viser.ViserServer(host="localhost", port=port, serve_static=False)
        
        try:
            # Create URDF manager
            urdf_manager = SmartUrdfManager(server)
            urdf_configs = discover_workcell_urdfs("workcell_beta")
            urdf_configs = deduplicate_urdfs(urdf_configs)
            
            for urdf_path, urdf_name in urdf_configs:
                urdf_manager.add_urdf(urdf_path, urdf_name, load_meshes=True, load_collision_meshes=False)
            
            # Create replay controller
            full_data_path = str(project_root / "data" / data_file)
            replay_controller = SimpleReplayController(full_data_path, downsample_factor=downsampling_factor)
            
            # Create corrected profiler
            profiler = CorrectedSingleProfiler()
            profiler.hook_into_controller(urdf_manager, replay_controller)
            
            # Run complete data file once
            profiler.start_profiling()
            replay_controller.play()
            
            # Wait for completion
            start_time = time.time()
            timeout = 60  # Max 60 seconds
            
            while replay_controller.is_playing and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            profiler.stop_profiling()
            
            # Calculate results
            return self._calculate_corrected_results(profiler, downsampling_factor, data_file)
            
        finally:
            # Clean up server
            try:
                server.stop()
            except:
                pass
                
    def _calculate_corrected_results(self, profiler, downsampling_factor: int, data_file: str) -> CorrectedRateResults:
        """Calculate corrected results with robust metrics"""
        
        if not profiler.intervals:
            raise ValueError("No timing data collected")
            
        # Basic statistics
        intervals = profiler.intervals
        avg_interval = statistics.mean(intervals)
        std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
        
        # Robust consistency calculation
        target_interval = (downsampling_factor / 500.0) * 1000  # Expected interval in ms
        
        # Method 1: Coefficient of Variation based consistency
        cv_consistency = max(0, 100 - (std_interval / avg_interval * 100)) if avg_interval > 0 else 0
        
        # Method 2: Target interval based consistency  
        target_based_deviations = [abs(interval - target_interval) for interval in intervals]
        avg_deviation = statistics.mean(target_based_deviations)
        target_consistency = max(0, 100 - (avg_deviation / target_interval * 100))
        
        # Method 3: Stability analysis (consecutive interval differences)
        if len(intervals) > 1:
            consecutive_diffs = [abs(intervals[i+1] - intervals[i]) for i in range(len(intervals)-1)]
            avg_consecutive_diff = statistics.mean(consecutive_diffs)
            stability = max(0, 100 - (avg_consecutive_diff / avg_interval * 100))
        else:
            stability = 0
            
        # Final consistency: weighted average of methods
        final_consistency = (cv_consistency * 0.4 + target_consistency * 0.4 + stability * 0.2)
        
        return CorrectedRateResults(
            downsampling_factor=downsampling_factor,
            target_rate_hz=500.0 / downsampling_factor,
            actual_rate_hz=1000.0 / avg_interval,
            avg_interval_ms=avg_interval,
            std_interval_ms=std_interval,
            min_interval_ms=min(intervals),
            max_interval_ms=max(intervals),
            consistency_percent=final_consistency,
            interval_regularity=target_consistency,
            timing_stability=stability,
            avg_processing_ms=statistics.mean(profiler.processing_times) if profiler.processing_times else 0,
            avg_urdf_ms=statistics.mean(profiler.urdf_times) if profiler.urdf_times else 0,
            sample_count=len(intervals),
            data_file=data_file
        )
        
    def _aggregate_factor_results(self, factor: int, results: List[CorrectedRateResults]) -> CorrectedRateResults:
        """Aggregate results from multiple data files for same downsampling factor"""
        
        if len(results) == 1:
            return results[0]
            
        # Average the key metrics
        avg_consistency = statistics.mean([r.consistency_percent for r in results])
        avg_actual_rate = statistics.mean([r.actual_rate_hz for r in results])
        avg_interval = statistics.mean([r.avg_interval_ms for r in results])
        avg_std = statistics.mean([r.std_interval_ms for r in results])
        
        # Use first result as template, update aggregated values
        base_result = results[0]
        return CorrectedRateResults(
            downsampling_factor=factor,
            target_rate_hz=500.0 / factor,
            actual_rate_hz=avg_actual_rate,
            avg_interval_ms=avg_interval,
            std_interval_ms=avg_std,
            min_interval_ms=min([r.min_interval_ms for r in results]),
            max_interval_ms=max([r.max_interval_ms for r in results]),
            consistency_percent=avg_consistency,
            interval_regularity=statistics.mean([r.interval_regularity for r in results]),
            timing_stability=statistics.mean([r.timing_stability for r in results]),
            avg_processing_ms=statistics.mean([r.avg_processing_ms for r in results]),
            avg_urdf_ms=statistics.mean([r.avg_urdf_ms for r in results]),
            sample_count=sum([r.sample_count for r in results]),
            data_file="aggregated"
        )
        
    def _generate_corrected_analysis(self):
        """Generate corrected analysis with expected linear trend"""
        
        print(f"\n{'='*90}")
        print(f"🔧 CORRECTED MULTI-RATE ANALYSIS - FIXED RESULTS")
        print(f"{'='*90}")
        
        if not self.results:
            print("❌ No results to analyze")
            return
            
        # Sort results by downsampling factor for clear comparison
        sorted_results = sorted(self.results, key=lambda r: r.downsampling_factor)
        
        # Summary table
        print(f"\n📊 CORRECTED CONSISTENCY COMPARISON:")
        print(f"{'Factor':<8} {'Target':<12} {'Actual':<12} {'Consistency':<12} {'Variance':<12} {'Verdict'}")
        print("-" * 80)
        
        for result in sorted_results:
            verdict = self._get_corrected_verdict(result.consistency_percent)
            print(f"{result.downsampling_factor}x"
                  f"{result.target_rate_hz:>11.1f}Hz"
                  f"{result.actual_rate_hz:>11.1f}Hz"
                  f"{result.consistency_percent:>11.1f}%"
                  f"{result.std_interval_ms:>11.2f}ms"
                  f"  {verdict}")
        
        # Verify linear trend
        print(f"\n📈 TREND VERIFICATION:")
        consistencies = [r.consistency_percent for r in sorted_results]
        factors = [r.downsampling_factor for r in sorted_results]
        
        # Check if trend is approximately linear (higher downsampling = better consistency)
        if len(consistencies) >= 2:
            is_improving = all(consistencies[i] <= consistencies[i+1] for i in range(len(consistencies)-1))
            if is_improving:
                print(f"  ✅ LINEAR TREND CONFIRMED: Consistency improves with higher downsampling")
                print(f"     {factors[0]}x: {consistencies[0]:.1f}% → {factors[-1]}x: {consistencies[-1]:.1f}%")
            else:
                print(f"  ⚠️  NON-LINEAR TREND: Results still inconsistent")
        
        # Performance analysis
        self._analyze_corrected_performance()
        
    def _analyze_corrected_performance(self):
        """Analyze the corrected performance patterns"""
        
        print(f"\n🎯 CORRECTED PERFORMANCE ANALYSIS:")
        
        if not self.results:
            return
            
        # Find best and worst
        best_result = max(self.results, key=lambda r: r.consistency_percent)
        worst_result = min(self.results, key=lambda r: r.consistency_percent)
        
        print(f"\n✅ BEST PERFORMANCE:")
        print(f"  Downsampling: {best_result.downsampling_factor}x ({best_result.actual_rate_hz:.1f}Hz)")
        print(f"  Consistency: {best_result.consistency_percent:.1f}%")
        print(f"  Stability: {best_result.timing_stability:.1f}%")
        
        print(f"\n❌ WORST PERFORMANCE:")
        print(f"  Downsampling: {worst_result.downsampling_factor}x ({worst_result.actual_rate_hz:.1f}Hz)")
        print(f"  Consistency: {worst_result.consistency_percent:.1f}%")
        print(f"  Stability: {worst_result.timing_stability:.1f}%")
        
        # Expected vs actual comparison
        print(f"\n💡 EXPECTED vs ACTUAL:")
        expected_best = max(self.results, key=lambda r: r.downsampling_factor)  # Highest downsampling should be best
        expected_worst = min(self.results, key=lambda r: r.downsampling_factor)  # Lowest downsampling should be worst
        
        if best_result.downsampling_factor == expected_best.downsampling_factor:
            print(f"  ✅ EXPECTED: {expected_best.downsampling_factor}x is best performer")
        else:
            print(f"  ⚠️  UNEXPECTED: Expected {expected_best.downsampling_factor}x best, got {best_result.downsampling_factor}x")
            
        if worst_result.downsampling_factor == expected_worst.downsampling_factor:
            print(f"  ✅ EXPECTED: {expected_worst.downsampling_factor}x is worst performer")
        else:
            print(f"  ⚠️  UNEXPECTED: Expected {expected_worst.downsampling_factor}x worst, got {worst_result.downsampling_factor}x")
    
    def _get_corrected_verdict(self, consistency: float) -> str:
        """Get verdict based on consistency"""
        if consistency >= 95:
            return "🟢 EXCELLENT"
        elif consistency >= 85:
            return "🟡 GOOD"
        elif consistency >= 70:
            return "🟠 ACCEPTABLE"  
        else:
            return "🔴 POOR"
            
    def _export_corrected_data(self):
        """Export corrected analysis data"""
        
        export_data = {
            "corrected_analysis": {
                "timestamp": time.time(),
                "data_files": self.data_files,
                "methodology": "Fixed data file runs to eliminate replay restart artifacts"
            },
            "results": []
        }
        
        for result in self.results:
            export_data["results"].append({
                "downsampling_factor": result.downsampling_factor,
                "target_rate_hz": result.target_rate_hz,
                "actual_rate_hz": result.actual_rate_hz,
                "consistency_percent": result.consistency_percent,
                "avg_interval_ms": result.avg_interval_ms,
                "std_interval_ms": result.std_interval_ms,
                "timing_stability": result.timing_stability,
                "sample_count": result.sample_count
            })
        
        # Export to fixed_multi_rate directory
        timestamp = int(time.time())
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        
        filename = f"corrected_multi_rate_analysis_{timestamp}.json"
        filepath = results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        print(f"\n📁 Corrected analysis exported to: {filepath}")


class CorrectedSingleProfiler:
    """Simplified single profiler for corrected analysis"""
    
    def __init__(self):
        self.intervals = []
        self.processing_times = []
        self.urdf_times = []
        
        self.is_profiling = False
        self.last_time = 0
        self.original_update_method = None
        
    def hook_into_controller(self, urdf_manager, replay_controller):
        """Hook into controller"""
        self.urdf_manager = urdf_manager
        self.replay_controller = replay_controller
        
        self.original_update_method = replay_controller._update_visualization
        replay_controller._update_visualization = self._profile_update
        
    def start_profiling(self):
        """Start profiling"""
        self.is_profiling = True
        self.last_time = time.perf_counter()
        
    def stop_profiling(self):
        """Stop profiling"""
        self.is_profiling = False
        
    def _profile_update(self):
        """Profile single update"""
        if not self.is_profiling:
            return self.original_update_method()
            
        now = time.perf_counter()
        
        # Record interval (skip first measurement)
        if self.last_time > 0:
            interval_ms = (now - self.last_time) * 1000
            self.intervals.append(interval_ms)
            
        # Time the actual update
        processing_start = time.perf_counter()
        
        # Execute original update
        entry = self.replay_controller.get_current_entry()
        if entry:
            joint_configs = {}
            for urdf_name in self.replay_controller.mapper.get_all_urdf_names():
                joint_config = self.replay_controller.mapper.create_joint_config_for_urdf(urdf_name, entry)
                if joint_config:
                    joint_configs[urdf_name] = joint_config
            
            # Create and apply configuration
            full_config = self._create_full_configuration(joint_configs)
            
            urdf_start = time.perf_counter()
            self.urdf_manager.update_all_configurations(full_config)
            urdf_end = time.perf_counter()
            
            processing_end = time.perf_counter()
            
            self.processing_times.append((processing_end - processing_start) * 1000)
            self.urdf_times.append((urdf_end - urdf_start) * 1000)
        
        self.last_time = now
        
    def _create_full_configuration(self, joint_configs):
        """Create full configuration array"""
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
    # Check available data files
    data_dir = project_root / "data"
    available_files = []
    
    for filename in ["robot_status1.data.json", "robot_status2.data.json"]:
        if (data_dir / filename).exists():
            available_files.append(filename)
    
    if not available_files:
        print("❌ No data files found in data/ directory")
        print("Looking for: robot_status1.data.json, robot_status2.data.json")
        exit(1)
        
    print(f"📊 Using data files: {available_files}")
    
    # Run corrected profiler
    profiler = CorrectedMultiRateProfiler(available_files)
    profiler.run_corrected_analysis([1, 3, 5, 10])
