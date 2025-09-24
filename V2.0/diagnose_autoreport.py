#!/usr/bin/env python3
"""
Diagnostic script to check FluidNC auto-reporting and idle state behavior
"""

import asyncio
import sys
import os
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def diagnose_auto_reporting():
    """Diagnose FluidNC auto-reporting behavior"""
    print("🔍 FluidNC Auto-Reporting Diagnostic")
    print("=" * 50)
    
    try:
        from motion.fluidnc_controller import FluidNCController
        from core.types import Position4D
        import logging
        
        # Setup logging to see what's happening
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        print("📡 Initializing FluidNC connection...")
        controller = FluidNCController()
        
        # Initialize connection
        await controller.initialize()
        print("✅ Connection established")
        
        # Check current auto-report setting
        print("\n🔧 Checking auto-report configuration...")
        try:
            response = await controller._send_command('$Report/Interval')
            print(f"   Current auto-report interval: {response}")
        except Exception as e:
            print(f"   ❌ Failed to check interval: {e}")
        
        # Test background monitoring
        print("\n📊 Testing background monitor...")
        await controller.start_background_monitoring()
        
        # Wait and check for updates
        print("⏱️  Monitoring for 10 seconds...")
        start_time = time.time()
        last_position = None
        update_count = 0
        
        for i in range(10):
            await asyncio.sleep(1)
            
            # Get current status
            status = await controller.get_status()
            current_time = time.time()
            
            if status and 'position' in status:
                position = status['position']
                if position != last_position:
                    update_count += 1
                    last_position = position
                    print(f"   Update {update_count}: {position} (age: {current_time - start_time:.1f}s)")
                else:
                    print(f"   No change: {position} (age: {current_time - start_time:.1f}s)")
            else:
                print(f"   No status data (age: {current_time - start_time:.1f}s)")
        
        print(f"\n📈 Summary: {update_count} position updates in 10 seconds")
        
        # Test manual status query
        print("\n🔄 Testing manual status query...")
        manual_status = await controller.get_status()
        if manual_status:
            print(f"   Manual query result: {manual_status.get('position', 'No position')}")
            print(f"   Status age: {manual_status.get('timestamp', 'No timestamp')}")
        else:
            print("   ❌ Manual query failed")
        
        # Test small movement to trigger reporting
        print("\n🎯 Testing movement to trigger auto-reporting...")
        try:
            current_pos = await controller.get_current_position()
            print(f"   Current position: {current_pos}")
            
            # Small Z movement
            delta = Position4D(0, 0, 0.1, 0)
            print(f"   Moving by: {delta}")
            
            success = await controller.move_relative(delta, speed=5.0)
            if success:
                print("   ✅ Movement completed")
                
                # Check for updates after movement
                await asyncio.sleep(2)
                new_pos = await controller.get_current_position()
                print(f"   New position: {new_pos}")
            else:
                print("   ❌ Movement failed")
                
        except Exception as e:
            print(f"   ❌ Movement test error: {e}")
        
        # Clean up
        await controller.stop_background_monitoring()
        await controller.disconnect()
        
        print("\n" + "=" * 50)
        print("✅ Diagnostic completed")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main diagnostic function"""
    try:
        asyncio.run(diagnose_auto_reporting())
    except KeyboardInterrupt:
        print("\n🛑 Diagnostic interrupted")
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")

if __name__ == "__main__":
    main()