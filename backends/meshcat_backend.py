import numpy as np
import os
import yourdfpy
import meshcat
from pathlib import Path
from meshcat import geometry

# -- Configuration --
# Simple example URDF without complex mesh dependencies
ROOT = Path(__file__).parent.parent
URDF_PATH = ROOT / "assets/urdf/example.urdf"
MESH_FOLDER_PATH = None  # No mesh folder needed for simple example
ZMQ_URL = "tcp://127.0.0.1:6000"

def main():
    # --- 1. Initialize ZMQ Connection ---
    print(f"Connecting to MeshCat server at {ZMQ_URL}...")
    vis = meshcat.Visualizer(zmq_url=ZMQ_URL)  # assumes server at 6000
    vis["robot"].delete()  # clear any previous objects at /robot

    # --- 2. Load Robot and Meshes using yourdfpy ---
    os.environ["ROS_PACKAGE_PATH"] = str(ROOT / "assets/urdf")
    print(f"Loading robot from: {URDF_PATH}")
    # Load URDF using yourdfpy
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

    # Iterate through links and visuals
    for link in robot.robot.links:
        for i, visual in enumerate(link.visuals):
            # Determine a unique path for this visual
            visual_name = visual.name or f"visual_{i}"
            path = f"robot/{link.name}/{visual_name}"

            print(f"🔧 Processing visual: {path}")


            # Create geometry object depending on type
            geom_obj = None
            if visual.geometry.mesh:  # mesh geometry
                verts = visual.geometry.mesh.vertices  # NumPy array of shape (N,3)
                faces = visual.geometry.mesh.faces     # NumPy array of shape (M,3)
                geom_obj = geometry.TriangularMeshGeometry(verts, faces)
            elif visual.geometry.box:
                sx, sy, sz = visual.geometry.box.size
                geom_obj = geometry.Box([sx, sy, sz])
            elif visual.geometry.cylinder:
                r = visual.geometry.cylinder.radius
                h = visual.geometry.cylinder.length
                geom_obj = geometry.Cylinder(h, r)  # (height, radius)
            elif visual.geometry.sphere:
                geom_obj = geometry.Sphere(visual.geometry.sphere.radius)

            # Use a simple white material
            material = geometry.MeshLambertMaterial(color=0xFFFFFF)

            # Send geometry and set transform
            vis[path].set_object(geom_obj, material)
            # Apply the visual's origin transform (if any)
            origin = visual.origin if visual.origin is not None else np.eye(4)
            vis[path].set_transform(origin)

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print(f"\nShutting down...")


if __name__ == "__main__":
    main()
