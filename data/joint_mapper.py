"""
Joint Mapper for Robot Replay Demo
Maps robot data parts to URDF joint names
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

class JointMapper:
    """Maps robot data parts to URDF joint names using real config data"""
    
    def __init__(self):
        # Real mapping based on model_manager_test_config.yaml
        self.part_to_urdf_mapping = {
            # ARM part (6 joints) - maps to infeed_and_squash_turner
            "ARM": {
                "urdf_name": "infeed_and_squash_turner",
                "joint_names": [
                    "ur_base_link_to_shoulder",
                    "shoulder_to_upper_arm",
                    "upper_arm_to_forearm",
                    "forearm_to_wrist_1",
                    "wrist_1_to_wrist_2",
                    "wrist_2_to_wrist_3"
                ]
            },
            
            # PEDESTAL part (2 joints) - maps to infeed_and_squash_turner (gantry system)
            "PEDESTAL": {
                "urdf_name": "infeed_and_squash_turner",
                "joint_names": [
                    "robot_gantry_base_to_zstage",
                    "robot_gantry_zstage_to_ystage"
                ]
            },
            
            # BAND_SEPARATOR part (5 joints) - maps to band_separator URDF
            "BAND_SEPARATOR": {
                "urdf_name": "band_separator", 
                "joint_names": [
                    "band_separator_base_to_ystage",
                    "band_separator_ystage_to_lowerjaw_zstage",
                    "band_separator_lowerjaw_zstage_to_xstage",
                    "band_separator_ystage_to_upperjaw_zstage",
                    "band_separator_upperjaw_zstage_to_xstage"
                ]
            },
            
            # EOAT parts - end effector components (part of infeed_and_squash_turner)
            "EOAT_BLADE": {
                "urdf_name": "infeed_and_squash_turner",
                "joint_names": ["tool_base_to_blade"]
            },
            
            "EOAT_GRIPPER": {
                "urdf_name": "infeed_and_squash_turner", 
                "joint_names": ["tool_base_to_left_paddle"]
            },
            
            "EOAT_EJECTOR": {
                "urdf_name": "infeed_and_squash_turner",
                "joint_names": ["tool_base_to_blade", "tool_base_to_left_paddle"]
            }
        }
        
        # Expected DOF counts from config for validation
        self.expected_dof_counts = {
            "ARM": 6,
            "PEDESTAL": 2,
            "BAND_SEPARATOR": 5,  # Config shows 5, not 4!
            "EOAT_BLADE": 1,
            "EOAT_GRIPPER": 1,
            "EOAT_EJECTOR": 2
        }
    
    def get_mapped_joints(self, part_name: str) -> Optional[Dict]:
        """Get the URDF mapping for a robot part"""
        return self.part_to_urdf_mapping.get(part_name)
    
    def get_all_urdf_names(self) -> List[str]:
        """Get all URDF names that need to be loaded"""
        urdf_names = []
        for part_data in self.part_to_urdf_mapping.values():
            urdf_name = part_data["urdf_name"]
            if urdf_name not in urdf_names:
                urdf_names.append(urdf_name)
        return urdf_names
    
    def get_joint_mapping_for_urdf(self, urdf_name: str) -> Dict[str, List[str]]:
        """Get all joints that map to a specific URDF"""
        joint_mapping = {}
        
        for part_name, part_data in self.part_to_urdf_mapping.items():
            if part_data["urdf_name"] == urdf_name:
                joint_mapping[part_name] = part_data["joint_names"]
        
        return joint_mapping
    
    def create_joint_config_for_urdf(self, urdf_name: str, robot_data: Dict) -> Dict[str, float]:
        """Create joint configuration for a specific URDF from robot data"""
        joint_config = {}
        
        # Get all parts that map to this URDF
        joint_mapping = self.get_joint_mapping_for_urdf(urdf_name)
        
        for part_name, joint_names in joint_mapping.items():
            if part_name in robot_data['parts']:
                part_positions = robot_data['parts'][part_name]
                
                # Map each joint position to its name
                for i, joint_name in enumerate(joint_names):
                    if i < len(part_positions):
                        joint_config[joint_name] = part_positions[i]
                    else:
                        joint_config[joint_name] = 0.0  # Default if not enough data
        
        return joint_config
    
    def print_mapping_summary(self):
        """Print summary of the joint mapping"""
        print("\n[MAPPER] === JOINT MAPPING SUMMARY ===")
        
        for part_name, part_data in self.part_to_urdf_mapping.items():
            urdf_name = part_data["urdf_name"]
            joint_names = part_data["joint_names"]
            
            print(f"{part_name} → {urdf_name}")
            for i, joint_name in enumerate(joint_names):
                print(f"  Joint {i}: {joint_name}")
    
    def validate_mapping(self, robot_data_parts: Dict[str, int]) -> bool:
        """Validate that the mapping matches the robot data"""
        print("\n[MAPPER] === VALIDATION ===")
        
        all_valid = True
        
        for part_name, expected_joint_count in robot_data_parts.items():
            if part_name in self.part_to_urdf_mapping:
                mapped_joints = self.part_to_urdf_mapping[part_name]["joint_names"]
                mapped_count = len(mapped_joints)
                
                if mapped_count == expected_joint_count:
                    print(f"✅ {part_name}: {mapped_count} joints (matches)")
                else:
                    print(f"❌ {part_name}: Expected {expected_joint_count}, mapped {mapped_count}")
                    all_valid = False
            else:
                print(f"❌ {part_name}: No mapping defined")
                all_valid = False
        
        return all_valid
    
    def validate_robot_data(self, robot_data: Dict) -> Tuple[bool, List[str]]:
        """Validate robot data against expected mappings and detect unrecognized parts"""
        print("\n[MAPPER] === ROBOT DATA VALIDATION ===")
        
        unrecognized_parts = []
        dof_mismatches = []
        all_valid = True
        
        if 'parts' not in robot_data:
            print("❌ No 'parts' key found in robot data")
            return False, ["Missing 'parts' key"]
        
        # Check each part in robot data
        for part_name, part_positions in robot_data['parts'].items():
            if part_name not in self.part_to_urdf_mapping:
                print(f"⚠️  UNRECOGNIZED PART: {part_name} (has {len(part_positions)} joints)")
                unrecognized_parts.append(part_name)
                all_valid = False
            else:
                # Check DOF count
                expected_dof = len(self.part_to_urdf_mapping[part_name]["joint_names"])
                actual_dof = len(part_positions)
                
                if expected_dof != actual_dof:
                    print(f"❌ {part_name}: Expected {expected_dof} DOF, got {actual_dof}")
                    dof_mismatches.append(f"{part_name}: {expected_dof} vs {actual_dof}")
                    all_valid = False
                else:
                    print(f"✅ {part_name}: {actual_dof} DOF (matches)")
        
        # Check for missing expected parts
        expected_parts = set(self.part_to_urdf_mapping.keys())
        actual_parts = set(robot_data['parts'].keys())
        missing_parts = expected_parts - actual_parts
        
        if missing_parts:
            print(f"⚠️  MISSING PARTS: {missing_parts}")
            # Don't mark as invalid - some parts might be optional
        
        print(f"\n[MAPPER] Summary: {len(unrecognized_parts)} unrecognized, {len(dof_mismatches)} DOF mismatches")
        
        return all_valid, unrecognized_parts + dof_mismatches
    
    def get_comprehensive_validation_report(self, robot_data: Dict) -> str:
        """Get a comprehensive validation report for debugging"""
        report = []
        report.append("=== COMPREHENSIVE VALIDATION REPORT ===")
        
        # Validate robot data
        is_valid, errors = self.validate_robot_data(robot_data)
        
        if is_valid:
            report.append("✅ All robot data parts are recognized and properly mapped")
        else:
            report.append("❌ Issues found:")
            for error in errors:
                report.append(f"  - {error}")
        
        # Show expected vs actual DOF counts
        report.append("\n=== DOF COMPARISON ===")
        for part_name, expected_dof in self.expected_dof_counts.items():
            if part_name in robot_data.get('parts', {}):
                actual_dof = len(robot_data['parts'][part_name])
                status = "✅" if expected_dof == actual_dof else "❌"
                report.append(f"{status} {part_name}: Expected {expected_dof}, Got {actual_dof}")
            else:
                report.append(f"⚠️  {part_name}: Missing from robot data")
        
        # Show URDF mapping summary
        report.append("\n=== URDF MAPPING SUMMARY ===")
        for urdf_name in self.get_all_urdf_names():
            parts = self.get_joint_mapping_for_urdf(urdf_name)
            total_joints = sum(len(joints) for joints in parts.values())
            report.append(f"📦 {urdf_name}: {len(parts)} parts, {total_joints} joints")
            for part_name, joint_names in parts.items():
                report.append(f"  - {part_name}: {len(joint_names)} joints")
        
        return "\n".join(report)


def test_joint_mapper():
    """Test the joint mapper"""
    print("=== TESTING JOINT MAPPER ===")
    
    # Create mapper
    mapper = JointMapper()
    
    # Print mapping summary
    mapper.print_mapping_summary()
    
    # Test validation with expected joint counts from parser
    robot_parts = {
        "ARM": 6,
        "PEDESTAL": 2, 
        "EOAT_BLADE": 1,
        "EOAT_GRIPPER": 1,
        "EOAT_EJECTOR": 2,
        "BAND_SEPARATOR": 4
    }
    
    is_valid = mapper.validate_mapping(robot_parts)
    print(f"\nMapping validation: {'✅ VALID' if is_valid else '❌ INVALID'}")
    
    # Test creating joint config
    print("\n=== TESTING JOINT CONFIG CREATION ===")
    
    # Sample robot data
    sample_data = {
        'sequence_id': 42,
        'parts': {
            'ARM': [1.054, -2.113, 1.150, -2.179, -1.048, 1.571],
            'PEDESTAL': [0.589, 2.026],
            'BAND_SEPARATOR': [-0.536, 1.914, -1.117, 0.000]
        }
    }
    
    # Test creating config for band_separator URDF
    config = mapper.create_joint_config_for_urdf("band_separator", sample_data)
    print(f"band_separator joint config: {config}")
    
    # Get all URDF names
    urdf_names = mapper.get_all_urdf_names()
    print(f"URDFs needed: {urdf_names}")


if __name__ == "__main__":
    test_joint_mapper()
