const WebSocket = require('ws');

describe('Protocol Diagnostic Tests', () => {
  describe('Direct WebSocket Connection Tests', () => {
    test('should connect directly to meshcat-server root path', (done) => {
      /**
       * PURPOSE: Test direct WebSocket connection to meshcat-server root
       * SUCCESS: Connection established - meshcat-server WebSocket is working
       * FAILURE: Connection failed - WebSocket server configuration issue
       * NEXT STEPS: Check meshcat-server WebSocket setup and configuration
       */
      const ws = new WebSocket('ws://127.0.0.1:7000');
      let connectionOpened = false;
      const events = [];
      
      ws.on('open', () => {
        events.push('open');
        console.log('✅ Direct connection to meshcat-server root path successful');
        console.log('📋 DIAGNOSIS: meshcat-server WebSocket is properly configured');
        connectionOpened = true;
        
        // Send a test message to verify bidirectional communication
        ws.send('test-connection');
      });

      ws.on('message', (data) => {
        events.push('message');
        console.log(`📋 Received message: ${data.toString()}`);
      });

      ws.on('close', (code, reason) => {
        events.push('close');
        console.log(`📋 Connection closed: code=${code}, reason=${reason.toString()}`);
        console.log(`📋 Event sequence: ${events.join(' → ')}`);
        
        if (connectionOpened) {
          done();
        } else {
          done.fail('Connection failed to open properly');
        }
      });

      ws.on('error', (error) => {
        events.push('error');
        console.log(`❌ Direct connection error: ${error.message}`);
        console.log('📋 DIAGNOSIS: meshcat-server WebSocket not accessible');
        console.log('📋 ACTION: Verify meshcat-server is running and WebSocket is enabled');
        done.fail(`Direct connection failed: ${error.message}`);
      });

      // Close connection after 2 seconds to test lifecycle
      setTimeout(() => {
        if (connectionOpened) {
          ws.close();
        } else {
          ws.terminate();
          done.fail('Direct connection timeout');
        }
      }, 2000);
    });

    test('should test connection to /ws path (expected to fail)', (done) => {
      /**
       * PURPOSE: Test if meshcat-server serves WebSocket on /ws path
       * SUCCESS: Unexpected - means server serves on /ws (rare)
       * FAILURE: Expected - confirms server only serves on root path
       * NEXT STEPS: If succeeds, proxy doesn't need path rewriting
       */
      const ws = new WebSocket('ws://127.0.0.1:7000/ws');
      let connectionOpened = false;
      let errorReceived = false;
      
      ws.on('open', () => {
        console.log('⚠️  UNEXPECTED: meshcat-server accepts connections on /ws path');
        console.log('📋 DIAGNOSIS: Server serves WebSocket on /ws - proxy config may be correct');
        connectionOpened = true;
        ws.close();
      });

      ws.on('error', (error) => {
        errorReceived = true;
        if (error.message.includes('404')) {
          console.log('✅ EXPECTED: meshcat-server returns 404 for /ws path');
          console.log('📋 DIAGNOSIS: Server only serves on root path, proxy needs path rewriting');
          done();
        } else {
          console.log(`❌ Unexpected error on /ws path: ${error.message}`);
          console.log('📋 DIAGNOSIS: Different error than expected 404');
          done.fail(`Unexpected /ws path error: ${error.message}`);
        }
      });

      ws.on('close', (code, reason) => {
        if (connectionOpened) {
          console.log('⚠️  /ws path connection succeeded unexpectedly');
          done();
        } else if (!errorReceived) {
          console.log('✅ EXPECTED: /ws path connection failed (likely 404)');
          console.log('📋 DIAGNOSIS: Server only serves on root path');
          done();
        }
      });

      setTimeout(() => {
        if (!connectionOpened && !errorReceived) {
          ws.terminate();
          console.log('✅ EXPECTED: /ws path connection timeout');
          done();
        }
      }, 3000);
    });

    test('should test various WebSocket paths', async () => {
      /**
       * PURPOSE: Systematically test different WebSocket paths
       * SUCCESS: Identifies which paths work - informs proxy configuration
       * FAILURE: No paths work - server configuration issue
       * NEXT STEPS: Configure proxy based on working paths
       */
      const pathsToTest = [
        { path: '/', description: 'root path' },
        { path: '/ws', description: 'websocket path' },
        { path: '/websocket', description: 'full websocket path' },
        { path: '/meshcat', description: 'meshcat path' }
      ];

      const results = [];

      for (const pathTest of pathsToTest) {
        const result = await new Promise((resolve) => {
          const ws = new WebSocket(`ws://127.0.0.1:7000${pathTest.path}`);
          let success = false;
          let errorMessage = null;

          const timeout = setTimeout(() => {
            ws.terminate();
            resolve({
              path: pathTest.path,
              description: pathTest.description,
              success: false,
              error: 'timeout'
            });
          }, 2000);

          ws.on('open', () => {
            success = true;
            clearTimeout(timeout);
            ws.close();
          });

          ws.on('close', () => {
            clearTimeout(timeout);
            resolve({
              path: pathTest.path,
              description: pathTest.description,
              success,
              error: errorMessage
            });
          });

          ws.on('error', (error) => {
            errorMessage = error.message;
            clearTimeout(timeout);
            resolve({
              path: pathTest.path,
              description: pathTest.description,
              success: false,
              error: error.message
            });
          });
        });

        results.push(result);
      }

      // Analyze results
      console.log('📋 WebSocket path analysis:');
      const workingPaths = results.filter(r => r.success);
      const failingPaths = results.filter(r => !r.success);

      results.forEach(result => {
        const status = result.success ? '✅ WORKS' : '❌ FAILS';
        const error = result.error ? ` (${result.error})` : '';
        console.log(`📋   ${result.path} (${result.description}): ${status}${error}`);
      });

      console.log(`📋 Summary: ${workingPaths.length} working, ${failingPaths.length} failing`);

      if (workingPaths.length > 0) {
        console.log('📋 RECOMMENDATION: Configure proxy to forward to working paths:');
        workingPaths.forEach(path => {
          console.log(`📋   - Use target path: ${path.path}`);
        });
      } else {
        console.log('📋 DIAGNOSIS: No WebSocket paths work - server configuration issue');
      }

      expect(results.length).toBe(pathsToTest.length);
    }, 10000);
  });

  describe('WebSocket Handshake Analysis', () => {
    test('should analyze WebSocket handshake details', (done) => {
      /**
       * PURPOSE: Examine WebSocket handshake process in detail
       * SUCCESS: Handshake completes - protocol compatibility confirmed
       * FAILURE: Handshake fails - protocol version or header issues
       * NEXT STEPS: Fix protocol compatibility issues
       */
      const ws = new WebSocket('ws://127.0.0.1:7000', {
        headers: {
          'User-Agent': 'WebSocket-Diagnostic-Test',
          'Accept': '*/*'
        }
      });

      const handshakeDetails = {
        events: [],
        startTime: Date.now(),
        endTime: null
      };

      ws.on('open', () => {
        handshakeDetails.events.push('open');
        handshakeDetails.endTime = Date.now();
        
        console.log('✅ WebSocket handshake completed successfully');
        console.log(`📋 Handshake time: ${handshakeDetails.endTime - handshakeDetails.startTime}ms`);
        console.log(`📋 Protocol: ${ws.protocol || 'none'}`);
        console.log(`📋 Extensions: ${ws.extensions || 'none'}`);
        console.log(`📋 Ready state: ${ws.readyState}`);
        
        ws.close();
      });

      ws.on('message', (data) => {
        handshakeDetails.events.push('message');
        console.log(`📋 Handshake message: ${data.toString()}`);
      });

      ws.on('close', (code, reason) => {
        handshakeDetails.events.push('close');
        console.log(`📋 Handshake event sequence: ${handshakeDetails.events.join(' → ')}`);
        console.log(`📋 Close code: ${code}, reason: ${reason.toString()}`);
        
        if (handshakeDetails.events.includes('open')) {
          console.log('📋 DIAGNOSIS: WebSocket handshake working correctly');
          done();
        } else {
          done.fail('WebSocket handshake failed');
        }
      });

      ws.on('error', (error) => {
        handshakeDetails.events.push('error');
        console.log(`❌ WebSocket handshake error: ${error.message}`);
        console.log('📋 DIAGNOSIS: WebSocket handshake failed');
        console.log('📋 ACTION: Check protocol compatibility and server configuration');
        done.fail(`Handshake failed: ${error.message}`);
      });

      setTimeout(() => {
        if (!handshakeDetails.events.includes('open')) {
          ws.terminate();
          done.fail('WebSocket handshake timeout');
        }
      }, 5000);
    });

    test('should test WebSocket with different headers', async () => {
      /**
       * PURPOSE: Test how different headers affect WebSocket connections
       * SUCCESS: Identifies header requirements - guides proxy configuration
       * FAILURE: All headers fail - server header validation too strict
       * NEXT STEPS: Configure proxy headers based on successful combinations
       */
      const headerCombinations = [
        {
          name: 'No custom headers',
          headers: {}
        },
        {
          name: 'Standard browser headers',
          headers: {
            'Origin': 'http://localhost:3000',
            'User-Agent': 'Mozilla/5.0 WebSocket Test'
          }
        },
        {
          name: 'Proxy-like headers',
          headers: {
            'Host': 'localhost:3000',
            'Origin': 'http://localhost:3000'
          }
        },
        {
          name: 'Direct target headers',
          headers: {
            'Host': '127.0.0.1:7000',
            'Origin': 'http://127.0.0.1:7000'
          }
        }
      ];

      const results = [];

      for (const headerTest of headerCombinations) {
        const result = await new Promise((resolve) => {
          const ws = new WebSocket('ws://127.0.0.1:7000', { headers: headerTest.headers });
          let success = false;
          let errorMessage = null;
          let messages = [];

          const timeout = setTimeout(() => {
            ws.terminate();
            resolve({
              name: headerTest.name,
              success: false,
              error: 'timeout',
              messages
            });
          }, 2000);

          ws.on('open', () => {
            success = true;
          });

          ws.on('message', (data) => {
            messages.push(data.toString());
          });

          ws.on('close', () => {
            clearTimeout(timeout);
            resolve({
              name: headerTest.name,
              success,
              error: errorMessage,
              messages
            });
          });

          ws.on('error', (error) => {
            errorMessage = error.message;
          });
        });

        results.push(result);
      }

      // Analyze header test results
      console.log('📋 WebSocket header compatibility analysis:');
      const successfulHeaders = results.filter(r => r.success);
      const failedHeaders = results.filter(r => !r.success);

      results.forEach(result => {
        const status = result.success ? '✅ SUCCESS' : '❌ FAILED';
        const error = result.error ? ` (${result.error})` : '';
        console.log(`📋   ${result.name}: ${status}${error}`);
        if (result.messages.length > 0) {
          console.log(`📋     Messages: ${result.messages.join(', ')}`);
        }
      });

      console.log(`📋 Header compatibility: ${successfulHeaders.length}/${results.length} combinations work`);

      if (successfulHeaders.length > 0) {
        console.log('📋 RECOMMENDATION: Proxy should use compatible headers');
      } else {
        console.log('📋 DIAGNOSIS: Server rejects all header combinations');
      }

      expect(results.length).toBe(headerCombinations.length);
    }, 15000);
  });
});
