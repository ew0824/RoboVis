/**
 * Frontend Performance Profiler - Debug Frontend Lag Issues
 * 
 * This profiler measures the complete frontend pipeline to identify why
 * 90Hz backend data feels laggy but 50Hz feels smooth. It provides
 * real-time metrics and systematic analysis.
 * 
 * Key Measurements:
 * 1. WebSocket message receive rate (actual Hz received)
 * 2. Visual render frame rate (actual frames drawn)
 * 3. Frame processing time per WebSocket message
 * 4. Frame drops and rendering delays
 * 5. Browser performance bottlenecks
 * 6. Visual synchronization issues
 * 
 * Usage:
 * Include this script in the Viser frontend and call:
 * const profiler = new FrontendPerformanceProfiler();
 * profiler.start();
 */

class FrontendPerformanceProfiler {
    constructor() {
        // Timing measurements
        this.messageTimestamps = [];
        this.renderTimestamps = [];
        this.processingTimes = [];
        this.frameDrops = 0;
        
        // Performance metrics
        this.isProfilering = false;
        this.startTime = 0;
        this.lastReportTime = 0;
        this.reportInterval = 1000; // Report every 1 second
        
        // WebSocket monitoring
        this.originalWebSocket = null;
        this.messageCount = 0;
        this.totalMessageSize = 0;
        
        // Visual rendering monitoring
        this.renderFrameCount = 0;
        this.lastRenderCheck = 0;
        this.renderCheckInterval = 1000;
        
        // Frame processing queue monitoring
        this.processingQueue = [];
        this.maxQueueSize = 0;
        this.queueOverflowCount = 0;
        
        // Browser performance monitoring
        this.gcPauses = [];
        this.longTasks = [];
        this.memoryUsage = [];
        
        // Results storage
        this.performanceLog = [];
        
        // DOM elements for display
        this.metricsDisplay = null;
        this.createMetricsDisplay();
        
        // Bind methods
        this.measureRenderRate = this.measureRenderRate.bind(this);
        this.reportMetrics = this.reportMetrics.bind(this);
    }
    
    start() {
        console.log('[FRONTEND-PROFILER] 🔍 Starting frontend performance profiling');
        this.isProfilering = true;
        this.startTime = performance.now();
        this.lastReportTime = this.startTime;
        this.lastRenderCheck = this.startTime;
        
        // Hook into WebSocket
        this.hookWebSocket();
        
        // Start render rate monitoring
        this.measureRenderRate();
        
        // Start performance monitoring
        this.setupPerformanceObservers();
        
        // Start periodic reporting
        setInterval(this.reportMetrics, this.reportInterval);
        
        console.log('[FRONTEND-PROFILER] Frontend profiler started');
    }
    
    stop() {
        this.isProfilering = false;
        this.generateComprehensiveReport();
        console.log('[FRONTEND-PROFILER] Frontend profiling stopped');
    }
    
    hookWebSocket() {
        // Find and hook into the Viser WebSocket
        const originalWebSocket = window.WebSocket;
        const profiler = this;
        
        window.WebSocket = function(url, protocols) {
            const ws = new originalWebSocket(url, protocols);
            profiler.originalWebSocket = ws;
            
            // Hook message reception
            const originalOnMessage = ws.onmessage;
            ws.onmessage = function(event) {
                profiler.onWebSocketMessage(event);
                if (originalOnMessage) {
                    originalOnMessage.call(this, event);
                }
            };
            
            console.log('[FRONTEND-PROFILER] WebSocket hooked:', url);
            return ws;
        };
        
        // Also try to hook into existing WebSocket if already connected
        this.findExistingWebSocket();
    }
    
