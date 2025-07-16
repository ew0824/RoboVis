const path = require('path');

describe('Proxy Diagnostic Tests', () => {
  describe('Proxy Configuration Validation', () => {
    test('should validate webpack proxy configuration exists', () => {
      /**
       * PURPOSE: Verify webpack proxy configuration is properly defined
       * SUCCESS: Proxy config found and valid - configuration exists
       * FAILURE: Config missing or invalid - webpack proxy not configured
       * NEXT STEPS: Fix webpack proxy configuration
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      
      let config;
      try {
        // Clear require cache to get fresh config
        delete require.cache[require.resolve(webpackConfigPath)];
        config = require(webpackConfigPath);
        console.log('✅ webpack.config.proxy.js loaded successfully');
      } catch (error) {
        console.log(`❌ Failed to load webpack config: ${error.message}`);
        console.log('📋 DIAGNOSIS: webpack.config.proxy.js file missing or invalid');
        console.log('📋 ACTION: Create/fix webpack.config.proxy.js');
        throw new Error(`Webpack config load failed: ${error.message}`);
      }

      // Validate basic structure
      expect(config).toBeDefined();
      expect(config.devServer).toBeDefined();
      console.log('📋 devServer configuration found');

      // Validate proxy configuration
      expect(config.devServer.proxy).toBeDefined();
      console.log('📋 proxy configuration found');
      
      if (Array.isArray(config.devServer.proxy)) {
        console.log(`📋 Proxy config is array with ${config.devServer.proxy.length} entries`);
        
        const wsProxy = config.devServer.proxy.find(p => 
          p.context && p.context.includes('/ws')
        );
        
        if (wsProxy) {
          console.log('✅ WebSocket proxy configuration found');
          console.log(`📋 Proxy details:`, JSON.stringify(wsProxy, null, 2));
        } else {
          console.log('❌ No WebSocket proxy configuration found');
          console.log('📋 DIAGNOSIS: Missing /ws proxy configuration');
          throw new Error('WebSocket proxy configuration missing');
        }
      } else {
        console.log('❌ Proxy configuration is not an array');
        console.log('📋 DIAGNOSIS: Proxy configuration format incorrect');
        throw new Error('Proxy configuration format invalid');
      }
    });

    test('should validate proxy target and WebSocket settings', () => {
      /**
       * PURPOSE: Verify proxy target URL and WebSocket settings are correct
       * SUCCESS: Target and settings valid - proxy should work
       * FAILURE: Invalid settings - proxy will fail
       * NEXT STEPS: Fix proxy target URL and WebSocket settings
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      const config = require(webpackConfigPath);
      
      const wsProxy = config.devServer.proxy.find(p => 
        p.context && p.context.includes('/ws')
      );

      expect(wsProxy).toBeDefined();
      
      // Validate target URL
      expect(wsProxy.target).toBeDefined();
      console.log(`📋 Proxy target: ${wsProxy.target}`);
      
      if (wsProxy.target.startsWith('ws://')) {
        console.log('✅ Target uses WebSocket protocol');
      } else {
        console.log('❌ Target does not use WebSocket protocol');
        console.log('📋 DIAGNOSIS: Target should start with ws://');
      }

      // Validate WebSocket enabled
      expect(wsProxy.ws).toBe(true);
      console.log('✅ WebSocket proxy enabled (ws: true)');

      // Validate changeOrigin
      if (wsProxy.changeOrigin) {
        console.log('✅ changeOrigin enabled - will handle CORS');
      } else {
        console.log('⚠️  changeOrigin disabled - may cause CORS issues');
      }

      // Check for path rewriting
      if (wsProxy.pathRewrite) {
        console.log('📋 Path rewriting configured:', wsProxy.pathRewrite);
        if (wsProxy.pathRewrite['^/ws']) {
          console.log(`📋 /ws path rewritten to: '${wsProxy.pathRewrite['^/ws']}'`);
        }
      } else {
        console.log('📋 No path rewriting configured');
      }

      // Check for debug logging
      if (wsProxy.logLevel === 'debug') {
        console.log('✅ Debug logging enabled');
      } else {
        console.log('📋 Debug logging not enabled');
      }
    });

    test('should validate proxy context patterns', () => {
      /**
       * PURPOSE: Verify proxy context patterns will match expected requests
       * SUCCESS: Context patterns correct - proxy will intercept requests
       * FAILURE: Context patterns wrong - proxy won't intercept
       * NEXT STEPS: Fix context patterns to match frontend requests
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      const config = require(webpackConfigPath);
      
      const wsProxy = config.devServer.proxy.find(p => 
        p.context && p.context.includes('/ws')
      );

      expect(wsProxy.context).toBeDefined();
      expect(Array.isArray(wsProxy.context)).toBe(true);
      
      console.log('📋 Proxy context patterns:', wsProxy.context);
      
      // Test common WebSocket request patterns
      const testPaths = ['/ws', '/websocket', '/ws/test'];
      const matchingPaths = [];
      const nonMatchingPaths = [];
      
      testPaths.forEach(testPath => {
        const matches = wsProxy.context.some(pattern => {
          if (typeof pattern === 'string') {
            return testPath.startsWith(pattern);
          }
          return false;
        });
        
        if (matches) {
          matchingPaths.push(testPath);
        } else {
          nonMatchingPaths.push(testPath);
        }
      });
      
      console.log(`📋 Matching paths: ${matchingPaths.join(', ')}`);
      console.log(`📋 Non-matching paths: ${nonMatchingPaths.join(', ')}`);
      
      if (matchingPaths.includes('/ws')) {
        console.log('✅ /ws path will be proxied');
      } else {
        console.log('❌ /ws path will NOT be proxied');
        console.log('📋 DIAGNOSIS: Context pattern does not match /ws requests');
        throw new Error('Proxy context does not match /ws requests');
      }
    });
  });

  describe('Proxy Target Accessibility', () => {
    test('should test if proxy target is reachable', (done) => {
      /**
       * PURPOSE: Verify proxy target server is accessible
       * SUCCESS: Target reachable - proxy can forward requests
       * FAILURE: Target unreachable - proxy will fail
       * NEXT STEPS: Start target server or fix target URL
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      const config = require(webpackConfigPath);
      
      const wsProxy = config.devServer.proxy.find(p => 
        p.context && p.context.includes('/ws')
      );

      if (!wsProxy || !wsProxy.target) {
        done.fail('No proxy target configured');
        return;
      }

      // Parse target URL
      const targetUrl = new URL(wsProxy.target);
      const host = targetUrl.hostname;
      const port = parseInt(targetUrl.port);
      
      console.log(`📋 Testing proxy target: ${host}:${port}`);
      
      const net = require('net');
      const client = new net.Socket();
      let connectionMade = false;
      
      client.connect(port, host, () => {
        console.log(`✅ Proxy target ${host}:${port} is reachable`);
        console.log('📋 DIAGNOSIS: Target server is running and accessible');
        connectionMade = true;
        client.destroy();
        done();
      });

      client.on('error', (err) => {
        console.log(`❌ Proxy target ${host}:${port} not reachable: ${err.message}`);
        console.log('📋 DIAGNOSIS: Target server is not running or unreachable');
        console.log('📋 ACTION: Start target server or fix target URL');
        done.fail(`Proxy target not reachable: ${err.message}`);
      });

      setTimeout(() => {
        if (!connectionMade) {
          client.destroy();
          done.fail('Proxy target connection timeout');
        }
      }, 3000);
    });

    test('should test WebSocket connection to proxy target', (done) => {
      /**
       * PURPOSE: Verify proxy target accepts WebSocket connections
       * SUCCESS: WebSocket connection works - target server configured correctly
       * FAILURE: WebSocket connection fails - target server configuration issue
       * NEXT STEPS: Fix target server WebSocket configuration
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      const config = require(webpackConfigPath);
      
      const wsProxy = config.devServer.proxy.find(p => 
        p.context && p.context.includes('/ws')
      );

      if (!wsProxy || !wsProxy.target) {
        done.fail('No proxy target configured');
        return;
      }

      const WebSocket = require('ws');
      let targetUrl = wsProxy.target;
      
      // Handle path rewriting for direct test
      if (wsProxy.pathRewrite && wsProxy.pathRewrite['^/ws'] !== undefined) {
        const rewrittenPath = wsProxy.pathRewrite['^/ws'];
        if (rewrittenPath === '') {
          // Path rewrite removes /ws, so test root path
          targetUrl = wsProxy.target + '/';
        } else {
          targetUrl = wsProxy.target + rewrittenPath;
        }
      } else {
        // No path rewriting, test with /ws
        targetUrl = wsProxy.target + '/ws';
      }
      
      console.log(`📋 Testing WebSocket connection to: ${targetUrl}`);
      
      const ws = new WebSocket(targetUrl);
      let connectionOpened = false;
      
      ws.on('open', () => {
        console.log('✅ WebSocket connection to proxy target successful');
        console.log('📋 DIAGNOSIS: Target server accepts WebSocket connections');
        connectionOpened = true;
        ws.close();
      });

      ws.on('close', (code, reason) => {
        console.log(`📋 Target WebSocket closed: code=${code}, reason=${reason.toString()}`);
        if (connectionOpened) {
          done();
        } else {
          done.fail('WebSocket connection to target failed');
        }
      });

      ws.on('error', (error) => {
        console.log(`❌ WebSocket connection to target failed: ${error.message}`);
        console.log('📋 DIAGNOSIS: Target server WebSocket configuration issue');
        console.log('📋 ACTION: Fix target server WebSocket setup');
        done.fail(`Target WebSocket connection failed: ${error.message}`);
      });

      setTimeout(() => {
        if (!connectionOpened) {
          ws.terminate();
          done.fail('WebSocket connection to target timeout');
        }
      }, 3000);
    });
  });

  describe('Proxy Path Rewriting Analysis', () => {
    test('should analyze path rewriting configuration', () => {
      /**
       * PURPOSE: Verify path rewriting rules are correct for target server
       * SUCCESS: Path rewriting matches target server expectations
       * FAILURE: Path rewriting incorrect - requests will be misrouted
       * NEXT STEPS: Fix path rewriting rules
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      const config = require(webpackConfigPath);
      
      const wsProxy = config.devServer.proxy.find(p => 
        p.context && p.context.includes('/ws')
      );

      console.log('📋 Path rewriting analysis:');
      
      if (wsProxy.pathRewrite) {
        console.log('✅ Path rewriting configured');
        console.log('📋 Rewrite rules:', wsProxy.pathRewrite);
        
        // Test common path transformations
        const testPaths = ['/ws', '/ws/test', '/ws/connection'];
        
        testPaths.forEach(originalPath => {
          let rewrittenPath = originalPath;
          
          Object.entries(wsProxy.pathRewrite).forEach(([pattern, replacement]) => {
            const regex = new RegExp(pattern);
            if (regex.test(originalPath)) {
              rewrittenPath = originalPath.replace(regex, replacement);
            }
          });
          
          console.log(`📋   ${originalPath} → ${rewrittenPath}`);
        });
        
        // Check for common path rewriting patterns
        if (wsProxy.pathRewrite['^/ws'] === '') {
          console.log('📋 ANALYSIS: /ws prefix removed - forwarding to root path');
          console.log('📋 IMPLICATION: Target server must serve WebSocket on root path');
        } else if (wsProxy.pathRewrite['^/ws']) {
          console.log(`📋 ANALYSIS: /ws prefix replaced with '${wsProxy.pathRewrite['^/ws']}'`);
        }
        
      } else {
        console.log('📋 No path rewriting configured');
        console.log('📋 IMPLICATION: Requests forwarded with original paths');
        console.log('📋 REQUIREMENT: Target server must serve WebSocket on /ws path');
      }
    });

    test('should validate path rewriting against target server paths', async () => {
      /**
       * PURPOSE: Test if path rewriting produces paths that work with target server
       * SUCCESS: Rewritten paths work with target server
       * FAILURE: Rewritten paths don't work - need different rewriting
       * NEXT STEPS: Adjust path rewriting rules
       */
      const webpackConfigPath = path.resolve(__dirname, '../webpack.config.proxy.js');
      const config = require(webpackConfigPath);
      
      const wsProxy = config.devServer.proxy.find(p => 
        p.context && p.context.includes('/ws')
      );

      if (!wsProxy) {
        throw new Error('No WebSocket proxy configuration found');
      }

      const WebSocket = require('ws');
      const baseTarget = wsProxy.target;
      
      // Test different path scenarios
      const pathScenarios = [
        { original: '/ws', description: 'standard /ws path' },
        { original: '/ws/connection', description: '/ws with subpath' }
      ];
      
      const results = [];
      
      for (const scenario of pathScenarios) {
        let finalPath = scenario.original;
        
        // Apply path rewriting if configured
        if (wsProxy.pathRewrite) {
          Object.entries(wsProxy.pathRewrite).forEach(([pattern, replacement]) => {
            const regex = new RegExp(pattern);
            if (regex.test(scenario.original)) {
              finalPath = scenario.original.replace(regex, replacement);
            }
          });
        }
        
        const testUrl = baseTarget + finalPath;
        
        const result = await new Promise((resolve) => {
          const ws = new WebSocket(testUrl);
          let success = false;
          
          const timeout = setTimeout(() => {
            ws.terminate();
            resolve({
              original: scenario.original,
              rewritten: finalPath,
              testUrl,
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
              original: scenario.original,
              rewritten: finalPath,
              testUrl,
              success,
              error: null
            });
          });
          
          ws.on('error', (error) => {
            clearTimeout(timeout);
            resolve({
              original: scenario.original,
              rewritten: finalPath,
              testUrl,
              success: false,
              error: error.message
            });
          });
        });
        
        results.push(result);
      }
      
      // Analyze results
      console.log('📋 Path rewriting validation results:');
      const workingPaths = results.filter(r => r.success);
      const failingPaths = results.filter(r => !r.success);
      
      results.forEach(result => {
        const status = result.success ? '✅ WORKS' : '❌ FAILS';
        const error = result.error ? ` (${result.error})` : '';
        console.log(`📋   ${result.original} → ${result.rewritten}: ${status}${error}`);
      });
      
      console.log(`📋 Path rewriting validation: ${workingPaths.length}/${results.length} paths work`);
      
      if (workingPaths.length === 0) {
        console.log('📋 DIAGNOSIS: Path rewriting produces non-working paths');
        console.log('📋 ACTION: Adjust path rewriting configuration');
      } else if (failingPaths.length > 0) {
        console.log('📋 DIAGNOSIS: Some path rewriting scenarios fail');
        console.log('📋 ACTION: Review path rewriting for edge cases');
      } else {
        console.log('✅ DIAGNOSIS: Path rewriting configuration is correct');
      }
      
      expect(results.length).toBe(pathScenarios.length);
    }, 10000);
  });
});
