#!/usr/bin/env python3
"""
Test Homing with Proper Completion Detection
Tests homing and waits for the "MSG:DBG: Homing Done" message before declaring success.
"""

import serial
import time
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_homing_with_completion_detection():
    """Test homing with proper completion detection"""
    port = '/dev/ttyUSB0'
    baud_rate = 115200
    
    logger.info(f"🔌 Testing homing with completion detection at {port}")
    
    try:
        # Open serial connection
        ser = serial.Serial(port, baud_rate, timeout=2.0)
        time.sleep(1.0)  # Allow connection to stabilize
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        logger.info("✅ Serial connection established")
        
        # Check initial status
        logger.info("📤 Checking initial status (?)")
        ser.write(b"?\n")
        ser.flush()
        
        time.sleep(0.5)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            logger.info(f"📥 Initial status: {response.strip()}")
        
        # Clear alarm if needed
        logger.info("📤 Sending unlock command ($X)")
        ser.write(b"$X\n")
        ser.flush()
        
        time.sleep(0.5)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            logger.info(f"📥 Unlock response: {response.strip()}")
        
        # Safety warning
        print("\n" + "="*60)
        print("⚠️  SAFETY WARNING: About to send $H homing command!")
        print("⚠️  Ensure all axes can move freely to limit switches!")
        print("⚠️  Be ready to hit emergency stop if needed!")
        print("="*60)
        
        response = input("Send $H command and wait for completion? (y/N): ").strip().lower()
        if response != 'y':
            logger.info("⏭️  Homing test cancelled")
            ser.close()
            return True
        
        # Send homing command
        logger.info("📤 Sending homing command ($H)")
        ser.write(b"$H\n")
        ser.flush()
        
        # Monitor for completion
        start_time = time.time()
        responses = []
        homing_started = False
        homing_done = False
        timeout = 120.0  # 2 minutes timeout
        
        logger.info("📊 Monitoring for homing completion...")
        
        while (time.time() - start_time) < timeout:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                if data.strip():
                    elapsed = time.time() - start_time
                    responses.append(f"[{elapsed:.1f}s] {data.strip()}")
                    
                    # Check each line for homing messages
                    for line in data.strip().split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Log the message
                        logger.info(f"📥 [{elapsed:.1f}s] {line}")
                        
                        # Check for homing start
                        if '[MSG:DBG: Homing' in line and not homing_started:
                            homing_started = True
                            logger.info("🏠 Homing sequence started!")
                        
                        # Check for homing completion
                        if '[MSG:DBG: Homing' in line and 'Done' in line:
                            homing_done = True
                            logger.info("✅ Homing Done message received!")
                            break
                        
                        # Check for errors
                        if 'ALARM' in line.upper():
                            logger.error(f"❌ Alarm detected: {line}")
                            break
                        elif line.startswith('error:'):
                            logger.error(f"❌ Error detected: {line}")
                            break
            
            # If homing is done, wait a moment then check status
            if homing_done:
                logger.info("⏳ Homing Done detected, checking final status...")
                time.sleep(1.0)
                
                # Check final status
                ser.write(b"?\n")
                ser.flush()
                time.sleep(0.5)
                
                if ser.in_waiting > 0:
                    status_response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    logger.info(f"📊 Final status: {status_response.strip()}")
                    
                    if 'Idle' in status_response:
                        logger.info("✅ Homing completed successfully - status is Idle!")
                        break
                    elif 'Alarm' in status_response:
                        logger.error("❌ Homing failed - status is Alarm!")
                        break
                    else:
                        logger.warning(f"⚠️ Unexpected final status: {status_response}")
                        break
            
            time.sleep(0.1)  # Check every 100ms
        
        # Summary
        if homing_done:
            logger.info("✅ Homing test completed successfully!")
            logger.info(f"📈 Total homing time: {time.time() - start_time:.1f} seconds")
        else:
            if homing_started:
                logger.error("❌ Homing started but never completed (timeout)")
            else:
                logger.error("❌ Homing never started (no debug messages received)")
        
        logger.info(f"📋 Total messages received: {len(responses)}")
        
        # Close connection
        ser.close()
        logger.info("🔌 Connection closed")
        
        return homing_done
        
    except serial.SerialException as e:
        logger.error(f"❌ Serial connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_homing_with_completion_detection()
    if success:
        logger.info("✅ Homing completion detection test passed")
    else:
        logger.error("❌ Homing completion detection test failed")
        sys.exit(1)