const WebSocket = require('ws');
const { spawn } = require('child_process');
const path = require('path');

describe('WebSocket Proxy Integration', () => {
  let mockMeshcatServer;
  let webpackDevServer;
  let receivedMessages = [];

  beforeAll(async () => {
    // Start a mock meshcat server on port 7000
    mockMeshcatServer = new WebSocket.Server({ 
      port: 7000,
      path: '/ws'
    });

    mockMeshcatServer.on('connection', (ws) => {
      console.log('Mock meshcat server: client connected');
      
      // Echo back any messages for testing
      ws.on('message', (message) => {
        console.log('Mock meshcat server received:', message.toString());
        receivedMessages.push(message.toString());
        ws.send(`echo: ${message}`);
      });

      // Send a welcome message
      ws.send(JSON.stringify({ type: 'welcome', message: 'Connected to mock meshcat server' }));
    });

    // Wait for server to start
    await new Promise(resolve => setTimeout(resolve, 1000));
  });

  afterAll(async () => {
    if (mockMeshcatServer) {
      mockMeshcatServer.close();
    }
    if (webpackDevServer) {
      webpackDevServer.kill();
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  });

  beforeEach(() => {
    receivedMessages = [];
  });

  test('should proxy WebSocket connections from /ws to port 7000', async () => {
    // This test will fail until we implement the proxy
    const client = new WebSocket('ws://localhost:3000/ws');
    
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Test timeout - proxy may not be working'));
      }, 5000);

      client.on('open', () => {
        console.log('Client connected to proxy');
        client.send('test message');
      });

      client.on('message', (data) => {
        console.log('Client received:', data.toString());
        const message = data.toString();
        
        if (message.includes('echo: test message')) {
          clearTimeout(timeout);
          client.close();
          resolve();
        }
      });

      client.on('error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });
    });
  }, 10000);

  test('should handle connection errors gracefully', async () => {
    // Close the mock server temporarily
    mockMeshcatServer.close();
    
    const client = new WebSocket('ws://localhost:3000/ws');
    
    return new Promise((resolve) => {
      client.on('error', (error) => {
        expect(error).toBeDefined();
        resolve();
      });

      client.on('open', () => {
        // This shouldn't happen when server is down
        client.close();
        throw new Error('Connection should have failed');
      });
    });
  });

  test('should forward binary messages correctly', async () => {
    // Restart mock server for this test
    mockMeshcatServer = new WebSocket.Server({ 
      port: 7000,
      path: '/ws'
    });

    mockMeshcatServer.on('connection', (ws) => {
      ws.on('message', (message) => {
        // Echo back binary data
        ws.send(message);
      });
    });

    await new Promise(resolve => setTimeout(resolve, 500));

    const client = new WebSocket('ws://localhost:3000/ws');
    const testBuffer = Buffer.from([1, 2, 3, 4, 5]);
    
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Binary message test timeout'));
      }, 5000);

      client.on('open', () => {
        client.send(testBuffer);
      });

      client.on('message', (data) => {
        if (Buffer.isBuffer(data) && data.equals(testBuffer)) {
          clearTimeout(timeout);
          client.close();
          resolve();
        }
      });

      client.on('error', reject);
    });
  }, 10000);
});
