#!/bin/bash

echo "Starting MeshCat URDF Visualizer..."
echo ""

echo "1. Starting backend (WebSocket server on port 7000)..."
echo "   Run: python backends/meshcat_backend.py"
echo ""

echo "2. Starting frontend (Development server on port 3000)..."
echo "   Run: cd frontends/meshcat && npm start"
echo ""

echo "3. Open browser to: http://localhost:3000"
echo ""

echo "Note: Make sure to install frontend dependencies first:"
echo "   cd frontends/meshcat && npm install"
echo "" 