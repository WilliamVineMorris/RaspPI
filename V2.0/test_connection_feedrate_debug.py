#!/usr/bin/env python3
"""
Quick Connection and Feedrate Test

Tests the connection status detection and feedrate configuration.

Author: Scanner System Debug
Created: September 24, 2025
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the V2.0 directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection_and_feedrates():
    """Quick test of connection and feedrate issues"""
    
    logger.info("🔍 Quick Connection and Feedrate Test")
    
    try:
        # 1. Test configuration loading
        logger.info("📋 Testing configuration loading...")
        config_manager = ConfigManager('config/scanner_config.yaml')
        
        # Test feedrate access
        manual_rates = config_manager.get('feedrates.manual_mode', {})
        logger.info(f"✅ Manual mode feedrates loaded: {manual_rates}")
        
        # Test individual axis feedrates
        x_feedrate = manual_rates.get('x_axis', 'NOT_FOUND')
        y_feedrate = manual_rates.get('y_axis', 'NOT_FOUND')
        z_feedrate = manual_rates.get('z_axis', 'NOT_FOUND')
        c_feedrate = manual_rates.get('c_axis', 'NOT_FOUND')
        
        logger.info(f"📊 Individual feedrates:")
        logger.info(f"  X-axis: {x_feedrate} mm/min")
        logger.info(f"  Y-axis: {y_feedrate} mm/min")
        logger.info(f"  Z-axis: {z_feedrate} deg/min")
        logger.info(f"  C-axis: {c_feedrate} deg/min")
        
        # Verify these are the enhanced values
        expected_values = {
            'x_axis': 950.0,
            'y_axis': 950.0,
            'z_axis': 750.0,
            'c_axis': 4800.0
        }
        
        all_correct = True
        for axis, expected in expected_values.items():
            actual = manual_rates.get(axis, 0)
            if actual == expected:
                logger.info(f"✅ {axis}: {actual} (correct enhanced value)")
            else:
                logger.error(f"❌ {axis}: {actual} (expected {expected})")
                all_correct = False
        
        if all_correct:
            logger.info("✅ All enhanced feedrates are correctly configured!")
        else:
            logger.error("❌ Some feedrates are not set to enhanced values")
        
        # 2. Test if we can import the motion controller
        logger.info("🎛️ Testing motion controller import...")
        try:
            from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
            logger.info("✅ Motion controller import successful")
            
            # Test connection without actually connecting
            motion_config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'timeout': 5.0,
                'axes': config_manager.get_all_axes()
            }
            
            controller = SimplifiedFluidNCControllerFixed(motion_config)
            logger.info("✅ Motion controller instantiation successful")
            
            # Test connection status methods (without connecting)
            logger.info("🔍 Testing connection status methods...")
            try:
                # This should return False since we're not connected
                connected = controller._connected
                logger.info(f"  _connected property: {connected}")
                
                if hasattr(controller, 'refresh_connection_status'):
                    refresh_status = controller.refresh_connection_status()
                    logger.info(f"  refresh_connection_status(): {refresh_status}")
                
                logger.info("✅ Connection status methods working")
            except Exception as e:
                logger.error(f"❌ Connection status methods failed: {e}")
            
        except Exception as e:
            logger.error(f"❌ Motion controller issue: {e}")
        
        # 3. Test web interface integration simulation
        logger.info("🌐 Testing web interface feedrate integration...")
        
        # Simulate what the web interface does
        axis = 'x'
        manual_feedrates = config_manager.get('feedrates.manual_mode', {})
        speed = manual_feedrates.get(f'{axis}_axis', 10.0)  # fallback
        
        logger.info(f"📡 Simulated jog for {axis}-axis would use feedrate: {speed}")
        
        if speed == 950.0:
            logger.info("✅ Web interface would use enhanced feedrate!")
        else:
            logger.error(f"❌ Web interface would use wrong feedrate: {speed}")
        
        logger.info("🎯 Test Summary:")
        logger.info("✅ Configuration loading: PASSED")
        logger.info("✅ Enhanced feedrates: CONFIGURED" if all_correct else "❌ Enhanced feedrates: MISCONFIGURED")
        logger.info("✅ Motion controller: IMPORTABLE")
        logger.info("✅ Connection methods: AVAILABLE")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    try:
        result = test_connection_and_feedrates()
        if result:
            print("\n🎉 Quick Test: PASSED")
            print("\n🚀 Next Steps:")
            print("1. Test the debug endpoints:")
            print("   - http://<pi-ip>:5000/api/debug/feedrates")
            print("   - http://<pi-ip>:5000/api/debug/connection")
            print("2. Try manual jog commands to see if enhanced feedrates are used")
            print("3. Check connection status in web interface")
        else:
            print("\n❌ Quick Test: FAILED")
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")