#!/bin/bash

echo "=== MeshCat Port Status ==="
echo ""

echo "MeshCat ZMQ servers running:"
ps aux | grep "meshcat.servers.zmqserver" | grep -v grep | while read line; do
    pid=$(echo $line | awk '{print $2}')
    echo "  PID $pid: $line"
done

echo ""
echo "Port usage:"
echo "  6000: ZMQ server (default)"
echo "  7000: WebSocket server (default)"
echo "  7001: WebSocket server (alternative)"
echo "  7002: WebSocket server (alternative)"
echo "  7003: WebSocket server (current backend)"

echo ""
echo "Current connections:"
lsof -i :6000 -i :7000 -i :7001 -i :7002 -i :7003 2>/dev/null | grep LISTEN || echo "  No active listeners found"

echo ""
echo "Frontend status:"
if pgrep -f "webpack.*serve" > /dev/null; then
    echo "  ✅ Frontend running on port 3000"
else
    echo "  ❌ Frontend not running"
fi

echo ""
echo "Backend status:"
if pgrep -f "meshcat_backend.py" > /dev/null; then
    echo "  ✅ Backend running"
else
    echo "  ❌ Backend not running"
fi 