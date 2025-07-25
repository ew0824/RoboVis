"""
Robot Data Parser for Demo
Loads robot_status.data.json and extracts joint positions for robot replay
"""

import json
import numpy as np
from typing import Dict, List, Optional, Tuple

class RobotDataParser:
    """Simple robot data parser for demo purposes"""
    
    def __init__(self, json_file: str = "data/robot_status_beta.data.json"):
        self.json_file = json_file
        self.raw_data = None
        self.parsed_data = None
        self.part_info = {}
        
    def load_data(self) -> None:
        """Load the robot data JSON file"""
        print(f"[PARSER] Loading robot data from {self.json_file}")
        try:
            with open(self.json_file, 'r') as f:
                self.raw_data = json.load(f)
            print(f"[PARSER] Loaded {len(self.raw_data)} data entries")
        except Exception as e:
            print(f"[PARSER] Error loading data: {e}")
            raise
    
    def parse_data(self, downsample_factor: int = 1) -> None:
        """Parse the data and extract joint positions"""
        if self.raw_data is None:
            self.load_data()
        
        print(f"[PARSER] Parsing data with downsample factor {downsample_factor}")
        
        # Downsample the data
        downsampled_data = self.raw_data[::downsample_factor]
        print(f"[PARSER] Downsampled to {len(downsampled_data)} entries")
        
        # Parse each entry
        parsed_entries = []
        part_joint_counts = {}
        
        for entry in downsampled_data:
            parsed_entry = {
                'sequence_id': int(entry['sequenceId']),
                'timestamp_ns': int(entry['timestampNs']),
                'parts': {}
            }
            
            # Extract joint positions for each part
            for part_data in entry['parts']:
                part_name = part_data['part']
                
                # Get joint positions
                if 'position' in part_data and 'values' in part_data['position']:
                    joint_positions = part_data['position']['values']
                    parsed_entry['parts'][part_name] = joint_positions
                    
                    # Track joint counts for each part
                    if part_name not in part_joint_counts:
                        part_joint_counts[part_name] = len(joint_positions)
                    
            parsed_entries.append(parsed_entry)
        
        self.parsed_data = parsed_entries
        self.part_info = part_joint_counts
        
        print(f"[PARSER] Found parts with joint counts:")
        for part, count in part_joint_counts.items():
            print(f"  - {part}: {count} joints")
    
    def get_part_names(self) -> List[str]:
        """Get list of all robot parts"""
        return list(self.part_info.keys())
    
    def get_part_joint_count(self, part_name: str) -> int:
        """Get number of joints for a specific part"""
        return self.part_info.get(part_name, 0)
    
    def get_sequence_ids(self) -> List[int]:
        """Get list of all sequence IDs"""
        if self.parsed_data is None:
            return []
        return [entry['sequence_id'] for entry in self.parsed_data]
    
    def get_data_by_sequence_id(self, sequence_id: int) -> Optional[Dict]:
        """Get data for a specific sequence ID"""
        if self.parsed_data is None:
            return None
        
        for entry in self.parsed_data:
            if entry['sequence_id'] == sequence_id:
                return entry
        return None
    
    def get_data_by_index(self, index: int) -> Optional[Dict]:
        """Get data by index in the parsed data"""
        if self.parsed_data is None or index >= len(self.parsed_data):
            return None
        return self.parsed_data[index]
    
    def get_timeline_info(self) -> Dict:
        """Get timeline information"""
        if self.parsed_data is None:
            return {}
        
        sequence_ids = self.get_sequence_ids()
        timestamps = [entry['timestamp_ns'] for entry in self.parsed_data]
        
        return {
            'total_entries': len(self.parsed_data),
            'sequence_range': (min(sequence_ids), max(sequence_ids)),
            'timestamp_range': (min(timestamps), max(timestamps)),
            'duration_seconds': (max(timestamps) - min(timestamps)) / 1e9
        }
    
    def get_joint_positions_for_part(self, part_name: str) -> List[List[float]]:
        """Get all joint positions for a specific part as a list of lists"""
        if self.parsed_data is None:
            return []
        
        positions = []
        for entry in self.parsed_data:
            if part_name in entry['parts']:
                positions.append(entry['parts'][part_name])
        return positions
    
    def print_summary(self) -> None:
        """Print summary of parsed data"""
        if self.parsed_data is None:
            print("[PARSER] No data parsed yet")
            return
        
        timeline = self.get_timeline_info()
        print(f"\n[PARSER] === DATA SUMMARY ===")
        print(f"Total entries: {timeline['total_entries']}")
        print(f"Sequence ID range: {timeline['sequence_range']}")
        print(f"Duration: {timeline['duration_seconds']:.1f} seconds")
        print(f"Parts found: {len(self.part_info)}")
        
        for part, count in self.part_info.items():
            positions = self.get_joint_positions_for_part(part)
            if positions:
                # Show first and last positions
                first_pos = positions[0]
                last_pos = positions[-1]
                print(f"  {part} ({count} joints):")
                print(f"    First: {[f'{x:.3f}' for x in first_pos]}")
                print(f"    Last:  {[f'{x:.3f}' for x in last_pos]}")


def test_parser():
    """Test the data parser"""
    print("=== TESTING ROBOT DATA PARSER ===")
    
    # Create parser
    parser = RobotDataParser()
    
    # Load and parse data
    parser.load_data()
    parser.parse_data(downsample_factor=10)
    
    # Print summary
    parser.print_summary()
    
    # Test getting specific data
    print("\n=== TESTING DATA ACCESS ===")
    
    # Get first sequence ID
    sequence_ids = parser.get_sequence_ids()
    if sequence_ids:
        first_seq_id = sequence_ids[0]
        print(f"Testing with sequence ID: {first_seq_id}")
        
        data = parser.get_data_by_sequence_id(first_seq_id)
        if data:
            print(f"Sequence {first_seq_id} data:")
            print(f"  Timestamp: {data['timestamp_ns']}")
            print(f"  Parts: {list(data['parts'].keys())}")
            
            # Show ARM data if available
            if 'ARM' in data['parts']:
                arm_positions = data['parts']['ARM']
                print(f"  ARM positions: {[f'{x:.3f}' for x in arm_positions]}")


if __name__ == "__main__":
    test_parser()
