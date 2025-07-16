const { spawn } = require('child_process');
const WebSocket = require('ws');
const path = require('path');

describe('Proxy Fix Verification Tests', () => {
  let devServerProcess = null;
  let serverReady = false;

  const startDevServer = () => {
    return new Promise((resolve, reject) => {
      console.log('📋 Starting webpack dev server with FIXED proxy configuration...');
      
      const configPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      devServerProcess = spawn('npx', ['webpack', 'serve', '--mode', 'development', '--config', configPath], {
        cwd: path.resolve(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let hasError = false;

      devServerProcess.stdout.on('data', (data) => {
        const text = data.toString();
        console.log(`📋 Dev Server: ${text.trim()}`);
        
        if (text.includes('Project is running at') || text.includes('compiled successfully')) {
          if (!serverReady) {
            serverReady = true;
            setTimeout(resolve, 2000);
          }
        }
      });

      devServerProcess.stderr.on('data', (data) => {
        const text = data.toString();
        console.log(`📋 Dev Server Log: ${text.trim()}`);
        
        // Monitor for the error we're trying to fix
        if (text.includes('ERR_STREAM_WRITE_AFTER_END')) {
          hasError = true;
          console.log('❌ STILL BROKEN: ERR_STREAM_WRITE_AFTER_END error detected!');
        }
        
        if (text.includes('Invalid Host/Origin header')) {
          hasError = true;
          console.log('❌ STILL BROKEN: Invalid Host/Origin header error detected!');
        }
      });

      devServerProcess.on('error', reject);

      setTimeout(() => {
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
        
        const cleanup = () => {
          devServerProcess = null;
          serverReady = false;
          resolve();
        };

        devServerProcess.on('exit', cleanup);
        setTimeout(() => {
          if (devServerProcess && !devServerProcess.killed) {
            devServerProcess.kill('SIGKILL');
            cleanup();
          }
        }, 5000);
      } else {
        resolve();
      }
    });
  };

  beforeAll(async () => {
    await startDevServer();
  }, 45000);

  afterAll(async () => {
    await stopDevServer();
  }, 10000);

  test('should verify proxy fix eliminates ERR_STREAM_WRITE_AFTER_END error', async () => {
    /**
     * PURPOSE: Verify the header fix resolves the connection rejection issue
     * SUCCESS: Connections succeed without "Invalid Host/Origin header" errors
     * FAILURE: Still getting header rejection or write-after-end errors
     * NEXT STEPS: Try different header configurations
     */
    let errorDetected = false;
    let invalidHeaderDetected = false;
    let successfulConnections = 0;
    const totalConnections = 3;

    // Monitor server output during test
    const errorMonitor = (data) => {
      const text = data.toString();
      if (text.includes('ERR_STREAM_WRITE_AFTER_END')) {
        errorDetected = true;
      }
      if (text.includes('Invalid Host/Origin header')) {
        invalidHeaderDetected = true;
      }
    };

    if (devServerProcess && devServerProcess.stderr) {
      devServerProcess.stderr.on('data', errorMonitor);
    }

    // Test connections
    const connectionPromises = [];

    for (let i = 0; i < totalConnections; i++) {
      const connectionPromise = new Promise((resolve) => {
        const ws = new WebSocket('ws://localhost:3000/ws');
        const connectionId = i + 1;
        let connectionSuccess = false;
        let receivedData = false;

        const timeout = setTimeout(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.close();
          } else {
            ws.terminate();
          }
          resolve({
            connectionId,
            success: connectionSuccess,
            receivedData,
            error: 'timeout'
          });
        }, 5000);

        ws.on('open', () => {
          connectionSuccess = true;
          console.log(`✅ Connection ${connectionId} opened successfully`);
          ws.send(`verification-test-${connectionId}`);
        });

        ws.on('message', (data) => {
          receivedData = true;
          const message = data.toString();
          
          // Check if we're getting error messages (bad) or actual data (good)
          if (message.includes('Invalid Host/Origin header')) {
            console.log(`❌ Connection ${connectionId} received header error: ${message.substring(0, 100)}...`);
          } else {
            console.log(`✅ Connection ${connectionId} received valid data: ${message.substring(0, 50)}...`);
          }
        });

        ws.on('close', (code, reason) => {
          clearTimeout(timeout);
          console.log(`📋 Connection ${connectionId} closed: code=${code}`);
          
          // Code 1005 was the problematic close code from header rejection
          if (code === 1005) {
            console.log(`⚠️  Connection ${connectionId} closed with code 1005 (possible header rejection)`);
          }
          
          resolve({
            connectionId,
            success: connectionSuccess,
            receivedData,
            closeCode: code,
            closeReason: reason.toString()
          });
        });

        ws.on('error', (error) => {
          clearTimeout(timeout);
          console.log(`❌ Connection ${connectionId} error: ${error.message}`);
          resolve({
            connectionId,
            success: false,
            receivedData: false,
            error: error.message
          });
        });
      });

      connectionPromises.push(connectionPromise);
      
      // Stagger connections
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    const results = await Promise.all(connectionPromises);

    // Remove error monitor
    if (devServerProcess && devServerProcess.stderr) {
      devServerProcess.stderr.removeListener('data', errorMonitor);
    }

    // Analyze results
    console.log('\n📋 PROXY FIX VERIFICATION RESULTS:');
    console.log('=====================================');

    results.forEach(result => {
      const status = result.success ? '✅ SUCCESS' : '❌ FAILED';
      console.log(`📋 Connection ${result.connectionId}: ${status}`);
      if (result.closeCode) {
        console.log(`📋   Close code: ${result.closeCode}`);
      }
      if (result.error) {
        console.log(`📋   Error: ${result.error}`);
      }
      if (result.success) {
        successfulConnections++;
      }
    });

    console.log(`\n📋 Summary: ${successfulConnections}/${totalConnections} connections successful`);
    console.log(`📋 ERR_STREAM_WRITE_AFTER_END detected: ${errorDetected ? 'YES ❌' : 'NO ✅'}`);
    console.log(`📋 Invalid Host/Origin header detected: ${invalidHeaderDetected ? 'YES ❌' : 'NO ✅'}`);

    if (!errorDetected && !invalidHeaderDetected && successfulConnections > 0) {
      console.log('\n🎉 SUCCESS: Proxy fix appears to be working!');
      console.log('📋 No ERR_STREAM_WRITE_AFTER_END errors detected');
      console.log('📋 No Invalid Host/Origin header errors detected');
      console.log('📋 Connections are succeeding');
    } else {
      console.log('\n❌ ISSUE: Proxy fix may not be complete');
      if (errorDetected) console.log('📋 - Still seeing ERR_STREAM_WRITE_AFTER_END errors');
      if (invalidHeaderDetected) console.log('📋 - Still seeing Invalid Host/Origin header errors');
      if (successfulConnections === 0) console.log('📋 - No connections succeeded');
    }

    // Test assertions
    expect(successfulConnections).toBeGreaterThan(0);
    expect(errorDetected).toBe(false);
    expect(invalidHeaderDetected).toBe(false);
  }, 20000);
});
