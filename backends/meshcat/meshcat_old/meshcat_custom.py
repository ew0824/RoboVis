import time
import os
from pathlib import Path
import numpy as np
import zmq
import msgpack
import yourdfpy

# -- Configuration --
# Simple example URDF without complex mesh dependencies
ROOT = Path(__file__).parent.parent
URDF_PATH = ROOT / "assets/urdf/example.urdf"
MESH_FOLDER_PATH = None  # No mesh folder needed for simple example
ZMQ_URL = "tcp://127.0.0.1:6000"

def send_command(socket, command, path, data=None):
    """
    Helper function to pack and send a command to the MeshCat ZMQ server.
    Uses the correct 3-frame ZMQ protocol expected by meshcat-server.
    """
    # 3-frame ZMQ protocol: [command_utf8, path_utf8, data]
    msg = [
        command.encode('utf-8'),  # Frame 1: command
        path.encode('utf-8'),     # Frame 2: path  
    ]
    if data is not None:
        if isinstance(data, bytes):
            # For delete command - send raw bytes
            msg.append(data)
        else:  
            # For other commands - msgpack the data
            msg.append(msgpack.packb(data, use_bin_type=True))
    
    socket.send_multipart(msg)
    response = socket.recv()
    print(f"   ZMQ Response: {response.decode()}")

def main():
    print("🤖 Starting URDF Backend...")

    # --- 1. Initialize ZMQ Connection ---
    print(f"Connecting to MeshCat server at {ZMQ_URL}...")
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(ZMQ_URL)
    print("✅ Connected successfully!")

    # --- 2. Load Robot and Meshes using yourdfpy ---
    os.environ["ROS_PACKAGE_PATH"] = str(ROOT / "assets/urdf")
    print(f"Loading robot from: {URDF_PATH}")
    
    try:
        # For debugging, use a simple URDF first if you have one!
        # URDF_PATH = "path/to/simple_primitives.urdf" 
        robot = yourdfpy.URDF.load(URDF_PATH, load_meshes=True)
        print("✅ Robot loaded successfully!")
    except Exception as e:
        print(f"❌ Error loading robot: {e}")
        return

    # --- 3. Send Robot Geometry to MeshCat ---
    print("Sending robot geometry to the visualizer...")
    robot_path_prefix = "/ROBOT"
    
    # Clear existing robot (3-frame ZMQ protocol - delete needs empty data frame)
    send_command(socket, "delete", robot_path_prefix, b"")

    geometry_count = 0
    for link in robot.robot.links:
        for i, visual in enumerate(link.visuals):
            # Create a unique path for each visual element
            # Use index if visual name is None
            visual_name = visual.name if visual.name is not None else f"visual_{i}"
            mesh_path = f"{robot_path_prefix}/{link.name}/{visual_name}"
            
            print(f"🔧 Processing visual: {mesh_path}")
            
            geometry_data = None
            geom = visual.geometry
            
            if geom.mesh:
                print(f"   📁 Mesh geometry detected: {geom.mesh.filename}")
                # ✅ FIX: Create the correctly formatted dictionary for a mesh
                try:
                    vertices = geom.mesh.vertices.astype(np.float32).T
                    faces = geom.mesh.faces.astype(np.uint32).T
                    geometry_data = {
                        'type': 'TriangleMeshGeometry',
                        'vertices': vertices,
                        'faces': faces
                    }
                except Exception as e:
                    print(f"   ❌ Error processing mesh data: {e}")
                    continue

            elif geom.box:
                print(f"   📦 Box geometry: {geom.box.size}")
                geometry_data = {
                    'type': 'BoxGeometry',
                    'width': float(geom.box.size[0]),
                    'height': float(geom.box.size[1]),
                    'depth': float(geom.box.size[2])
                }
            elif geom.cylinder:
                print(f"   🛢️  Cylinder geometry: r={geom.cylinder.radius}, l={geom.cylinder.length}")
                geometry_data = {
                    'type': 'CylinderGeometry',
                    'radiusTop': float(geom.cylinder.radius),
                    'radiusBottom': float(geom.cylinder.radius),
                    'height': float(geom.cylinder.length)
                }
            elif geom.sphere:
                print(f"   🌐 Sphere geometry: r={geom.sphere.radius}")
                geometry_data = {
                    'type': 'SphereGeometry',
                    'radius': float(geom.sphere.radius)
                }
            
            if geometry_data:
                # Create proper MeshCat object data (for ZMQ frame 3)
                import uuid
                geom_uuid = str(uuid.uuid4())
                mat_uuid = str(uuid.uuid4())
                obj_uuid = str(uuid.uuid4())
                
                object_data = {
                    "metadata": {"version": 4.5, "type": "Object"},
                    "geometries": [{
                        "uuid": geom_uuid,
                        **geometry_data
                    }],
                    "materials": [{
                        "uuid": mat_uuid,
                        "type": "MeshLambertMaterial",
                        "color": 0xffffff,  # White
                        "emissive": 0,
                        "side": 2,
                        "depthFunc": 3,
                        "depthTest": True,
                        "depthWrite": True
                    }],
                    "object": {
                        "uuid": obj_uuid,
                        "type": "Mesh",
                        "geometry": geom_uuid,
                        "material": mat_uuid
                    }
                }
                
                # Send with correct 3-frame protocol
                send_command(socket, "set_object", mesh_path, object_data)
                
                # Set the initial transform (origin)
                if visual.origin is not None:
                    transform_matrix = visual.origin.flatten().tolist()
                else:
                    # Use identity transform if no origin specified
                    transform_matrix = np.eye(4).flatten().tolist()
                
                # Send transform with correct 3-frame protocol
                send_command(socket, "set_transform", mesh_path, transform_matrix)

                geometry_count += 1
                print(f"   ✅ Sent geometry and initial transform to MeshCat")

    print(f"\n✅ Robot geometry sent! ({geometry_count} geometries processed)")

    # --- 4. Animation Loop ---
    # (Your animation loop looks good, but let's get static display first)
    print("Displaying static robot. Press Ctrl+C to exit.")
    try:
        # Keep the script alive to see the result
        while True:
            time.sleep(1)
            # You can add your animation logic back in here later!
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        socket.close()
        context.term()
        print("Backend shut down cleanly.")

if __name__ == "__main__":
    main()
