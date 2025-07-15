#!/usr/bin/env python3
"""
SIMPLEST implementation of MeshCat URDF visualizer using all built in functionalities with robomeshcat.
Any modification is to accomodate for the eoat urdf structure.
"""

"""
This one does not work if we were to add another frontend that links to it. 

Meshcat.Visualizer() automatically spawns a server + a Tornado HTTP/WS server at default port.

http://127.0.0.1:7000 automatically listens to http://127.0.0.1:7000/ws (loads from the same origin and port).

Any additional frontend server runs at a different port and gets rejected by Tornado's origin check code due to the port-mismatch. Need to replace the Tornado with our own WebSocket handler?
"""


import os
from pathlib import Path
from robomeshcat import Scene, Robot

# Paths (need extra .parent since file is now in meshcat_old/ subdirectory)
root = Path(__file__).parent.parent.parent
urdf = root / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
meshes = root / "assets/urdf/eoat_7/meshes"

# Set ROS_PACKAGE_PATH for URDF loading
os.environ["ROS_PACKAGE_PATH"] = str(root / "assets/urdf")

def main():
    # Create scene and load robot
    scene = Scene()
    # print("Connect front-end to:", scene.url().replace("http", "ws") + "/ws")
    print(f"Loading robot...")
    robot = Robot(urdf_path=str(urdf), mesh_folder_path=str(meshes))

    print(f"Robot loaded successfully!")
    print(f"Number of links: {len(robot._model.frames)}")
    print(f"Number of joints: {len(robot._model.joints)}")
    print(f"Number of geometry objects: {len(robot._geom_model.geometryObjects)}")
        
    scene.add_robot(robot)

    print("Robot loaded successfully")
    print("Open your browser to view the visualization")
    print("Press Ctrl+C to exit")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
