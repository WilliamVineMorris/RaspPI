#!/usr/bin/env python3
"""
Example script to run a real scan with persistent output
"""

import asyncio
import tempfile
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from core.config_manager import ConfigManager
from scanning import ScanOrchestrator

async def real_scan_example():
    """Example of running a scan with persistent output"""
    
    # Create a permanent output directory
    scan_output_dir = Path.home() / "scanner_scans" / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    scan_output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🗂️  Scan output directory: {scan_output_dir}")
    
    # Create config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
system:
  name: production_scanner
  log_level: INFO
motion:
  controller:
    port: /dev/ttyUSB0
    baud_rate: 115200
  axes:
    x_axis:
      type: linear
      units: mm
      min_limit: 0.0
      max_limit: 100.0
      max_feedrate: 1000.0
      home_position: 0.0
    y_axis:
      type: linear
      units: mm
      min_limit: 0.0
      max_limit: 100.0
      max_feedrate: 1000.0
      home_position: 0.0
    z_axis:
      type: linear
      units: mm
      min_limit: 0.0
      max_limit: 50.0
      max_feedrate: 500.0
      home_position: 0.0
    c_axis:
      type: rotational
      units: degrees
      min_limit: 0.0
      max_limit: 360.0
      max_feedrate: 100.0
      home_position: 0.0
      continuous: true
cameras:
  camera_1:
    port: 0
    resolution: [1920, 1080]
    name: main
  camera_2:
    port: 1
    resolution: [1920, 1080]
    name: secondary
lighting:
  led_zones:
    zone_1:
      gpio_pin: 18
      name: main_light
      max_intensity: 80
    zone_2:
      gpio_pin: 19
      name: secondary_light
      max_intensity: 80
web_interface:
  port: 8080
  host: 0.0.0.0
""")
        config_file = f.name
    
    try:
        # Initialize scanning system
        config_manager = ConfigManager(config_file)
        orchestrator = ScanOrchestrator(config_manager)
        await orchestrator.initialize()
        
        # Create scan pattern
        print("📐 Creating scan pattern...")
        pattern = orchestrator.create_cylindrical_pattern(
            x_range=(-20.0, 20.0),      # Horizontal movement
            y_range=(20.0, 60.0),       # Vertical movement  
            z_rotations=[0.0, 30.0, 60.0], # Turntable rotation
            c_angles=[-15.0, 0.0, 15.0] # Camera pivot
        )
        
        print(f"📊 Pattern has {len(pattern.generate_points())} scan points")
        
        # Start scan
        print("🚀 Starting scan...")
        scan_state = await orchestrator.start_scan(
            pattern=pattern,
            output_directory=scan_output_dir,
            scan_id=f"production_scan_{datetime.now().strftime('%H%M%S')}"
        )
        
        print(f"📝 Scan ID: {scan_state.scan_id}")
        print(f"📍 Status: {scan_state.status}")
        
        # Wait for completion
        print("⏳ Waiting for scan completion...")
        completed = await orchestrator.wait_for_scan_completion(timeout=60.0)
        
        if completed:
            print("✅ Scan completed successfully!")
        else:
            print("⏰ Scan timed out")
            
        print(f"📊 Final status: {scan_state.status}")
        
        # List output files
        output_files = list(scan_output_dir.glob("*"))
        print(f"📁 Generated {len(output_files)} files:")
        for file in sorted(output_files):
            print(f"   📄 {file.name}")
            
        print(f"\n🗂️  All files saved to: {scan_output_dir}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import os
        os.unlink(config_file)

if __name__ == "__main__":
    asyncio.run(real_scan_example())