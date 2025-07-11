#!/bin/bash

echo "=== Starting MeshCat URDF Visualizer ==="
echo ""

# Kill any existing MeshCat servers
echo "Cleaning up existing MeshCat servers..."
pkill -f "meshcat.servers.zmqserver" 2>/dev/null
pkill -f meshcat_backend 2>/dev/null

echo ""
echo "1. Starting backend (WebSocket server on port 7000)..."
echo "   Run: python backends/meshcat_backend.py"
echo ""

echo "2. Starting frontend (Development server on port 3000)..."
echo "   Run: cd frontends/meshcat && npm start"
echo ""

echo "3. Open browser to: http://localhost:3000"
echo ""

echo "=== Port Configuration ==="
echo "Backend:  WebSocket server on port 7000 (consistent)"
echo "Frontend: Development server on port 3000"
echo ""

echo "Note: The backend will now use port 7000 consistently!"
echo "      No more changing ports!" 