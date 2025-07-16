#!/usr/bin/env python3
"""
WebSocket-only MeshCat backend that works with external frontends.
This approach avoids all cross-origin issues by only serving WebSocket connections.
"""

import os
import time
from pathlib import Path
import tornado.web
import meshcat.servers.zmqserver as zmqserver
from robomeshcat import Robot

# Paths
# WORKSPACE = Path(__file__).resolve().parents[1]
# URDF = WORKSPACE / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
# MESHFOLD = WORKSPACE / "assets/urdf/eoat_7/meshes"

WORKSPACE = Path(__file__).parent.parent
URDF = WORKSPACE / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
MESHFOLD = WORKSPACE / "assets/urdf/eoat_7/meshes"

# Set ROS_PACKAGE_PATH for Pinocchio to resolve package:// URLs
os.environ["ROS_PACKAGE_PATH"] = str(WORKSPACE / "assets/urdf")

class WebSocketOnlyBridge(zmqserver.ZMQWebSocketBridge):
    """WebSocket-only bridge that doesn't serve static files."""
    
    def make_app(self):
        """Create Tornado app with only WebSocket endpoint."""
        return tornado.web.Application([
            (r"/ws", zmqserver.WebSocketHandler, {"bridge": self}),
        ])
    
    def setup_zmq(self, zmq_url):
        """Connect to existing ZMQ server instead of creating a new one."""
        import zmq
        from tornado import ioloop
        from zmq.eventloop.zmqstream import ZMQStream
        
        # Create ZMQ context and socket
        context = zmq.Context()
        zmq_socket = context.socket(zmq.PAIR)
        
        # Connect to existing ZMQ server (don't bind)
        zmq_socket.connect(zmq_url)
        
        # Create ZMQ stream for tornado integration
        zmq_stream = ZMQStream(zmq_socket, ioloop.IOLoop.current())
        zmq_stream.on_recv(self.zmq_message_callback)
        
        return zmq_socket, zmq_stream, zmq_url
    
    def zmq_message_callback(self, frames):
        """Handle ZMQ messages."""
        # Forward messages to all connected WebSocket clients
        for websocket in self.websockets:
            try:
                for frame in frames:
                    websocket.write_message(frame, binary=True)
            except Exception as e:
                print(f"Error forwarding message to WebSocket: {e}")

def main():
    print("=" * 60)
    print("Starting WebSocket-Only MeshCat Backend")
    print("=" * 60)
    
    # 1. Create meshcat visualizer first (this starts its own ZMQ server)
    print("1. Creating MeshCat visualizer...")
    import meshcat
    vis = meshcat.Visualizer()  # Let it create its own ZMQ server
    print(f"   ✓ ZMQ server started at {vis.window.zmq_url}")
    
    # 2. Load robot and connect to visualizer
    print("2. Loading robot...")
    robot = Robot(
        urdf_path=str(URDF),
        mesh_folder_path=str(MESHFOLD)
    )
    # Connect robot to the visualizer for rendering
    robot.viz = vis
    
    print(f"   ✓ Robot loaded: {len(robot._model.joints)} joints")
    print(f"   ✓ Geometry objects: {len(robot._geom_model.geometryObjects)}")
    
    # 3. Now create WebSocket bridge using the same ZMQ URL as visualizer
    print("3. Starting WebSocket bridge on port 7001...")
    bridge = WebSocketOnlyBridge(
        zmq_url=vis.window.zmq_url,  # Use the ZMQ URL from visualizer
        host="0.0.0.0", 
        port=7001
    )
    print("   ✓ WebSocket ready at ws://127.0.0.1:7001/ws")
    
    print("\n" + "=" * 60)
    print("✅ READY!")
    print("=" * 60)
    print("WebSocket Server: ws://127.0.0.1:7001/ws")
    print("Frontend can connect from any port (e.g., 3000)")
    print("Press Ctrl+C to exit")
    print("=" * 60)
    
    try:
        bridge.run()  # This blocks and runs the server
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")

if __name__ == "__main__":
    main()
