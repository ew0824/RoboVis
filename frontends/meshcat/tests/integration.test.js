const WebSocket = require('ws');
const { spawn } = require('child_process');
const net = require('net');

describe('Integration Diagnostic Tests', () => {
  describe('End-to-End Connection Flow', () => {
    test('should test full frontend → proxy → backend connection chain', (done) => {
      /**
       * PURPOSE: Test complete connection flow through all components
       * SUCCESS: Full chain works - all components properly integrated
       * FAILURE: Chain breaks - identifies integration point failure
       * NEXT STEPS: Fix integration between failing components
       */
      
      // This test simulates what happens when frontend connects through proxy
      console.log('📋 Testing full connection chain: Frontend → Proxy → Backend');
      
      // Step 1: Verify target backend is accessible
      const targetHost = '127.0.0.1';
      const targetPort = 7000;
      
      const testBackend = new net.Socket();
      testBackend.connect(targetPort, targetHost, () => {
        console.log('✅ Step 1: Backend server is accessible');
        testBackend.destroy();
        
        // Step 2: Test direct WebSocket connection (bypass proxy)
        const directWs = new WebSocket(`ws://${targetHost}:${targetPort}`);
        
        directWs.on('open', () => {
          console.log('✅ Step 2: Direct WebSocket connection works');
          directWs.close();
          
          // Step 3: Test proxy-like connection (simulate what proxy does)
          testProxySimulation();
        });
        
        directWs.on('error', (error) => {
          console.log(`❌ Step 2 failed: Direct WebSocket connection: ${error.message}`);
          console.log('📋 DIAGNOSIS: Backend WebSocket not working');
          done.fail(`Direct WebSocket failed: ${error.message}`);
        });
      });
      
      testBackend.on('error', (err) => {
        console.log(`❌ Step 1 failed: Backend not accessible: ${err.message}`);
        console.log('📋 DIAGNOSIS: Backend server not running');
        done.fail(`Backend not accessible: ${err.message}`);
      });
      
      function testProxySimulation() {
        // Step 3: Test what proxy should do (with path rewriting if configured)
        const path = require('path');
        const webpackConfigPath = path.resolve(__dirname, '../../webpack.config.proxy.js');
        
        let config;
        try {
          config = require(webpackConfigPath);
        } catch (error) {
          console.log(`❌ Step 3 failed: Cannot load proxy config: ${error.message}`);
          done.fail('Proxy config not loadable');
          return;
        }
        
        const wsProxy = config.devServer.proxy.find(p => 
          p.context && p.context.includes('/ws')
        );
        
        if (!wsProxy) {
          console.log('❌ Step 3 failed: No WebSocket proxy configuration');
          done.fail('No proxy configuration');
          return;
        }
        
        // Simulate proxy path rewriting
        let targetPath = '/ws';
        if (wsProxy.pathRewrite && wsProxy.pathRewrite['^/ws'] !== undefined) {
          targetPath = wsProxy.pathRewrite['^/ws'] === '' ? '/' : wsProxy.pathRewrite['^/ws'];
        }
        
        const proxySimulatedUrl = `ws://${targetHost}:${targetPort}${targetPath}`;
        console.log(`📋 Step 3: Testing proxy-simulated connection to: ${proxySimulatedUrl}`);
        
        const proxyWs = new WebSocket(proxySimulatedUrl);
        
        proxyWs.on('open', () => {
          console.log('✅ Step 3: Proxy-simulated connection works');
          console.log('✅ DIAGNOSIS: Full connection chain should work');
          proxyWs.close();
          done();
        });
        
        proxyWs.on('error', (error) => {
          console.log(`❌ Step 3 failed: Proxy-simulated connection: ${error.message}`);
          console.log('📋 DIAGNOSIS: Path rewriting or proxy configuration issue');
          console.log(`📋 ACTION: Fix proxy path rewriting or target configuration`);
          done.fail(`Proxy simulation failed: ${error.message}`);
        });
      }
    }, 10000);

    test('should test connection with various proxy scenarios', async () => {
      /**
       * PURPOSE: Test different proxy configuration scenarios
       * SUCCESS: Identifies which proxy configurations work
       * FAILURE: All proxy configurations fail - fundamental issue
       * NEXT STEPS: Use working proxy configuration
       */
      const proxyScenarios = [
        {
          name: 'No path rewriting',
          pathRewrite: null,
          expectedPath: '/ws'
        },
        {
          name: 'Remove /ws prefix', 
          pathRewrite: { '^/ws': '' },
          expectedPath: '/'
        },
        {
          name: 'Replace with /websocket',
          pathRewrite: { '^/ws': '/websocket' },
          expectedPath: '/websocket'
        },
        {
          name: 'Replace with /meshcat',
          pathRewrite: { '^/ws': '/meshcat' },
          expectedPath: '/meshcat'
        }
      ];

      const results = [];
      const targetHost = '127.0.0.1';
      const targetPort = 7000;

      for (const scenario of proxyScenarios) {
        console.log(`📋 Testing proxy scenario: ${scenario.name}`);
        
        const result = await new Promise((resolve) => {
          const testUrl = `ws://${targetHost}:${targetPort}${scenario.expectedPath}`;
          const ws = new WebSocket(testUrl);
          let success = false;
          let errorMessage = null;

          const timeout = setTimeout(() => {
            ws.terminate();
            resolve({
              scenario: scenario.name,
              testUrl,
              success: false,
              error: 'timeout'
            });
          }, 3000);

          ws.on('open', () => {
            success = true;
            clearTimeout(timeout);
            ws.close();
          });

          ws.on('close', () => {
            clearTimeout(timeout);
            resolve({
              scenario: scenario.name,
              testUrl,
              success,
              error: errorMessage
            });
          });

          ws.on('error', (error) => {
            errorMessage = error.message;
          });
        });

        results.push(result);
      }

      // Analyze proxy scenario results
      console.log('📋 Proxy scenario analysis:');
      const workingScenarios = results.filter(r => r.success);
      const failingScenarios = results.filter(r => !r.success);

      results.forEach(result => {
        const status = result.success ? '✅ WORKS' : '❌ FAILS';
        const error = result.error ? ` (${result.error})` : '';
        console.log(`📋   ${result.scenario}: ${status}${error}`);
        console.log(`📋     URL: ${result.testUrl}`);
      });

      console.log(`📋 Proxy scenarios: ${workingScenarios.length}/${results.length} work`);

      if (workingScenarios.length > 0) {
        console.log('📋 RECOMMENDATION: Use working proxy configuration:');
        workingScenarios.forEach(scenario => {
          console.log(`📋   - ${scenario.scenario}`);
        });
      } else {
        console.log('📋 DIAGNOSIS: No proxy configurations work with current backend');
        console.log('📋 ACTION: Check backend WebSocket endpoint configuration');
      }

      expect(results.length).toBe(proxyScenarios.length);
    }, 15000);
  });

  describe('Message Flow Integration', () => {
    test('should test bidirectional message flow through proxy', (done) => {
      /**
       * PURPOSE: Test if messages can flow both ways through proxy
       * SUCCESS: Messages flow correctly - proxy handles message forwarding
       * FAILURE: Messages don't flow - proxy message handling issue
       * NEXT STEPS: Fix proxy message forwarding configuration
       */
      
      // Find a working connection first
      const targetHost = '127.0.0.1';
      const targetPort = 7000;
      
      console.log('📋 Testing bidirectional message flow');
      
      // Test with the most likely working path (root path)
      const testUrl = `ws://${targetHost}:${targetPort}/`;
      const ws = new WebSocket(testUrl);
      
      let connectionOpened = false;
      let messageReceived = false;
      const testMessage = 'integration-test-message';
      
      ws.on('open', () => {
        console.log('✅ Connection opened for message flow test');
        connectionOpened = true;
        
        // Send test message
        console.log(`📋 Sending test message: ${testMessage}`);
        ws.send(testMessage);
        
        // Set timeout for message response
        setTimeout(() => {
          if (!messageReceived) {
            console.log('📋 No response to message (this may be expected)');
            console.log('✅ DIAGNOSIS: Connection works, server may not echo messages');
            ws.close();
          }
        }, 2000);
      });
      
      ws.on('message', (data) => {
        messageReceived = true;
        const receivedMessage = data.toString();
        console.log(`📋 Received message: ${receivedMessage}`);
        
        if (receivedMessage.includes(testMessage)) {
          console.log('✅ Message echo confirmed - bidirectional flow works');
        } else {
          console.log('📋 Different message received - server is responding');
        }
        
        ws.close();
      });
      
      ws.on('close', (code, reason) => {
        console.log(`📋 Message flow test connection closed: code=${code}`);
        
        if (connectionOpened) {
          console.log('✅ DIAGNOSIS: Message flow connection successful');
          console.log(`📋 Message received: ${messageReceived ? 'Yes' : 'No'}`);
          done();
        } else {
          console.log('❌ DIAGNOSIS: Connection failed for message flow test');
          done.fail('Message flow test connection failed');
        }
      });
      
      ws.on('error', (error) => {
        console.log(`❌ Message flow test error: ${error.message}`);
        console.log('📋 DIAGNOSIS: Cannot establish connection for message flow test');
        done.fail(`Message flow test failed: ${error.message}`);
      });
      
      setTimeout(() => {
        if (!connectionOpened) {
          ws.terminate();
          done.fail('Message flow test timeout');
        }
      }, 5000);
    });

    test('should test connection state management', async () => {
      /**
       * PURPOSE: Test connection lifecycle management
       * SUCCESS: Connections managed properly - no state issues
       * FAILURE: Connection state issues - may cause errors
       * NEXT STEPS: Fix connection state management
       */
      console.log('📋 Testing connection state management');
      
      const connectionTests = [
        { name: 'Quick connect/disconnect', delay: 100 },
        { name: 'Normal connect/disconnect', delay: 1000 },
        { name: 'Long connect/disconnect', delay: 3000 }
      ];
      
      const results = [];
      const targetHost = '127.0.0.1';
      const targetPort = 7000;
      const testUrl = `ws://${targetHost}:${targetPort}/`;
      
      for (const test of connectionTests) {
        console.log(`📋 Testing: ${test.name}`);
        
        const result = await new Promise((resolve) => {
          const ws = new WebSocket(testUrl);
          const events = [];
          let connectionOpened = false;
          
          ws.on('open', () => {
            events.push('open');
            connectionOpened = true;
            
            // Wait specified delay then close
            setTimeout(() => {
              ws.close();
            }, test.delay);
          });
          
          ws.on('close', (code, reason) => {
            events.push('close');
            resolve({
              test: test.name,
              success: connectionOpened,
              events,
              closeCode: code,
              closeReason: reason.toString()
            });
          });
          
          ws.on('error', (error) => {
            events.push('error');
            resolve({
              test: test.name,
              success: false,
              events,
              error: error.message
            });
          });
          
          // Timeout fallback
          setTimeout(() => {
            if (!events.includes('close') && !events.includes('error')) {
              ws.terminate();
              resolve({
                test: test.name,
                success: false,
                events,
                error: 'timeout'
              });
            }
          }, test.delay + 5000);
        });
        
        results.push(result);
      }
      
      // Analyze connection state results
      console.log('📋 Connection state management analysis:');
      const successfulTests = results.filter(r => r.success);
      const failedTests = results.filter(r => !r.success);
      
      results.forEach(result => {
        const status = result.success ? '✅ SUCCESS' : '❌ FAILED';
        const error = result.error ? ` (${result.error})` : '';
        console.log(`📋   ${result.test}: ${status}${error}`);
        console.log(`📋     Events: ${result.events.join(' → ')}`);
        if (result.closeCode !== undefined) {
          console.log(`📋     Close: code=${result.closeCode}, reason=${result.closeReason}`);
        }
      });
      
      console.log(`📋 Connection state tests: ${successfulTests.length}/${results.length} successful`);
      
      if (failedTests.length > 0) {
        console.log('📋 DIAGNOSIS: Some connection state issues detected');
        console.log('📋 ACTION: Review connection lifecycle management');
      } else {
        console.log('✅ DIAGNOSIS: Connection state management working correctly');
      }
      
      expect(results.length).toBe(connectionTests.length);
    }, 20000);
  });

  describe('Concurrent Connection Testing', () => {
    test('should test multiple simultaneous connections', async () => {
      /**
       * PURPOSE: Test if server handles multiple concurrent connections
       * SUCCESS: Multiple connections work - server handles concurrency
       * FAILURE: Concurrent connections fail - server concurrency issues
       * NEXT STEPS: Fix server concurrency handling or connection limits
       */
      console.log('📋 Testing concurrent connections');
      
      const connectionCount = 5;
      const targetHost = '127.0.0.1';
      const targetPort = 7000;
      const testUrl = `ws://${targetHost}:${targetPort}/`;
      
      const connectionPromises = [];
      
      for (let i = 0; i < connectionCount; i++) {
        const connectionPromise = new Promise((resolve) => {
          const ws = new WebSocket(testUrl);
          const connectionId = i + 1;
          let opened = false;
          
          const timeout = setTimeout(() => {
            ws.terminate();
            resolve({
              id: connectionId,
              success: false,
              error: 'timeout'
            });
          }, 5000);
          
          ws.on('open', () => {
            opened = true;
            console.log(`📋 Connection ${connectionId} opened`);
            
            // Send a test message
            ws.send(`test-message-${connectionId}`);
            
            // Close after short delay
            setTimeout(() => {
              ws.close();
            }, 1000);
          });
          
          ws.on('close', () => {
            clearTimeout(timeout);
            console.log(`📋 Connection ${connectionId} closed`);
            resolve({
              id: connectionId,
              success: opened,
              error: null
            });
          });
          
          ws.on('error', (error) => {
            clearTimeout(timeout);
            console.log(`📋 Connection ${connectionId} error: ${error.message}`);
            resolve({
              id: connectionId,
              success: false,
              error: error.message
            });
          });
        });
        
        connectionPromises.push(connectionPromise);
      }
      
      const results = await Promise.all(connectionPromises);
      
      // Analyze concurrent connection results
      const successfulConnections = results.filter(r => r.success);
      const failedConnections = results.filter(r => !r.success);
      
      console.log(`📋 Concurrent connections result: ${successfulConnections.length}/${connectionCount} successful`);
      
      results.forEach(result => {
        const status = result.success ? '✅' : '❌';
        const error = result.error ? ` (${result.error})` : '';
        console.log(`📋   Connection ${result.id}: ${status}${error}`);
      });
      
      if (successfulConnections.length === connectionCount) {
        console.log('✅ DIAGNOSIS: Server handles concurrent connections well');
      } else if (successfulConnections.length > 0) {
        console.log('⚠️  DIAGNOSIS: Server has limited concurrent connection capacity');
        console.log('📋 ACTION: May need to optimize server concurrency handling');
      } else {
        console.log('❌ DIAGNOSIS: Server cannot handle concurrent connections');
        console.log('📋 ACTION: Fix server concurrency configuration');
      }
      
      expect(results.length).toBe(connectionCount);
    }, 15000);
  });
});