    findExistingWebSocket() {
        // Try to find existing WebSocket connections
        // This is a heuristic approach since we can't directly access all WebSocket instances
        console.log('[FRONTEND-PROFILER] Searching for existing WebSocket connections...');
        
        // Check if Viser has exposed its WebSocket
        if (window.viser && window.viser.websocket) {
            this.hookExistingWebSocket(window.viser.websocket);
        }
        
        // Check common patterns
        const possibleNames = ['ws', 'websocket', 'socket', 'connection'];
        for (const name of possibleNames) {
            if (window[name] && window[name].send) {
                this.hookExistingWebSocket(window[name]);
                break;
            }
        }
    }
    
    hookExistingWebSocket(ws) {
        console.log('[FRONTEND-PROFILER] Found existing WebSocket, hooking into it');
        this.originalWebSocket = ws;
        
        const originalOnMessage = ws.onmessage;
        const profiler = this;
        
        ws.onmessage = function(event) {
            profiler.onWebSocketMessage(event);
            if (originalOnMessage) {
                originalOnMessage.call(this, event);
            }
        };
    }
    
    onWebSocketMessage(event) {
        if (!this.isProfilering) return;
        
        const now = performance.now();
        const processingStart = now;
        
        // Record message timing
        this.messageTimestamps.push(now);
        this.messageCount++;
        
        // Record message size
        const messageSize = event.data ? event.data.length : 0;
        this.totalMessageSize += messageSize;
        
        // Add to processing queue
        this.processingQueue.push({
            timestamp: now,
            size: messageSize,
            processed: false
        });
        
        // Track queue size
        if (this.processingQueue.length > this.maxQueueSize) {
            this.maxQueueSize = this.processingQueue.length;
        }
        
        // Simulate frame processing (measure actual processing time)
        // We'll hook into the actual processing later
        const processingEnd = performance.now();
        const processingTime = processingEnd - processingStart;
        this.processingTimes.push(processingTime);
        
        // Mark as processed
        if (this.processingQueue.length > 0) {
            this.processingQueue[0].processed = true;
            this.processingQueue.shift();
        }
        
        // Check for queue overflow (frames being dropped)
        if (this.processingQueue.length > 10) {
            this.frameDrops++;
            this.queueOverflowCount++;
        }
    }
    
    measureRenderRate() {
        if (!this.isProfilering) return;
        
        const now = performance.now();
        this.renderTimestamps.push(now);
        this.renderFrameCount++;
        
        // Continue measuring
        requestAnimationFrame(this.measureRenderRate);
    }
    
