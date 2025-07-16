const WebSocket = require('ws');

describe('Error Reproduction Diagnostic Tests', () => {
  describe('ERR_STREAM_WRITE_AFTER_END Reproduction', () => {
    test('should reproduce write-after-end error conditions', async () => {
      /**
       * PURPOSE: Systematically reproduce the specific ERR_STREAM_WRITE_AFTER_END error
       * SUCCESS: Error reproduced - confirms error conditions and triggers
       * FAILURE: Error not reproduced - different issue or conditions changed
       * NEXT STEPS: Fix the specific conditions that cause the error
       */
      console.log('📋 Attempting to reproduce ERR_STREAM_WRITE_AFTER_END error');
      
      const errorScenarios = [
        {
          name: 'Rapid connect/disconnect cycles',
          test: () => rapidConnectDisconnect()
        },
        {
          name: 'Connection to non-existent path',
          test: () => connectToNonExistentPath()
        },
        {
          name: 'Immediate close after connect',
          test: () => immediateCloseAfterConnect()
        },
        {
          name: 'Multiple messages then close',
          test: () => multipleMessagesThenClose()
        },
        {
          name: 'Connection termination race condition',
          test: () => connectionTerminationRace()
        }
      ];

      const results = [];

      for (const scenario of errorScenarios) {
        console.log(`📋 Testing scenario: ${scenario.name}`);
        
        try {
          const result = await scenario.test();
          results.push({
            scenario: scenario.name,
            ...result
          });
        } catch (error) {
          results.push({
            scenario: scenario.name,
            error: error.message,
            reproduced: false
          });
        }
      }

      // Analyze error reproduction results
      console.log('📋 Error reproduction analysis:');
      const reproducedErrors = results.filter(r => r.reproduced);
      const failedReproductions = results.filter(r => !r.reproduced);

      results.forEach(result => {
        const status = result.reproduced ? '🎯 REPRODUCED' : '❌ NOT REPRODUCED';
        console.log(`📋   ${result.scenario}: ${status}`);
        if (result.errorType) {
          console.log(`📋     Error type: ${result.errorType}`);
        }
        if (result.errorCount) {
          console.log(`📋     Error count: ${result.errorCount}`);
        }
        if (result.details) {
          console.log(`📋     Details: ${result.details}`);
        }
      });

      console.log(`📋 Error reproduction: ${reproducedErrors.length}/${results.length} scenarios reproduced errors`);

      if (reproducedErrors.length > 0) {
        console.log('🎯 DIAGNOSIS: Successfully reproduced error conditions');
        console.log('📋 ACTION: Focus on fixing the conditions that cause these errors');
        reproducedErrors.forEach(error => {
          console.log(`📋   - Fix: ${error.scenario}`);
        });
      } else {
        console.log('📋 DIAGNOSIS: Could not reproduce ERR_STREAM_WRITE_AFTER_END');
        console.log('📋 ACTION: Error may be environment-specific or requires different conditions');
      }

      expect(results.length).toBe(errorScenarios.length);
    }, 30000);

    async function rapidConnectDisconnect() {
      /**
       * This scenario attempts to reproduce errors caused by rapid connection cycling
       */
      return new Promise((resolve) => {
        const connections = [];
        let errorCount = 0;
        let writeAfterEndErrors = 0;
        let completedConnections = 0;
        const totalConnections = 10;

        for (let i = 0; i < totalConnections; i++) {
          setTimeout(() => {
            const ws = new WebSocket('ws://127.0.0.1:7000/ws'); // Intentionally wrong path
            connections.push(ws);

            ws.on('open', () => {
              // Immediately try to send and close
              ws.send(`rapid-test-${i}`);
              setTimeout(() => ws.close(), 10);
            });

            ws.on('error', (error) => {
              errorCount++;
              if (error.message.includes('write after end')) {
                writeAfterEndErrors++;
              }
            });

            ws.on('close', () => {
              completedConnections++;
              if (completedConnections === totalConnections) {
                resolve({
                  reproduced: writeAfterEndErrors > 0,
                  errorType: 'write after end',
                  errorCount: writeAfterEndErrors,
                  totalErrors: errorCount,
                  details: `${writeAfterEndErrors} write-after-end errors out of ${totalConnections} connections`
                });
              }
            });
          }, i * 50); // Stagger connections
        }

        setTimeout(() => {
          connections.forEach(ws => ws.terminate());
          resolve({
            reproduced: writeAfterEndErrors > 0,
            errorType: 'timeout',
            errorCount: writeAfterEndErrors,
            details: 'Test timed out'
          });
        }, 10000);
      });
    }

    async function connectToNonExistentPath() {
      /**
       * This scenario tests connecting to paths that don't exist (like /ws when server serves /)
       */
      return new Promise((resolve) => {
        const ws = new WebSocket('ws://127.0.0.1:7000/ws');
        let errorOccurred = false;
        let errorMessage = null;

        ws.on('open', () => {
          // This shouldn't happen if path doesn't exist
          ws.close();
        });

        ws.on('error', (error) => {
          errorOccurred = true;
          errorMessage = error.message;
          
          if (error.message.includes('404')) {
            resolve({
              reproduced: true,
              errorType: '404 path not found',
              details: 'Server returned 404 for /ws path - this can trigger write-after-end'
            });
          }
        });

        ws.on('close', (code, reason) => {
          if (!errorOccurred) {
            resolve({
              reproduced: false,
              details: `Connection closed without error: code=${code}`
            });
          } else {
            resolve({
              reproduced: errorMessage && errorMessage.includes('404'),
              errorType: 'connection error',
              details: errorMessage
            });
          }
        });

        setTimeout(() => {
          ws.terminate();
          resolve({
            reproduced: false,
            details: 'Connection timeout'
          });
        }, 5000);
      });
    }

    async function immediateCloseAfterConnect() {
      /**
       * This scenario tests immediate connection termination which can cause write-after-end
       */
      return new Promise((resolve) => {
        const ws = new WebSocket('ws://127.0.0.1:7000/');
        let errorOccurred = false;
        let errorType = null;

        ws.on('open', () => {
          // Immediately terminate connection
          ws.terminate();
        });

        ws.on('error', (error) => {
          errorOccurred = true;
          errorType = error.message;
        });

        ws.on('close', () => {
          resolve({
            reproduced: errorOccurred && errorType && errorType.includes('write after end'),
            errorType: errorType,
            details: 'Immediate termination after open'
          });
        });

        setTimeout(() => {
          resolve({
            reproduced: false,
            details: 'Immediate close test completed without write-after-end error'
          });
        }, 2000);
      });
    }

    async function multipleMessagesThenClose() {
      /**
       * This scenario sends multiple messages rapidly then closes
       */
      return new Promise((resolve) => {
        const ws = new WebSocket('ws://127.0.0.1:7000/');
        let errorOccurred = false;
        let errorType = null;
        let messagesSent = 0;

        ws.on('open', () => {
          // Send multiple messages rapidly
          for (let i = 0; i < 5; i++) {
            try {
              ws.send(`message-${i}`);
              messagesSent++;
            } catch (error) {
              errorOccurred = true;
              errorType = error.message;
            }
          }

          // Close immediately after sending
          setTimeout(() => ws.close(), 10);
        });

        ws.on('error', (error) => {
          errorOccurred = true;
          errorType = error.message;
        });

        ws.on('close', () => {
          resolve({
            reproduced: errorOccurred && errorType && errorType.includes('write after end'),
            errorType: errorType,
            details: `Sent ${messagesSent} messages before close`
          });
        });

        setTimeout(() => {
          ws.terminate();
          resolve({
            reproduced: false,
            details: 'Multiple messages test completed'
          });
        }, 3000);
      });
    }

    async function connectionTerminationRace() {
      /**
       * This scenario creates race conditions between connection and termination
       */
      return new Promise((resolve) => {
        const ws = new WebSocket('ws://127.0.0.1:7000/');
        let errorOccurred = false;
        let errorType = null;

        // Set up race condition - terminate while connection may still be establishing
        setTimeout(() => {
          try {
            ws.send('race-condition-message');
            ws.close();
          } catch (error) {
            errorOccurred = true;
            errorType = error.message;
          }
        }, 5); // Very short delay to create race condition

        ws.on('open', () => {
          // Connection opened, but termination may have already been called
          try {
            ws.send('after-open-message');
          } catch (error) {
            errorOccurred = true;
            errorType = error.message;
          }
        });

        ws.on('error', (error) => {
          errorOccurred = true;
          errorType = error.message;
        });

        ws.on('close', () => {
          resolve({
            reproduced: errorOccurred && errorType && errorType.includes('write after end'),
            errorType: errorType,
            details: 'Race condition between connect and terminate'
          });
        });

        setTimeout(() => {
          ws.terminate();
          resolve({
            reproduced: false,
            details: 'Race condition test completed'
          });
        }, 2000);
      });
    }
  });

  describe('Proxy-Specific Error Reproduction', () => {
    test('should reproduce proxy-related connection errors', async () => {
      /**
       * PURPOSE: Reproduce errors specific to proxy configuration and forwarding
       * SUCCESS: Proxy errors reproduced - identifies proxy-specific issues
       * FAILURE: No proxy errors - proxy configuration may be correct
       * NEXT STEPS: Fix identified proxy configuration issues
       */
      console.log('📋 Testing proxy-specific error scenarios');

      const proxyScenarios = [
        {
          name: 'Connection through non-existent proxy',
          url: 'ws://localhost:3000/ws',
          expectedError: 'ECONNREFUSED'
        },
        {
          name: 'Wrong proxy target path',
          url: 'ws://127.0.0.1:7000/wrong-path',
          expectedError: '404'
        },
        {
          name: 'Proxy target server down',
          url: 'ws://127.0.0.1:9999/ws',
          expectedError: 'ECONNREFUSED'
        }
      ];

      const results = [];

      for (const scenario of proxyScenarios) {
        console.log(`📋 Testing: ${scenario.name}`);

        const result = await new Promise((resolve) => {
          const ws = new WebSocket(scenario.url);
          let errorOccurred = false;
          let errorMessage = null;

          const timeout = setTimeout(() => {
            ws.terminate();
            resolve({
              scenario: scenario.name,
              reproduced: false,
              error: 'timeout',
              expected: scenario.expectedError
            });
          }, 5000);

          ws.on('open', () => {
            clearTimeout(timeout);
            ws.close();
            resolve({
              scenario: scenario.name,
              reproduced: false,
              error: 'unexpected_success',
              expected: scenario.expectedError,
              details: 'Connection succeeded when error was expected'
            });
          });

          ws.on('error', (error) => {
            clearTimeout(timeout);
            errorOccurred = true;
            errorMessage = error.message;

            const reproduced = errorMessage.includes(scenario.expectedError);
            resolve({
              scenario: scenario.name,
              reproduced,
              error: errorMessage,
              expected: scenario.expectedError,
              details: reproduced ? 'Expected error reproduced' : 'Different error than expected'
            });
          });

          ws.on('close', (code) => {
            if (!errorOccurred) {
              clearTimeout(timeout);
              resolve({
                scenario: scenario.name,
                reproduced: false,
                error: `close_code_${code}`,
                expected: scenario.expectedError,
                details: 'Connection closed without expected error'
              });
            }
          });
        });

        results.push(result);
      }

      // Analyze proxy error results
      console.log('📋 Proxy error reproduction analysis:');
      const reproducedErrors = results.filter(r => r.reproduced);

      results.forEach(result => {
        const status = result.reproduced ? '🎯 REPRODUCED' : '❌ NOT REPRODUCED';
        console.log(`📋   ${result.scenario}: ${status}`);
        console.log(`📋     Expected: ${result.expected}`);
        console.log(`📋     Actual: ${result.error}`);
        if (result.details) {
          console.log(`📋     Details: ${result.details}`);
        }
      });

      if (reproducedErrors.length > 0) {
        console.log('🎯 DIAGNOSIS: Proxy-related errors successfully reproduced');
        console.log('📋 ACTION: Fix proxy configuration based on reproduced errors');
      } else {
        console.log('📋 DIAGNOSIS: Proxy errors not reproduced as expected');
        console.log('📋 ACTION: Check if proxy and backend setup matches test assumptions');
      }

      expect(results.length).toBe(proxyScenarios.length);
    }, 20000);
  });

  describe('Connection Lifecycle Error Analysis', () => {
    test('should analyze connection state transitions that cause errors', async () => {
      /**
       * PURPOSE: Identify specific connection state transitions that trigger errors
       * SUCCESS: Error-causing transitions identified - provides fix targets
       * FAILURE: No problematic transitions - error may be configuration-based
       * NEXT STEPS: Fix identified problematic state transitions
       */
      console.log('📋 Analyzing connection lifecycle for error-prone transitions');

      const lifecycleTests = [
        {
          name: 'CONNECTING → CLOSING transition',
          test: () => testConnectingToClosing()
        },
        {
          name: 'OPEN → CLOSING rapid transition',
          test: () => testOpenToClosingRapid()
        },
        {
          name: 'Multiple state changes',
          test: () => testMultipleStateChanges()
        }
      ];

      const results = [];

      for (const test of lifecycleTests) {
        console.log(`📋 Testing: ${test.name}`);
        
        try {
          const result = await test.test();
          results.push({
            test: test.name,
            ...result
          });
        } catch (error) {
          results.push({
            test: test.name,
            error: error.message,
            problematic: false
          });
        }
      }

      // Analyze lifecycle results
      console.log('📋 Connection lifecycle analysis:');
      const problematicTransitions = results.filter(r => r.problematic);

      results.forEach(result => {
        const status = result.problematic ? '⚠️  PROBLEMATIC' : '✅ CLEAN';
        console.log(`📋   ${result.test}: ${status}`);
        if (result.stateSequence) {
          console.log(`📋     States: ${result.stateSequence.join(' → ')}`);
        }
        if (result.errorCount) {
          console.log(`📋     Errors: ${result.errorCount}`);
        }
        if (result.details) {
          console.log(`📋     Details: ${result.details}`);
        }
      });

      if (problematicTransitions.length > 0) {
        console.log('⚠️  DIAGNOSIS: Problematic connection state transitions found');
        console.log('📋 ACTION: Fix connection state management for these transitions');
      } else {
        console.log('✅ DIAGNOSIS: Connection state transitions appear clean');
      }

      expect(results.length).toBe(lifecycleTests.length);

      async function testConnectingToClosing() {
        return new Promise((resolve) => {
          const ws = new WebSocket('ws://127.0.0.1:7000/');
          const states = [];
          let errorCount = 0;

          // Immediately try to close while connecting
          setTimeout(() => {
            states.push(`readyState_${ws.readyState}_before_close`);
            try {
              ws.close();
              states.push('close_called');
            } catch (error) {
              errorCount++;
              states.push(`close_error: ${error.message}`);
            }
          }, 1);

          ws.on('open', () => {
            states.push('opened');
          });

          ws.on('close', () => {
            states.push('closed');
            resolve({
              problematic: errorCount > 0,
              stateSequence: states,
              errorCount,
              details: 'Attempted close during connection establishment'
            });
          });

          ws.on('error', (error) => {
            errorCount++;
            states.push(`error: ${error.message}`);
          });

          setTimeout(() => {
            ws.terminate();
            resolve({
              problematic: errorCount > 0,
              stateSequence: states,
              errorCount,
              details: 'Test timeout'
            });
          }, 3000);
        });
      }

      async function testOpenToClosingRapid() {
        return new Promise((resolve) => {
          const ws = new WebSocket('ws://127.0.0.1:7000/');
          const states = [];
          let errorCount = 0;

          ws.on('open', () => {
            states.push('opened');
            
            // Rapid operations after open
            try {
              ws.send('test message');
              states.push('message_sent');
              ws.close();
              states.push('close_called');
            } catch (error) {
              errorCount++;
              states.push(`rapid_operation_error: ${error.message}`);
            }
          });

          ws.on('close', () => {
            states.push('closed');
            resolve({
              problematic: errorCount > 0,
              stateSequence: states,
              errorCount,
              details: 'Rapid operations immediately after open'
            });
          });

          ws.on('error', (error) => {
            errorCount++;
            states.push(`error: ${error.message}`);
          });

          setTimeout(() => {
            ws.terminate();
            resolve({
              problematic: errorCount > 0,
              stateSequence: states,
              errorCount,
              details: 'Test timeout'
            });
          }, 3000);
        });
      }

      async function testMultipleStateChanges() {
        return new Promise((resolve) => {
          const ws = new WebSocket('ws://127.0.0.1:7000/');
          const states = [];
          let errorCount = 0;

          // Monitor state changes
          const checkState = () => {
            states.push(`state_${ws.readyState}`);
          };

          const stateChecker = setInterval(checkState, 10);

          ws.on('open', () => {
            states.push('event_open');
            checkState();
          });

          ws.on('close', () => {
            states.push('event_close');
            clearInterval(stateChecker);
            resolve({
              problematic: errorCount > 0,
              stateSequence: states,
              errorCount,
              details: 'Multiple state transitions monitored'
            });
          });

          ws.on('error', (error) => {
            errorCount++;
            states.push(`event_error: ${error.message}`);
          });

          // Close after delay
          setTimeout(() => {
            checkState();
            ws.close();
          }, 1000);

          setTimeout(() => {
            clearInterval(stateChecker);
            ws.terminate();
            resolve({
              problematic: errorCount > 0,
              stateSequence: states,
              errorCount,
              details: 'Test timeout'
            });
          }, 5000);
        });
      }
    }, 25000);
  });
});
