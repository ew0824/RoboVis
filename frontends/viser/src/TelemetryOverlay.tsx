import React, { useState, useEffect, useRef } from 'react';
import { Box, Text, Paper } from '@mantine/core';
import { decode } from '@msgpack/msgpack';

interface TelemetryData {
  seq: number;
  ns: number;
  nq: number;
  hz: number;
}

interface TelemetryStats {
  latency: number;
  rate: number;
  messageCount: number;
  bandwidth: number;
  connected: boolean;
}

export function TelemetryOverlay() {
  const [stats, setStats] = useState<TelemetryStats>({
    latency: 0,
    rate: 0,
    messageCount: 0,
    bandwidth: 0,
    connected: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const statsRef = useRef<TelemetryStats>(stats);
  const lastMessageTimeRef = useRef<number>(0);
  const bandwidthBytesRef = useRef<number>(0);
  const bandwidthWindowRef = useRef<number>(Date.now());

  // Update ref when stats change
  useEffect(() => {
    statsRef.current = stats;
  }, [stats]);

  useEffect(() => {
    // Connect to telemetry WebSocket server
    const connectWebSocket = () => {
      try {
        const ws = new WebSocket('ws://localhost:8081');
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('[TELEMETRY] Connected to telemetry server');
          setStats(prev => ({ ...prev, connected: true }));
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
            const data = decode(dataForDecode) as TelemetryData;
            const receiveTime = performance.now() * 1e6; // Convert to nanoseconds
            
            // Calculate round-trip latency
            const latency = Math.max(0, (receiveTime - data.ns) / 1e6); // Convert to milliseconds
            
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
              latency: latency,
              rate: data.hz,
              messageCount: data.seq,
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
            Latency: <span style={{ color: '#FFD700' }}>{stats.latency.toFixed(1)}ms</span>
          </Text>
          
          <Text size="xs">
            Rate: <span style={{ color: '#00CED1' }}>{stats.rate.toFixed(1)}Hz</span>
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
