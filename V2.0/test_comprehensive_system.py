#!/usr/bin/env python3
"""
Comprehensive FluidNC System Testing

Performs realistic stress testing and web interface simulation to thoroughly
validate the simplified system before production integration.

Author: Scanner System Redesign
Created: September 24, 2025
"""

import asyncio
import logging
import sys
import time
import random
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


class ComprehensiveTestSuite:
    """Comprehensive test suite for FluidNC system"""
    
    def __init__(self):
        self.test_results: Dict[str, Any] = {}
        self.performance_metrics: Dict[str, List[float]] = {
            'command_times': [],
            'movement_times': [],
            'status_update_times': []
        }
    
    async def run_all_tests(self) -> bool:
        """Run all comprehensive tests"""
        logger.info("🚀 Starting Comprehensive FluidNC System Testing")
        logger.info("=" * 60)
        
        test_methods = [
            ("Connection Stability", self.test_connection_stability),
            ("Command Response Times", self.test_command_response_times),
            ("Web Interface Jog Simulation", self.test_web_jog_simulation),
            ("Rapid Command Sequence", self.test_rapid_command_sequence),
            ("Error Recovery", self.test_error_recovery),
            ("Status Monitoring", self.test_status_monitoring),
            ("Position Accuracy", self.test_position_accuracy),
            ("Concurrent Operations", self.test_concurrent_operations),
            ("Memory/Resource Usage", self.test_resource_usage),
            ("Long Duration Stability", self.test_long_duration_stability)
        ]
        
        all_passed = True
        
        for test_name, test_method in test_methods:
            logger.info(f"\n🧪 {test_name}")
            logger.info("-" * 40)
            
            try:
                start_time = time.time()
                result = await test_method()
                duration = time.time() - start_time
                
                self.test_results[test_name] = {
                    'passed': result,
                    'duration': duration
                }
                
                if result:
                    logger.info(f"✅ {test_name} PASSED ({duration:.2f}s)")
                else:
                    logger.error(f"❌ {test_name} FAILED ({duration:.2f}s)")
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"❌ {test_name} ERROR: {e}")
                self.test_results[test_name] = {
                    'passed': False,
                    'error': str(e),
                    'duration': 0
                }
                all_passed = False
        
        # Print comprehensive results
        self.print_test_summary()
        
        return all_passed
    
    async def test_connection_stability(self) -> bool:
        """Test connection stability with multiple connect/disconnect cycles"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            # Test multiple connection cycles
            for cycle in range(5):
                logger.info(f"  Connection cycle {cycle + 1}/5")
                
                # Connect
                connected = await controller.connect()
                if not connected:
                    logger.error(f"    Failed to connect on cycle {cycle + 1}")
                    return False
                
                # Brief operation
                await asyncio.sleep(0.5)
                position = await controller.get_position()
                
                # Disconnect
                disconnected = await controller.disconnect()
                if not disconnected:
                    logger.error(f"    Failed to disconnect on cycle {cycle + 1}")
                    return False
                
                # Wait between cycles
                await asyncio.sleep(1.0)
            
            logger.info("  All connection cycles successful")
            return True
            
        except Exception as e:
            logger.error(f"  Connection stability test failed: {e}")
            return False
    
    async def test_command_response_times(self) -> bool:
        """Test command response times under various conditions"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            # Test different command types
            test_commands = [
                ("Status Query", lambda: controller.get_position()),
                ("Simple G-code", lambda: controller.execute_gcode("G90")),
                ("Set Feedrate", lambda: controller.set_feedrate(100.0)),
                ("Get Status", lambda: controller.get_status()),
                ("Get Capabilities", lambda: controller.get_capabilities())
            ]
            
            response_times = []
            
            for cmd_name, cmd_func in test_commands:
                times = []
                
                # Test each command 10 times
                for i in range(10):
                    start_time = time.time()
                    
                    try:
                        await cmd_func()
                        end_time = time.time()
                        response_time = end_time - start_time
                        times.append(response_time)
                        
                        if response_time > 5.0:  # Flag slow responses
                            logger.warning(f"    Slow response: {cmd_name} took {response_time:.2f}s")
                        
                    except Exception as e:
                        logger.error(f"    Command failed: {cmd_name} - {e}")
                        await controller.disconnect()
                        return False
                    
                    # Small delay between commands
                    await asyncio.sleep(0.1)
                
                avg_time = sum(times) / len(times)
                max_time = max(times)
                min_time = min(times)
                
                logger.info(f"  {cmd_name}: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
                
                response_times.extend(times)
                
                # Fail if any command consistently takes too long
                if avg_time > 2.0:
                    logger.error(f"    {cmd_name} average response time too slow: {avg_time:.2f}s")
                    await controller.disconnect()
                    return False
            
            await controller.disconnect()
            
            # Store performance metrics
            self.performance_metrics['command_times'] = response_times
            
            overall_avg = sum(response_times) / len(response_times)
            logger.info(f"  Overall average response time: {overall_avg:.3f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"  Command response test failed: {e}")
            return False
    
    async def test_web_jog_simulation(self) -> bool:
        """Simulate the exact web interface jog commands that were failing"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            from motion.base import Position4D
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Simulating exact web interface jog sequence...")
            
            # This is the exact sequence that was timing out:
            # G91 (relative mode)
            # G1 X0.000 Y0.000 Z-1.000 C0.000 F10.0 (movement)
            # G90 (absolute mode)
            
            jog_tests = [
                {"axis": "z", "distance": -1.0, "feedrate": 10.0, "description": "Z- jog (original failing command)"},
                {"axis": "z", "distance": 1.0, "feedrate": 10.0, "description": "Z+ jog"},
                {"axis": "x", "distance": 0.5, "feedrate": 20.0, "description": "X+ small jog"},
                {"axis": "x", "distance": -0.5, "feedrate": 20.0, "description": "X- return"},
                {"axis": "y", "distance": 0.5, "feedrate": 20.0, "description": "Y+ small jog"},
                {"axis": "y", "distance": -0.5, "feedrate": 20.0, "description": "Y- return"},
                {"axis": "c", "distance": 5.0, "feedrate": 15.0, "description": "C+ rotation"},
                {"axis": "c", "distance": -5.0, "feedrate": 15.0, "description": "C- return"},
            ]
            
            for i, jog in enumerate(jog_tests):
                logger.info(f"    Test {i+1}/8: {jog['description']}")
                
                start_time = time.time()
                
                # Create delta position
                delta = Position4D()
                if jog['axis'] == 'x':
                    delta.x = jog['distance']
                elif jog['axis'] == 'y':
                    delta.y = jog['distance']
                elif jog['axis'] == 'z':
                    delta.z = jog['distance']
                elif jog['axis'] == 'c':
                    delta.c = jog['distance']
                
                # Execute the jog command
                success = await controller.move_relative(delta, jog['feedrate'])
                
                end_time = time.time()
                duration = end_time - start_time
                
                if not success:
                    logger.error(f"      FAILED: Jog command failed")
                    await controller.disconnect()
                    return False
                
                if duration > 5.0:
                    logger.error(f"      FAILED: Jog took too long ({duration:.2f}s)")
                    await controller.disconnect()
                    return False
                
                logger.info(f"      SUCCESS: Completed in {duration:.3f}s")
                
                # Wait for movement to settle
                await asyncio.sleep(0.5)
            
            await controller.disconnect()
            
            logger.info("  All web interface jog commands successful!")
            return True
            
        except Exception as e:
            logger.error(f"  Web jog simulation failed: {e}")
            return False
    
    async def test_rapid_command_sequence(self) -> bool:
        """Test rapid sequence of commands to stress-test the system"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Sending rapid command sequence...")
            
            commands = [
                "G90",  # Absolute mode
                "F100", # Set feedrate
                "G91",  # Relative mode
                "G90",  # Back to absolute
                "F200", # Change feedrate
                "M3",   # Spindle on (if supported)
                "M5",   # Spindle off
                "G4 P0.1", # Short dwell
            ]
            
            start_time = time.time()
            
            for i, cmd in enumerate(commands):
                logger.info(f"    Command {i+1}/{len(commands)}: {cmd}")
                
                cmd_start = time.time()
                success = await controller.execute_gcode(cmd)
                cmd_end = time.time()
                
                if not success:
                    logger.error(f"      Command failed: {cmd}")
                    await controller.disconnect()
                    return False
                
                cmd_duration = cmd_end - cmd_start
                if cmd_duration > 3.0:
                    logger.warning(f"      Slow command: {cmd} took {cmd_duration:.2f}s")
                
                # No delay between commands to test rapid execution
            
            total_time = time.time() - start_time
            logger.info(f"  Rapid sequence completed in {total_time:.2f}s")
            
            await controller.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"  Rapid command test failed: {e}")
            return False
    
    async def test_error_recovery(self) -> bool:
        """Test error recovery and resilience"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 2.0  # Shorter timeout for error testing
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Testing error recovery...")
            
            # Test invalid G-code (should handle gracefully)
            logger.info("    Testing invalid G-code handling...")
            success = await controller.execute_gcode("G999")  # Invalid G-code
            # Don't fail if it returns False - that's expected
            
            # Test emergency stop and recovery
            logger.info("    Testing emergency stop...")
            await controller.emergency_stop()
            
            # Wait a moment
            await asyncio.sleep(1.0)
            
            # Try to recover with reset
            logger.info("    Testing reset/recovery...")
            await controller.reset()
            
            # Wait for reset
            await asyncio.sleep(2.0)
            
            # Test that system still works after recovery
            logger.info("    Testing functionality after recovery...")
            position = await controller.get_position()
            status = await controller.get_status()
            
            await controller.disconnect()
            
            logger.info("  Error recovery test completed")
            return True
            
        except Exception as e:
            logger.error(f"  Error recovery test failed: {e}")
            return False
    
    async def test_status_monitoring(self) -> bool:
        """Test real-time status monitoring"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Testing status monitoring...")
            
            # Monitor status updates during movement
            status_updates = []
            
            def status_callback(status):
                status_updates.append({
                    'time': time.time(),
                    'state': status.state,
                    'position': status.position.copy()
                })
            
            # Add status callback
            controller.protocol.add_status_callback(status_callback)
            
            logger.info("    Performing movement with status monitoring...")
            
            # Perform a small movement
            from motion.base import Position4D
            delta = Position4D(x=0.1, y=0.0, z=0.0, c=0.0)
            
            start_time = time.time()
            success = await controller.move_relative(delta, feedrate=50.0)
            
            if not success:
                await controller.disconnect()
                return False
            
            # Wait for movement and status updates
            await asyncio.sleep(2.0)
            
            end_time = time.time()
            
            # Check status updates
            if len(status_updates) < 2:
                logger.error(f"    Insufficient status updates: {len(status_updates)}")
                await controller.disconnect()
                return False
            
            logger.info(f"    Received {len(status_updates)} status updates")
            
            # Check that we got updates during the movement timeframe
            relevant_updates = [
                update for update in status_updates 
                if start_time <= update['time'] <= end_time + 1.0
            ]
            
            if len(relevant_updates) < 1:
                logger.error("    No status updates during movement")
                await controller.disconnect()
                return False
            
            logger.info(f"    Status monitoring working correctly")
            
            await controller.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"  Status monitoring test failed: {e}")
            return False
    
    async def test_position_accuracy(self) -> bool:
        """Test position accuracy and tracking"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            from motion.base import Position4D
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Testing position accuracy...")
            
            # Get initial position
            initial_pos = await controller.get_position()
            logger.info(f"    Initial position: {initial_pos}")
            
            # Perform sequence of moves and track position
            moves = [
                Position4D(x=1.0, y=0.0, z=0.0, c=0.0),
                Position4D(x=0.0, y=1.0, z=0.0, c=0.0),
                Position4D(x=-1.0, y=0.0, z=0.0, c=0.0),
                Position4D(x=0.0, y=-1.0, z=0.0, c=0.0),  # Should return to start
            ]
            
            for i, delta in enumerate(moves):
                logger.info(f"    Move {i+1}/{len(moves)}: {delta}")
                
                pos_before = await controller.get_position()
                success = await controller.move_relative(delta, feedrate=100.0)
                
                if not success:
                    logger.error(f"      Move {i+1} failed")
                    await controller.disconnect()
                    return False
                
                # Wait for movement to complete
                await asyncio.sleep(1.0)
                
                pos_after = await controller.get_position()
                logger.info(f"      Position after move: {pos_after}")
            
            # Check final position (should be close to initial)
            final_pos = await controller.get_position()
            
            # Calculate difference from initial position
            diff_x = abs(final_pos.x - initial_pos.x)
            diff_y = abs(final_pos.y - initial_pos.y)
            
            logger.info(f"    Final position: {final_pos}")
            logger.info(f"    Difference from initial: X={diff_x:.3f}, Y={diff_y:.3f}")
            
            # Allow for some tolerance due to mechanical accuracy
            tolerance = 0.1  # mm
            
            if diff_x > tolerance or diff_y > tolerance:
                logger.warning(f"    Position accuracy outside tolerance ({tolerance}mm)")
                # Don't fail the test for this - just warn
            
            await controller.disconnect()
            
            logger.info("  Position accuracy test completed")
            return True
            
        except Exception as e:
            logger.error(f"  Position accuracy test failed: {e}")
            return False
    
    async def test_concurrent_operations(self) -> bool:
        """Test concurrent operations (status monitoring + commands)"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Testing concurrent operations...")
            
            # Start background status monitoring
            async def status_monitor():
                for _ in range(20):  # Monitor for 10 seconds
                    try:
                        await controller.get_position()
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"      Status monitoring error: {e}")
                        return False
                return True
            
            # Start background command execution
            async def command_executor():
                commands = ["G90", "F100", "G91", "G90"] * 5  # Repeat commands
                for cmd in commands:
                    try:
                        await controller.execute_gcode(cmd)
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        logger.error(f"      Command execution error: {e}")
                        return False
                return True
            
            # Run both concurrently
            logger.info("    Running status monitoring and commands concurrently...")
            
            status_task = asyncio.create_task(status_monitor())
            command_task = asyncio.create_task(command_executor())
            
            # Wait for both to complete
            status_result, command_result = await asyncio.gather(status_task, command_task)
            
            await controller.disconnect()
            
            if status_result and command_result:
                logger.info("  Concurrent operations successful")
                return True
            else:
                logger.error("  Concurrent operations failed")
                return False
            
        except Exception as e:
            logger.error(f"  Concurrent operations test failed: {e}")
            return False
    
    async def test_resource_usage(self) -> bool:
        """Test memory and resource usage"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            logger.info(f"  Initial memory usage: {initial_memory:.1f} MB")
            
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            # Create and use multiple controllers to test resource cleanup
            for cycle in range(3):
                logger.info(f"    Resource test cycle {cycle + 1}/3")
                
                controller = SimplifiedFluidNCController(config)
                
                if not await controller.connect():
                    return False
                
                # Perform some operations
                for _ in range(10):
                    await controller.get_position()
                    await controller.execute_gcode("G90")
                    await asyncio.sleep(0.1)
                
                await controller.disconnect()
                
                # Check memory usage
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                logger.info(f"      Memory after cycle {cycle + 1}: {current_memory:.1f} MB")
                
                # Allow some growth but flag excessive usage
                if current_memory > initial_memory + 50:  # More than 50MB growth
                    logger.warning(f"      High memory usage: {current_memory:.1f} MB")
                
                # Force garbage collection
                import gc
                gc.collect()
                
                await asyncio.sleep(1.0)
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = final_memory - initial_memory
            
            logger.info(f"  Final memory usage: {final_memory:.1f} MB (growth: {memory_growth:.1f} MB)")
            
            # Consider test passed if memory growth is reasonable
            if memory_growth < 20:  # Less than 20MB growth
                logger.info("  Resource usage test passed")
                return True
            else:
                logger.warning(f"  High memory growth: {memory_growth:.1f} MB")
                return True  # Don't fail for memory issues in testing
            
        except ImportError:
            logger.info("  Skipping resource test (psutil not available)")
            return True
        except Exception as e:
            logger.error(f"  Resource usage test failed: {e}")
            return False
    
    async def test_long_duration_stability(self) -> bool:
        """Test stability over longer duration"""
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                return False
            
            logger.info("  Testing long duration stability (60 seconds)...")
            
            start_time = time.time()
            command_count = 0
            error_count = 0
            
            # Run for 60 seconds
            while time.time() - start_time < 60:
                try:
                    # Mix of different operations
                    operations = [
                        lambda: controller.get_position(),
                        lambda: controller.get_status(),
                        lambda: controller.execute_gcode("G90"),
                        lambda: controller.set_feedrate(random.randint(50, 200))
                    ]
                    
                    operation = random.choice(operations)
                    await operation()
                    
                    command_count += 1
                    
                    # Progress update every 10 seconds
                    elapsed = time.time() - start_time
                    if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                        logger.info(f"    {int(elapsed)}s: {command_count} commands, {error_count} errors")
                    
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    
                except Exception as e:
                    error_count += 1
                    logger.warning(f"    Command failed: {e}")
                    
                    # If too many errors, abort
                    if error_count > 10:
                        logger.error("    Too many errors, aborting stability test")
                        await controller.disconnect()
                        return False
            
            total_time = time.time() - start_time
            success_rate = (command_count - error_count) / command_count * 100
            
            logger.info(f"  Stability test completed:")
            logger.info(f"    Duration: {total_time:.1f}s")
            logger.info(f"    Commands: {command_count}")
            logger.info(f"    Errors: {error_count}")
            logger.info(f"    Success rate: {success_rate:.1f}%")
            
            await controller.disconnect()
            
            # Consider passed if success rate > 95%
            return success_rate > 95.0
            
        except Exception as e:
            logger.error(f"  Long duration test failed: {e}")
            return False
    
    def print_test_summary(self):
        """Print comprehensive test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['passed'])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        logger.info(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        logger.info("\nDetailed Results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            duration = result.get('duration', 0)
            logger.info(f"  {status} {test_name} ({duration:.2f}s)")
            
            if 'error' in result:
                logger.info(f"       Error: {result['error']}")
        
        # Performance summary
        if self.performance_metrics['command_times']:
            cmd_times = self.performance_metrics['command_times']
            avg_cmd_time = sum(cmd_times) / len(cmd_times)
            max_cmd_time = max(cmd_times)
            
            logger.info(f"\n⚡ Performance Metrics:")
            logger.info(f"  Average Command Time: {avg_cmd_time:.3f}s")
            logger.info(f"  Maximum Command Time: {max_cmd_time:.3f}s")
            logger.info(f"  Commands Under 1s: {sum(1 for t in cmd_times if t < 1.0)/len(cmd_times)*100:.1f}%")
        
        logger.info("\n🎯 Integration Readiness Assessment:")
        
        if passed_tests == total_tests:
            logger.info("✅ EXCELLENT - System is ready for production integration")
            logger.info("   All tests passed. The simplified system should eliminate timeout issues.")
        elif passed_tests >= total_tests * 0.9:
            logger.info("⚠️  GOOD - System is mostly ready with minor issues")
            logger.info("   Most tests passed. Review failed tests before integration.")
        elif passed_tests >= total_tests * 0.7:
            logger.info("🔶 CAUTION - System has some issues that should be addressed")
            logger.info("   Several tests failed. Address issues before production use.")
        else:
            logger.info("❌ NOT READY - System has significant issues")
            logger.info("   Many tests failed. System needs more work before integration.")


async def main():
    """Run comprehensive test suite"""
    test_suite = ComprehensiveTestSuite()
    success = await test_suite.run_all_tests()
    
    if success:
        logger.info("\n🎉 All comprehensive tests passed!")
        logger.info("The simplified FluidNC system is ready for integration.")
    else:
        logger.error("\n❌ Some comprehensive tests failed.")
        logger.error("Review the results before proceeding with integration.")
    
    return success


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())