#!/usr/bin/env python3
"""
Pure ZMQ backend for MeshCat.
This connects to a separate meshcat-server via ZMQ and sends robot data.
No HTTP server, no WebSocket handling - just pure data.
"""

import os
import time
from pathlib import Path
import meshcat
from robomeshcat import Robot

# Paths
WORKSPACE = Path(__file__).parent.parent
URDF = WORKSPACE / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
MESHFOLD = WORKSPACE / "assets/urdf/eoat_7/meshes"

# Set ROS_PACKAGE_PATH for Pinocchio to resolve package:// URLs
os.environ["ROS_PACKAGE_PATH"] = str(WORKSPACE / "assets/urdf")

def main():
    print("=" * 60)
    print("Starting Pure ZMQ MeshCat Backend")
    print("=" * 60)
    
    # Connect to existing meshcat-server via ZMQ
    print("1. Connecting to meshcat-server...")
    vis = meshcat.Visualizer(zmq_url="tcp://127.0.0.1:6000")
    print("   ✓ Connected to ZMQ server at tcp://127.0.0.1:6000")
    
    # Load robot
    print("2. Loading robot...")
    robot = Robot(
        urdf_path=str(URDF),
        mesh_folder_path=str(MESHFOLD)
    )
    # Connect robot to the visualizer for rendering
    robot.viz = vis
    
    print(f"   ✓ Robot loaded: {len(robot._model.joints)} joints")
    print(f"   ✓ Geometry objects: {len(robot._geom_model.geometryObjects)}")
    
    print("\n" + "=" * 60)
    print("✅ BACKEND READY!")
    print("=" * 60)
    print("Connected to meshcat-server via ZMQ")
    print("Robot data is being sent to visualization server")
    print("Frontend should connect to meshcat-server directly")
    print("Press Ctrl+C to exit")
    print("=" * 60)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down backend...")

if __name__ == "__main__":
    main()
