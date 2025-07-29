"""
Telemetry Module for Viser Backend Performance Monitoring

This module provides WebSocket-based telemetry functionality to monitor
the performance of the Viser backend in real-time. It tracks update rates,
message counts, and provides latency measurement capabilities.

Features:
- WebSocket server on port 8081 for telemetry data
- Real-time performance metrics publishing
- Ping/pong latency measurement
- Multi-client support with automatic cleanup

Usage:
    from telemetry import start_telemetry_server, publish_telemetry
    
    # Initialize telemetry
    start_telemetry_server()
    
    # Publish metrics during robot updates
    publish_telemetry(joint_configuration_array)
"""

from __future__ import annotations

import time
import asyncio
import threading
import websockets
from typing import Set
import msgpack
import numpy as np

# Global telemetry state
seq_counter = 0
last_telemetry_time = time.perf_counter()
telemetry_clients: Set[websockets.WebSocketServerProtocol] = set()


def start_telemetry_server():
    """
    Start the telemetry WebSocket server in a background thread.
    
    The server listens on ws://0.0.0.0:8081 and accepts connections
    from telemetry monitoring clients. Each client can receive real-time
    performance data and participate in ping/pong latency measurements.
    
    The server runs in a daemon thread and will automatically shut down
    when the main process exits.
    """
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
    time.sleep(0.1)  # Give server time to start


def publish_telemetry(cfg: np.ndarray) -> None:
    """
    Publish telemetry data with current performance metrics.
    
    Args:
        cfg: Joint configuration array (used to determine DOF count)
        
    This function should be called after each robot configuration update
    to track performance metrics. It calculates the update rate and sends
    the data to all connected telemetry clients.
    
    The published data includes:
    - seq: Sequence number (incremental)
    - ns: Timestamp in nanoseconds
    - nq: Number of joint degrees of freedom
    - hz: Current update rate
    """
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
    
    # Log to console periodically or when performance is poor
    if seq_counter % 50 == 0 or hz < 10:
        print(f"[TELEMETRY] seq={seq_counter}, nq={cfg.shape[0]}, rate={hz:.1f}Hz, bytes={len(packed)}")


def send_telemetry_to_clients(payload_bytes: bytes):
    """
    Send telemetry data to all connected WebSocket clients.
    
    Args:
        payload_bytes: Serialized telemetry payload
        
    This function handles sending data to multiple clients while
    automatically cleaning up disconnected clients. It uses thread-safe
    operations to schedule WebSocket sends in the appropriate event loops.
    """
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


async def handle_telemetry_client(websocket):
    """
    Handle individual telemetry WebSocket client connections.
    
    Args:
        websocket: WebSocket connection from client
        
    This coroutine manages the lifecycle of each telemetry client,
    including connection tracking, ping/pong handling for latency
    measurement, and graceful disconnection handling.
    
    Supports ping/pong messages for latency measurement:
    - Client sends: {"type": "ping", "client_timestamp": <ns>}
    - Server responds: {"type": "pong", "client_timestamp": <ns>, "server_timestamp": <ns>}
    """
    connect_time = time.perf_counter()
    telemetry_clients.add(websocket)
    print(f"[TELEMETRY] Client connected from {websocket.remote_address}, total clients: {len(telemetry_clients)}")
    
    try:
        async for message in websocket:
            try:
                data = msgpack.unpackb(message)
                if isinstance(data, dict) and data.get("type") == "ping":
                    pong_response = {
                        "type": "pong",
                        "client_timestamp": data.get("client_timestamp"),
                        "server_timestamp": time.perf_counter_ns()
                    }
                    pong_bytes = msgpack.packb(pong_response, use_bin_type=True)
                    await websocket.send(pong_bytes)
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


def get_telemetry_stats():
    """
    Get current telemetry statistics.
    
    Returns:
        dict: Contains current telemetry state including:
            - connected_clients: Number of active WebSocket connections
            - message_count: Total messages sent
            - last_update_time: Timestamp of last telemetry update
    """
    return {
        "connected_clients": len(telemetry_clients),
        "message_count": seq_counter,
        "last_update_time": last_telemetry_time
    }


def reset_telemetry_counters():
    """Reset telemetry counters (useful for benchmarking)."""
    global seq_counter, last_telemetry_time
    seq_counter = 0
    last_telemetry_time = time.perf_counter()
    print("[TELEMETRY] Counters reset")
