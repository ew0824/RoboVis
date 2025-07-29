"""
Telemetry-enabled Viser URDF robot visualizer for performance benchmarking.
Launch: python benchmarks/viser_push_bench.py --urdf_path assets/urdf/example.urdf

This version adds telemetry logging to measure performance characteristics.
"""

from __future__ import annotations

import time
import asyncio
import threading
import websockets
from typing import Literal, Optional, Set
import msgpack  # For telemetry message encoding

import numpy as np
import tyro
from robot_descriptions.loaders.yourdfpy import load_robot_description
from yourdfpy import URDF

import viser
from viser.extras import ViserUrdf

DEFAULT_URDF_PATH = "assets/urdf/example.urdf"
DEFAULT_URDF_PATH = "assets/urdf/eoat_7/urdf/eoat/eoat.urdf"

# Global telemetry counter and timing
seq_counter = 0
last_telemetry_time = time.perf_counter()

# WebSocket telemetry clients
telemetry_clients: Set[websockets.WebSocketServerProtocol] = set()

async def handle_telemetry_client(websocket):
    """Handle new telemetry WebSocket connections."""
    connect_time = time.perf_counter()
    telemetry_clients.add(websocket)
    # print(f"[TELEMETRY-DEBUG] Client connected from {websocket.remote_address} at {connect_time}")
    print(f"[TELEMETRY] Client connected from {websocket.remote_address}, total clients: {len(telemetry_clients)}")
    
    try:
        # Keep connection alive and handle disconnection
        # print(f"[TELEMETRY-DEBUG] Waiting for client {websocket.remote_address} to close...")
        await websocket.wait_closed()
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        # print(f"[TELEMETRY-DEBUG] Client {websocket.remote_address} closed after {duration:.2f} seconds")
    except websockets.exceptions.ConnectionClosed as e:
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        # print(f"[TELEMETRY-DEBUG] Client {websocket.remote_address} connection closed exception after {duration:.2f}s: {e}")
    except Exception as e:
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        # print(f"[TELEMETRY-DEBUG] Client {websocket.remote_address} unexpected error after {duration:.2f}s: {e}")
    finally:
        telemetry_clients.discard(websocket)
        # print(f"[TELEMETRY] Client disconnected, remaining clients: {len(telemetry_clients)}")

def start_telemetry_server():
    """Start the telemetry WebSocket server in a background thread."""
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def server_main():
            print("[TELEMETRY] Starting WebSocket server on ws://0.0.0.0:8081")
            async with websockets.serve(handle_telemetry_client, "0.0.0.0", 8081):
                print("[TELEMETRY] WebSocket server ready for connections")
                # Keep server running
                await asyncio.Future()  # Run forever
        
        try:
            loop.run_until_complete(server_main())
        except Exception as e:
            print(f"[TELEMETRY] WebSocket server error: {e}")
    
    # Start server in daemon thread
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(0.1)  # Give server time to start

def send_telemetry_to_clients(payload_bytes: bytes):
    """Send telemetry data to all connected WebSocket clients."""
    if not telemetry_clients:
        return
    
    # Send to all clients, remove disconnected ones
    disconnected = set()
    
    for client in telemetry_clients.copy():
        try:
            # Schedule sending in a thread-safe way
            def send_task(client_ref=client, data=payload_bytes):
                asyncio.create_task(client_ref.send(data))
            
            if hasattr(client, 'loop') and client.loop:
                client.loop.call_soon_threadsafe(send_task)
            else:
                # Fallback - skip this client
                disconnected.add(client)
        except Exception as e:
            print(f"[TELEMETRY] Error sending to client {client.remote_address}: {e}")
            disconnected.add(client)
    
    # Clean up disconnected clients
    if disconnected:
        telemetry_clients.difference_update(disconnected)

def publish_telemetry(cfg: np.ndarray) -> None:
    """Publish telemetry with performance metrics."""
    global seq_counter, last_telemetry_time
    seq_counter += 1
    
    current_time = time.perf_counter()
    timestamp_ns = time.perf_counter_ns()
    
    # Calculate time since last telemetry event
    dt = current_time - last_telemetry_time
    hz = 1.0 / dt if dt > 0 else 0.0
    last_telemetry_time = current_time
    
    # Create telemetry payload
    payload = {
        "seq": seq_counter,
        "ns": timestamp_ns,
        "nq": int(cfg.shape[0]),
        "hz": round(hz, 1),
    }
    
    # Encode payload for WebSocket use
    try:
        packed = msgpack.packb(payload, use_bin_type=True)
    except Exception as e:
        print(f"[TELEMETRY] Msgpack encoding error: {e}")
        return
    
    # Send to WebSocket clients
    send_telemetry_to_clients(packed)
    
    # Log to console with rate information
    print(f"[TELEMETRY] seq={seq_counter}, ts={timestamp_ns}, nq={cfg.shape[0]}, rate={hz:.1f}Hz, bytes={len(packed)}")

  
