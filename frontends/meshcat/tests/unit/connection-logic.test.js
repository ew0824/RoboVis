describe('Connection Logic', () => {
  let originalWindow;
  let originalProcess;

  beforeEach(() => {
    // Mock window and process objects
    originalWindow = global.window;
    originalProcess = global.process;
    
    global.window = {
      location: {
        host: 'localhost:3000',
        port: '3000',
        protocol: 'http:'
      }
    };
    
    global.process = {
      env: {
        NODE_ENV: 'development'
      }
    };
  });

  afterEach(() => {
    global.window = originalWindow;
    global.process = originalProcess;
  });

  describe('URL generation', () => {
    test('should generate proxy URL in development environment', () => {
      // This test will fail until we implement the logic
      const { generateWebSocketURL } = require('../../src/connection-utils');
      
      const url = generateWebSocketURL();
      expect(url).toBe('ws://localhost:3000/ws');
    });

    test('should generate direct URL in production environment', () => {
      global.process.env.NODE_ENV = 'production';
      global.window.location.port = '8080';
      global.window.location.host = 'example.com:8080';
      
      const { generateWebSocketURL } = require('../../src/connection-utils');
      
      const url = generateWebSocketURL();
      expect(url).toBe('ws://127.0.0.1:7000/ws');
    });

    test('should use provided URL when specified', () => {
      const { generateWebSocketURL } = require('../../src/connection-utils');
      
      const customUrl = 'ws://custom-server:9000/ws';
      const url = generateWebSocketURL(customUrl);
      expect(url).toBe(customUrl);
    });

    test('should detect development environment by port', () => {
      global.process.env.NODE_ENV = 'production'; // Override NODE_ENV
      global.window.location.port = '3000'; // But still on dev port
      
      const { generateWebSocketURL } = require('../../src/connection-utils');
      
      const url = generateWebSocketURL();
      expect(url).toBe('ws://localhost:3000/ws'); // Should still use proxy
    });
  });

  describe('Environment detection', () => {
    test('should detect development environment', () => {
      const { isDevelopment } = require('../../src/connection-utils');
      
      expect(isDevelopment()).toBe(true);
    });

    test('should detect production environment', () => {
      global.process.env.NODE_ENV = 'production';
      global.window.location.port = '80';
      
      const { isDevelopment } = require('../../src/connection-utils');
      
      expect(isDevelopment()).toBe(false);
    });

    test('should handle missing process.env gracefully', () => {
      delete global.process.env;
      
      const { isDevelopment } = require('../../src/connection-utils');
      
      // Should default to checking port
      expect(isDevelopment()).toBe(true); // port is 3000
    });
  });
});
