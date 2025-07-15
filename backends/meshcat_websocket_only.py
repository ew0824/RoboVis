#!/usr/bin/env python3
"""
Same-origin MeshCat setup: serve custom frontend from MeshCat's own HTTP server.
This completely avoids cross-origin issues by serving everything from the same port.
"""

import os
import shutil
from pathlib import Path
from robomeshcat import Robot
import meshcat

# Paths
WORKSPACE = Path(__file__).parent.parent
URDF = WORKSPACE / "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
MESHFOLD = WORKSPACE / "assets/urdf/eoat_7/meshes"
FRONTEND_DIST = WORKSPACE / "frontends/meshcat/dist"
FRONTEND_CUSTOM = WORKSPACE / "frontends/meshcat/index_crossorigin.html"

# Set ROS_PACKAGE_PATH for Pinocchio to resolve package:// URLs
os.environ["ROS_PACKAGE_PATH"] = str(WORKSPACE / "assets/urdf")

def main():
    print("=" * 60)
    print("Starting Same-Origin MeshCat Setup")
    print("=" * 60)
    
    # 1. Create standard MeshCat visualizer (HTTP + WebSocket on same port)
    print("1. Creating MeshCat visualizer...")
    vis = meshcat.Visualizer()
    web_url = vis.window.web_url
    print(f"   ✓ MeshCat server started at {web_url}")
    print(f"   ✓ WebSocket available at {web_url.replace('http', 'ws')}/ws")
    
    # 2. Load robot
    print("2. Loading robot...")
    robot = Robot(
        urdf_path=str(URDF),
        mesh_folder_path=str(MESHFOLD)
    )
    # Connect robot to the visualizer for rendering
    robot.viz = vis
    
    print(f"   ✓ Robot loaded: {len(robot._model.joints)} joints")
    print(f"   ✓ Geometry objects: {len(robot._geom_model.geometryObjects)}")
    
    # 3. Copy our custom frontend to MeshCat's static directory
    print("3. Setting up custom frontend...")
    
    # Find MeshCat's static directory
    import meshcat.servers.zmqserver as zmqserver
    static_dir = Path(zmqserver.__file__).parent / "static"
    
    if FRONTEND_DIST.exists():
        # Copy built JS files
        for js_file in FRONTEND_DIST.glob("*.js"):
            shutil.copy2(js_file, static_dir / js_file.name)
            print(f"   ✓ Copied {js_file.name}")
    
    if FRONTEND_CUSTOM.exists():
        # Copy custom HTML file
        shutil.copy2(FRONTEND_CUSTOM, static_dir / "custom.html")
        print(f"   ✓ Copied custom.html")
    
    print("\n" + "=" * 60)
    print("✅ READY!")
    print("=" * 60)
    print(f"MeshCat Server: {web_url}")
    print(f"Default viewer: {web_url}/static/")
    print(f"Custom frontend: {web_url}/static/custom.html")
    print(f"WebSocket: {web_url.replace('http', 'ws')}/ws")
    print("Same-origin setup - no cross-origin issues!")
    print("Press Ctrl+C to exit")
    print("=" * 60)
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")

if __name__ == "__main__":
    main()
