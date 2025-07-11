#!/usr/bin/env python3
"""
MeshCat-based URDF visualizer backend using RoboMeshCat.
WebSocket-only mode - no static file serving.
"""

import os
import sys
import time
from pathlib import Path

# Add the external RoboMeshCat to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "external" / "RoboMeshCat"))

from robomeshcat import Robot
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
import meshcat.servers.zmqserver as zmqserver
import subprocess
import threading
import zmq


def main():
    """Load and visualize the eoat_7 URDF in MeshCat WebSocket-only mode."""
    
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
        # Start MeshCat ZMQ server manually (WebSocket-only)
        print("Starting MeshCat ZMQ server (WebSocket-only)...")
        
        # Use fixed ports for consistency
        zmq_url = "tcp://127.0.0.1:6000"
        
        # Start the ZMQ server as a subprocess with specific URL
        server_proc, zmq_url, web_url = zmqserver.start_zmq_server_as_subprocess(zmq_url=zmq_url)
        
        print(f"ZMQ server running on: {zmq_url}")
        print(f"WebSocket server running on: {web_url}")
        print(f"Frontend should connect to WebSocket URL: ws://{web_url.split('://')[1]}")
        print("Frontend can connect to this WebSocket URL")
        
        # Create MeshCat visualizer that connects to our server
        viewer = meshcat.Visualizer(zmq_url=zmq_url)
        
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
        
        # Add robot objects directly to the viewer
        print("Adding robot objects to MeshCat...")
        for obj_name, obj in robot._objects.items():
            obj._set_vis(viewer)
            obj._set_object()
            print(f"  Added object: {obj_name}")
        
        print("Robot objects added to MeshCat!")
        print("WebSocket server is running. Frontend can connect to view the robot.")
        print("Press Ctrl+C to exit.")
        
        # Keep the server running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            server_proc.terminate()
            server_proc.wait()
            
    except Exception as e:
        print(f"Error loading or displaying robot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
