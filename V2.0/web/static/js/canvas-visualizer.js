/**
 * Simple 2D Canvas-based Scan Path Visualizer
 * No external dependencies - pure JavaScript + Canvas
 * Shows top view (X-Z plane) and side view (Y-Z plane)
 */

function create2DVisualizer() {
    // Create canvas elements for top and side views
    const container = document.getElementById('scan-path-3d-plot');
    container.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
                <h5 style="margin: 0 0 0.5rem 0; text-align: center;">Top View (X-Z Plane)</h5>
                <canvas id="topViewCanvas" width="400" height="400" 
                        style="border: 1px solid #ddd; background: white; width: 100%;"></canvas>
            </div>
            <div>
                <h5 style="margin: 0 0 0.5rem 0; text-align: center;">Side View (Y-Z Plane)</h5>
                <canvas id="sideViewCanvas" width="400" height="400" 
                        style="border: 1px solid #ddd; background: white; width: 100%;"></canvas>
            </div>
        </div>
        <div style="margin-top: 1rem; text-align: center; font-size: 0.85rem; color: #666;">
            <span>🔵 Start → </span>
            <span>🔴 End</span>
            <span style="margin-left: 1rem;">• Total Points: <strong id="canvas-point-count">0</strong></span>
        </div>
    `;
}

function visualizeScanPathCanvas(points) {
    if (!points || points.length === 0) {
        const container = document.getElementById('scan-path-3d-plot');
        container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No points to display</div>';
        return;
    }
    
    create2DVisualizer();
    
    // Convert cylindrical to Cartesian
    const cartesianPoints = points.map(p => {
        const z_rad = p.z * Math.PI / 180;
        return {
            x: p.x * Math.cos(z_rad),
            y: p.y,
            z: p.x * Math.sin(z_rad),
            index: p.index || 0
        };
    });
    
    // Draw top view (X-Z plane)
    drawTopView(cartesianPoints);
    
    // Draw side view (Y-Z plane)
    drawSideView(cartesianPoints);
    
    // Update point count
    document.getElementById('canvas-point-count').textContent = points.length;
    
    // Update info display
    const xCoords = cartesianPoints.map(p => p.x);
    const yCoords = cartesianPoints.map(p => p.y);
    const zCoords = cartesianPoints.map(p => p.z);
    updateVisualizerInfo(points, xCoords, yCoords, zCoords);
}

function drawTopView(points) {
    const canvas = document.getElementById('topViewCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 40;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Find bounds
    const xCoords = points.map(p => p.x);
    const zCoords = points.map(p => p.z);
    const xMin = Math.min(...xCoords);
    const xMax = Math.max(...xCoords);
    const zMin = Math.min(...zCoords);
    const zMax = Math.max(...zCoords);
    
    // Scale to fit canvas
    const xRange = xMax - xMin || 1;
    const zRange = zMax - zMin || 1;
    const scale = Math.min((width - 2 * padding) / xRange, (height - 2 * padding) / zRange);
    
    function toCanvasX(x) {
        return padding + (x - xMin) * scale;
    }
    
    function toCanvasY(z) {
        return height - padding - (z - zMin) * scale;
    }
    
    // Draw grid
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 10; i++) {
        const x = padding + (width - 2 * padding) * i / 10;
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        
        const y = padding + (height - 2 * padding) * i / 10;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }
    
    // Draw axes
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.lineTo(width - padding - 10, height - padding - 5);
    ctx.moveTo(width - padding, height - padding);
    ctx.lineTo(width - padding - 10, height - padding + 5);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    ctx.lineTo(padding, padding);
    ctx.lineTo(padding - 5, padding + 10);
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding + 5, padding + 10);
    ctx.stroke();
    
    // Labels
    ctx.fillStyle = '#333';
    ctx.font = '12px sans-serif';
    ctx.fillText('X', width - padding + 5, height - padding + 5);
    ctx.fillText('Z', padding - 5, padding - 5);
    
    // Draw path
    ctx.lineWidth = 2;
    for (let i = 0; i < points.length - 1; i++) {
        const p1 = points[i];
        const p2 = points[i + 1];
        
        const t = i / (points.length - 1);
        ctx.strokeStyle = interpolateColor(t);
        
        ctx.beginPath();
        ctx.moveTo(toCanvasX(p1.x), toCanvasY(p1.z));
        ctx.lineTo(toCanvasX(p2.x), toCanvasY(p2.z));
        ctx.stroke();
    }
    
    // Draw points
    points.forEach((p, i) => {
        const t = i / (points.length - 1);
        ctx.fillStyle = interpolateColor(t);
        ctx.beginPath();
        ctx.arc(toCanvasX(p.x), toCanvasY(p.z), 4, 0, 2 * Math.PI);
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
    });
}

function drawSideView(points) {
    const canvas = document.getElementById('sideViewCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 40;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Find bounds
    const yCoords = points.map(p => p.y);
    const zCoords = points.map(p => p.z);
    const yMin = Math.min(...yCoords);
    const yMax = Math.max(...yCoords);
    const zMin = Math.min(...zCoords);
    const zMax = Math.max(...zCoords);
    
    // Scale to fit canvas
    const yRange = yMax - yMin || 1;
    const zRange = zMax - zMin || 1;
    const scale = Math.min((width - 2 * padding) / zRange, (height - 2 * padding) / yRange);
    
    function toCanvasX(z) {
        return padding + (z - zMin) * scale;
    }
    
    function toCanvasY(y) {
        return height - padding - (y - yMin) * scale;
    }
    
    // Draw grid
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 10; i++) {
        const x = padding + (width - 2 * padding) * i / 10;
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
        
        const y = padding + (height - 2 * padding) * i / 10;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }
    
    // Draw axes
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.lineTo(width - padding - 10, height - padding - 5);
    ctx.moveTo(width - padding, height - padding);
    ctx.lineTo(width - padding - 10, height - padding + 5);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    ctx.lineTo(padding, padding);
    ctx.lineTo(padding - 5, padding + 10);
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding + 5, padding + 10);
    ctx.stroke();
    
    // Labels
    ctx.fillStyle = '#333';
    ctx.font = '12px sans-serif';
    ctx.fillText('Z', width - padding + 5, height - padding + 5);
    ctx.fillText('Y', padding - 5, padding - 5);
    
    // Draw path
    ctx.lineWidth = 2;
    for (let i = 0; i < points.length - 1; i++) {
        const p1 = points[i];
        const p2 = points[i + 1];
        
        const t = i / (points.length - 1);
        ctx.strokeStyle = interpolateColor(t);
        
        ctx.beginPath();
        ctx.moveTo(toCanvasX(p1.z), toCanvasY(p1.y));
        ctx.lineTo(toCanvasX(p2.z), toCanvasY(p2.y));
        ctx.stroke();
    }
    
    // Draw points
    points.forEach((p, i) => {
        const t = i / (points.length - 1);
        ctx.fillStyle = interpolateColor(t);
        ctx.beginPath();
        ctx.arc(toCanvasX(p.z), toCanvasY(p.y), 4, 0, 2 * Math.PI);
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
    });
}

function interpolateColor(t) {
    // Blue (0,0,255) to Red (255,0,0)
    const r = Math.round(255 * t);
    const b = Math.round(255 * (1 - t));
    return `rgb(${r}, 0, ${b})`;
}

// Export for use in scans.html
window.visualizeScanPath2D = visualizeScanPathCanvas;
