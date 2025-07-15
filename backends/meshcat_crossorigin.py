#!/usr/bin/env python3
"""
MeshCat URDF visualizer with cross-origin WebSocket support.
This version properly monkey-patches the WebSocket handler to allow cross-origin connections.
"""

import os
import sys
from pathlib import Path

# Import MeshCat components before patching
import meshcat.servers.zmqserver as zmqserver

# Add RoboMeshCat to path
sys.path.insert(0, str(Path(__file__).parent.parent / "external" / "RoboMeshCat" / "src"))
from robomeshcat import Scene, Robot

# Paths
root = Path(__file__).parent.parent
urdf = root / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
meshes = root / "assets/urdf/eoat_7/meshes"

# Set ROS_PACKAGE_PATH for URDF loading
os.environ["ROS_PACKAGE_PATH"] = str(root / "assets/urdf")

def patch_websocket_handler():
    """Monkey patch the WebSocketHandler to allow cross-origin connections."""
    import tornado.websocket
    
    # Patch both the zmqserver version and tornado base version
    original_check_origin = zmqserver.WebSocketHandler.check_origin
    tornado_original = tornado.websocket.WebSocketHandler.check_origin
    
    def check_origin_allow_all(self, origin):
        """Allow connections from any origin during development."""
        print(f"WebSocket connection from origin: {origin} - ALLOWED")
        return True
    
    # Replace the methods in both places
    zmqserver.WebSocketHandler.check_origin = check_origin_allow_all
    tornado.websocket.WebSocketHandler.check_origin = check_origin_allow_all
    print("WebSocket handler patched to allow cross-origin connections")
    print("Patched both zmqserver.WebSocketHandler and tornado.websocket.WebSocketHandler")

def main():
    """Load and visualize the eoat_7 URDF in MeshCat with cross-origin WebSocket support."""
    
    print("Patching WebSocket handler for cross-origin support...")
    patch_websocket_handler()
    
    print("Creating MeshCat scene...")
    # Create scene - this will automatically start the server with patched handler
    scene = Scene()
    
    print(f"Loading robot...")
    robot = Robot(urdf_path=str(urdf), mesh_folder_path=str(meshes))

    print(f"Robot loaded successfully!")
    print(f"Number of links: {len(robot._model.frames)}")
    print(f"Number of joints: {len(robot._model.joints)}")
    print(f"Number of geometry objects: {len(robot._geom_model.geometryObjects)}")
        
    scene.add_robot(robot)

    print("Robot loaded successfully")
    print("Cross-origin WebSocket connections are now allowed!")
    print("Frontend can connect from any port (e.g., port 3000)")
    print("WebSocket URL: ws://127.0.0.1:7000/ws")
    print("MeshCat viewer: http://127.0.0.1:7000")
    print("Press Ctrl+C to exit")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
