/**
 * Connection utilities for MeshCat WebSocket proxy
 */

/**
 * Determines if we're in development environment
 * @returns {boolean} True if in development environment
 */
function isDevelopment() {
  // Check NODE_ENV first - explicit development
  if (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development') {
    return true;
  }
  
  // Check if we're on localhost with a dev port (local development)
  if (typeof window !== 'undefined' && window.location) {
    const isLocalhost = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' ||
                       window.location.host.startsWith('localhost:');
    const isDevPort = ['3000', '8080', '3001'].includes(window.location.port);
    
    if (isLocalhost && isDevPort) {
      return true;
    }
  }
  
  // If NODE_ENV is explicitly production and not localhost, it's production
  return false;
}

/**
 * Checks if current port suggests development environment
 * @returns {boolean} True if on development port
 */
function isDevPort() {
  if (typeof window !== 'undefined' && window.location) {
    const port = window.location.port;
    // Common development ports
    return port === '3000' || port === '8080' || port === '3001';
  }
  return false;
}

/**
 * Generates the appropriate WebSocket URL based on environment
 * @param {string} [customUrl] - Custom URL to use if provided 
 * @returns {string} WebSocket URL
 */
function generateWebSocketURL(customUrl) {
  // If custom URL provided, use it
  if (customUrl) {
    return customUrl;
  }

  // In development, use proxy to same origin
  if (isDevelopment()) {
    if (typeof window !== 'undefined' && window.location) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}/ws`;
    }
    // Fallback if window is not available but we're in development
    return 'ws://localhost:3000/ws';
  }

  // Production - direct connection to meshcat server
  return 'ws://127.0.0.1:7000/ws';
}

module.exports = {
  isDevelopment,
  generateWebSocketURL
};
