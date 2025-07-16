# MeshCat WebSocket Proxy Diagnostic Test Suite

This test suite systematically diagnoses the WebSocket proxy connection issue between the frontend and meshcat-server.

## Problem Statement
When running `npm run dev:proxy`, the frontend cannot connect to the meshcat backend, resulting in:
- `ERR_STREAM_WRITE_AFTER_END` errors in webpack proxy
- WebSocket connection code 1006 (abnormal closure)
- Connection timeouts and failures

## Test Architecture

### Layer 1: Infrastructure Tests (`infrastructure.test.js`)
**Purpose**: Verify each component works in isolation
- Tests if meshcat-server is running and accessible
- Tests if ports are available and responding
- Tests basic WebSocket functionality

**Success Criteria**: All individual components are functional
**Failure Analysis**: Identifies which specific component is down/misconfigured

### Layer 2: Protocol Tests (`protocol.test.js`) 
**Purpose**: Test communication protocols and paths
- Tests direct WebSocket connections to meshcat-server
- Tests different WebSocket paths and endpoints
- Tests WebSocket handshake completion

**Success Criteria**: Direct connections work without proxy
**Failure Analysis**: Identifies protocol/path mismatches

### Layer 3: Proxy Tests (`proxy.test.js`)
**Purpose**: Test webpack proxy configuration and forwarding
- Tests proxy configuration validity
- Tests proxy WebSocket upgrade handling
- Tests proxy forwarding behavior

**Success Criteria**: Proxy correctly forwards WebSocket requests
**Failure Analysis**: Identifies proxy configuration issues

### Layer 4: Integration Tests (`integration.test.js`)
**Purpose**: Test full frontend → proxy → backend flow
- Tests end-to-end connection establishment
- Tests message passing through proxy
- Tests connection lifecycle management

**Success Criteria**: Complete connection chain works
**Failure Analysis**: Identifies integration issues between components

### Layer 5: Error Reproduction Tests (`error-reproduction.test.js`)
**Purpose**: Systematically reproduce the specific error patterns
- Reproduces ERR_STREAM_WRITE_AFTER_END conditions
- Tests rapid connection/disconnection scenarios
- Tests connection state management issues

**Success Criteria**: Errors are reproduced and root cause identified
**Failure Analysis**: Confirms error triggers and conditions

### Layer 6: Live Proxy Tests (`live-proxy.test.js`) ⚠️ **CRITICAL**
**Purpose**: Test against actual running webpack dev server with proxy (reproduces real failing scenario)
- Starts actual webpack dev server with proxy configuration
- Tests browser-like WebSocket connection patterns
- Reproduces ERR_STREAM_WRITE_AFTER_END in live environment
- Tests concurrent connections and proxy forwarding under load

**Success Criteria**: Successfully reproduces the actual error you experience with `npm run dev:proxy`
**Failure Analysis**: Identifies exact conditions that trigger ERR_STREAM_WRITE_AFTER_END in live proxy

## Test Execution Strategy

1. **Run Infrastructure Tests First** - Verify all components are operational
2. **Run Protocol Tests** - Confirm direct connections work
3. **Run Proxy Tests** - Validate proxy configuration
4. **Run Integration Tests** - Test full connection chain
5. **Run Error Reproduction** - Reproduce specific error conditions

## Interpreting Results

### If Infrastructure Tests Fail:
- Check if meshcat-server is running (`meshcat-server --zmq-url tcp://127.0.0.1:6000`)
- Check if backend is running (`python backends/meshcat_backend.py`)
- Check port availability and conflicts

### If Protocol Tests Fail:
- Verify meshcat-server WebSocket endpoint paths
- Check WebSocket server configuration
- Validate protocol versions and handshake requirements

### If Proxy Tests Fail:
- Review webpack proxy configuration
- Check proxy target URLs and paths
- Validate proxy options (ws, changeOrigin, etc.)

### If Integration Tests Fail:
- Check connection flow through each component
- Validate message formats and protocols
- Review connection state management

### If Error Reproduction Succeeds:
- Analyze error conditions and triggers
- Identify root cause of ERR_STREAM_WRITE_AFTER_END
- Plan targeted fix based on specific failure mode

## Expected Outcomes

This test suite will definitively identify:
1. **Which component is failing** (frontend, proxy, or backend)
2. **What type of failure** (configuration, protocol, timing, etc.)
3. **Under what conditions** the failure occurs
4. **What specific fix** is needed

## Running the Tests

```bash
# Run all diagnostic tests
npm test

# Run specific test layer
npm test -- --testPathPattern="infrastructure"
npm test -- --testPathPattern="protocol"
npm test -- --testPathPattern="proxy"
npm test -- --testPathPattern="integration"
npm test -- --testPathPattern="error-reproduction"
npm test -- --testPathPattern="live-proxy"

# ⚠️ Run ONLY the critical live proxy test (reproduces your exact error)
npm test -- --testPathPattern="live-proxy"
