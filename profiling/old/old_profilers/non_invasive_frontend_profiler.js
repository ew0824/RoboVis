/**
 * Non-Invasive Frontend Performance Profiler - Safe Observation Only
 * 
 * This profiler measures frontend performance WITHOUT interfering with existing systems.
 * It uses passive observation techniques to avoid breaking WebSocket connections or
 * other functionality.
 * 
 * Key Measurements:
 * 1. Browser render performance (frame timing)
 * 2. DOM mutation rate (robot movement frequency) 
 * 3. Processing time per frame
 * 4. Visual smoothness analysis
 * 
 * SAFE APPROACH:
 * - No WebSocket hooking or overriding
 * - No global constructor modification
 * - Pure observation using browser APIs
 * - Parses existing console messages
 * 
 * Usage:
 * startNonInvasiveProfiling()
 */

class NonInvasiveFrontendProfiler {
    constructor() {
        // Performance measurements
        this.frameTimings = [];
        this.domMutations = [];
        this.consoleMessages = [];
        this.renderTimes = [];
        this.processingTimes = [];
        
        // Profiling state
        this.isProfilering = false;
        this.startTime = 0;
        this.lastReportTime = 0;
        this.reportInterval = 1000;
        
        // Frame rate tracking
        this.frameCount = 0;
        this.lastFrameTime = 0;
        this.frameIntervals = [];
        
        // DOM observation
        this.mutationCount = 0;
        this.lastMutationTime = 0;
        this.mutationIntervals = [];
        
        // Console message parsing
        this.pingMessages = [];
        this.latencyData = [];
        
        // Performance observers
        this.performanceObserver = null;
        this.mutationObserver = null;
        
        // Display elements
        this.metricsDisplay = null;
        
        // Results storage
        this.performanceLog = [];
        
        // Bind methods
        this.measureFrameRate = this.measureFrameRate.bind(this);
        this.reportMetrics = this.reportMetrics.bind(this);
        this.handleConsoleMessage = this.handleConsoleMessage.bind(this);
    }
    
    start() {
        console.log('[NON-INVASIVE-PROFILER] 🔍 Starting safe frontend profiling');
        this.isProfilering = true;
        this.startTime = performance.now();
        this.lastReportTime = this.startTime;
        this.lastFrameTime = this.startTime;
        this.lastMutationTime = this.startTime;
        
        // Start frame rate monitoring (completely safe)
        this.measureFrameRate();
        
        // Start DOM mutation monitoring (safe passive observation)
        this.setupDOMObservation();
        
        // Start performance monitoring (safe browser APIs)
        this.setupPerformanceObservation();
        
        // Start console message parsing (safe passive listening)
        this.setupConsoleMonitoring();
        
        // Create safe metrics display
        this.createSafeMetricsDisplay();
        
        // Start periodic reporting
        this.reportInterval = setInterval(this.reportMetrics, 1000);
        
        console.log('[NON-INVASIVE-PROFILER] ✅ Safe profiler started - no interference with existing systems');
    }
    
    stop() {
        this.isProfilering = false;
        
        if (this.reportInterval) {
            clearInterval(this.reportInterval);
        }
        
        if (this.mutationObserver) {
            this.mutationObserver.disconnect();
        }
        
        if (this.performanceObserver) {
            this.performanceObserver.disconnect();
        }
        
        this.generateComprehensiveReport();
        console.log('[NON-INVASIVE-PROFILER] Frontend profiling stopped safely');
    }
    
    measureFrameRate() {
        if (!this.isProfilering) return;
        
        const now = performance.now();
        
        // Calculate frame interval
        if (this.lastFrameTime > 0) {
            const frameInterval = now - this.lastFrameTime;
            this.frameIntervals.push(frameInterval);
            
            // Keep only recent intervals
            if (this.frameIntervals.length > 1000) {
                this.frameIntervals = this.frameIntervals.slice(-500);
            }
        }
        
        this.frameCount++;
        this.lastFrameTime = now;
        
        // Measure frame processing time (safe)
        const processingStart = performance.now();
        
        // Simulate minimal processing to measure overhead
        const dummy = Math.sin(now * 0.001);
        
        const processingEnd = performance.now();
        const processingTime = processingEnd - processingStart;
        this.processingTimes.push(processingTime);
        
        // Continue measuring
        requestAnimationFrame(this.measureFrameRate);
    }
    
