const path = require('path');

describe('Webpack Proxy Configuration', () => {
  let webpackConfig;

  beforeEach(() => {
    // Reset the webpack config for each test
    jest.resetModules();
  });

  test('should have proxy configuration for /ws endpoint', () => {
    // This test will fail initially until we implement the proxy
    const webpackConfigPath = path.resolve(__dirname, '../../webpack.config.js');
    const configs = require(webpackConfigPath);
    
    // webpack.config.js exports an array, get the development config
    const devConfig = Array.isArray(configs) ? configs[0] : configs;
    
    expect(devConfig.devServer).toBeDefined();
    expect(devConfig.devServer.proxy).toBeDefined();
    expect(devConfig.devServer.proxy['/ws']).toBeDefined();
    
    const proxyConfig = devConfig.devServer.proxy['/ws'];
    expect(proxyConfig.target).toBe('ws://127.0.0.1:7000');
    expect(proxyConfig.ws).toBe(true);
    expect(proxyConfig.changeOrigin).toBe(true);
  });

  test('should maintain existing devServer configuration', () => {
    const webpackConfigPath = path.resolve(__dirname, '../../webpack.config.js');
    const configs = require(webpackConfigPath);
    const devConfig = Array.isArray(configs) ? configs[0] : configs;
    
    expect(devConfig.devServer.port).toBe(3000);
    expect(devConfig.devServer.hot).toBe(true);
    expect(devConfig.devServer.compress).toBe(true);
  });

  test('should have proper static directory configuration', () => {
    const webpackConfigPath = path.resolve(__dirname, '../../webpack.config.js');
    const configs = require(webpackConfigPath);
    const devConfig = Array.isArray(configs) ? configs[0] : configs;
    
    expect(devConfig.devServer.static).toBeDefined();
    expect(devConfig.devServer.static.directory).toBeDefined();
  });
});