    setupPerformanceObservers() {
        // Monitor long tasks (JavaScript blocking)
        if ('PerformanceObserver' in window) {
            try {
                const longTaskObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.duration > 16.67) { // Longer than 60fps frame budget
                            this.longTasks.push({
                                duration: entry.duration,
                                startTime: entry.startTime,
                                name: entry.name
                            });
                        }
                    }
                });
                longTaskObserver.observe({entryTypes: ['longtask']});
            } catch (e) {
                console.warn('[FRONTEND-PROFILER] Long task observer not supported');
            }
        }
        
        // Monitor memory usage
        if (performance.memory) {
            setInterval(() => {
                this.memoryUsage.push({
                    timestamp: performance.now(),
                    usedJSHeapSize: performance.memory.usedJSHeapSize,
                    totalJSHeapSize: performance.memory.totalJSHeapSize,
                    jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
                });
            }, 1000);
        }
        
        // Monitor garbage collection (heuristic)
        this.monitorGarbageCollection();
    }
    
    monitorGarbageCollection() {
        let lastHeapSize = performance.memory ? performance.memory.usedJSHeapSize : 0;
        
        setInterval(() => {
            if (performance.memory) {
                const currentHeapSize = performance.memory.usedJSHeapSize;
                
                // Detect potential GC (significant memory drop)
                if (lastHeapSize - currentHeapSize > 1024 * 1024) { // 1MB drop
                    this.gcPauses.push({
                        timestamp: performance.now(),
                        memoryFreed: lastHeapSize - currentHeapSize
                    });
                }
                
                lastHeapSize = currentHeapSize;
            }
        }, 100);
    }
    
    reportMetrics() {
        if (!this.isProfilering) return;
        
        const now = performance.now();
        const elapsed = now - this.lastReportTime;
        
        // Calculate WebSocket receive rate
        const recentMessages = this.messageTimestamps.filter(t => now - t < 1000);
        const websocketHz = recentMessages.length;
        
        // Calculate visual render rate
        const recentRenders = this.renderTimestamps.filter(t => now - t < 1000);
        const renderHz = recentRenders.length;
        
        // Calculate processing times
        const recentProcessingTimes = this.processingTimes.slice(-100);
        const avgProcessingTime = recentProcessingTimes.length > 0 
            ? recentProcessingTimes.reduce((a, b) => a + b) / recentProcessingTimes.length 
            : 0;
        const maxProcessingTime = recentProcessingTimes.length > 0 
            ? Math.max(...recentProcessingTimes) 
            : 0;
        
        // Calculate frame drops
        const recentFrameDrops = this.frameDrops;
        
        // Calculate queue metrics
        const currentQueueSize = this.processingQueue.length;
        
        // Calculate long task metrics
        const recentLongTasks = this.longTasks.filter(t => now - t.startTime < 1000);
        const totalBlockingTime = recentLongTasks.reduce((sum, task) => sum + task.duration, 0);
        
        // Create performance report
        const report = {
            timestamp: now,
            websocketHz: websocketHz,
            renderHz: renderHz,
            processingTimeAvg: avgProcessingTime,
            processingTimeMax: maxProcessingTime,
            frameDrops: recentFrameDrops,
            queueSize: currentQueueSize,
            maxQueueSize: this.maxQueueSize,
            longTaskCount: recentLongTasks.length,
            totalBlockingTime: totalBlockingTime,
            gcPauses: this.gcPauses.length,
            memoryUsageMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1024 / 1024) : 0
        };
        
        this.performanceLog.push(report);
        
        // Update live display
        this.updateMetricsDisplay(report);
        
        // Console log for debugging
        console.log('[FRONTEND-PROFILER] Performance Report:', {
            'WebSocket Hz': websocketHz,
            'Visual Hz': renderHz,
            'Avg Processing': `${avgProcessingTime.toFixed(2)}ms`,
            'Max Processing': `${maxProcessingTime.toFixed(2)}ms`,
            'Frame Drops': recentFrameDrops,
            'Queue Size': currentQueueSize,
            'Blocking Time': `${totalBlockingTime.toFixed(1)}ms`,
            'Memory': `${report.memoryUsageMB}MB`
        });
        
        // Reset counters
        this.frameDrops = 0;
        this.lastReportTime = now;
    }
    
    createMetricsDisplay() {
        // Create floating metrics display
        this.metricsDisplay = document.createElement('div');
        this.metricsDisplay.id = 'frontend-profiler-metrics';
        this.metricsDisplay.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            z-index: 10000;
            min-width: 300px;
            border: 2px solid #00ff00;
        `;
        
        document.body.appendChild(this.metricsDisplay);
        
        // Add title
        const title = document.createElement('div');
        title.textContent = '🔍 Frontend Performance Profiler';
        title.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #00ff00;';
        this.metricsDisplay.appendChild(title);
        
        // Add metrics container
        this.metricsContainer = document.createElement('div');
        this.metricsDisplay.appendChild(this.metricsContainer);
        
        // Add controls
        const controls = document.createElement('div');
        controls.style.cssText = 'margin-top: 10px; border-top: 1px solid #333; padding-top: 10px;';
        
        const stopButton = document.createElement('button');
        stopButton.textContent = 'Stop Profiling';
        stopButton.style.cssText = 'background: #ff0000; color: white; border: none; padding: 5px 10px; cursor: pointer;';
        stopButton.onclick = () => this.stop();
        
        const exportButton = document.createElement('button');
        exportButton.textContent = 'Export Data';
        exportButton.style.cssText = 'background: #0066cc; color: white; border: none; padding: 5px 10px; margin-left: 5px; cursor: pointer;';
        exportButton.onclick = () => this.exportData();
        
        controls.appendChild(stopButton);
        controls.appendChild(exportButton);
        this.metricsDisplay.appendChild(controls);
    }
    
    updateMetricsDisplay(report) {
        if (!this.metricsContainer) return;
        
        // Create status indicators
        const websocketStatus = report.websocketHz > 80 ? '🟢' : report.websocketHz > 50 ? '🟡' : '🔴';
        const renderStatus = report.renderHz > 50 ? '🟢' : report.renderHz > 30 ? '🟡' : '🔴';
        const lagStatus = report.processingTimeMax < 16 ? '🟢' : report.processingTimeMax < 33 ? '🟡' : '🔴';
        
        this.metricsContainer.innerHTML = `
            <div>WebSocket Rate: ${websocketStatus} ${report.websocketHz} Hz</div>
            <div>Visual Render: ${renderStatus} ${report.renderHz} Hz</div>
            <div>Processing Avg: ${report.processingTimeAvg.toFixed(2)}ms</div>
            <div>Processing Max: ${lagStatus} ${report.processingTimeMax.toFixed(2)}ms</div>
            <div>Frame Drops: ${report.frameDrops}</div>
            <div>Queue Size: ${report.queueSize} / ${report.maxQueueSize}</div>
            <div>Long Tasks: ${report.longTaskCount}</div>
            <div>Blocking Time: ${report.totalBlockingTime.toFixed(1)}ms</div>
            <div>Memory: ${report.memoryUsageMB}MB</div>
            <div>GC Pauses: ${report.gcPauses}</div>
        `;
    }
    
    generateComprehensiveReport() {
        console.log('\n[FRONTEND-PROFILER] 📊 COMPREHENSIVE FRONTEND PERFORMANCE REPORT');
        console.log('='.repeat(80));
        
        if (this.performanceLog.length === 0) {
            console.log('❌ No performance data collected');
            return;
        }
        
        // Calculate averages
        const avgWebsocketHz = this.performanceLog.reduce((sum, r) => sum + r.websocketHz, 0) / this.performanceLog.length;
        const avgRenderHz = this.performanceLog.reduce((sum, r) => sum + r.renderHz, 0) / this.performanceLog.length;
        const avgProcessingTime = this.performanceLog.reduce((sum, r) => sum + r.processingTimeAvg, 0) / this.performanceLog.length;
        const maxProcessingTime = Math.max(...this.performanceLog.map(r => r.processingTimeMax));
        const totalFrameDrops = this.performanceLog.reduce((sum, r) => sum + r.frameDrops, 0);
        const totalLongTasks = this.performanceLog.reduce((sum, r) => sum + r.longTaskCount, 0);
        const totalBlockingTime = this.performanceLog.reduce((sum, r) => sum + r.totalBlockingTime, 0);
        
        console.log('\n📋 PERFORMANCE SUMMARY:');
        console.log(`  Duration: ${((performance.now() - this.startTime) / 1000).toFixed(1)}s`);
        console.log(`  WebSocket Rate: ${avgWebsocketHz.toFixed(1)} Hz`);
        console.log(`  Visual Rate: ${avgRenderHz.toFixed(1)} Hz`);
        console.log(`  Rate Gap: ${(avgWebsocketHz - avgRenderHz).toFixed(1)} Hz`);
        
        console.log('\n⏱️  PROCESSING TIMES:');
        console.log(`  Average: ${avgProcessingTime.toFixed(2)}ms`);
        console.log(`  Maximum: ${maxProcessingTime.toFixed(2)}ms`);
        console.log(`  60fps Budget: 16.67ms`);
        console.log(`  Budget Usage: ${((avgProcessingTime / 16.67) * 100).toFixed(1)}%`);
        
        console.log('\n📉 PERFORMANCE ISSUES:');
        console.log(`  Frame Drops: ${totalFrameDrops}`);
        console.log(`  Long Tasks: ${totalLongTasks}`);
        console.log(`  Total Blocking: ${totalBlockingTime.toFixed(1)}ms`);
        console.log(`  GC Pauses: ${this.gcPauses.length}`);
        
        // Analyze the lag issue
        console.log('\n🔍 LAG ANALYSIS:');
        if (avgWebsocketHz > avgRenderHz + 10) {
            console.log(`  🔥 BOTTLENECK: Visual rendering cannot keep up with data`);
            console.log(`  📊 Data Rate: ${avgWebsocketHz.toFixed(1)} Hz`);
            console.log(`  📊 Visual Rate: ${avgRenderHz.toFixed(1)} Hz`);
            console.log(`  📊 Performance Gap: ${(avgWebsocketHz - avgRenderHz).toFixed(1)} Hz`);
        }
        
        if (maxProcessingTime > 16.67) {
            console.log(`  🔥 BOTTLENECK: Frame processing exceeds 60fps budget`);
            console.log(`  📊 Max Processing: ${maxProcessingTime.toFixed(2)}ms`);
            console.log(`  📊 Frames Affected: ${this.performanceLog.filter(r => r.processingTimeMax > 16.67).length}`);
        }
        
        if (totalFrameDrops > 0) {
            console.log(`  🔥 BOTTLENECK: Frames being dropped due to processing backlog`);
            console.log(`  📊 Dropped Frames: ${totalFrameDrops}`);
        }
        
        // Performance recommendations
        console.log('\n💡 RECOMMENDATIONS:');
        if (avgWebsocketHz > 60 && avgRenderHz < 60) {
            console.log('  - Implement rate-limited visualization (60fps max)');
            console.log('  - Decouple data processing from visual updates');
        }
        if (maxProcessingTime > 20) {
            console.log('  - Optimize WebGL/Three.js rendering performance');
            console.log('  - Consider LOD (Level of Detail) for complex meshes');
        }
        if (totalLongTasks > 10) {
            console.log('  - Break up long JavaScript tasks with setTimeout/requestIdleCallback');
            console.log('  - Consider Web Workers for heavy processing');
        }
        
        console.log('\n✅ Frontend performance analysis complete');
    }
    
    exportData() {
        const data = {
            summary: {
                duration: (performance.now() - this.startTime) / 1000,
                totalMessages: this.messageCount,
                totalFrameDrops: this.performanceLog.reduce((sum, r) => sum + r.frameDrops, 0),
                avgWebsocketHz: this.performanceLog.reduce((sum, r) => sum + r.websocketHz, 0) / this.performanceLog.length,
                avgRenderHz: this.performanceLog.reduce((sum, r) => sum + r.renderHz, 0) / this.performanceLog.length
            },
            performanceLog: this.performanceLog,
            longTasks: this.longTasks,
            gcPauses: this.gcPauses,
            memoryUsage: this.memoryUsage
        };
        
        // Download as JSON
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `frontend_performance_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('[FRONTEND-PROFILER] Performance data exported');
    }
}

// Auto-start when script is loaded
window.FrontendPerformanceProfiler = FrontendPerformanceProfiler;

// Convenience function to start profiling
window.startFrontendProfiling = function() {
    if (window.frontendProfiler) {
        console.warn('Frontend profiler already running');
        return window.frontendProfiler;
    }
    
    window.frontendProfiler = new FrontendPerformanceProfiler();
    window.frontendProfiler.start();
    return window.frontendProfiler;
};

// Convenience function to stop profiling
window.stopFrontendProfiling = function() {
    if (window.frontendProfiler) {
        window.frontendProfiler.stop();
        window.frontendProfiler = null;
    }
};

console.log('🔍 Frontend Performance Profiler loaded');
console.log('Call startFrontendProfiling() to begin debugging frontend lag');