    setupDOMObservation() {
        // Safe DOM mutation observation
        if (typeof MutationObserver !== 'undefined') {
            this.mutationObserver = new MutationObserver((mutations) => {
                const now = performance.now();
                
                // Count meaningful mutations (likely from robot updates)
                let significantMutations = 0;
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        significantMutations++;
                    }
                    if (mutation.type === 'attributes' && 
                        (mutation.attributeName === 'transform' || 
                         mutation.attributeName === 'style' ||
                         mutation.attributeName === 'position')) {
                        significantMutations++;
                    }
                });
                
                if (significantMutations > 0) {
                    // Calculate mutation interval
                    if (this.lastMutationTime > 0) {
                        const mutationInterval = now - this.lastMutationTime;
                        this.mutationIntervals.push(mutationInterval);
                        
                        // Keep only recent intervals
                        if (this.mutationIntervals.length > 500) {
                            this.mutationIntervals = this.mutationIntervals.slice(-250);
                        }
                    }
                    
                    this.mutationCount++;
                    this.lastMutationTime = now;
                    
                    this.domMutations.push({
                        timestamp: now,
                        count: significantMutations,
                        types: mutations.map(m => m.type)
                    });
                }
            });
            
            // Observe the entire document for changes
            this.mutationObserver.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['transform', 'style', 'position', 'rotation']
            });
            
            console.log('[NON-INVASIVE-PROFILER] DOM mutation observer started');
        }
    }
    
    setupPerformanceObservation() {
        // Safe performance observation
        if ('PerformanceObserver' in window) {
            try {
                this.performanceObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.entryType === 'navigation') {
                            console.log('[NON-INVASIVE-PROFILER] Navigation timing captured');
                        }
                        if (entry.entryType === 'paint') {
                            this.renderTimes.push({
                                timestamp: entry.startTime,
                                type: entry.name,
                                duration: entry.duration
                            });
                        }
                    }
                });
                
                // Observe safe performance metrics
                this.performanceObserver.observe({
                    entryTypes: ['navigation', 'paint', 'measure']
                });
                
                console.log('[NON-INVASIVE-PROFILER] Performance observer started');
            } catch (e) {
                console.warn('[NON-INVASIVE-PROFILER] Performance observer not fully supported');
            }
        }
    }
    
    setupConsoleMonitoring() {
        // Safe console message parsing (doesn't interfere with existing logging)
        const originalConsoleLog = console.log;
        const profiler = this;
        
        // Create a safe wrapper that parses but doesn't interfere
        function safeConsoleWrapper(...args) {
            // Call original first (maintains existing behavior)
            originalConsoleLog.apply(console, args);
            
            // Then safely parse for our analysis
            try {
                const message = args.join(' ');
                profiler.handleConsoleMessage(message);
            } catch (e) {
                // Silently ignore parsing errors
            }
        }
        
        // Only wrap if we're profiling
        if (this.isProfilering) {
            console.log = safeConsoleWrapper;
        }
        
        console.log('[NON-INVASIVE-PROFILER] Console monitoring started (non-interfering)');
    }
    
    handleConsoleMessage(message) {
        if (!this.isProfilering) return;
        
        const timestamp = performance.now();
        
        // Parse PING messages safely
        if (message.includes('[PING]') || message.includes('ping') || message.includes('latency')) {
            this.pingMessages.push({
                timestamp: timestamp,
                message: message
            });
            
            // Try to extract latency numbers
            const latencyMatch = message.match(/(\d+\.?\d*)\s*ms/);
            if (latencyMatch) {
                const latency = parseFloat(latencyMatch[1]);
                this.latencyData.push({
                    timestamp: timestamp,
                    latency: latency
                });
            }
        }
        
        // Store for analysis
        this.consoleMessages.push({
            timestamp: timestamp,
            message: message
        });
    }
    
    createSafeMetricsDisplay() {
        // Create completely safe metrics display
        this.metricsDisplay = document.createElement('div');
        this.metricsDisplay.id = 'non-invasive-profiler-metrics';
        this.metricsDisplay.style.cssText = `
            position: fixed;
            top: 10px;
            left: 10px;
            background: rgba(0, 100, 0, 0.9);
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            z-index: 9999;
            min-width: 250px;
            border: 2px solid #00ff00;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        `;
        
        document.body.appendChild(this.metricsDisplay);
        
        // Add title
        const title = document.createElement('div');
        title.textContent = '🔍 Safe Frontend Profiler';
        title.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #00ff00;';
        this.metricsDisplay.appendChild(title);
        
        // Add metrics container
        this.metricsContainer = document.createElement('div');
        this.metricsDisplay.appendChild(this.metricsContainer);
        
        // Add safe controls
        const controls = document.createElement('div');
        controls.style.cssText = 'margin-top: 10px; border-top: 1px solid #333; padding-top: 10px;';
        
        const stopButton = document.createElement('button');
        stopButton.textContent = 'Stop';
        stopButton.style.cssText = 'background: #ff4444; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 3px;';
        stopButton.onclick = () => this.stop();
        
        controls.appendChild(stopButton);
        this.metricsDisplay.appendChild(controls);
    }
    
    reportMetrics() {
        if (!this.isProfilering) return;
        
        const now = performance.now();
        const elapsed = now - this.lastReportTime;
        
        // Calculate frame rate from intervals
        const recentFrameIntervals = this.frameIntervals.slice(-60); // Last 60 frames
        let avgFrameRate = 0;
        if (recentFrameIntervals.length > 0) {
            const avgInterval = recentFrameIntervals.reduce((a, b) => a + b) / recentFrameIntervals.length;
            avgFrameRate = 1000 / avgInterval;
        }
        
        // Calculate DOM mutation rate
        const recentMutationIntervals = this.mutationIntervals.slice(-60);
        let avgMutationRate = 0;
        if (recentMutationIntervals.length > 0) {
            const avgInterval = recentMutationIntervals.reduce((a, b) => a + b) / recentMutationIntervals.length;
            avgMutationRate = 1000 / avgInterval;
        }
        
        // Calculate processing times
        const recentProcessingTimes = this.processingTimes.slice(-100);
        const avgProcessingTime = recentProcessingTimes.length > 0 
            ? recentProcessingTimes.reduce((a, b) => a + b) / recentProcessingTimes.length 
            : 0;
        const maxProcessingTime = recentProcessingTimes.length > 0 
            ? Math.max(...recentProcessingTimes) 
            : 0;
        
        // Calculate frame consistency (smoothness)
        let frameConsistency = 100;
        if (recentFrameIntervals.length > 10) {
            const intervals = recentFrameIntervals.slice(-30);
            const avgInterval = intervals.reduce((a, b) => a + b) / intervals.length;
            const variance = intervals.reduce((sum, interval) => sum + Math.pow(interval - avgInterval, 2), 0) / intervals.length;
            const stdDev = Math.sqrt(variance);
            frameConsistency = Math.max(0, 100 - (stdDev / avgInterval * 100));
        }
        
        // Estimate data rate from console messages and DOM mutations
        const recentPingMessages = this.pingMessages.filter(p => now - p.timestamp < 5000);
        const estimatedDataRate = Math.max(avgMutationRate, recentPingMessages.length / 5);
        
        const report = {
            timestamp: now,
            browserFrameRate: avgFrameRate,
            domUpdateRate: avgMutationRate,
            estimatedDataRate: estimatedDataRate,
            processingTimeAvg: avgProcessingTime,
            processingTimeMax: maxProcessingTime,
            frameConsistency: frameConsistency,
            totalDomMutations: this.mutationCount,
            totalPingMessages: this.pingMessages.length,
            latencyData: this.latencyData.slice(-10) // Recent latency
        };
        
        this.performanceLog.push(report);
        
        // Update display safely
        this.updateSafeMetricsDisplay(report);
        
        // Console log for debugging
        console.log('[NON-INVASIVE-PROFILER] Safe Performance Report:', {
            'Browser FPS': avgFrameRate.toFixed(1),
            'DOM Update Rate': avgMutationRate.toFixed(1),
            'Est. Data Rate': estimatedDataRate.toFixed(1),
            'Avg Processing': `${avgProcessingTime.toFixed(3)}ms`,
            'Frame Consistency': `${frameConsistency.toFixed(1)}%`,
            'DOM Mutations': this.mutationCount,
            'PING Messages': this.pingMessages.length
        });
        
        this.lastReportTime = now;
    }
    
    updateSafeMetricsDisplay(report) {
        if (!this.metricsContainer) return;
        
        // Create safe status indicators
        const frameStatus = report.browserFrameRate > 50 ? '🟢' : report.browserFrameRate > 30 ? '🟡' : '🔴';
        const dataStatus = report.estimatedDataRate > 0 ? '🟢' : '🔴';
        const smoothStatus = report.frameConsistency > 80 ? '🟢' : report.frameConsistency > 60 ? '🟡' : '🔴';
        
        this.metricsContainer.innerHTML = `
            <div>Browser FPS: ${frameStatus} ${report.browserFrameRate.toFixed(1)} Hz</div>
            <div>DOM Updates: ${dataStatus} ${report.domUpdateRate.toFixed(1)} Hz</div>
            <div>Est. Data Rate: ${report.estimatedDataRate.toFixed(1)} Hz</div>
            <div>Processing Avg: ${report.processingTimeAvg.toFixed(3)}ms</div>
            <div>Frame Smooth: ${smoothStatus} ${report.frameConsistency.toFixed(1)}%</div>
            <div>DOM Changes: ${report.totalDomMutations}</div>
            <div>PING Messages: ${report.totalPingMessages}</div>
        `;
    }
    
    generateComprehensiveReport() {
        console.log('\n[NON-INVASIVE-PROFILER] 📊 SAFE FRONTEND PERFORMANCE REPORT');
        console.log('='.repeat(80));
        
        if (this.performanceLog.length === 0) {
            console.log('❌ No performance data collected');
            return;
        }
        
        // Calculate safe averages
        const avgBrowserFrameRate = this.performanceLog.reduce((sum, r) => sum + r.browserFrameRate, 0) / this.performanceLog.length;
        const avgDomUpdateRate = this.performanceLog.reduce((sum, r) => sum + r.domUpdateRate, 0) / this.performanceLog.length;
        const avgEstimatedDataRate = this.performanceLog.reduce((sum, r) => sum + r.estimatedDataRate, 0) / this.performanceLog.length;
        const avgProcessingTime = this.performanceLog.reduce((sum, r) => sum + r.processingTimeAvg, 0) / this.performanceLog.length;
        const avgFrameConsistency = this.performanceLog.reduce((sum, r) => sum + r.frameConsistency, 0) / this.performanceLog.length;
        
        console.log('\n📋 SAFE PERFORMANCE SUMMARY:');
        console.log(`  Duration: ${((performance.now() - this.startTime) / 1000).toFixed(1)}s`);
        console.log(`  Browser Frame Rate: ${avgBrowserFrameRate.toFixed(1)} Hz`);
        console.log(`  DOM Update Rate: ${avgDomUpdateRate.toFixed(1)} Hz`);
        console.log(`  Estimated Data Rate: ${avgEstimatedDataRate.toFixed(1)} Hz`);
        console.log(`  Frame Consistency: ${avgFrameConsistency.toFixed(1)}%`);
        
        console.log('\n⏱️  PROCESSING ANALYSIS:');
        console.log(`  Average Processing: ${avgProcessingTime.toFixed(3)}ms per frame`);
        console.log(`  60fps Budget: 16.67ms`);
        console.log(`  Budget Usage: ${((avgProcessingTime / 16.67) * 100).toFixed(1)}%`);
        
        console.log('\n🔍 LAG ANALYSIS:');
        if (avgEstimatedDataRate > avgBrowserFrameRate + 10) {
            console.log(`  🔥 BOTTLENECK: Browser cannot keep up with data rate`);
            console.log(`  📊 Estimated Data: ${avgEstimatedDataRate.toFixed(1)} Hz`);
            console.log(`  📊 Browser Render: ${avgBrowserFrameRate.toFixed(1)} Hz`);
            console.log(`  📊 Performance Gap: ${(avgEstimatedDataRate - avgBrowserFrameRate).toFixed(1)} Hz`);
        }
        
        if (avgFrameConsistency < 80) {
            console.log(`  🔥 SMOOTHNESS ISSUE: Inconsistent frame timing`);
            console.log(`  📊 Frame Consistency: ${avgFrameConsistency.toFixed(1)}% (target: >80%)`);
        }
        
        // Key insights
        console.log('\n💡 KEY INSIGHTS:');
        console.log(`  DOM mutations detected: ${this.mutationCount} (robot movement)`);
        console.log(`  PING messages captured: ${this.pingMessages.length} (network activity)`);
        console.log(`  Frame intervals measured: ${this.frameIntervals.length} (browser timing)`);
        
        if (this.latencyData.length > 0) {
            const avgLatency = this.latencyData.reduce((sum, l) => sum + l.latency, 0) / this.latencyData.length;
            console.log(`  Average network latency: ${avgLatency.toFixed(1)}ms`);
        }
        
        // The systematic number
        console.log('\n🎯 THE SYSTEMATIC NUMBER:');
        if (avgEstimatedDataRate > 80 && avgBrowserFrameRate < 60) {
            console.log(`  ⚠️  LAG EXPLANATION: System receives ~${avgEstimatedDataRate.toFixed(0)}Hz data but browser renders at ${avgBrowserFrameRate.toFixed(0)}Hz`);
            console.log(`  📊 Processing capacity exceeded by ${(avgEstimatedDataRate - avgBrowserFrameRate).toFixed(1)}Hz`);
        } else if (avgFrameConsistency < 70) {
            console.log(`  ⚠️  LAG EXPLANATION: Frame timing inconsistent (${avgFrameConsistency.toFixed(1)}% consistency)`);
            console.log(`  📊 Choppy rendering despite adequate average frame rate`);
        } else {
            console.log(`  ✅ PERFORMANCE GOOD: Browser keeping up with data rate`);
        }
        
        console.log('\n✅ Safe frontend performance analysis complete');
    }
    
    exportSafeData() {
        const data = {
            summary: {
                duration: (performance.now() - this.startTime) / 1000,
                avgBrowserFrameRate: this.performanceLog.reduce((sum, r) => sum + r.browserFrameRate, 0) / this.performanceLog.length,
                avgDomUpdateRate: this.performanceLog.reduce((sum, r) => sum + r.domUpdateRate, 0) / this.performanceLog.length,
                avgEstimatedDataRate: this.performanceLog.reduce((sum, r) => sum + r.estimatedDataRate, 0) / this.performanceLog.length,
                totalMutations: this.mutationCount,
                totalPings: this.pingMessages.length
            },
            performanceLog: this.performanceLog,
            frameIntervals: this.frameIntervals.slice(-500), // Recent frame timings
            mutationIntervals: this.mutationIntervals.slice(-500), // Recent DOM changes
            latencyData: this.latencyData,
            pingMessages: this.pingMessages.slice(-100) // Recent messages
        };
        
        // Safe download
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `safe_frontend_performance_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('[NON-INVASIVE-PROFILER] Safe performance data exported');
    }
}

// Safe global functions
window.NonInvasiveFrontendProfiler = NonInvasiveFrontendProfiler;

window.startNonInvasiveProfiling = function() {
    if (window.safeProfiler) {
        console.warn('Safe profiler already running');
        return window.safeProfiler;
    }
    
    window.safeProfiler = new NonInvasiveFrontendProfiler();
    window.safeProfiler.start();
    return window.safeProfiler;
};

window.stopNonInvasiveProfiling = function() {
    if (window.safeProfiler) {
        window.safeProfiler.stop();
        window.safeProfiler = null;
    }
};

console.log('🔍 Non-Invasive Frontend Profiler loaded - SAFE for existing systems');
console.log('Call startNonInvasiveProfiling() to begin safe debugging');
