#!/usr/bin/env python3
"""
FluidNC Communication Diagnostic
Tests basic communication with FluidNC to identify why homing commands aren't working
"""

import serial
import time
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_basic_communication():
    """Test basic FluidNC communication"""
    port = '/dev/ttyUSB0'
    baud_rate = 115200
    
    logger.info(f"🔌 Testing FluidNC communication at {port}")
    
    try:
        # Open serial connection
        ser = serial.Serial(port, baud_rate, timeout=2.0)
        time.sleep(1.0)  # Allow connection to stabilize
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        logger.info("✅ Serial connection established")
        
        # Test 1: Send status request
        logger.info("📤 Sending status request (?)")
        ser.write(b"?\n")
        ser.flush()
        
        # Wait for response
        time.sleep(0.5)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            logger.info(f"📥 Status response: {response.strip()}")
        else:
            logger.warning("⚠️ No response to status request")
        
        # Test 2: Send unlock command
        logger.info("📤 Sending unlock command ($X)")
        ser.write(b"$X\n")
        ser.flush()
        
        # Wait for response
        time.sleep(0.5)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            logger.info(f"📥 Unlock response: {response.strip()}")
        else:
            logger.warning("⚠️ No response to unlock command")
        
        # Test 3: Check status after unlock
        logger.info("📤 Checking status after unlock (?)")
        ser.write(b"?\n")
        ser.flush()
        
        time.sleep(0.5)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            logger.info(f"📥 Status after unlock: {response.strip()}")
        else:
            logger.warning("⚠️ No response to status check")
        
        # Test 4: Try homing command
        print("\n" + "="*50)
        print("⚠️  SAFETY WARNING: About to send $H homing command!")
        print("⚠️  Ensure all axes can move freely to limit switches!")
        print("⚠️  Be ready to hit emergency stop if needed!")
        print("="*50)
        
        response = input("Send $H command? (y/N): ").strip().lower()
        if response == 'y':
            logger.info("📤 Sending homing command ($H)")
            ser.write(b"$H\n")
            ser.flush()
            
            # Monitor for longer period
            start_time = time.time()
            responses = []
            
            while (time.time() - start_time) < 10.0:  # Monitor for 10 seconds
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    if data.strip():
                        responses.append(f"[{time.time()-start_time:.1f}s] {data.strip()}")
                        logger.info(f"📥 Homing response: {data.strip()}")
                
                time.sleep(0.1)
            
            if responses:
                logger.info("✅ Received homing responses:")
                for resp in responses:
                    logger.info(f"   {resp}")
            else:
                logger.error("❌ No response to $H command")
        else:
            logger.info("⏭️  Skipping homing test")
        
        # Close connection
        ser.close()
        logger.info("🔌 Connection closed")
        
        return True
        
    except serial.SerialException as e:
        logger.error(f"❌ Serial connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_basic_communication()
    if success:
        logger.info("✅ Communication test completed")
    else:
        logger.error("❌ Communication test failed")
        sys.exit(1)