#!/usr/bin/env python3
"""
High-frequency robot configuration stress testing driver for Viser.
This script connects directly to a Viser server and drives robot joints
at high frequencies to stress test the telemetry and visualization systems.

Usage:
    python benchmarks/viser_stress_driver.py --ws ws://localhost:8080 --joints 4 --hz 240
    python benchmarks/viser_stress_driver.py --ws ws://dev-dsk-edmwang-2c-680aebf8.us-west-2.amazon.com:8080 --joints 120 --hz 300
"""

import asyncio
import argparse
import time
import numpy as np
import websockets
import json
import msgpack
from typing import Optional

def parse_args():
    parser = argparse.ArgumentParser(description='Viser stress testing driver')
    parser.add_argument('--ws', default='ws://127.0.0.1:8080', 
                       help='Viser WebSocket URL (default: ws://127.0.0.1:8080)')
    parser.add_argument('--joints', type=int, default=4, 
                       help='Number of joints to simulate (default: 4)')
    parser.add_argument('--hz', type=float, default=240.0, 
                       help='Update frequency in Hz (default: 240.0)')
    parser.add_argument('--amplitude', type=float, default=0.5, 
                       help='Joint movement amplitude in radians (default: 0.5)')
    parser.add_argument('--wave-freq', type=float, default=0.5, 
                       help='Sine wave frequency for joint motion (default: 0.5 Hz)')
    parser.add_argument('--protocol', choices=['json', 'msgpack'], default='msgpack',
                       help='Message protocol to use (default: msgpack)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    return parser.parse_args()

class ViserStressDriver:
    def __init__(self, ws_url: str, joints: int, hz: float, amplitude: float, 
                 wave_freq: float, protocol: str = 'msgpack', verbose: bool = False):
        self.ws_url = ws_url
        self.joints = joints
        self.hz = hz
        self.amplitude = amplitude
        self.wave_freq = wave_freq
        self.protocol = protocol
        self.verbose = verbose
        
        # Calculate timing
        self.period = 1.0 / hz
        
        # Generate phase offsets for each joint to create interesting motion
        self.phases = np.linspace(0, 2*np.pi, joints, endpoint=False)
        
        # Statistics
        self.msg_count = 0
        self.start_time = None
        self.last_stats_time = None
        
    async def connect_and_drive(self):
        """Connect to Viser WebSocket and start driving joints."""
        print(f"🚀 Starting Viser stress driver:")
        print(f"   WebSocket: {self.ws_url}")
        print(f"   Joints: {self.joints}")
        print(f"   Frequency: {self.hz:.1f} Hz ({self.period*1000:.1f}ms period)")
        print(f"   Amplitude: ±{self.amplitude:.2f} rad")
        print(f"   Wave frequency: {self.wave_freq:.2f} Hz")
        print(f"   Protocol: {self.protocol}")
        print()
        
        try:
            # Try different WebSocket endpoints that Viser might use
            endpoints = ['', '/ws', '/websocket', '/app']
            
            for endpoint in endpoints:
                full_url = self.ws_url.rstrip('/') + endpoint
                try:
                    print(f"🔗 Attempting connection to: {full_url}")
                    async with websockets.connect(full_url) as websocket:
                        print(f"✅ Connected successfully to: {full_url}")
                        await self.drive_joints(websocket)
                        return  # Success, exit function
                except Exception as e:
                    if self.verbose:
                        print(f"❌ Failed to connect to {full_url}: {e}")
                    continue
            
            # If all endpoints failed
            print(f"❌ Failed to connect to any WebSocket endpoint")
            print(f"   Tried: {[self.ws_url + ep for ep in endpoints]}")
            
        except KeyboardInterrupt:
            print("\n⏹️  Interrupted by user")
        except Exception as e:
            print(f"❌ Connection error: {e}")
    
    async def drive_joints(self, websocket):
        """Drive joint configurations at the specified frequency."""
        self.start_time = time.perf_counter()
        self.last_stats_time = self.start_time
        
        print(f"🎮 Starting joint drive loop...")
        print(f"📊 Statistics will be printed every 5 seconds")
        print(f"⏹️  Press Ctrl+C to stop")
        print()
        
        try:
            while True:
                loop_start = time.perf_counter()
                
                # Generate synthetic joint configuration
                t = loop_start - self.start_time
                joint_angles = self.amplitude * np.sin(2 * np.pi * self.wave_freq * t + self.phases)
                
                # Try different message formats that Viser might expect
                messages_to_try = [
                    # Common robot configuration message formats
                    {"type": "robot_config", "joints": joint_angles.tolist()},
                    {"type": "joint_positions", "positions": joint_angles.tolist()},
                    {"cfg": joint_angles.tolist()},
                    {"config": joint_angles.tolist()},
                    {"q": joint_angles.tolist()},
                    # ViserUrdf might use these
                    {"joint_angles": joint_angles.tolist()},
                    {"urdf_config": joint_angles.tolist()},
                ]
                
                # Send message
                try:
                    for msg_format in messages_to_try:
                        if self.protocol == 'msgpack':
                            data = msgpack.packb(msg_format)
                            await websocket.send(data)
                        else:  # json
                            data = json.dumps(msg_format)
                            await websocket.send(data)
                        
                        self.msg_count += 1
                        
                        # Only try first format after initial attempts
                        if self.msg_count > len(messages_to_try):
                            break
                
                except websockets.exceptions.ConnectionClosed:
                    print("❌ WebSocket connection closed")
                    break
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️  Send error: {e}")
                
                # Print statistics every 5 seconds
                if loop_start - self.last_stats_time >= 5.0:
                    await self.print_statistics(loop_start)
                    self.last_stats_time = loop_start
                
                # Sleep to maintain frequency
                loop_end = time.perf_counter()
                sleep_time = self.period - (loop_end - loop_start)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                elif self.verbose and sleep_time < -0.001:  # Warning if we're running behind
                    print(f"⚠️  Running {-sleep_time*1000:.1f}ms behind schedule")
                    
        except KeyboardInterrupt:
            print("\n⏹️  Drive loop interrupted by user")
            await self.print_final_statistics()
    
    async def print_statistics(self, current_time: float):
        """Print performance statistics."""
        elapsed = current_time - self.start_time
        avg_hz = self.msg_count / elapsed if elapsed > 0 else 0
        
        print(f"📊 Stats: {self.msg_count:,} msgs | "
              f"{elapsed:.1f}s | "
              f"{avg_hz:.1f} Hz avg | "
              f"Target: {self.hz:.1f} Hz | "
              f"Joints: {self.joints}")
    
    async def print_final_statistics(self):
        """Print final performance summary."""
        if self.start_time:
            elapsed = time.perf_counter() - self.start_time
            avg_hz = self.msg_count / elapsed if elapsed > 0 else 0
            
            print()
            print("📈 Final Statistics:")
            print(f"   Total messages: {self.msg_count:,}")
            print(f"   Total time: {elapsed:.2f} seconds")
            print(f"   Average frequency: {avg_hz:.2f} Hz")
            print(f"   Target frequency: {self.hz:.1f} Hz")
            print(f"   Efficiency: {(avg_hz/self.hz)*100:.1f}%" if self.hz > 0 else "N/A")
            print(f"   Joints simulated: {self.joints}")

async def main():
    args = parse_args()
    
    driver = ViserStressDriver(
        ws_url=args.ws,
        joints=args.joints,
        hz=args.hz,
        amplitude=args.amplitude,
        wave_freq=args.wave_freq,
        protocol=args.protocol,
        verbose=args.verbose
    )
    
    await driver.connect_and_drive()

if __name__ == "__main__":
    asyncio.run(main())
