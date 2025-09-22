#!/usr/bin/env python3
"""
Debug FluidNC Connection Script
Test FluidNC connection with detailed diagnostics
"""

import asyncio
import logging
import serial
import time
from typing import Optional

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class FluidNCDebugger:
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.connection: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        """Establish serial connection"""
        try:
            logger.info(f"🔌 Connecting to {self.port} at {self.baudrate} baud...")
            
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2.0,
                writeTimeout=2.0,
                rtscts=False,
                dsrdtr=False
            )
            
            if self.connection.is_open:
                logger.info("✅ Serial connection established")
                return True
            else:
                logger.error("❌ Failed to open serial port")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def send_command(self, command: str, timeout: float = 2.0) -> Optional[str]:
        """Send command and get response"""
        if not self.connection or not self.connection.is_open:
            logger.error("❌ No active connection")
            return None
            
        try:
            # Clear input buffer
            self.connection.reset_input_buffer()
            
            # Send command
            cmd_line = f"{command}\n"
            logger.debug(f"📤 Sending: {repr(cmd_line)}")
            self.connection.write(cmd_line.encode('utf-8'))
            self.connection.flush()
            
            # Read response with timeout
            start_time = time.time()
            response_lines = []
            
            while time.time() - start_time < timeout:
                if self.connection.in_waiting > 0:
                    try:
                        line = self.connection.readline().decode('utf-8').strip()
                        if line:
                            logger.debug(f"📥 Received: {repr(line)}")
                            response_lines.append(line)
                            
                            # FluidNC typically responds with 'ok' or 'error'
                            if line.lower().startswith(('ok', 'error')):
                                break
                    except UnicodeDecodeError:
                        logger.warning("⚠️  Received non-UTF8 data")
                        continue
                
                time.sleep(0.01)  # Small sleep to prevent busy waiting
            
            if response_lines:
                full_response = '\n'.join(response_lines)
                logger.info(f"✅ Response: {repr(full_response)}")
                return full_response
            else:
                logger.warning(f"⚠️  No response to command: {command}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Command failed: {e}")
            return None
    
    def test_basic_communication(self):
        """Test basic communication patterns"""
        logger.info("🧪 Testing basic communication...")
        
        # Test 1: Simple status query
        logger.info("📋 Test 1: Status query")
        response = self.send_command("?")
        if response:
            logger.info("✅ Status query successful")
        else:
            logger.warning("⚠️  Status query failed")
        
        # Test 2: Get version/build info
        logger.info("📋 Test 2: Version query")
        response = self.send_command("$I")
        if response:
            logger.info("✅ Version query successful")
        else:
            logger.warning("⚠️  Version query failed")
            
        # Test 3: Get current state
        logger.info("📋 Test 3: State query")
        response = self.send_command("$G")
        if response:
            logger.info("✅ State query successful")
        else:
            logger.warning("⚠️  State query failed")
            
        # Test 4: Get settings (first few)
        logger.info("📋 Test 4: Settings query")
        response = self.send_command("$$")
        if response:
            logger.info("✅ Settings query successful")
        else:
            logger.warning("⚠️  Settings query failed")
    
    def test_fluidnc_detection(self):
        """Test if this is actually a FluidNC device"""
        logger.info("🔍 Testing FluidNC detection...")
        
        # Look for FluidNC-specific responses
        test_commands = [
            ("?", "Status format check"),
            ("$I", "Build info check"),  
            ("$+", "Extended command check"),
            ("$LocalFS/List", "FluidNC filesystem check")
        ]
        
        fluidnc_indicators = 0
        
        for cmd, description in test_commands:
            logger.info(f"📋 {description}: {cmd}")
            response = self.send_command(cmd, timeout=3.0)
            
            if response:
                response_lower = response.lower()
                if any(indicator in response_lower for indicator in 
                       ['fluidnc', 'grbl', 'alarm', 'mpos', 'wpos']):
                    fluidnc_indicators += 1
                    logger.info(f"✅ FluidNC indicator found in response")
                else:
                    logger.info(f"ℹ️  No FluidNC indicators in response")
            else:
                logger.warning(f"⚠️  No response to {cmd}")
        
        logger.info(f"📊 FluidNC indicators found: {fluidnc_indicators}/{len(test_commands)}")
        
        if fluidnc_indicators >= 2:
            logger.info("🎉 Device appears to be FluidNC compatible!")
            return True
        else:
            logger.warning("⚠️  Device may not be FluidNC or not responding correctly")
            return False
    
    def run_full_test(self):
        """Run complete diagnostic test"""
        logger.info("🚀 Starting FluidNC Connection Diagnostics")
        logger.info(f"Port: {self.port}")
        logger.info(f"Baudrate: {self.baudrate}")
        logger.info("=" * 60)
        
        try:
            # Step 1: Connect
            if not self.connect():
                logger.error("❌ FAILED: Could not establish connection")
                return False
            
            # Wait a moment for device to settle
            logger.info("⏳ Waiting for device to settle...")
            time.sleep(2.0)
            
            # Step 2: Test basic communication
            self.test_basic_communication()
            
            # Step 3: Test FluidNC detection
            is_fluidnc = self.test_fluidnc_detection()
            
            logger.info("=" * 60)
            if is_fluidnc:
                logger.info("🎉 DIAGNOSIS: FluidNC device detected and responsive!")
                logger.info("💡 RECOMMENDATION: Check your FluidNC configuration")
            else:
                logger.info("⚠️  DIAGNOSIS: Device present but may not be FluidNC")
                logger.info("💡 RECOMMENDATIONS:")
                logger.info("   • Verify this is a FluidNC device")
                logger.info("   • Check FluidNC firmware is properly flashed")
                logger.info("   • Try different baud rates (9600, 38400, 57600)")
                logger.info("   • Check cable connections")
            
            return is_fluidnc
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR: {e}")
            return False
            
        finally:
            if self.connection and self.connection.is_open:
                self.connection.close()
                logger.info("🔌 Connection closed")

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug FluidNC Connection')
    parser.add_argument('--port', default='/dev/ttyUSB0', 
                       help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=115200,
                       help='Baud rate (default: 115200)')
    
    args = parser.parse_args()
    
    debugger = FluidNCDebugger(args.port, args.baudrate)
    success = debugger.run_full_test()
    
    exit(0 if success else 1)

if __name__ == "__main__":
    main()