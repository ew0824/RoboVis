# Viser High-Frequency Stress Testing Guide

This guide explains how to stress test the Viser telemetry system with high-frequency robot joint updates to simulate real-world data loads.

## 🎯 Purpose

- **Performance Testing**: Measure telemetry system performance under high load
- **Bandwidth Analysis**: Test WebSocket throughput and latency
- **System Limits**: Find maximum sustainable update rates
- **Real-world Simulation**: Simulate continuous robot operation

## 🚀 Method 1: Internal Stress Testing Loop (Recommended)

**File**: `benchmarks/viser_push_bench_with_stress_testing.py`

### Usage

```bash
# Basic stress testing mode (240 Hz, all joints)
python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 240

# Custom configuration
python benchmarks/viser_push_bench_with_stress_testing.py \
    --stress \
    --stress-hz 300 \
    --stress-amplitude 0.6 \
    --stress-wave-freq 0.3 \
    --stress-joints 4

# Remote deployment
python benchmarks/viser_push_bench_with_stress_testing.py \
    --stress \
    --stress-hz 250 \
    --urdf_path assets/urdf/eoat_7/urdf/eoat/eoat.urdf
```

### Parameters

- `--stress`: Enable stress testing mode
- `--stress-hz`: Update frequency (Hz) - default: 240
- `--stress-amplitude`: Joint movement amplitude (rad) - default: 0.4
- `--stress-wave-freq`: Sine wave frequency (Hz) - default: 0.5
- `--stress-joints`: Number of joints to drive - default: all available

### GUI Control

Once running, use the **🔥 Stress Testing Control** section in the GUI:
- ✅ **Enable Stress Testing**: Toggle high-frequency updates on/off
- 📊 **Status**: Shows current status and parameters

### Benefits

✅ **Guaranteed compatibility** - uses internal `viser_urdf.update_cfg()`  
✅ **GUI integration** - manual sliders still work  
✅ **Telemetry integration** - automatically triggers telemetry  
✅ **Real-time control** - enable/disable via GUI  

---

## 🎮 Method 2: External Driver (Experimental)

**File**: `benchmarks/viser_stress_driver.py`

### Usage

```bash
# Local testing
python benchmarks/viser_stress_driver.py \
    --ws ws://localhost:8080 \
    --joints 4 \
    --hz 240

# Remote testing
python benchmarks/viser_stress_driver.py \
    --ws ws://dev-dsk-edmwang-2c-680aebf8.us-west-2.amazon.com:8080 \
    --joints 120 \
    --hz 300 \
    --verbose

# Protocol testing
python benchmarks/viser_stress_driver.py \
    --ws ws://localhost:8080 \
    --protocol json \
    --amplitude 0.8 \
    --wave-freq 1.0
```

### Parameters

- `--ws`: Viser WebSocket URL
- `--joints`: Number of joints to simulate - default: 4
- `--hz`: Update frequency (Hz) - default: 240
- `--amplitude`: Joint movement amplitude (rad) - default: 0.5
- `--wave-freq`: Sine wave frequency (Hz) - default: 0.5
- `--protocol`: Message protocol (`msgpack` or `json`) - default: msgpack
- `--verbose`: Enable detailed logging

### Benefits

✅ **External process** - independent of main server  
✅ **Protocol exploration** - tests different WebSocket message formats  
✅ **Scalable** - can run multiple drivers simultaneously  
✅ **Realistic** - simulates external robot controllers  

### ⚠️ Limitations

❓ **Protocol uncertainty** - may not match Viser's expected format  
❓ **Connection issues** - WebSocket endpoint discovery needed  
❓ **Message format** - trials different formats to find working one  

---

## 📊 Telemetry Monitoring

Both methods integrate with the telemetry system. Monitor performance via:

### Browser Console
```
[TELEMETRY] Extracted hostname: dev-dsk-edmwang-2c-680aebf8.us-west-2.amazon.com
[TELEMETRY] Connected to telemetry server
```

### Backend Logs
```
🔥 [STRESS] 12,000 updates | 50.0s | 240.0 Hz avg | Target: 240.0 Hz
[TELEMETRY] seq=12000, ts=123456789, nq=4, rate=240.1Hz, bytes=34
```

### Frontend Overlay
- 🟢 **Green**: Active telemetry data
- ⚪ **Latency**: Round-trip time (ms)
- 📈 **Rate**: Update frequency (Hz)
- 🔢 **Messages**: Total message count
- 📶 **Bandwidth**: Data transfer rate

---

## 🎛️ Recommended Testing Scenarios

### 1. Baseline Performance
```bash
python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 60
```
Low-frequency baseline to verify system stability.

### 2. Standard Robot Operation
```bash
python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 120 --stress-joints 6
```
Typical 6-DOF robot at 120 Hz control rate.

### 3. High-Performance Testing
```bash
python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 500 --stress-amplitude 0.3
```
Push system limits with 500 Hz updates.

### 4. Multi-Joint Stress Test
```bash
python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 240 --stress-joints 120
```
Large multi-DOF system simulation.

### 5. Network Latency Testing (Remote)
```bash
# On remote server
python benchmarks/viser_push_bench_with_stress_testing.py --stress --stress-hz 300

# Access via browser
http://your-hostname:4173/?websocket=ws://your-hostname:8080&telemetry=true
```

---

## 📈 Performance Metrics to Monitor

### Telemetry Overlay
- **Latency < 50ms**: Excellent
- **Latency 50-100ms**: Good
- **Latency > 100ms**: Investigate network/processing delays

### Backend Performance
- **Achieved Hz ≈ Target Hz**: System keeping up
- **Achieved Hz < Target Hz**: System overloaded
- **Telemetry rate matches update rate**: Good integration

### Browser Performance
- **Smooth visualization**: Frontend handling updates well
- **Frame drops**: Consider reducing update rate
- **Memory growth**: Check for WebGL memory leaks

---

## 🔧 Troubleshooting

### Telemetry Not Working
1. Check WebSocket connection: `ws://hostname:8081`
2. Verify backend binding: should be `0.0.0.0:8081`
3. Test browser console for connection errors

### Low Update Rates
1. Increase system resources (CPU/memory)
2. Reduce `stress_hz` parameter
3. Disable collision mesh rendering
4. Close other applications

### Network Issues (Remote)
1. Verify firewall allows ports 8080, 8081
2. Use public hostname, not localhost
3. Test with `curl` or `telnet` first

### External Driver Not Connecting
1. Try verbose mode: `--verbose`
2. Check different WebSocket endpoints
3. Verify Viser server is running
4. Test basic WebSocket connection first

---

## 🎯 Next Steps

After successful stress testing, you can:
1. **Compare frameworks**: Test MeshCat with similar loads
2. **Optimize performance**: Profile bottlenecks
3. **Scale testing**: Multiple robot simulation
4. **Rich visualization**: Add complex rendering features

Happy stress testing! 🚀
