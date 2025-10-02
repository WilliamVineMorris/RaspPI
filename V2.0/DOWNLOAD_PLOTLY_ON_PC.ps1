# Download Plotly.js on Windows PC
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Downloading Plotly.js on Windows PC" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Create directory if it doesn't exist
$targetDir = "web\static\js"
if (-not (Test-Path $targetDir)) {
    Write-Host "Creating directory: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$targetFile = "$targetDir\plotly-2.27.0.min.js"
$url = "https://cdn.plotly.ly/plotly-2.27.0.min.js"

Write-Host "Downloading from: $url" -ForegroundColor Yellow
Write-Host "Saving to: $targetFile" -ForegroundColor Yellow
Write-Host ""
Write-Host "This may take a minute (~3.5 MB)..." -ForegroundColor Gray
Write-Host ""

try {
    # Download with progress
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $targetFile -ErrorAction Stop
    $ProgressPreference = 'Continue'
    
    # Verify download
    $fileInfo = Get-Item $targetFile
    $fileSizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "SUCCESS! Plotly.js downloaded" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "File: $targetFile" -ForegroundColor White
    Write-Host "Size: $fileSizeMB MB" -ForegroundColor White
    Write-Host ""
    
    # Verify it's JavaScript
    $firstLine = Get-Content $targetFile -First 1
    if ($firstLine -match "plotly|function") {
        Write-Host "File verified - appears to be valid JavaScript" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Commit and push to GitHub:" -ForegroundColor Yellow
    Write-Host "   git add web/static/js/plotly-2.27.0.min.js" -ForegroundColor White
    Write-Host "   git commit -m ""Add Plotly.js for local hosting""" -ForegroundColor White
    Write-Host "   git push" -ForegroundColor White
    Write-Host ""
    Write-Host "2. On the Pi, pull changes:" -ForegroundColor Yellow
    Write-Host "   cd ~/Documents/RaspPI/V2.0" -ForegroundColor White
    Write-Host "   git pull" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Restart web server on Pi:" -ForegroundColor Yellow
    Write-Host "   python3 run_web_interface.py" -ForegroundColor White
    Write-Host ""
    Write-Host "4. In browser: Ctrl+Shift+R (hard refresh)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "The visualizer should now work!" -ForegroundColor Green
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "ERROR: Download failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Alternative: Manual Download" -ForegroundColor Yellow
    Write-Host "1. Open in browser: $url" -ForegroundColor White
    Write-Host "2. Right-click -> Save As..." -ForegroundColor White
    Write-Host "3. Save to: $targetFile" -ForegroundColor White
    Write-Host ""
}

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
