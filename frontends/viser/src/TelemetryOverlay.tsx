import React, { useState, useEffect, useRef } from 'react';
import { Box, Text, Paper } from '@mantine/core';
import { decode, encode } from '@msgpack/msgpack';

interface TelemetryData {
  seq: number;
  ns: number;
  nq: number;
  hz: number;
}

interface PongData {
  type: 'pong';
  client_timestamp: number;
  server_timestamp: number;
}

interface TelemetryStats {
  latency: number;
  rate: number;
  messageCount: number;
  bandwidth: number;
  connected: boolean;
  fps: number;
}

export function TelemetryOverlay() {
  const [stats, setStats] = useState<TelemetryStats>({
    latency: 0,
    rate: 0,
    messageCount: 0,
    bandwidth: 0,
    connected: false,
    fps: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const statsRef = useRef<TelemetryStats>(stats);
  const lastMessageTimeRef = useRef<number>(0);
  const bandwidthBytesRef = useRef<number>(0);
  const bandwidthWindowRef = useRef<number>(Date.now());
  
  // FPS tracking refs
  const frameCountRef = useRef<number>(0);
  const fpsStartTimeRef = useRef<number>(performance.now());

  // Ping/Pong latency tracking refs
  const lastPingTimeRef = useRef<number>(0);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Update ref when stats change
  useEffect(() => {
    statsRef.current = stats;
  }, [stats]);

  // Send ping message for latency measurement
  const sendPing = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const pingMessage = {
        type: 'ping',
        client_timestamp: performance.now()
      };
      const pingBytes = encode(pingMessage);
      wsRef.current.send(pingBytes);
      lastPingTimeRef.current = performance.now();
      // console.log('[PING] Sent ping message:', pingMessage); // Debug: uncomment to see pings
    } else {
      console.log('[PING] Cannot send ping - WebSocket not ready');
    }
  };

  useEffect(() => {
    // Connect to telemetry WebSocket server
    const connectWebSocket = () => {
      try {
        // Extract hostname from the websocket URL parameter
        const searchParams = new URLSearchParams(window.location.search);
        const websocketUrl = searchParams.get('websocket');
        let hostname = 'localhost'; // fallback
        
        if (websocketUrl) {
          try {
            const wsUrl = new URL(websocketUrl);
            hostname = wsUrl.hostname;
          } catch (e) {
            console.warn('[TELEMETRY] Failed to parse websocket URL, using localhost');
          }
        }
        
        const telemetryUrl = `ws://${hostname}:8081`;
        console.log(`[TELEMETRY] Extracted hostname: ${hostname}`);
        console.log(`[TELEMETRY] Connecting to ${telemetryUrl}`);

        const ws = new WebSocket(telemetryUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('[TELEMETRY] Connected to telemetry server');
          setStats(prev => ({ ...prev, connected: true }));
          
          // Start ping interval for latency measurement
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
          }
          pingIntervalRef.current = setInterval(sendPing, 1000); // Ping every second
          sendPing(); // Send initial ping
        };

        ws.onmessage = async (event) => {
          try {
            let messageSize = 0;
            let dataForDecode = event.data;
            
            if (event.data instanceof ArrayBuffer) {
              messageSize = event.data.byteLength;
            } else if (event.data instanceof Blob) {
              messageSize = event.data.size;
              // Convert Blob to ArrayBuffer for msgpack
              dataForDecode = await event.data.arrayBuffer();
            } else {
              messageSize = event.data.length || 0;
            }
            
            // Decode msgpack data
            const data = decode(dataForDecode);
            
            // Debug all incoming messages
            if (Math.random() < 0.01) { // Log 1% of messages to see what we're getting
              console.log('[MESSAGE] Received:', data);
            }
            
            // Handle pong responses for latency measurement  
            if (data && typeof data === 'object' && (data as any).type === 'pong') {
              console.log('[PONG] Received pong response:', data);
              const pongData = data as PongData;
              const now = performance.now();
              const roundTripLatency = now - pongData.client_timestamp;
              
              setStats(prev => ({ ...prev, latency: roundTripLatency }));
              
              console.log(`[LATENCY] Round-trip: ${roundTripLatency.toFixed(1)}ms`);
              return; // Don't process as telemetry data
            }
            
            // Handle regular telemetry data
            const telemetryData = data as TelemetryData;
            const latency = statsRef.current.latency; // Use existing latency from pong
            
            // Update bandwidth calculation
            bandwidthBytesRef.current += messageSize;
            const now = Date.now();
            
            // Calculate bandwidth over 1-second window
            let bandwidth = 0;
            if (now - bandwidthWindowRef.current >= 1000) {
              bandwidth = bandwidthBytesRef.current; // bytes per second
              bandwidthBytesRef.current = 0;
              bandwidthWindowRef.current = now;
            } else {
              bandwidth = statsRef.current.bandwidth; // Keep previous value
            }

            setStats(prev => ({
              ...prev,
              latency: latency,
              rate: telemetryData.hz,
              messageCount: telemetryData.seq,
              bandwidth: bandwidth,
              connected: true,
            }));

            lastMessageTimeRef.current = now;
          } catch (error) {
            console.error('[TELEMETRY] Error decoding message:', error);
          }
        };

        ws.onclose = () => {
          console.log('[TELEMETRY] Disconnected from telemetry server');
          setStats(prev => ({ ...prev, connected: false }));
          
          // Stop ping interval
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
          }
          
          // Attempt to reconnect after 2 seconds
          setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = (error) => {
          console.error('[TELEMETRY] WebSocket error:', error);
          setStats(prev => ({ ...prev, connected: false }));
        };
      } catch (error) {
        console.error('[TELEMETRY] Failed to connect:', error);
        setTimeout(connectWebSocket, 2000);
      }
    };

    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
    };
  }, []);

  // Check for connection timeout
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      if (stats.connected && now - lastMessageTimeRef.current > 5000) {
        setStats(prev => ({ ...prev, connected: false }));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [stats.connected]);

  // FPS tracking using requestAnimationFrame
  useEffect(() => {
    let animationId: number;

    const trackFPS = (currentTime: number) => {
      frameCountRef.current++;
      
      // Calculate FPS every second
      if (currentTime - fpsStartTimeRef.current >= 1000) {
        const elapsedSeconds = (currentTime - fpsStartTimeRef.current) / 1000;
        const actualFPS = frameCountRef.current / elapsedSeconds;
        
        setStats(prev => ({ ...prev, fps: actualFPS }));
        
        // Reset counters
        frameCountRef.current = 0;
        fpsStartTimeRef.current = currentTime;
      }
      
      animationId = requestAnimationFrame(trackFPS);
    };
    
    animationId = requestAnimationFrame(trackFPS);
    
    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }, []);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B/s';
    const k = 1024;
    const sizes = ['B/s', 'KB/s', 'MB/s'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  return (
    <Paper
      style={{
        position: 'absolute',
        top: '1em',
        left: '1em',
        padding: '0.8em',
        minWidth: '180px',
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        color: 'white',
        zIndex: 1000,
        fontFamily: 'monospace',
        fontSize: '0.85em',
        border: stats.connected ? '2px solid #4CAF50' : '2px solid #f44336',
      }}
    >
      <Box>
        <Text 
          size="sm" 
          style={{ 
            fontWeight: 'bold', 
            marginBottom: '0.5em',
            color: stats.connected ? '#4CAF50' : '#f44336'
          }}
        >
          TELEMETRY {stats.connected ? '●' : '○'}
        </Text>
        
        <Box style={{ display: 'flex', flexDirection: 'column', gap: '0.2em' }}>
          <Text size="xs">
            Latency: <span style={{ color: stats.latency > 0 ? '#FFD700' : '#888888' }}>
              {stats.latency > 0 ? `${stats.latency.toFixed(1)}ms` : 'N/A'}
            </span>
          </Text>
          
          <Text size="xs">
            Msg Rate: <span style={{ color: '#00CED1' }}>{stats.rate.toFixed(1)}Hz</span>
          </Text>
          
          <Text size="xs">
            FPS: <span style={{ color: '#FF6B35' }}>{stats.fps.toFixed(1)}</span>
          </Text>
          
          <Text size="xs">
            Messages: <span style={{ color: '#98FB98' }}>{stats.messageCount.toLocaleString()}</span>
          </Text>
          
          <Text size="xs">
            Bandwidth: <span style={{ color: '#DDA0DD' }}>{formatBytes(stats.bandwidth)}</span>
          </Text>
        </Box>
      </Box>
    </Paper>
  );
}
