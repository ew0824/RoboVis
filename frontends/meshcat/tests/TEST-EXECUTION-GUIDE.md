# MeshCat WebSocket Proxy Diagnostic Test Execution Guide

This guide provides step-by-step instructions for running the diagnostic tests and interpreting their results to identify and fix your WebSocket proxy connection issues.

## Prerequisites

Before running the tests, ensure you have:

1. **MeshCat Server Running**: 
   ```bash
   meshcat-server --zmq-url tcp://127.0.0.1:6000
   ```

2. **Backend Process Running**:
   ```bash
   python backends/meshcat_backend.py
   ```

3. **Node.js Dependencies Installed**:
   ```bash
   cd frontends/meshcat
   npm install
   ```

## Test Execution Order

**IMPORTANT**: Run tests in the specified order for systematic diagnosis.

### Step 1: Infrastructure Tests
```bash
npm test -- --testPathPattern="infrastructure"
```

**What This Tests**: Basic system components (ports, processes, connectivity)

**If This Fails**:
- ❌ **Port 6000 not accessible**: Start meshcat-server
- ❌ **Port 7000 not accessible**: Check meshcat-server WebSocket configuration  
- ❌ **Port 3000 in use**: Kill conflicting process or use different port
- ❌ **Process not found**: Start missing processes

**Expected Output**: All ports accessible, processes running

---

### Step 2: Protocol Tests
```bash
npm test -- --testPathPattern="protocol"
```

**What This Tests**: Direct WebSocket connections, path availability, handshake process

**If This Fails**:
- ❌ **Root path connection fails**: meshcat-server WebSocket not working
- ❌ **All paths fail**: Server configuration issue
- ❌ **Handshake fails**: Protocol compatibility issue

**Expected Output**: 
- ✅ Root path (`/`) connection works
- ❌ `/ws` path connection fails (this is expected - confirms path issue)
- Path analysis shows which paths work

---

### Step 3: Proxy Tests  
```bash
npm test -- --testPathPattern="proxy"
```

**What This Tests**: Proxy configuration, target accessibility, path rewriting

**If This Fails**:
- ❌ **Proxy config missing**: Fix webpack.config.proxy.js
- ❌ **Target not reachable**: Start target server
- ❌ **Path rewriting wrong**: Adjust pathRewrite configuration

**Expected Output**: 
- ✅ Proxy configuration valid
- ✅ Target server reachable
- Analysis of path rewriting effectiveness

---

### Step 4: Integration Tests
```bash
npm test -- --testPathPattern="integration"
```

**What This Tests**: End-to-end connection flow, message passing, concurrent connections

**If This Fails**:
- ❌ **Connection chain breaks**: Fix integration between components
- ❌ **Message flow fails**: Check message forwarding
- ❌ **Concurrent connections fail**: Server concurrency issues

**Expected Output**: 
- ✅ Full connection chain works
- Identification of working proxy scenarios
- Connection lifecycle validation

---

### Step 5: Error Reproduction Tests
```bash
npm test -- --testPathPattern="error-reproduction"
```

**What This Tests**: Reproduces specific error conditions, identifies error triggers

**If This Succeeds** (reproduces errors):
- 🎯 **ERR_STREAM_WRITE_AFTER_END reproduced**: Confirms error conditions
- 🎯 **404 errors reproduced**: Path issues confirmed
- 🎯 **State transition errors**: Connection lifecycle issues

**Expected Output**: 
- Error conditions reproduced and analyzed
- Specific triggers identified
- Fix targets provided

---

### Step 6: Live Proxy Tests ⚠️ **CRITICAL**
```bash
npm test -- --testPathPattern="live-proxy"
```

**What This Tests**: Tests against actual running webpack dev server with proxy (the real failing scenario)

**⚠️ IMPORTANT**: This test **starts a real webpack dev server** and may reproduce the actual error you're experiencing

**If This Succeeds** (reproduces the real error):
- 🎯 **Real ERR_STREAM_WRITE_AFTER_END reproduced**: Confirms the actual problem
- 🎯 **Browser connection patterns identified**: Shows how frontend actually fails
- 🎯 **Proxy forwarding issues detected**: Pinpoints exact failure mode

**Expected Output**:
- Live webpack dev server starts successfully
- Multiple connection attempts are made
- **ERR_STREAM_WRITE_AFTER_END error is reproduced** in server logs
- Specific failure patterns are identified

**If This Fails to Start**:
- Port 3000 may be in use - kill existing processes
- Webpack configuration issues
- Node.js environment problems

---

## Run All Diagnostic Tests
```bash
npm test
```

