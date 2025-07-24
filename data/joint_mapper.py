"""
Joint Mapper for Robot Replay Demo
Maps robot data parts to URDF joint names
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

class JointMapper:
    """Maps robot data parts to URDF joint names for demo"""
    
    def __init__(self):
        # Hardcoded mapping for demo - adjust these by trial and error
        self.part_to_urdf_mapping = {
            # ARM part (6 joints) - likely maps to infeed_and_squash_turner
            "ARM": {
                "urdf_name": "infeed_and_squash_turner",
                "joint_names": [
                    "scara_arm_1_joint",
                    "scara_arm_2_joint", 
                    "scara_eoat_joint",
                    "scara_arm_1_to_scara_arm_2_joint",
                    "scara_arm_2_to_scara_eoat_joint",
                    "scara_eoat_to_scara_tool_joint"
                ]
            },
            
            # PEDESTAL part (2 joints) - likely gantry system
            "PEDESTAL": {
                "urdf_name": "robot_gantry",
                "joint_names": [
                    "robot_gantry_xstage_joint",
                    "robot_gantry_ystage_joint"
                ]
            },
            
            # BAND_SEPARATOR part (4 joints) - maps to band_separator URDF
            "BAND_SEPARATOR": {
                "urdf_name": "band_separator", 
                "joint_names": [
                    "band_separator_base_to_ystage",
                    "band_separator_ystage_to_zstage",
                    "band_separator_zstage_to_xstage",
                    "band_separator_extra_joint"  # 4th joint - might need adjustment
                ]
            },
            
            # EOAT parts - end effector components
            "EOAT_BLADE": {
                "urdf_name": "eoat_blade",
                "joint_names": ["blade_actuator_joint"]
            },
            
            "EOAT_GRIPPER": {
                "urdf_name": "eoat_gripper", 
                "joint_names": ["gripper_joint"]
            },
            
            "EOAT_EJECTOR": {
                "urdf_name": "eoat_ejector",
                "joint_names": ["ejector_joint_1", "ejector_joint_2"]
            }
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
