"""
Enhanced telemetry-enabled Viser URDF robot visualizer with optional stress testing loop.
This version includes both manual sliders AND automated high-frequency joint driving.

Launch: 
    # Normal mode (sliders only):
    python benchmarks/viser_push_bench_with_stress_testing.py
    
    # Stress testing mode (automated driving):
    python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 240 --stress-joints 4
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
    """Handle new telemetry WebSocket connections and ping/pong for latency measurement."""
    connect_time = time.perf_counter()
    telemetry_clients.add(websocket)
    print(f"[TELEMETRY] Client connected from {websocket.remote_address}, total clients: {len(telemetry_clients)}")
    
    try:
        # Listen for ping messages from client for latency measurement
        async for message in websocket:
            try:
                # print(f"[TELEMETRY] Received message from client: {type(message)}, length: {len(message) if hasattr(message, '__len__') else 'N/A'}") # Debug: uncomment to see all messages
                
                # Try to decode as msgpack ping message
                data = msgpack.unpackb(message)
                # print(f"[TELEMETRY] Decoded message: {data}") # Debug: uncomment to see decoded messages
                
                if isinstance(data, dict) and data.get("type") == "ping":
                    # print(f"[PING] Received ping from client: {data}") # Debug: uncomment to see pings
                    # Echo back the ping as a pong with the same client timestamp
                    pong_response = {
                        "type": "pong",
                        "client_timestamp": data.get("client_timestamp"),
                        "server_timestamp": time.perf_counter_ns()
                    }
                    pong_bytes = msgpack.packb(pong_response, use_bin_type=True)
                    await websocket.send(pong_bytes)
                    # print(f"[PONG] Sent pong response: {pong_response}") # Debug: uncomment to see pong responses
            except Exception as e:
                print(f"[TELEMETRY] Error processing message: {e}")
                
    except websockets.exceptions.ConnectionClosed as e:
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        print(f"[TELEMETRY] Client {websocket.remote_address} disconnected after {duration:.1f}s")
    except Exception as e:
        disconnect_time = time.perf_counter()
        duration = disconnect_time - connect_time
        print(f"[TELEMETRY] Client {websocket.remote_address} error: {e}")
    finally:
        telemetry_clients.discard(websocket)
        print(f"[TELEMETRY] Removed client, remaining: {len(telemetry_clients)}")

def start_telemetry_server():
    """Start the telemetry WebSocket server in a background thread."""
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def server_main():
            print("[TELEMETRY] Starting WebSocket server on ws://0.0.0.0:8081")
            async with websockets.serve(handle_telemetry_client, "0.0.0.0", 8081):
                print("[TELEMETRY] WebSocket server ready for connections")
                await asyncio.Future()  # Run forever
        
        try:
            loop.run_until_complete(server_main())
        except Exception as e:
            print(f"[TELEMETRY] WebSocket server error: {e}")
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(0.1)

def send_telemetry_to_clients(payload_bytes: bytes):
    """Send telemetry data to all connected WebSocket clients."""
    if not telemetry_clients:
        return
    
    disconnected = set()
    for client in telemetry_clients.copy():
        try:
            def send_task(client_ref=client, data=payload_bytes):
                asyncio.create_task(client_ref.send(data))
            
            if hasattr(client, 'loop') and client.loop:
                client.loop.call_soon_threadsafe(send_task)
            else:
                disconnected.add(client)
        except Exception as e:
            print(f"[TELEMETRY] Error sending to client {client.remote_address}: {e}")
            disconnected.add(client)
    
    if disconnected:
        telemetry_clients.difference_update(disconnected)

def publish_telemetry(cfg: np.ndarray) -> None:
    """Publish telemetry with performance metrics."""
    global seq_counter, last_telemetry_time
    seq_counter += 1
    
    current_time = time.perf_counter()
    timestamp_ns = time.perf_counter_ns()
    
    dt = current_time - last_telemetry_time
    hz = 1.0 / dt if dt > 0 else 0.0
    last_telemetry_time = current_time
    
    payload = {
        "seq": seq_counter,
        "ns": timestamp_ns,
        "nq": int(cfg.shape[0]),
        "hz": round(hz, 1),
    }
    
    try:
        packed = msgpack.packb(payload, use_bin_type=True)
    except Exception as e:
        print(f"[TELEMETRY] Msgpack encoding error: {e}")
        return
    
    send_telemetry_to_clients(packed)
    
    # Only print occasionally to avoid console flooding
    if seq_counter % 50 == 0 or hz < 10:  # Print every 50th message or low frequency
        print(f"[TELEMETRY] seq={seq_counter}, ts={timestamp_ns}, nq={cfg.shape[0]}, rate={hz:.1f}Hz, bytes={len(packed)}")

# Stress testing loop for high-frequency testing
async def stress_testing_loop(
    viser_urdf: ViserUrdf,
    nq: int,
    hz: float = 250.0,
    amplitude: float = 0.5,
    wave_freq: float = 0.5,
):
    """Generate high-frequency synthetic joint movements for stress testing."""
    print(f"🚀 [STRESS] Starting high-frequency joint driver:")
    print(f"   Joints: {nq}")
    print(f"   Frequency: {hz:.1f} Hz")
    print(f"   Amplitude: ±{amplitude:.2f} rad")
    print(f"   Wave frequency: {wave_freq:.2f} Hz")
    print()
    
    period = 1.0 / hz
    phases = np.linspace(0, 2*np.pi, nq, endpoint=False)
    t0 = time.perf_counter()
    msg_count = 0
    last_stats = t0
    
    while True:
        loop_start = time.perf_counter()
        
        # Generate sinusoidal joint motion
        t = loop_start - t0
        q = amplitude * np.sin(2*np.pi*wave_freq*t + phases)
        
        # Update robot and publish telemetry
        viser_urdf.update_cfg(q.astype(np.float32))
        publish_telemetry(q)
        msg_count += 1
        
        # Print statistics every 10 seconds
        if loop_start - last_stats >= 10.0:
            elapsed = loop_start - t0
            avg_hz = msg_count / elapsed if elapsed > 0 else 0
            print(f"🔥 [STRESS] {msg_count:,} updates | {elapsed:.1f}s | {avg_hz:.1f} Hz avg | Target: {hz:.1f} Hz")
            last_stats = loop_start
        
        # Sleep to maintain frequency
        loop_end = time.perf_counter()
        sleep_time = period - (loop_end - loop_start)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

def create_robot_control_sliders(
    server: viser.ViserServer, viser_urdf: ViserUrdf
) -> tuple[list[viser.GuiInputHandle[float]], list[float]]:
    """Create slider for each joint of the robot."""
    slider_handles: list[viser.GuiInputHandle[float]] = []
    initial_config: list[float] = []
    for joint_name, (lower, upper) in viser_urdf.get_actuated_joint_limits().items():
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
            cfg = np.array([s.value for s in _slider_handles], dtype=np.float32)
            viser_urdf.update_cfg(cfg)
            publish_telemetry(cfg)
            
        slider.on_update(_on_update)
        slider_handles.append(slider)
        initial_config.append(initial_pos)
    return slider_handles, initial_config

def main(
    urdf_path: str = DEFAULT_URDF_PATH,
    load_meshes: bool = True,
    load_collision_meshes: bool = True,
    # Stress testing loop options
    stress: bool = False,
    stress_hz: float = 240.0,
    stress_amplitude: float = 0.4,
    stress_wave_freq: float = 0.5,
    stress_joints: Optional[int] = None,
) -> None:
    """
    Main function with optional stress testing loop for performance testing.
    
    Args:
        stress: Enable high-frequency automated joint driving
        stress_hz: Frequency of automated updates (Hz)
        stress_amplitude: Joint movement amplitude (radians)
        stress_wave_freq: Frequency of sine wave motion (Hz)
        stress_joints: Number of joints to drive (None = use all available)
    """

    # Start Viser server
    server = viser.ViserServer(
        host="0.0.0.0",
        port=8080, 
        serve_static=False,
    )

    # Initialize telemetry system
    start_telemetry_server()
    print("[TELEMETRY] Telemetry system initialized with WebSocket server")

    # Load URDF
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
        collision_mesh_color_override=(1.0, 0.0, 0.0, 0.5),
    )

    # Create sliders (even in stress testing mode, for manual control)
    with server.gui.add_folder("Joint position control"):
        (slider_handles, initial_config) = create_robot_control_sliders(
            server, viser_urdf
        )

    # Add visibility checkboxes
    with server.gui.add_folder("Visibility"):
        show_meshes_cb = server.gui.add_checkbox("Show meshes", viser_urdf.show_visual)
        show_collision_meshes_cb = server.gui.add_checkbox("Show collision meshes", viser_urdf.show_collision)

    @show_meshes_cb.on_update
    def _(_):
        viser_urdf.show_visual = show_meshes_cb.value

    @show_collision_meshes_cb.on_update
    def _(_):
        viser_urdf.show_collision = show_collision_meshes_cb.value

    show_meshes_cb.visible = load_meshes
    show_collision_meshes_cb.visible = load_collision_meshes

    # Set initial robot configuration
    cfg0 = np.array(initial_config, dtype=np.float32)
    viser_urdf.update_cfg(cfg0)
    publish_telemetry(cfg0)

    # Create grid
    trimesh_scene = viser_urdf._urdf.scene or viser_urdf._urdf.collision_scene
    server.scene.add_grid(
        "/grid",
        width=2,
        height=2,
        position=(
            0.0,
            0.0,
            trimesh_scene.bounds[0, 2] if trimesh_scene is not None else 0.0,
        ),
    )

    # Create joint reset button
    reset_button = server.gui.add_button("Reset")
    @reset_button.on_click
    def _(_):
        for s, init_q in zip(slider_handles, initial_config):
            s.value = init_q

    # Add stress testing control if enabled
    if stress:
        nq = stress_joints if stress_joints is not None else len(initial_config)
        
        with server.gui.add_folder("Stress Testing Control"):
            stress_enabled_cb = server.gui.add_checkbox("Enable Stress Testing", False)
            stress_hz_slider = server.gui.add_slider(
                "Frequency (Hz)",
                min=1.0,
                max=1000.0,
                step=1.0,
                initial_value=stress_hz,
            )
            stress_amplitude_slider = server.gui.add_slider(
                "Amplitude (rad)",
                min=0.1,
                max=2.0,
                step=0.1,
                initial_value=stress_amplitude,
            )
            stress_info = server.gui.add_text("Status", "Disabled")
        
        stress_task = None
        stress_thread = None
        stress_running = threading.Event()
        
        # Shared variables for dynamic control
        current_stress_hz = stress_hz
        current_stress_amplitude = stress_amplitude
        
        # Add slider callbacks for dynamic control
        @stress_hz_slider.on_update
        def _(_):
            nonlocal current_stress_hz
            current_stress_hz = stress_hz_slider.value
            if stress_thread is not None:
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq} joints"
                print(f"🎛️ [STRESS] Frequency updated to {current_stress_hz:.1f}Hz")
                
        @stress_amplitude_slider.on_update
        def _(_):
            nonlocal current_stress_amplitude
            current_stress_amplitude = stress_amplitude_slider.value
            if stress_thread is not None:
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq} joints, ±{current_stress_amplitude:.2f}rad"
                print(f"🎛️ [STRESS] Amplitude updated to ±{current_stress_amplitude:.2f}rad")
        
        def run_stress_testing_in_thread():
            """Run stress testing loop with dynamic parameter control."""
            print(f"🚀 [STRESS] Starting high-frequency joint driver:")
            print(f"   Joints: {nq}")
            print(f"   Initial Frequency: {current_stress_hz:.1f} Hz")
            print(f"   Initial Amplitude: ±{current_stress_amplitude:.2f} rad")
            print(f"   Wave frequency: {stress_wave_freq:.2f} Hz")
            print(f"   Note: Frequency and amplitude can be adjusted via GUI sliders")
            print()
            
            phases = np.linspace(0, 2*np.pi, nq, endpoint=False)
            t0 = time.perf_counter()
            msg_count = 0
            last_stats = t0
            last_hz_update = t0
            
            while stress_running.is_set():
                loop_start = time.perf_counter()
                
                # Get current dynamic parameters
                hz = current_stress_hz
                amplitude = current_stress_amplitude
                
                # Generate sinusoidal joint motion with current parameters
                t = loop_start - t0
                q = amplitude * np.sin(2*np.pi*stress_wave_freq*t + phases)
                
                # Update robot and publish telemetry
                viser_urdf.update_cfg(q.astype(np.float32))
                publish_telemetry(q)
                msg_count += 1
                
                # Print statistics every 10 seconds
                if loop_start - last_stats >= 10.0:
                    elapsed = loop_start - t0
                    avg_hz = msg_count / elapsed if elapsed > 0 else 0
                    print(f"🔥 [STRESS] {msg_count:,} updates | {elapsed:.1f}s | {avg_hz:.1f} Hz avg | Target: {hz:.1f} Hz | Amp: ±{amplitude:.2f}rad")
                    last_stats = loop_start
                
                # Calculate sleep time based on current frequency
                period = 1.0 / hz if hz > 0 else 1.0
                loop_end = time.perf_counter()
                sleep_time = period - (loop_end - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            print(f"⏹️ [STRESS] Stress testing stopped")
        
        @stress_enabled_cb.on_update
        def _(_):
            nonlocal stress_thread
            if stress_enabled_cb.value and stress_thread is None:
                # Start stress testing loop in thread
                stress_running.set()
                stress_thread = threading.Thread(target=run_stress_testing_in_thread, daemon=True)
                stress_thread.start()
                stress_info.value = f"🔥 ACTIVE - {current_stress_hz:.1f}Hz, {nq} joints"
                print(f"🚀 [STRESS] Started stress testing thread: {current_stress_hz:.1f}Hz, {nq} joints")
                
            elif not stress_enabled_cb.value and stress_thread is not None:
                # Stop stress testing loop
                stress_running.clear()
                stress_thread = None
                stress_info.value = "Disabled"
                print(f"⏹️ [STRESS] Stopped stress testing thread")
        
        print(f"[STRESS] Stress testing mode available - use GUI checkbox to enable")
        print(f"[STRESS] Config: {stress_hz:.1f}Hz, {nq} joints, ±{stress_amplitude:.2f}rad")
        print(f"[STRESS] Note: Frequency and amplitude can be adjusted in real-time via GUI sliders")
    
    print(f"[TELEMETRY] Backend started with telemetry logging enabled")
    
    # Sleep forever
    while True:
        time.sleep(10.0)

if __name__ == "__main__":
    tyro.cli(main)
