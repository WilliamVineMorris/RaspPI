#!/usr/bin/env python3
"""
Simple debug script to test scan execution
"""

import asyncio
import tempfile
import logging
from pathlib import Path

# Configure logging to see debug output
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from core.config_manager import ConfigManager
from scanning import ScanOrchestrator

async def debug_scan():
    """Test basic scan execution"""
    
    # Create a simple config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
system:
  name: debug_scanner
  log_level: DEBUG
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
    
    with tempfile.TemporaryDirectory() as scan_dir:
        try:
            print("Creating config manager...")
            config_manager = ConfigManager(config_file)
            
            print("Creating orchestrator...")
            orchestrator = ScanOrchestrator(config_manager)
            
            print("Initializing orchestrator...")
            await orchestrator.initialize()
            
            print("Creating simple pattern (single point)...")
            pattern = orchestrator.create_grid_pattern(
                x_range=(0.0, 0.0),
                y_range=(0.0, 0.0),
                spacing=10.0,
                z_height=5.0
            )
            
            print(f"Pattern has {len(pattern.generate_points())} points")
            
            print("Starting scan...")
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=scan_dir,
                scan_id="debug_scan"
            )
            
            print(f"Scan started: {scan_state.scan_id}")
            print(f"Initial status: {scan_state.status}")
            
            # Wait a bit and check status
            for i in range(10):
                await asyncio.sleep(0.5)
                status = orchestrator.get_scan_status()
                if status:
                    print(f"After {i*0.5}s: {status['status']}")
                    if status['status'] in ['COMPLETED', 'CANCELLED', 'FAILED']:
                        break
                else:
                    print(f"After {i*0.5}s: No status")
            
            # Try to wait for completion
            print("Waiting for completion...")
            completed = await orchestrator.wait_for_scan_completion(timeout=3.0)
            print(f"Completed: {completed}")
            print(f"Final status: {scan_state.status}")
            
            # Check files
            output_files = list(Path(scan_dir).glob("*"))
            print(f"Output files: {[f.name for f in output_files]}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            import os
            os.unlink(config_file)

if __name__ == "__main__":
    asyncio.run(debug_scan())