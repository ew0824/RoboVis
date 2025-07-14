#!/usr/bin/env python3
"""
Headless MeshCat backend (WebSocket only) using RoboMeshCat.
Run: python backend_meshcat.py
Connect frontend: ws://localhost:7000/ws
"""

import os, time
from pathlib import Path
import tornado.web
import meshcat.servers.zmqserver as zmqserver
from robomeshcat import Robot

WORKSPACE = Path(__file__).resolve().parents[1]
URDF      = WORKSPACE / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
MESHFOLD  = WORKSPACE / "assets/urdf/eoat_7/meshes"

# Set ROS_PACKAGE_PATH for Pinocchio to resolve package:// URLs (otherwise can't load URDF successfully)
os.environ["ROS_PACKAGE_PATH"] = str(WORKSPACE / "assets/urdf")

# 1. Start bridge WITHOUT static routes
class WSOnly(zmqserver.ZMQWebSocketBridge):
    def make_app(self):
        return tornado.web.Application([
            (r"/ws", zmqserver.WebSocketHandler, {"bridge": self}),
        ])

bridge = WSOnly(zmq_url="tcp://127.0.0.1:6000", host="0.0.0.0", port=7000)
print("WebSocket ready at ws://localhost:7000/ws  (no HTML served)")

# 2. Load robot with MeshCat visualizer connected to same ZMQ
import meshcat
vis = meshcat.Visualizer(zmq_url="tcp://127.0.0.1:6000")
robot = Robot(
    urdf_path=str(URDF),
    mesh_folder_path=str(MESHFOLD)
)
robot.viz = vis
print("Robot loaded, %d joints" % len(robot.joint_names))

# 3. Block forever
try:
    bridge.run()
except KeyboardInterrupt:
    print("\nGood-bye")