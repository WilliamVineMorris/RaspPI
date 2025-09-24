#!/usr/bin/env python3
"""
Simple Test for Enhanced Homing Detection
Tests just the message capture functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motion.simplified_fluidnc_protocol_fixed import SimplifiedFluidNCProtocolFixed
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_message_capture():
    """Test the enhanced message capture"""
    try:
        logger.info("🧪 Testing Enhanced Protocol Message Capture")
        logger.info("="*50)
        
        # Create protocol
        protocol = SimplifiedFluidNCProtocolFixed("/dev/ttyUSB0", 115200)
        
        # Connect
        if not protocol.connect():
            logger.error("❌ Failed to connect")
            return False
            
        logger.info("✅ Connected to FluidNC")
        
        # Test message capture capability
        if hasattr(protocol, 'get_recent_raw_messages'):
            logger.info("✅ Protocol has message capture capability!")
            
            # Wait a moment for some messages
            time.sleep(2)
            
            # Get recent messages
            messages = protocol.get_recent_raw_messages(20)
            logger.info(f"📝 Captured {len(messages)} recent messages:")
            
            for msg in messages:
                logger.info(f"   {msg}")
                
            # Test statistics
            stats = protocol.get_stats()
            logger.info(f"📊 Debug messages captured so far: {stats.get('debug_messages_captured', 0)}")
            
        else:
            logger.error("❌ Protocol missing message capture capability")
            return False
        
        # Test sending a command and capturing response
        logger.info("\n🧪 Testing command and response capture...")
        
        success, response = protocol.send_command("?")
        logger.info(f"Status command result: {success}, response: {response}")
        
        # Check captured messages again
        time.sleep(1)
        new_messages = protocol.get_recent_raw_messages(10)
        logger.info(f"📝 New messages after status request:")
        for msg in new_messages[-5:]:  # Last 5
            logger.info(f"   {msg}")
        
        # Disconnect
        protocol.disconnect()
        logger.info("🔌 Disconnected")
        
        logger.info("\n✅ Message capture test completed successfully!")
        logger.info("💡 The protocol is ready for enhanced homing detection")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_homing_message_detection():
    """Test actual homing with message detection"""
    try:
        logger.info("🧪 Testing Homing Message Detection")
        logger.info("="*50)
        
        protocol = SimplifiedFluidNCProtocolFixed("/dev/ttyUSB0", 115200)
        
        if not protocol.connect():
            logger.error("❌ Connection failed")
            return False
            
        logger.info("✅ Connected")
        
        # Get initial status
        status = protocol.get_current_status()
        logger.info(f"📊 Initial status: {status.state if status else 'Unknown'}")
        
        print("\n⚠️  HOMING TEST")
        print("This will run actual homing and monitor for debug messages")
        print("Make sure your machine is ready!")
        
        response = input("🔶 Proceed with homing? (y/N): ").strip().lower()
        if response != 'y':
            protocol.disconnect()
            return True
        
        logger.info("🏠 Starting homing with message monitoring...")
        
        # Send homing command using raw serial approach to avoid parsing conflicts
        logger.info("🏠 Sending homing command with direct serial approach...")
        
        try:
            # Direct serial send to avoid motion wait conflicts during homing
            with protocol.connection_lock:
                if protocol.serial_connection:
                    protocol.serial_connection.write(b"$H\n")
                    protocol.serial_connection.flush()
                    logger.info("✅ Homing command sent directly")
                    success = True
                    response = "Command sent via direct serial"
                else:
                    success = False
                    response = "No serial connection"
        except Exception as e:
            success = False
            response = f"Direct send error: {e}"
            
        logger.info(f"Homing command sent: {success}, response: {response}")
        
        if not success:
            logger.error("❌ Homing command failed")
            protocol.disconnect()
            return False
        
        # Monitor for completion messages
        timeout = 45.0
        start_time = time.time()
        homing_done = False
        
        logger.info("🏠 Monitoring for '[MSG:DBG: Homing done]'...")
        
        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            
            try:
                # Check recent messages with error protection
                messages = protocol.get_recent_raw_messages(50)
                
                for msg in messages:
                    if "[MSG:DBG: Homing done]" in msg:
                        logger.info(f"🎯 DETECTED: Homing completion at {elapsed:.1f}s!")
                        logger.info(f"   Message: {msg}")
                        homing_done = True
                        break
                    elif "[MSG:Homed:" in msg:
                        logger.info(f"✅ Axis homed: {msg}")
                
                if homing_done:
                    break
                    
                # Show periodic status with error protection
                if int(elapsed) % 5 == 0:
                    try:
                        current_status = protocol.get_current_status()
                        state = current_status.state if current_status else 'Unknown'
                        logger.info(f"🏠 Status at {elapsed:.0f}s: {state}")
                    except Exception as status_error:
                        logger.debug(f"🔧 Status check error at {elapsed:.0f}s: {status_error}")
                
            except Exception as loop_error:
                logger.debug(f"🔧 Monitoring loop error at {elapsed:.1f}s: {loop_error}")
                # Continue monitoring despite errors
            
            time.sleep(0.5)
        
        if homing_done:
            logger.info("✅ Enhanced homing detection SUCCESS!")
        else:
            logger.warning("⚠️ Timeout - no completion message detected")
        
        # Final status
        final_status = protocol.get_current_status()
        logger.info(f"📊 Final status: {final_status.state if final_status else 'Unknown'}")
        
        # Show all captured messages
        all_messages = protocol.get_recent_raw_messages(100)
        homing_messages = [msg for msg in all_messages if any(keyword in msg for keyword in ['Homing', 'Homed', 'MSG:DBG'])]
        
        if homing_messages:
            logger.info("📝 All homing-related messages captured:")
            for msg in homing_messages:
                logger.info(f"   {msg}")
        
        protocol.disconnect()
        
        return homing_done
        
    except Exception as e:
        logger.error(f"❌ Homing test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Enhanced Message Capture Test")
    print("1. Test message capture only")
    print("2. Test homing message detection")
    
    choice = input("Select test (1 or 2): ").strip()
    
    if choice == "1":
        success = test_message_capture()
    elif choice == "2":
        success = test_homing_message_detection()
    else:
        print("Invalid choice")
        sys.exit(1)
    
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed!")
        sys.exit(1)