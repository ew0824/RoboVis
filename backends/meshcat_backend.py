#!/usr/bin/env python3
"""
MeshCat-based URDF visualizer backend using RoboMeshCat.
"""

import os
import sys
import time
from pathlib import Path

# Add the external RoboMeshCat to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "external" / "RoboMeshCat"))

try:
    from robomeshcat import Scene, Robot
    import meshcat
    import meshcat.geometry as g
    import meshcat.transformations as tf
except ImportError as e:
    print(f"Error importing RoboMeshCat: {e}")
    print("Please ensure RoboMeshCat is installed and available in external/RoboMeshCat")
    sys.exit(1)

def main():
    """Load and visualize the eoat_7 URDF in MeshCat."""
    
    # Set up paths
    workspace_root = Path(__file__).parent.parent
    urdf_path = workspace_root / "assets" / "urdf" / "eoat_7" / "urdf" / "eoat" / "eoat.urdf"
    mesh_folder = workspace_root / "assets" / "urdf" / "eoat_7" / "meshes"
    
    # Set ROS_PACKAGE_PATH to help Pinocchio resolve package:// URLs
    ros_package_path = str(workspace_root / "assets" / "urdf")
    os.environ["ROS_PACKAGE_PATH"] = ros_package_path
    
    print(f"Loading URDF from: {urdf_path}")
    print(f"Mesh folder: {mesh_folder}")
    print(f"ROS_PACKAGE_PATH: {ros_package_path}")
    
    if not urdf_path.exists():
        print(f"Error: URDF file not found at {urdf_path}")
        sys.exit(1)
    
    if not mesh_folder.exists():
        print(f"Error: Mesh folder not found at {mesh_folder}")
        sys.exit(1)
    
    try:
        # Create Scene (which includes MeshCat viewer)
        print("Creating RoboMeshCat scene...")
        scene = Scene()
        
        # Load the robot with mesh folder path
        print("Loading robot with RoboMeshCat...")
        robot = Robot(
            urdf_path=str(urdf_path),
            mesh_folder_path=str(mesh_folder)
        )
        
        print(f"Robot loaded successfully!")
        print(f"Number of links: {len(robot._model.frames)}")
        print(f"Number of joints: {len(robot._model.joints)}")
        print(f"Number of geometry objects: {len(robot._geom_model.geometryObjects)}")
        
        # Add robot to scene
        print("Adding robot to scene...")
        scene.add_robot(robot)
        
        print("Robot added to scene!")
        print("Open your browser to view the visualization.")
        print("Press Ctrl+C to exit.")
        
        # Keep the scene open
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"Error loading or displaying robot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
