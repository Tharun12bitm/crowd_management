document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('analysisForm');
    const resultDiv = document.getElementById('result');
    const statusIndicator = document.getElementById('status-indicator');
    const cameraSection = document.getElementById('cameraSection');
    const liveStream = document.getElementById('liveStream');
    const cameraLabel = document.getElementById('cameraLabel');
    const cameraStatus = document.getElementById('cameraStatus');
    const captureBtn = document.getElementById('captureBtn');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const stopBtn = document.getElementById('stopBtn');
    const analysisResult = document.getElementById('analysisResult');

    let currentCameraUrl = '';

    // Test server connection
    testServerConnection();

    // Image event handlers for diagnostics
    liveStream.addEventListener('error', function() {
        console.error('Live stream image error');
        const probeDiv = document.getElementById('probeResult');
        probeDiv.style.display = 'block';
        probeDiv.textContent = '❌ Failed to load image — check camera URL or CORS.';
        cameraStatus.textContent = 'Error loading image';
        showResult('❌ Live image load failed', 'error');
    });

    liveStream.addEventListener('load', function() {
        const probeDiv = document.getElementById('probeResult');
        probeDiv.style.display = 'none';
        cameraStatus.textContent = 'Connected';
        showResult('📺 Live feed connected', 'success');
    });

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        await openCamera();
    });

    captureBtn.addEventListener('click', async function() {
        await captureSnapshot();
    });

    analyzeBtn.addEventListener('click', async function() {
        await analyzeCrowd();
    });


    stopBtn.addEventListener('click', function() {
        // stop any polling
        stopSnapshotPolling();
        liveStream.src = '';
        cameraSection.style.display = 'none';
        cameraLabel.textContent = '-';
        cameraStatus.textContent = 'Not connected';
        form.style.display = 'block';
        analysisResult.innerHTML = '';
        showResult('Camera closed', 'info');
    });

    async function openCamera() {
        currentCameraUrl = document.getElementById('cameraUrl').value.trim();
        const submitBtn = form.querySelector('button[type="submit"]');

        if (!currentCameraUrl) {
            showResult('Please provide a camera URL', 'error');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = '⏳ Opening...';
        showResult('📡 Probing camera...', 'loading');

        try {
            // Probe camera to determine streaming type
            cameraStatus.textContent = 'Probing...';
            const probeRes = await fetch(`/probe?url=${encodeURIComponent(currentCameraUrl)}`);
            const probe = await probeRes.json();
            // show probe debug info
            const probeDiv = document.getElementById('probeResult');
            probeDiv.style.display = 'block';
            probeDiv.textContent = `Probe: ${JSON.stringify(probe)}`;

            // prefer the resolved URL if provided by probe
            const resolved = probe.resolved_url || currentCameraUrl;

            if (probe.is_mjpeg) {
                // Use proxy MJPEG stream
                const streamUrl = `/video?url=${encodeURIComponent(resolved)}`;
                liveStream.src = streamUrl;
                liveStream.alt = 'MJPEG Stream';
                cameraLabel.textContent = resolved;
                cameraStatus.textContent = 'Streaming (MJPEG)';
                showResult('📹 MJPEG stream opened!', 'success');
            } else if (probe.is_image) {
                // Use periodic snapshot polling (use resolved URL for snapshots)
                liveStream.alt = 'Polling snapshots';
                startSnapshotPolling(resolved);
                cameraLabel.textContent = resolved;
                cameraStatus.textContent = 'Polling snapshots';
                showResult('📹 Snapshot polling started (approx. 1s)', 'success');
            } else {
                // Unknown type - try snapshot first
                startSnapshotPolling(resolved);
                cameraLabel.textContent = resolved;
                cameraStatus.textContent = 'Polling (fallback)';
                showResult('📹 Started snapshot polling (fallback)', 'info');
            }

            form.style.display = 'none';
            cameraSection.style.display = 'block';
        } catch (error) {
            console.error(error);
            showResult('❌ Failed to open camera', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '📹 Open Camera';
        }
    }

    let snapshotTimer = null;
    function startSnapshotPolling(resolvedUrl) {
        const urlToUse = resolvedUrl || currentCameraUrl;
        if (snapshotTimer) clearInterval(snapshotTimer);
        // Immediately load one
        liveStream.src = `/snapshot?url=${encodeURIComponent(urlToUse)}&t=${Date.now()}`;
        // Poll every 1s
        snapshotTimer = setInterval(() => {
            liveStream.src = `/snapshot?url=${encodeURIComponent(urlToUse)}&t=${Date.now()}`;
        }, 1000);
    }

    async function captureSnapshot() {
        const captureBtn = document.getElementById('captureBtn');
        captureBtn.disabled = true;
        captureBtn.textContent = '⏳ Capturing...';

        try {
            const response = await fetch(`/snapshot?url=${encodeURIComponent(currentCameraUrl)}&t=${Date.now()}`);
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `snapshot_${new Date().getTime()}.jpg`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                showResult('📸 Snapshot captured and downloaded!', 'success');
            } else {
                showResult('❌ Failed to capture snapshot', 'error');
            }
        } catch (error) {
            console.error(error);
            showResult('❌ Capture failed', 'error');
        } finally {
            captureBtn.disabled = false;
            captureBtn.textContent = '📸 Capture Snapshot';
        }
    }

    function stopSnapshotPolling() {
        if (snapshotTimer) {
            clearInterval(snapshotTimer);
            snapshotTimer = null;
        }
    }

    async function analyzeCrowd() {
        const analyzeBtn = document.getElementById('analyzeBtn');
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = '⏳ Analyzing...';
        analysisResult.innerHTML = '<p style="color: #718096;">🔄 Analyzing crowd...</p>';

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_url: currentCameraUrl })
            });

            const data = await response.json();

            if (data.success) {
                const analysis = data.data;
                const statusColor = analysis.status === 'HIGH CROWD' ? '#ff6b6b' : '#51cf66';
                const statusBgColor = analysis.status === 'HIGH CROWD' ? '#ffe0e0' : '#e6ffed';
                
                analysisResult.innerHTML = `
                    <div class="analysis-card" style="background: ${statusBgColor}; border-left: 4px solid ${statusColor};">
                        <h3 style="color: ${statusColor}; margin-bottom: 1rem;">${data.message}</h3>
                        <div class="analysis-grid">
                            <div class="analysis-item">
                                <span class="label">👥 People Count</span>
                                <span class="value">${analysis.count}</span>
                            </div>
                            <div class="analysis-item">
                                <span class="label">📊 Density</span>
                                <span class="value">${analysis.density}%</span>
                            </div>
                            <div class="analysis-item">
                                <span class="label">🆓 Free Space</span>
                                <span class="value">${analysis.free_space}%</span>
                            </div>
                            <div class="analysis-item">
                                <span class="label">⚠️ Status</span>
                                <span class="value" style="color: ${statusColor}; font-weight: bold;">${analysis.status}</span>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                analysisResult.innerHTML = `<p style="color: #c53030;">❌ ${data.error}</p>`;
            }
        } catch (error) {
            analysisResult.innerHTML = '<p style="color: #c53030;">❌ Analysis failed</p>';
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = '🔍 Analyze Crowd';
        }
    }

    function showResult(message, type) {
        resultDiv.textContent = message;
        resultDiv.className = `result ${type}`;
    }

    async function testServerConnection() {
        try {
            const response = await fetch('/health');
            if (response.ok) {
                statusIndicator.textContent = '✅ Server ready!';
                statusIndicator.style.background = '#c6f6d5';
                statusIndicator.style.color = '#22543d';
            }
        } catch (error) {
            statusIndicator.textContent = '⚠️ Server starting...';
            statusIndicator.style.background = '#fed7d7';
            statusIndicator.style.color = '#742a2a';
        }
    }
});