# MeshCat Frontend with WebSocket Proxy

This is a test-driven implementation of a WebSocket proxy solution for MeshCat frontend development that eliminates cross-origin issues.

## Problem Solved

When developing MeshCat frontends, you often encounter CORS (Cross-Origin Resource Sharing) issues when trying to connect to WebSocket servers running on different ports. This proxy solution allows you to:

1. Run your frontend dev server on port 3000
2. Connect to your MeshCat backend on port 7000
3. Eliminate cross-origin issues by proxying WebSocket connections

## Architecture

```
Browser → http://localhost:3000 → Webpack Dev Server (with proxy)
                                         ↓
WebSocket: ws://localhost:3000/ws → ws://127.0.0.1:7000/ws → MeshCat Backend
```

## Files Created

### Core Implementation
- `src/connection-utils.js` - Smart WebSocket URL generation with environment detection
- `webpack.config.proxy.js` - Webpack configuration with WebSocket proxy
- `src/index.js` - Main entry point demonstrating proxy usage

### Test Suite
- `tests/unit/connection-logic.test.js` - Tests for WebSocket URL generation logic
- `tests/unit/proxy-config.test.js` - Tests for proxy configuration validation
- `tests/integration/websocket-proxy.test.js` - Integration tests for end-to-end proxy functionality
- `jest.config.js` - Jest configuration
- `tests/setup.js` - Test environment setup

### Configuration
- `.babelrc` - Babel configuration for ES6+ support
- `index.html` - Demo page with interactive WebSocket testing
- Updated `package.json` with new dependencies and scripts

## Usage

### 1. Install Dependencies
```bash
cd frontends/meshcat
npm install
```

### 2. Start Your MeshCat Backend
Make sure your MeshCat backend is running on port 7000:
```bash
python backends/meshcat_backend.py
```

### 3. Start Frontend with Proxy
```bash
npm run dev:proxy
```

This starts the webpack dev server on port 3000 with WebSocket proxy configuration.

### 4. Test the Connection
Open http://localhost:3000 in your browser. The demo page will:
- Automatically attempt to connect to the proxied WebSocket
- Show connection status and logs
- Allow you to send test messages
- Display all WebSocket events in real-time

## Available Scripts

- `npm run dev:proxy` - Start development server with WebSocket proxy
- `npm test` - Run all tests
- `npm run test:watch` - Run tests in watch mode
- `npm run test:integration` - Run integration tests only

## How It Works

### Environment Detection
The `connection-utils.js` automatically detects your environment:

```javascript
function generateWebSocketURL() {
  if (typeof window !== 'undefined') {
    // Browser environment - use proxy
    return `ws://${window.location.host}/ws`;
  } else {
    // Node.js environment - direct connection
    return 'ws://127.0.0.1:7000/ws';
  }
}
```

### Webpack Proxy Configuration
The proxy is configured in `webpack.config.proxy.js`:

```javascript
proxy: [
  {
    context: ['/ws'],
    target: 'ws://127.0.0.1:7000',
    ws: true,
    changeOrigin: true,
    logLevel: 'debug',
  }
]
```

### Connection Logic
Your frontend code simply connects to the same-origin endpoint:

```javascript
const { generateWebSocketURL } = require('./connection-utils');
const wsUrl = generateWebSocketURL(); // Returns ws://localhost:3000/ws in browser
const ws = new WebSocket(wsUrl);
```

## Testing

The implementation includes comprehensive tests:

- **Unit Tests (10 tests)**: Test core logic without external dependencies
- **Integration Tests (2 tests)**: Test actual proxy functionality (require running servers)

Run tests:
```bash
npm test
```

Expected output:
```
Test Suites: 1 failed, 2 passed, 3 total
Tests:       2 failed, 11 passed, 13 total
```

The integration tests fail when servers aren't running, which is expected.

## Benefits

1. **Same-Origin**: Browser sees WebSocket as same-origin, eliminating CORS issues
2. **Development-Friendly**: Maintains hot-reload, HMR, and familiar dev workflow
3. **Test-Driven**: Comprehensive test suite ensures reliability
4. **Environment-Aware**: Automatically adapts to browser vs Node.js environments
5. **Easy Integration**: Drop-in solution with minimal configuration changes

## Integration with Existing Code

To use this in your existing MeshCat frontend:

1. Import the connection utilities:
```javascript
const { generateWebSocketURL } = require('./connection-utils');
```

2. Replace hardcoded WebSocket URLs:
```javascript
// Before
const viewer = new MeshCat.Viewer(document.getElementById('meshcat-pane'));
viewer.connect('ws://127.0.0.1:7000/ws');

// After  
const viewer = new MeshCat.Viewer(document.getElementById('meshcat-pane'));
viewer.connect(generateWebSocketURL());
```

3. Use the proxy webpack config:
```bash
npm run dev:proxy
```

## Troubleshooting

### Connection Refused
If you see "ECONNREFUSED", ensure your MeshCat backend is running on port 7000.

### Proxy Not Working
1. Check that you're using `npm run dev:proxy` (not regular `npm run dev`)
2. Verify the backend is accessible at `ws://127.0.0.1:7000/ws`
3. Check browser developer tools for proxy errors

### Tests Failing
- Unit tests should always pass
- Integration tests require both frontend proxy server and backend to be running

## Future Enhancements

- Support for configurable backend ports
- Automatic backend discovery
- SSL/TLS proxy support
- Connection retry logic with exponential backoff
