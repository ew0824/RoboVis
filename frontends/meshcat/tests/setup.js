// Jest setup file
global.console = {
  ...console,
  // uncomment to ignore specific log levels
  // log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};

// Mock WebSocket for tests
global.WebSocket = jest.fn();