def create_robot_control_sliders(
    server: viser.ViserServer, viser_urdf: ViserUrdf
) -> tuple[list[viser.GuiInputHandle[float]], list[float]]:
    """Create slider for each joint of the robot. We also update robot model
    when slider moves and publish telemetry data."""
    slider_handles: list[viser.GuiInputHandle[float]] = []
    initial_config: list[float] = []
    for joint_name, (
        lower,
        upper,
    ) in viser_urdf.get_actuated_joint_limits().items():
        lower = lower if lower is not None else -np.pi
        upper = upper if upper is not None else np.pi
        initial_pos = 0.0 if lower < -0.1 and upper > 0.1 else (lower + upper) / 2.0
        slider = server.gui.add_slider(
            label=joint_name,
            min=lower,
            max=upper,
            step=1e-3,
            initial_value=initial_pos,
        )
        
        def _on_update(_: object, *, _slider_handles=slider_handles) -> None:
            # Collect values from *all* sliders (avoid closure bug on loop var)
            cfg = np.array([s.value for s in _slider_handles], dtype=np.float32)
            viser_urdf.update_cfg(cfg)
            publish_telemetry(cfg)  # Add telemetry logging
            
        slider.on_update(_on_update)
        slider_handles.append(slider)
        initial_config.append(initial_pos)
    return slider_handles, initial_config


def main(
    urdf_path: str = DEFAULT_URDF_PATH,
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
) -> None:

    ########
    # 1. Start a websocket only Viser server (no static file handler)
    ########
    server = viser.ViserServer(
        host="0.0.0.0",
        port=8080, 
        serve_static=False, # this doesn't do anything
    )

    ########
    # 1.5. Initialize telemetry system
    ########
    start_telemetry_server()
    print("[TELEMETRY] Telemetry system initialized with WebSocket server")

    ########
    # 2. Load URDF
    ########
    urdf = URDF.load(
        urdf_path,
        load_meshes=load_meshes,
        build_scene_graph=load_meshes,
        load_collision_meshes=load_collision_meshes,
        build_collision_scene_graph=load_collision_meshes,
    )
    viser_urdf = ViserUrdf(
        server,
        urdf_or_path=urdf,
        load_meshes=load_meshes,
        load_collision_meshes=load_collision_meshes,
        collision_mesh_color_override=(1.0, 0.0, 0.0, 0.5), # this makes collision meshes red
    )

    ########
    # 3. [OPTIONAL] - Create sliders in GUI that help us move the robot joints.
    ########
    # Create sliders in GUI that help us move the robot joints.
    with server.gui.add_folder("Joint position control"):
        (slider_handles, initial_config) = create_robot_control_sliders(
            server, viser_urdf
        )

    # Add visibility checkboxes.
    with server.gui.add_folder("Visibility"):
        show_meshes_cb = server.gui.add_checkbox(
            "Show meshes",
            viser_urdf.show_visual,
        )
        show_collision_meshes_cb = server.gui.add_checkbox(
            "Show collision meshes", viser_urdf.show_collision
        )

    @show_meshes_cb.on_update
    def _(_):
        viser_urdf.show_visual = show_meshes_cb.value

    @show_collision_meshes_cb.on_update
    def _(_):
        viser_urdf.show_collision = show_collision_meshes_cb.value

    # Hide checkboxes if meshes are not loaded.
    show_meshes_cb.visible = load_meshes
    show_collision_meshes_cb.visible = load_collision_meshes

    # Set initial robot configuration.
    cfg0 = np.array(initial_config, dtype=np.float32)
    viser_urdf.update_cfg(cfg0)
    publish_telemetry(cfg0)  # Log initial telemetry

    # Create grid.
    trimesh_scene = viser_urdf._urdf.scene or viser_urdf._urdf.collision_scene
    server.scene.add_grid(
        "/grid",
        width=2,
        height=2,
        position=(
            0.0,
            0.0,
            # Get the minimum z value of the trimesh scene.
            trimesh_scene.bounds[0, 2] if trimesh_scene is not None else 0.0,
        ),
    )

    # Create joint reset button.
    reset_button = server.gui.add_button("Reset")

    @reset_button.on_click
    def _(_):
        for s, init_q in zip(slider_handles, initial_config):
            s.value = init_q

    print(f"[TELEMETRY] Backend started with telemetry logging enabled")
    
    # Sleep forever.
    while True:
        time.sleep(10.0)


if __name__ == "__main__":
    tyro.cli(main)
