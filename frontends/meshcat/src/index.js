const { generateWebSocketURL } = require('./connection-utils');

// Initialize MeshCat with proxy-aware WebSocket connection
function initializeMeshCat() {
  console.log('Initializing MeshCat with proxy support...');
  
  // Generate the appropriate WebSocket URL based on environment
  const wsUrl = generateWebSocketURL();
  console.log('WebSocket URL:', wsUrl);
  
  // Here you would normally initialize the MeshCat viewer
  // For now, we'll just demonstrate the connection logic
  try {
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = function(event) {
      console.log('WebSocket connection opened:', event);
    };
    
    ws.onmessage = function(event) {
      console.log('WebSocket message received:', event.data);
    };
    
    ws.onerror = function(error) {
      console.error('WebSocket error:', error);
    };
    
    ws.onclose = function(event) {
      console.log('WebSocket connection closed:', event);
    };
    
    return ws;
  } catch (error) {
    console.error('Failed to create WebSocket connection:', error);
    return null;
  }
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeMeshCat);
} else {
  initializeMeshCat();
}

// Export for use in tests or other modules
module.exports = { initializeMeshCat };
