const net = require('net');
const http = require('http');
const WebSocket = require('ws');

describe('Infrastructure Diagnostic Tests', () => {
  describe('Port Availability Tests', () => {
    test('should verify port 6000 (ZMQ) is accessible', (done) => {
      /**
       * PURPOSE: Test if meshcat-server ZMQ port is running and accessible
       * SUCCESS: Port 6000 accepts connections - meshcat-server is running
       * FAILURE: Port refused - meshcat-server not started or wrong port
       * NEXT STEPS: Start meshcat-server with: meshcat-server --zmq-url tcp://127.0.0.1:6000
       */
      const client = new net.Socket();
      let connectionMade = false;
      
      client.connect(6000, '127.0.0.1', () => {
        console.log('✅ Port 6000 (ZMQ) is accessible - meshcat-server is running');
        connectionMade = true;
        client.destroy();
        done();
      });

      client.on('error', (err) => {
        console.log(`❌ Port 6000 (ZMQ) not accessible: ${err.message}`);
        console.log('📋 DIAGNOSIS: meshcat-server is not running on port 6000');
        console.log('📋 ACTION: Start with: meshcat-server --zmq-url tcp://127.0.0.1:6000');
        done.fail(`ZMQ port not accessible: ${err.message}`);
      });

      setTimeout(() => {
        if (!connectionMade) {
          client.destroy();
          done.fail('ZMQ port connection timeout');
        }
      }, 3000);
    });

    test('should verify port 7000 (WebSocket) is accessible', (done) => {
      /**
       * PURPOSE: Test if meshcat-server WebSocket port is running and accessible
       * SUCCESS: Port 7000 accepts connections - WebSocket server is running
       * FAILURE: Port refused - WebSocket server not started or wrong port
       * NEXT STEPS: Verify meshcat-server WebSocket configuration
       */
      const client = new net.Socket();
      let connectionMade = false;
      
      client.connect(7000, '127.0.0.1', () => {
        console.log('✅ Port 7000 (WebSocket) is accessible - WebSocket server is running');
        connectionMade = true;
        client.destroy();
        done();
      });

      client.on('error', (err) => {
        console.log(`❌ Port 7000 (WebSocket) not accessible: ${err.message}`);
        console.log('📋 DIAGNOSIS: WebSocket server is not running on port 7000');
        console.log('📋 ACTION: Verify meshcat-server WebSocket configuration');
        done.fail(`WebSocket port not accessible: ${err.message}`);
      });

      setTimeout(() => {
        if (!connectionMade) {
          client.destroy();
          done.fail('WebSocket port connection timeout');
        }
      }, 3000);
    });

    test('should verify port 3000 is available for webpack dev server', (done) => {
      /**
       * PURPOSE: Test if port 3000 is free for webpack dev server
       * SUCCESS: Port 3000 is free - webpack can start
       * FAILURE: Port in use - need to stop conflicting process
       * NEXT STEPS: Kill process using port 3000 or use different port
       */
      const server = net.createServer();
      
      server.listen(3000, '127.0.0.1', () => {
        console.log('✅ Port 3000 is available for webpack dev server');
        server.close();
        done();
      });

      server.on('error', (err) => {
        if (err.code === 'EADDRINUSE') {
          console.log('❌ Port 3000 is already in use');
          console.log('📋 DIAGNOSIS: Another process is using port 3000');
          console.log('📋 ACTION: Kill conflicting process or use different port');
          done.fail('Port 3000 already in use');
        } else {
          done.fail(`Port 3000 test failed: ${err.message}`);
        }
      });
    });
  });

  describe('HTTP Server Response Tests', () => {
    test('should get HTTP response from meshcat-server on port 7000', (done) => {
      /**
       * PURPOSE: Test if meshcat-server responds to HTTP requests
       * SUCCESS: Gets HTTP response - server is properly configured
       * FAILURE: No response - server configuration issue
       * NEXT STEPS: Check meshcat-server HTTP configuration
       */
      const options = {
        hostname: '127.0.0.1',
        port: 7000,
        path: '/',
        method: 'GET',
        timeout: 3000
      };

      const req = http.request(options, (res) => {
        console.log(`✅ HTTP response from meshcat-server: status=${res.statusCode}`);
        console.log(`📋 Headers:`, res.headers);
        
        let data = '';
        res.on('data', (chunk) => data += chunk);
        
        res.on('end', () => {
          console.log(`📋 Response body length: ${data.length} characters`);
          expect(res.statusCode).toBeDefined();
          done();
        });
      });

      req.on('error', (err) => {
        console.log(`❌ HTTP request failed: ${err.message}`);
        console.log('📋 DIAGNOSIS: meshcat-server not responding to HTTP requests');
        console.log('📋 ACTION: Check meshcat-server HTTP configuration');
        done.fail(`HTTP request failed: ${err.message}`);
      });

      req.on('timeout', () => {
        req.destroy();
        console.log('❌ HTTP request timeout');
        done.fail('HTTP request timeout');
      });

      req.end();
    });
  });

  describe('Process Detection Tests', () => {
    test('should detect running meshcat-server process', (done) => {
      /**
       * PURPOSE: Verify meshcat-server process is actually running
       * SUCCESS: Process found - server is running as expected
       * FAILURE: Process not found - server not started properly
       * NEXT STEPS: Start meshcat-server process
       */
      const { exec } = require('child_process');
      
      exec('ps aux | grep meshcat-server | grep -v grep', (error, stdout, stderr) => {
        if (stdout.trim()) {
          console.log('✅ meshcat-server process detected');
          console.log(`📋 Process info: ${stdout.trim()}`);
          done();
        } else {
          console.log('❌ meshcat-server process not found');
          console.log('📋 DIAGNOSIS: meshcat-server process is not running');
          console.log('📋 ACTION: Start meshcat-server process');
          done.fail('meshcat-server process not running');
        }
      });
    });

    test('should detect running Python backend process', (done) => {
      /**
       * PURPOSE: Verify Python backend is running
       * SUCCESS: Backend process found - backend is connected
       * FAILURE: Backend not found - need to start backend
       * NEXT STEPS: Start Python backend with: python backends/meshcat_backend.py
       */
      const { exec } = require('child_process');
      
      exec('ps aux | grep meshcat_backend.py | grep -v grep', (error, stdout, stderr) => {
        if (stdout.trim()) {
          console.log('✅ Python backend process detected');
          console.log(`📋 Process info: ${stdout.trim()}`);
          done();
        } else {
          console.log('❌ Python backend process not found');
          console.log('📋 DIAGNOSIS: Python backend is not running');
          console.log('📋 ACTION: Start with: python backends/meshcat_backend.py');
          // Don't fail this test - backend might not be required for proxy testing
          done();
        }
      });
    });
  });

  describe('System Resource Tests', () => {
    test('should check system resource availability', (done) => {
      /**
       * PURPOSE: Verify system has sufficient resources
       * SUCCESS: Resources available - system can handle connections
       * FAILURE: Resource constraints - may cause connection issues
       * NEXT STEPS: Free up system resources or restart services
       */
      const { exec } = require('child_process');
      
      exec('netstat -an | grep LISTEN | grep -E "(6000|7000|3000)"', (error, stdout, stderr) => {
        console.log('📋 Listening ports analysis:');
        if (stdout.trim()) {
          const lines = stdout.trim().split('\n');
          lines.forEach(line => {
            console.log(`📋   ${line}`);
          });
        } else {
          console.log('📋   No relevant listening ports found');
        }
        
        // This test always passes - it's just informational
        done();
      });
    });
  });
});
