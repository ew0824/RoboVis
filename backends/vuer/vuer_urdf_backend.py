#!/usr/bin/env python3

import asyncio
import os
from pathlib import Path

from vuer import Vuer, VuerSession
from vuer.schemas import DefaultScene, Urdf, Movable

# Create Vuer app with static root pointing to the parent directory of eoat_7
# This allows package://eoat_7/... to resolve to static/eoat_7/...
app = Vuer(port=8012, static_root="assets/urdf")

@app.spawn(start=True)
async def main(session: VuerSession):
    print("Client connected!")
    
    # Path to the original EOAT_7 URDF file with package:// syntax
    urdf_path = "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"
    
    # Check if the URDF file exists
    if not os.path.exists(urdf_path):
        print(f"ERROR: URDF file not found at {urdf_path}")
        
        # Try to find any example URDF file
        example_urdf = "assets/urdf/example.urdf"
        if os.path.exists(example_urdf):
            urdf_src = f"http://localhost:8012/static/{example_urdf}"
            print(f"Using fallback URDF: {urdf_src}")
        else:
            print("No URDF files found!")
            # Keep session alive even without URDF
            while True:
                await asyncio.sleep(1.0)
    else:
        # Use the original URDF with package:// syntax
        # The static_root is set to assets/urdf so package://eoat_7/... should resolve to static/eoat_7/...
        urdf_src = f"http://localhost:8012/static/eoat_7/urdf/eoat/eoat.urdf"
        print(f"Loading URDF from: {urdf_path}")
        print(f"URDF URL: {urdf_src}")
    
    try:
        # Create the scene with the URDF
        # The key insight: we need to pass packages parameter to help resolve package:// URLs
        session.set @ DefaultScene(
            children=[
                Movable(
                    children=[
                        Urdf(
                            key="eoat-urdf",
                            src=urdf_src,
                            position=[0, 0, 0],
                            rotation=[0, 0, 0, 1],
                            # Try different approaches for package:// resolution
                            workingPath="http://localhost:8012/static/eoat_7/",
                            packages={"eoat_7": ""}  # Empty string means use workingPath
                        )
                    ]
                )
            ]
        )
        
        print("URDF scene sent successfully!")
        
    except Exception as e:
        print(f"Error loading URDF: {e}")
    
    # Keep the connection alive
    while True:
        await asyncio.sleep(1.0)

if __name__ == "__main__":
    print("Starting Vuer URDF backend on port 8012...")
    print("Visit: http://localhost:8012")
    print("=" * 50) 