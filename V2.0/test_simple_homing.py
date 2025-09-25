#!/usr/bin/env python3
"""
Simple Homing with Proper Completion Detection
Uses direct serial communication like the successful test
"""

import serial
import time
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleHomingController:
    """Simple homing controller that works like the successful test"""
    
    def __init__(self, port='/dev/ttyUSB0', baud_rate=115200):
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection = None
    
    def connect(self):
        """Connect to FluidNC"""
        try:
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=2.0)
            time.sleep(1.0)  # Allow connection to stabilize
            
            # Clear buffers
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from FluidNC"""
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
    
    def send_command(self, command):
        """Send a command and get response"""
        if not self.serial_connection:
            return False, "Not connected"
        
        try:
            # Send command
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()
            
            # Wait for response
            time.sleep(0.5)
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting).decode('utf-8', errors='ignore')
                return True, response.strip()
            else:
                return True, "No response"
        except Exception as e:
            return False, str(e)
    
    def home_with_completion_detection(self):
        """Home and wait for proper completion like the successful test"""
        if not self.serial_connection:
            return False, "Not connected"
        
        try:
            logger.info("🏠 Starting homing sequence...")
            
            # Clear alarm first
            logger.info("📤 Clearing alarm ($X)")
            success, response = self.send_command("$X")
            if success:
                logger.info(f"🔓 Unlock response: {response}")
            
            # Send homing command
            logger.info("📤 Sending homing command ($H)")
            self.serial_connection.write(b"$H\n")
            self.serial_connection.flush()
            
            # Monitor for completion like the successful test
            start_time = time.time()
            homing_started = False
            homing_done = False
            timeout = 120.0  # 2 minutes
            
            logger.info("📊 Monitoring for homing completion...")
            
            while (time.time() - start_time) < timeout:
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting).decode('utf-8', errors='ignore')
                    if data.strip():
                        elapsed = time.time() - start_time
                        
                        # Check each line for homing messages
                        for line in data.strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            
                            # Log progress (but less verbose than test script)
                            if '[MSG:DBG: Homing' in line and 'Cycle' in line:
                                logger.info(f"📊 [{elapsed:.1f}s] {line}")
                                homing_started = True
                            elif '[MSG:DBG: Homing' in line and 'done' in line.lower():
                                logger.info(f"✅ [{elapsed:.1f}s] {line}")
                                homing_done = True
                                break
                            elif 'MSG:Homed:' in line:
                                logger.info(f"✅ [{elapsed:.1f}s] {line}")
                            elif 'ALARM' in line.upper():
                                logger.error(f"❌ Alarm detected: {line}")
                                return False, f"Alarm during homing: {line}"
                            elif line.startswith('error:'):
                                logger.error(f"❌ Error detected: {line}")
                                return False, f"Error during homing: {line}"
                
                # If homing is done, verify status
                if homing_done:
                    logger.info("⏳ Homing done detected, verifying final status...")
                    time.sleep(1.0)
                    
                    # Check final status
                    success, status_response = self.send_command("?")
                    if success:
                        logger.info(f"📊 Final status: {status_response}")
                        
                        if 'Idle' in status_response:
                            logger.info("✅ Homing completed successfully - status is Idle!")
                            return True, "Homing completed successfully"
                        elif 'Alarm' in status_response:
                            logger.error("❌ Homing failed - status is Alarm!")
                            return False, "Final status is Alarm"
                        else:
                            logger.warning(f"⚠️ Unexpected final status: {status_response}")
                            return False, f"Unexpected status: {status_response}"
                
                time.sleep(0.1)  # Check every 100ms
            
            # Timeout
            if homing_started:
                logger.error("❌ Homing started but never completed (timeout)")
                return False, "Homing timeout after starting"
            else:
                logger.error("❌ Homing never started (no debug messages received)")
                return False, "Homing never started"
                
        except Exception as e:
            logger.error(f"❌ Homing error: {e}")
            return False, str(e)

async def test_simple_homing():
    """Test the simple homing controller"""
    logger.info("🧪 Testing Simple Homing Controller")
    logger.info("=" * 50)
    
    try:
        # Create controller
        controller = SimpleHomingController()
        
        logger.info("🔌 Connecting to FluidNC...")
        if not controller.connect():
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected to FluidNC")
        
        # Check initial status
        success, response = controller.send_command("?")
        if success:
            logger.info(f"📊 Initial status: {response}")
        
        # Safety confirmation
        logger.info("\n⚠️  SAFETY WARNING:")
        logger.info("⚠️  Ensure all axes can move freely to limit switches!")
        logger.info("⚠️  Be ready to hit emergency stop if needed!")
        
        input("\nPress Enter when ready to test homing (or Ctrl+C to cancel): ")
        
        # Test homing
        logger.info("\n🚀 Starting simple homing test...")
        
        homing_success, homing_response = controller.home_with_completion_detection()
        
        if homing_success:
            logger.info("✅ Simple homing completed successfully!")
            logger.info(f"📋 Response: {homing_response}")
        else:
            logger.error("❌ Simple homing failed!")
            logger.error(f"📋 Error: {homing_response}")
        
        # Disconnect
        controller.disconnect()
        logger.info("🔌 Disconnected from FluidNC")
        
        return homing_success
        
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_simple_homing())
        if success:
            logger.info("\n✅ Simple homing test passed!")
            logger.info("🎉 Homing system works with proper completion detection")
        else:
            logger.error("\n❌ Simple homing test failed!")
            logger.error("🔧 Check the homing logic")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)