## ⚠️ Run ONLY the Critical Live Proxy Test
```bash
npm test -- --testPathPattern="live-proxy"
```

**This is the most important test** - it reproduces your exact failing scenario!

## Interpreting Test Results

### ✅ All Tests Pass
Your configuration is correct. The issue may be:
- Environment-specific conditions
- Timing-related race conditions  
- Browser-specific WebSocket behavior

### ❌ Infrastructure Tests Fail
**Root Cause**: Basic system setup issues
**Action**: Fix server processes and port availability before continuing

### ❌ Protocol Tests Fail  
**Root Cause**: WebSocket server configuration issues
**Action**: Fix meshcat-server WebSocket setup and path configuration

### ❌ Proxy Tests Fail
**Root Cause**: Webpack proxy configuration issues  
**Action**: Fix proxy target, path rewriting, or context patterns

### ❌ Integration Tests Fail
**Root Cause**: Component integration issues
**Action**: Fix connection flow between frontend, proxy, and backend

### 🎯 Error Reproduction Tests Succeed
**Root Cause**: Specific error conditions identified
**Action**: Implement fixes for the reproduced error scenarios

## Common Test Failure Patterns

### Pattern 1: "Connection Refused" Errors
```
❌ Port 6000 (ZMQ) not accessible: connect ECONNREFUSED 127.0.0.1:6000
❌ Port 7000 (WebSocket) not accessible: connect ECONNREFUSED 127.0.0.1:7000
```
**Diagnosis**: meshcat-server not running  
**Fix**: Start meshcat-server with correct configuration

### Pattern 2: "404 Not Found" Errors  
```
✅ Direct connection to meshcat-server root path successful
❌ /ws path connection: Unexpected server response: 404
```
**Diagnosis**: Server serves on root path, proxy forwards to /ws path  
**Fix**: Add pathRewrite to remove /ws prefix

### Pattern 3: "Path Rewriting Issues"
```
✅ Proxy configuration valid
❌ Path rewriting produces non-working paths
```
**Diagnosis**: Path rewriting configuration incorrect  
**Fix**: Adjust pathRewrite rules based on server paths

### Pattern 4: "Write After End" Errors Reproduced
```
🎯 REPRODUCED: Connection to non-existent path
🎯 REPRODUCED: Rapid connect/disconnect cycles  
```
**Diagnosis**: Error conditions confirmed  
**Fix**: Address specific error triggers (path issues, connection management)

## Quick Fix Recommendations

Based on test results, apply these fixes:

### Fix 1: Add Path Rewriting (Most Common)
If protocol tests show root path works but /ws fails:
```javascript
// webpack.config.proxy.js
proxy: [{
  context: ['/ws'],
  target: 'ws://127.0.0.1:7000',
  ws: true,
  changeOrigin: true,
  pathRewrite: {
    '^/ws': '' // Remove /ws prefix
  }
}]
```

### Fix 2: Fix Proxy Target
If proxy tests show target not reachable:
```javascript
// Check and correct the target URL
target: 'ws://127.0.0.1:7000' // Ensure this matches your server
```

### Fix 3: Add Headers (If Needed)
If protocol tests show header issues:
```javascript
// Add headers if server requires specific ones
headers: {
  'Origin': 'http://127.0.0.1:7000'
}
```

## Test Output Examples

### Successful Test Output
```
✅ Port 6000 (ZMQ) is accessible - meshcat-server is running
✅ Direct connection to meshcat-server root path successful  
✅ EXPECTED: meshcat-server returns 404 for /ws path
✅ Proxy configuration valid
✅ Step 3: Proxy-simulated connection works
```

### Failed Test Output Requiring Fix
```
❌ Port 7000 (WebSocket) not accessible: connect ECONNREFUSED 127.0.0.1:7000
📋 DIAGNOSIS: WebSocket server is not running on port 7000
📋 ACTION: Verify meshcat-server WebSocket configuration
```

## Next Steps After Testing

1. **Review test output** for specific failure patterns
2. **Apply recommended fixes** based on test results  
3. **Re-run tests** to validate fixes
4. **Test actual proxy** with `npm run dev:proxy`
5. **Monitor for ERR_STREAM_WRITE_AFTER_END** errors

## Support Information

If tests don't provide clear direction:

1. **Save complete test output** to a file
2. **Check server logs** for additional error details  
3. **Verify environment setup** matches test assumptions
4. **Run tests with different server configurations** if needed

The diagnostic tests are designed to systematically identify the exact failure point in your WebSocket proxy setup, providing clear action items for fixes.
