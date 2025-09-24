#!/usr/bin/env python3
"""
Enhanced Protocol Debug Tool

Tests the enhanced FluidNC protocol directly to diagnose command timeout issues.
This helps identify if the problem is in protocol handling, command parsing, or FluidNC responses.

Run this to debug the timeout errors seen in the web interface.
"""

import asyncio
import logging
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from motion.fluidnc_protocol import FluidNCProtocol, FluidNCCommunicator
from motion.base import Position4D
import serial

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_protocol_direct():
    """Test FluidNC protocol directly with debugging"""
    logger.info("🔍 Enhanced FluidNC Protocol Debug Test")
    logger.info("=" * 60)
    
    try:
        # Connect to FluidNC
        logger.info("🔌 Connecting to FluidNC...")
        serial_conn = serial.Serial('/dev/ttyUSB0', 115200, timeout=2.0)
        logger.info(f"✅ Serial connected: {serial_conn.name}")
        
        # Create protocol handler
        protocol = FluidNCProtocol(serial_conn)
        await protocol.start()
        
        # Wait for startup
        await asyncio.sleep(1.0)
        
        logger.info("\n📋 Testing Basic Commands...")
        
        # Test simple commands that should work
        test_commands = [
            ("Status Query", "?"),  # Immediate command
            ("Get Settings", "$$"), # Line command  
            ("Units Command", "G21"), # Line command
            ("Relative Mode", "G91"), # Line command causing timeout
            ("Simple Move", "G1 X0 Y0 Z1 F100"), # Movement command
            ("Absolute Mode", "G90"), # Line command causing timeout
        ]
        
        results = []
        
        for test_name, command in test_commands:
            logger.info(f"\n🧪 Testing: {test_name} - '{command}'")
            
            try:
                start_time = time.time()
                
                if len(command) == 1:
                    # Immediate command
                    await protocol.send_immediate_command(command)
                    await asyncio.sleep(0.5)  # Wait for response
                    response = "immediate"
                else:
                    # Line command
                    response = await protocol.send_line_command(command, timeout=15.0)
                
                test_time = time.time() - start_time
                logger.info(f"✅ {test_name}: {response} ({test_time:.3f}s)")
                results.append((test_name, True, test_time, response))
                
            except Exception as e:
                test_time = time.time() - start_time
                logger.error(f"❌ {test_name}: {e} ({test_time:.3f}s)")
                results.append((test_name, False, test_time, str(e)))
            
            # Wait between commands
            await asyncio.sleep(1.0)
        
        # Get protocol statistics
        stats = protocol.get_stats()
        logger.info(f"\n📊 Protocol Statistics:")
        logger.info(f"   Messages processed: {stats['messages_processed']}")
        logger.info(f"   Commands sent: {stats['commands_sent']}")
        logger.info(f"   Pending commands: {stats['pending_commands']}")
        logger.info(f"   Runtime: {stats['runtime_seconds']:.1f}s")
        
        # Stop protocol
        await protocol.stop()
        serial_conn.close()
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("📋 Debug Test Results:")
        logger.info(f"{'='*60}")
        
        passed = 0
        for test_name, success, test_time, result in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            logger.info(f"  {status} {test_name} ({test_time:.3f}s): {result}")
            if success:
                passed += 1
        
        total = len(results)
        logger.info(f"\n🏁 Summary: {passed}/{total} tests passed")
        
        if passed < total:
            logger.error("\n🔍 DIAGNOSIS:")
            logger.error("  Command timeouts detected. Possible causes:")
            logger.error("  1. FluidNC not responding to specific G-code commands")
            logger.error("  2. FluidNC in wrong state (needs homing/unlock)")
            logger.error("  3. Message parsing not detecting 'ok' responses")
            logger.error("  4. Serial communication issues")
            logger.error("\n💡 SUGGESTIONS:")
            logger.error("  1. Check FluidNC status with '?' command")
            logger.error("  2. Try '$X' to unlock if in alarm state")
            logger.error("  3. Verify FluidNC firmware version compatibility")
        else:
            logger.info("\n🎉 All commands working - protocol is healthy!")
        
        return passed == total
        
    except Exception as e:
        logger.error(f"❌ Protocol debug test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_fluidnc_direct_serial():
    """Test direct serial communication without protocol layer"""
    logger.info("\n🔧 Testing Direct Serial Communication...")
    
    try:
        serial_conn = serial.Serial('/dev/ttyUSB0', 115200, timeout=5.0)
        
        # Send simple commands directly
        test_commands = ["?\n", "$$\n", "G21\n"]
        
        for command in test_commands:
            logger.info(f"📤 Sending: {repr(command)}")
            serial_conn.write(command.encode())
            serial_conn.flush()
            
            # Read response
            start_time = time.time()
            response_lines = []
            
            while time.time() - start_time < 3.0:
                if serial_conn.in_waiting > 0:
                    line = serial_conn.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        response_lines.append(line)
                        logger.info(f"📥 Response: {repr(line)}")
                        
                        # Stop on 'ok' or 'error'
                        if line in ['ok', 'OK'] or line.startswith('error'):
                            break
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ Command completed, {len(response_lines)} response lines")
            await asyncio.sleep(1.0)
        
        serial_conn.close()
        logger.info("✅ Direct serial test complete")
        return True
        
    except Exception as e:
        logger.error(f"❌ Direct serial test failed: {e}")
        return False


async def main():
    """Run protocol debugging"""
    logger.info("🚀 Starting Enhanced FluidNC Protocol Debug Session")
    
    # Test protocol layer
    protocol_ok = await test_protocol_direct()
    
    # Test direct serial if protocol fails
    if not protocol_ok:
        serial_ok = await test_fluidnc_direct_serial()
        
        if serial_ok:
            logger.error("📊 DIAGNOSIS: Protocol layer has issues, direct serial works")
        else:
            logger.error("📊 DIAGNOSIS: FluidNC or serial connection has issues")
    
    logger.info("🏁 Debug session complete")


if __name__ == "__main__":
    asyncio.run(main())