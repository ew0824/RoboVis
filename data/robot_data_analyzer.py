"""
Robot Data Analyzer
Analyzes robot_status.data.json files to understand joint movement patterns
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from robot_data_parser import RobotDataParser
from joint_mapper import JointMapper

class RobotDataAnalyzer:
    """Analyzes robot data to understand joint movement patterns"""
    
    def __init__(self, json_file: str):
        self.json_file = json_file
        self.parser = RobotDataParser(json_file)
        self.mapper = JointMapper()
        
        # Analysis results
        self.joint_ranges = {}
        self.joint_movements = {}
        self.active_joints = {}
        self.static_joints = {}
        self.analysis_report = ""
        
    def analyze(self, movement_threshold: float = 0.1) -> Dict:
        """Perform comprehensive analysis of robot data"""
        print(f"[ANALYZER] Analyzing {self.json_file}")
        
        # Load and parse data
        self.parser.load_data()
        self.parser.parse_data(downsample_factor=1)
        
        # Analyze each part
        analysis_results = {}
        
        for part_name in self.parser.get_part_names():
            part_analysis = self._analyze_part(part_name, movement_threshold)
            analysis_results[part_name] = part_analysis
            
        # Generate comprehensive report
        self._generate_report(analysis_results, movement_threshold)
        
        return analysis_results
    
    def _analyze_part(self, part_name: str, movement_threshold: float) -> Dict:
        """Analyze a specific robot part"""
        joint_positions = self.parser.get_joint_positions_for_part(part_name)
        
        if not joint_positions:
            return {"error": "No data found"}
        
        # Convert to numpy array for analysis
        positions_array = np.array(joint_positions)  # Shape: (time_steps, num_joints)
        num_joints = positions_array.shape[1]
        
        joint_analysis = {}
        
        for joint_idx in range(num_joints):
            joint_positions_over_time = positions_array[:, joint_idx]
            
            # Calculate statistics
            min_pos = np.min(joint_positions_over_time)
            max_pos = np.max(joint_positions_over_time)
            mean_pos = np.mean(joint_positions_over_time)
            std_pos = np.std(joint_positions_over_time)
            range_pos = max_pos - min_pos
            
            # Calculate movement metrics
            position_diff = np.diff(joint_positions_over_time)
            max_movement = np.max(np.abs(position_diff))
            total_movement = np.sum(np.abs(position_diff))
            
            # Determine if joint is active
            is_active = range_pos > movement_threshold
            
            joint_analysis[f"joint_{joint_idx}"] = {
                "min_position": float(min_pos),
                "max_position": float(max_pos),
                "mean_position": float(mean_pos),
                "std_position": float(std_pos),
                "range": float(range_pos),
                "max_movement": float(max_movement),
                "total_movement": float(total_movement),
                "is_active": is_active,
                "positions": joint_positions_over_time.tolist()
            }
        
        return {
            "num_joints": num_joints,
            "num_time_steps": len(joint_positions),
            "joints": joint_analysis
        }
    
    def _generate_report(self, analysis_results: Dict, movement_threshold: float):
        """Generate comprehensive analysis report"""
        report = []
        report.append("="*80)
        report.append(f"ROBOT DATA ANALYSIS REPORT")
        report.append(f"File: {self.json_file}")
        report.append(f"Movement Threshold: {movement_threshold:.3f} radians")
        report.append("="*80)
        
        total_joints = 0
        total_active_joints = 0
        
        for part_name, part_analysis in analysis_results.items():
            if "error" in part_analysis:
                report.append(f"\n❌ {part_name}: {part_analysis['error']}")
                continue
                
            num_joints = part_analysis["num_joints"]
            num_time_steps = part_analysis["num_time_steps"]
            joints = part_analysis["joints"]
            
            # Count active joints
            active_joints = [j for j in joints.values() if j["is_active"]]
            static_joints = [j for j in joints.values() if not j["is_active"]]
            
            total_joints += num_joints
            total_active_joints += len(active_joints)
            
            report.append(f"\n📦 {part_name.upper()}")
            report.append(f"   Joints: {num_joints}")
            report.append(f"   Time Steps: {num_time_steps}")
            report.append(f"   Active Joints: {len(active_joints)}")
            report.append(f"   Static Joints: {len(static_joints)}")
            
            # Show joint details
            for joint_name, joint_data in joints.items():
                status = "🟢 ACTIVE" if joint_data["is_active"] else "🔴 STATIC"
                range_val = joint_data["range"]
                total_movement = joint_data["total_movement"]
                
                report.append(f"     {joint_name}: {status}")
                report.append(f"       Range: {range_val:.4f} rad ({np.degrees(range_val):.1f}°)")
                report.append(f"       Total Movement: {total_movement:.4f} rad")
                report.append(f"       Position: [{joint_data['min_position']:.4f}, {joint_data['max_position']:.4f}]")
        
        # Summary
        report.append(f"\n🎯 SUMMARY")
        report.append(f"   Total Joints: {total_joints}")
        report.append(f"   Active Joints: {total_active_joints}")
        report.append(f"   Static Joints: {total_joints - total_active_joints}")
        report.append(f"   Activity Rate: {total_active_joints/total_joints*100:.1f}%")
        
        # Joint mapper validation
        report.append(f"\n🔍 JOINT MAPPER VALIDATION")
        for part_name, part_analysis in analysis_results.items():
            if "error" in part_analysis:
                continue
                
            expected_joints = self.mapper.get_mapped_joints(part_name)
            actual_joints = part_analysis["num_joints"]
            
            if expected_joints:
                expected_count = len(expected_joints["joint_names"])
                status = "✅" if expected_count == actual_joints else "❌"
                report.append(f"   {part_name}: {status} Expected {expected_count}, Got {actual_joints}")
            else:
                report.append(f"   {part_name}: ❌ No mapping defined")
        
        self.analysis_report = "\n".join(report)
        
    def print_report(self):
        """Print the analysis report"""
        print(self.analysis_report)
        
    def save_report(self, output_file: str):
        """Save the analysis report to a file"""
        with open(output_file, 'w') as f:
            f.write(self.analysis_report)
        print(f"[ANALYZER] Report saved to {output_file}")
    
    def get_most_active_joints(self, top_n: int = 10) -> List[Tuple[str, str, float]]:
        """Get the most active joints across all parts"""
        if not hasattr(self, 'analysis_results'):
            return []
            
        active_joints = []
        
        for part_name, part_analysis in self.analysis_results.items():
            if "error" in part_analysis:
                continue
                
            joints = part_analysis["joints"]
            for joint_name, joint_data in joints.items():
                if joint_data["is_active"]:
                    active_joints.append((
                        part_name,
                        joint_name,
                        joint_data["total_movement"]
                    ))
        
        # Sort by total movement
        active_joints.sort(key=lambda x: x[2], reverse=True)
        
        return active_joints[:top_n]
    
    def compare_with_other_file(self, other_file: str) -> Dict:
        """Compare this analysis with another robot data file"""
        print(f"[ANALYZER] Comparing {self.json_file} with {other_file}")
        
        other_analyzer = RobotDataAnalyzer(other_file)
        other_results = other_analyzer.analyze()
        
        # Compare results
        comparison = {
            "file1": self.json_file,
            "file2": other_file,
            "differences": []
        }
        
        # Compare each part
        for part_name in set(self.analysis_results.keys()) | set(other_results.keys()):
            part1 = self.analysis_results.get(part_name, {})
            part2 = other_results.get(part_name, {})
            
            if "error" in part1 or "error" in part2:
                continue
                
            # Compare joint counts
            joints1 = part1.get("num_joints", 0)
            joints2 = part2.get("num_joints", 0)
            
            if joints1 != joints2:
                comparison["differences"].append({
                    "part": part_name,
                    "type": "joint_count",
                    "file1_value": joints1,
                    "file2_value": joints2
                })
        
        return comparison


def analyze_both_files():
    """Analyze both robot status files and generate comparison report"""
    print("="*80)
    print("ANALYZING BOTH ROBOT STATUS FILES")
    print("="*80)
    
    # Check which files exist
    files_to_analyze = []
    for file_num in [1, 2]:
        file_path = f"data/robot_status{file_num}.data.json"
        if Path(file_path).exists():
            files_to_analyze.append(file_path)
        else:
            print(f"❌ {file_path} not found")
    
    if not files_to_analyze:
        print("❌ No robot status files found!")
        return
    
    analyzers = []
    for file_path in files_to_analyze:
        analyzer = RobotDataAnalyzer(file_path)
        analyzer.analysis_results = analyzer.analyze()
        analyzer.print_report()
        analyzers.append(analyzer)
        
        # Save individual reports
        report_file = file_path.replace('.data.json', '_analysis.txt')
        analyzer.save_report(report_file)
        
        print(f"\n🔥 MOST ACTIVE JOINTS in {file_path}:")
        active_joints = analyzer.get_most_active_joints(5)
        for i, (part, joint, movement) in enumerate(active_joints, 1):
            print(f"   {i}. {part}.{joint}: {movement:.4f} rad total movement")
    
    # Compare files if we have both
    if len(analyzers) == 2:
        print("\n" + "="*80)
        print("COMPARING ROBOT STATUS FILES")
        print("="*80)
        
        comparison = analyzers[0].compare_with_other_file(files_to_analyze[1])
        
        if comparison["differences"]:
            print("🔍 DIFFERENCES FOUND:")
            for diff in comparison["differences"]:
                print(f"   {diff['part']}: {diff['type']} - File1: {diff['file1_value']}, File2: {diff['file2_value']}")
        else:
            print("✅ Files have identical structure")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    analyze_both_files()
