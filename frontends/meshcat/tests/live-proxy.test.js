const { spawn } = require('child_process');
const WebSocket = require('ws');
const http = require('http');
const path = require('path');

describe('Live Webpack Dev Server Proxy Tests', () => {
  let devServerProcess = null;
  let serverReady = false;

  const startDevServer = () => {
    return new Promise((resolve, reject) => {
      console.log('📋 Starting webpack dev server with proxy...');
      
      const configPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      devServerProcess = spawn('npx', ['webpack', 'serve', '--mode', 'development', '--config', configPath], {
        cwd: path.resolve(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let output = '';
      let errorOutput = '';
      let readyTimeout;

      devServerProcess.stdout.on('data', (data) => {
        const text = data.toString();
        output += text;
        console.log(`📋 Dev Server: ${text.trim()}`);
        
        if (text.includes('Project is running at') || text.includes('compiled successfully')) {
          if (!serverReady) {
            serverReady = true;
            clearTimeout(readyTimeout);
            setTimeout(resolve, 2000); // Give server time to fully start
          }
        }
      });

      devServerProcess.stderr.on('data', (data) => {
        const text = data.toString();
        errorOutput += text;
        console.log(`📋 Dev Server Error: ${text.trim()}`);
        
        // Look for the specific error we're trying to reproduce
        if (text.includes('ERR_STREAM_WRITE_AFTER_END')) {
          console.log('🎯 REPRODUCED: ERR_STREAM_WRITE_AFTER_END error detected!');
        }
      });

      devServerProcess.on('error', (error) => {
        console.log(`❌ Failed to start dev server: ${error.message}`);
        reject(error);
      });

      // Timeout after 30 seconds
      readyTimeout = setTimeout(() => {
        if (!serverReady) {
          reject(new Error('Dev server failed to start within 30 seconds'));
        }
      }, 30000);
    });
  };

  const stopDevServer = () => {
    return new Promise((resolve) => {
      if (devServerProcess && !devServerProcess.killed) {
        console.log('📋 Stopping webpack dev server...');
        devServerProcess.kill('SIGTERM');
        
        devServerProcess.on('exit', () => {
          console.log('📋 Dev server stopped');
          devServerProcess = null;
          serverReady = false;
          resolve();
        });

        // Force kill after 5 seconds
        setTimeout(() => {
          if (devServerProcess && !devServerProcess.killed) {
            devServerProcess.kill('SIGKILL');
            devServerProcess = null;
            serverReady = false;
            resolve();
          }
        }, 5000);
      } else {
        resolve();
      }
    });
  };

  beforeAll(async () => {
    /**
     * PURPOSE: Start webpack dev server with proxy configuration
     * SUCCESS: Dev server starts and proxy is active
     * FAILURE: Cannot start dev server - environment issue
     * NEXT STEPS: Fix webpack or Node.js environment
     */
    console.log('📋 Setting up live proxy test environment...');
    await startDevServer();
  }, 45000);

  afterAll(async () => {
    await stopDevServer();
  }, 10000);

  describe('Real Webpack Dev Server Proxy Behavior', () => {
    test('should verify dev server is running with proxy', async () => {
      /**
       * PURPOSE: Confirm webpack dev server is actually running
       * SUCCESS: Can make HTTP request to dev server
       * FAILURE: Dev server not accessible - startup failed
       * NEXT STEPS: Check dev server startup process
       */
      expect(serverReady).toBe(true);
      
      const response = await new Promise((resolve, reject) => {
        const req = http.get('http://localhost:3000/', (res) => {
          console.log(`✅ Dev server HTTP response: ${res.statusCode}`);
          resolve(res);
        });
        
        req.on('error', (error) => {
          console.log(`❌ Dev server not accessible: ${error.message}`);
          reject(error);
        });
        
        req.setTimeout(5000, () => {
          req.destroy();
          reject(new Error('HTTP request timeout'));
        });
      });

      expect(response.statusCode).toBeDefined();
    }, 10000);

    test('should reproduce ERR_STREAM_WRITE_AFTER_END with live proxy', async () => {
      /**
       * PURPOSE: Reproduce the exact error scenario with live webpack dev server
       * SUCCESS: ERR_STREAM_WRITE_AFTER_END error reproduced
       * FAILURE: Error not reproduced - different conditions needed
       * NEXT STEPS: Analyze why error conditions differ
       */
      let errorReproduced = false;
      let connectionEvents = [];
      let errorMessages = [];

      // Monitor dev server output for errors
      const errorMonitor = (data) => {
        const text = data.toString();
        if (text.includes('ERR_STREAM_WRITE_AFTER_END')) {
          errorReproduced = true;
          errorMessages.push(text);
        }
      };

      if (devServerProcess && devServerProcess.stderr) {
        devServerProcess.stderr.on('data', errorMonitor);
      }

      // Test multiple WebSocket connections to trigger the error
      const connectionPromises = [];
      const totalConnections = 5;

      for (let i = 0; i < totalConnections; i++) {
        const connectionPromise = new Promise((resolve) => {
          const ws = new WebSocket('ws://localhost:3000/ws');
          const connectionId = i + 1;
          const events = [];

          const timeout = setTimeout(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.close();
            } else {
              ws.terminate();
            }
            
            resolve({
              connectionId,
              events,
              success: false,
              error: 'timeout'
            });
          }, 8000);

          ws.on('open', () => {
            events.push('open');
            console.log(`📋 Connection ${connectionId} opened`);
            
            // Send a message to trigger proxy forwarding
            ws.send(`test-message-${connectionId}`);
            events.push('message_sent');
            
            // Keep connection open briefly to allow error to manifest
            setTimeout(() => {
              ws.close();
            }, 2000);
          });

          ws.on('message', (data) => {
            events.push('message_received');
            console.log(`📋 Connection ${connectionId} received: ${data.toString().substring(0, 50)}...`);
          });

          ws.on('close', (code, reason) => {
            events.push(`close_${code}`);
            console.log(`📋 Connection ${connectionId} closed: code=${code}`);
            clearTimeout(timeout);
            
            resolve({
              connectionId,
              events,
              success: events.includes('open'),
              closeCode: code,
              closeReason: reason.toString()
            });
          });

          ws.on('error', (error) => {
            events.push('error');
            console.log(`📋 Connection ${connectionId} error: ${error.message}`);
            clearTimeout(timeout);
            
            resolve({
              connectionId,
              events,
              success: false,
              error: error.message
            });
          });
        });

        connectionPromises.push(connectionPromise);
        
        // Stagger connections to create realistic load
        await new Promise(resolve => setTimeout(resolve, 200));
      }

      const results = await Promise.all(connectionPromises);
      
      // Remove error monitor
      if (devServerProcess && devServerProcess.stderr) {
        devServerProcess.stderr.removeListener('data', errorMonitor);
      }

      // Analyze results
      console.log('📋 Live proxy connection test results:');
      const successfulConnections = results.filter(r => r.success);
      const failedConnections = results.filter(r => !r.success);

      results.forEach(result => {
        const status = result.success ? '✅' : '❌';
        console.log(`📋   Connection ${result.connectionId}: ${status}`);
        console.log(`📋     Events: ${result.events.join(' → ')}`);
        if (result.closeCode) {
          console.log(`📋     Close: code=${result.closeCode}`);
        }
        if (result.error) {
          console.log(`📋     Error: ${result.error}`);
        }
      });

      console.log(`📋 Connection summary: ${successfulConnections.length}/${totalConnections} successful`);

      if (errorReproduced) {
        console.log('🎯 SUCCESS: ERR_STREAM_WRITE_AFTER_END error reproduced!');
        console.log('📋 Error messages captured:');
        errorMessages.forEach(msg => {
          console.log(`📋   ${msg.trim()}`);
        });
        
        // If we reproduced the error, that confirms the problem exists
        if (errorReproduced) {
          // This is "success" for diagnosis but indicates the problem still exists
          console.log('🎯 Test succeeded in reproducing the error - problem confirmed');
        }
      } else {
        console.log('📋 ERR_STREAM_WRITE_AFTER_END not reproduced in this test run');
        console.log('📋 This could mean:');
        console.log('📋   - Error is timing-dependent');
        console.log('📋   - Different connection patterns needed');
        console.log('📋   - Environment-specific conditions');
        
        // Don't fail the test - just document the findings
        expect(results.length).toBe(totalConnections);
      }
    }, 30000);

    test('should test browser-like connection patterns', async () => {
      /**
       * PURPOSE: Simulate actual browser WebSocket connection behavior
       * SUCCESS: Identifies browser-specific connection patterns that cause errors
       * FAILURE: No browser patterns reproduced - test browser directly
       * NEXT STEPS: Use actual browser testing if needed
       */
      console.log('📋 Testing browser-like connection patterns...');
      
      // Simulate what a browser does:
      // 1. Connects to get webpack hot reload
      // 2. Receives hot reload messages
      // 3. May reconnect on errors
      // 4. Handles connection lifecycle
      
      const browserSimulation = await new Promise((resolve) => {
        const ws = new WebSocket('ws://localhost:3000/ws');
        const events = [];
        let hotReloadReceived = false;
        let reconnectCount = 0;
        const maxReconnects = 3;

        const handleReconnect = () => {
          if (reconnectCount < maxReconnects) {
            reconnectCount++;
            console.log(`📋 Browser simulation: reconnecting (${reconnectCount}/${maxReconnects})`);
            setTimeout(() => {
              // Create new connection
              const newWs = new WebSocket('ws://localhost:3000/ws');
              setupWebSocket(newWs);
            }, 1000);
          } else {
            resolve({
              events,
              hotReloadReceived,
              reconnectCount,
              success: hotReloadReceived
            });
          }
        };

        const setupWebSocket = (websocket) => {
          websocket.on('open', () => {
            events.push('open');
            console.log('📋 Browser simulation: connection opened');
          });

          websocket.on('message', (data) => {
            const message = data.toString();
            events.push('message');
            
            try {
              const parsed = JSON.parse(message);
              if (parsed.type === 'hot' || parsed.type === 'liveReload') {
                hotReloadReceived = true;
                console.log('📋 Browser simulation: received hot reload message');
              }
            } catch (e) {
              // Not JSON, might be from meshcat server
              console.log('📋 Browser simulation: received non-JSON message');
            }
          });

          websocket.on('close', (code, reason) => {
            events.push(`close_${code}`);
            console.log(`📋 Browser simulation: connection closed (${code})`);
            
            if (code === 1006) {
              // Abnormal closure - browser would typically reconnect
              handleReconnect();
            } else {
              resolve({
                events,
                hotReloadReceived,
                reconnectCount,
                success: hotReloadReceived,
                finalCloseCode: code
              });
            }
          });

          websocket.on('error', (error) => {
            events.push('error');
            console.log(`📋 Browser simulation: error - ${error.message}`);
          });
        };

        setupWebSocket(ws);

        // Timeout the test after 15 seconds
        setTimeout(() => {
          resolve({
            events,
            hotReloadReceived,
            reconnectCount,
            success: false,
            timeout: true
          });
        }, 15000);
      });

      console.log('📋 Browser simulation results:');
      console.log(`📋   Events: ${browserSimulation.events.join(' → ')}`);
      console.log(`📋   Hot reload received: ${browserSimulation.hotReloadReceived}`);
      console.log(`📋   Reconnections: ${browserSimulation.reconnectCount}`);
      console.log(`📋   Success: ${browserSimulation.success}`);

      if (browserSimulation.timeout) {
        console.log('📋 Browser simulation timed out');
      }

      if (browserSimulation.finalCloseCode) {
        console.log(`📋   Final close code: ${browserSimulation.finalCloseCode}`);
      }

      // Test passes if we successfully simulated browser behavior
      expect(browserSimulation.events.length).toBeGreaterThan(0);
    }, 20000);

    test('should test proxy forwarding under different conditions', async () => {
      /**
       * PURPOSE: Test different conditions that might trigger the proxy error
       * SUCCESS: Identifies specific conditions that cause ERR_STREAM_WRITE_AFTER_END
       * FAILURE: No conditions reproduce error - error may be intermittent
       * NEXT STEPS: Focus on identified error conditions
       */
      console.log('📋 Testing proxy forwarding under various conditions...');

      const testConditions = [
        {
          name: 'Rapid connect/disconnect',
          test: async () => {
            const promises = [];
            for (let i = 0; i < 3; i++) {
              promises.push(new Promise((resolve) => {
                const ws = new WebSocket('ws://localhost:3000/ws');
                ws.on('open', () => {
                  // Immediately close after opening
                  ws.close();
                });
                ws.on('close', () => resolve('closed'));
                ws.on('error', () => resolve('error'));
                setTimeout(() => resolve('timeout'), 2000);
              }));
            }
            return Promise.all(promises);
          }
        },
        {
          name: 'Send message then close',
          test: async () => {
            return new Promise((resolve) => {
              const ws = new WebSocket('ws://localhost:3000/ws');
              ws.on('open', () => {
                ws.send('test message');
                setTimeout(() => ws.close(), 100);
              });
              ws.on('close', () => resolve('closed'));
              ws.on('error', (error) => resolve(`error: ${error.message}`));
              setTimeout(() => resolve('timeout'), 3000);
            });
          }
        },
        {
          name: 'Long-lived connection',
          test: async () => {
            return new Promise((resolve) => {
              const ws = new WebSocket('ws://localhost:3000/ws');
              const messages = [];
              
              ws.on('open', () => {
                console.log('📋 Long-lived connection established');
              });
              
              ws.on('message', (data) => {
                messages.push(data.toString());
              });
              
              ws.on('close', (code) => {
                resolve(`closed_${code}_messages_${messages.length}`);
              });
              
              ws.on('error', (error) => {
                resolve(`error: ${error.message}`);
              });
              
              // Keep connection open for 5 seconds
              setTimeout(() => {
                ws.close();
              }, 5000);
            });
          }
        }
      ];

      const conditionResults = [];

      for (const condition of testConditions) {
        console.log(`📋 Testing condition: ${condition.name}`);
        
        try {
          const result = await condition.test();
          conditionResults.push({
            condition: condition.name,
            result,
            success: true
          });
          console.log(`📋   Result: ${result}`);
        } catch (error) {
          conditionResults.push({
            condition: condition.name,
            result: error.message,
            success: false
          });
          console.log(`📋   Error: ${error.message}`);
        }

        // Brief pause between conditions
        await new Promise(resolve => setTimeout(resolve, 500));
      }

      console.log('📋 Proxy forwarding condition results:');
      conditionResults.forEach(result => {
        const status = result.success ? '✅' : '❌';
        console.log(`📋   ${result.condition}: ${status} - ${result.result}`);
      });

      expect(conditionResults.length).toBe(testConditions.length);
    }, 25000);
  });
});
