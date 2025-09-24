#!/usr/bin/env python3
"""
Web Interface Jog Command Testing

This test specifically reproduces the exact jog commands that were failing
in the web interface with timeout errors. This will prove whether the
simplified system has actually solved the core problem.

Author: Scanner System Redesign  
Created: September 24, 2025
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


class WebJogTestSuite:
    """Test suite specifically for web interface jog commands"""
    
    def __init__(self):
        self.test_results = []
        self.total_test_time = 0
    
    async def test_original_failing_commands(self) -> bool:
        """Test the exact commands that were failing with timeouts"""
        logger.info("🧪 Testing Original Failing Web Interface Commands")
        logger.info("=" * 50)
        
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
                logger.error("❌ Failed to connect to FluidNC")
                return False
            
            logger.info("✅ Connected to FluidNC")
            
            # These are the EXACT commands that were timing out in the web interface:
            # From your error logs:
            # "Command timeout: G91"
            # "Command timeout: G1 X0.000 Y0.000 Z-1.000 C0.000 F10.0" 
            # "Command timeout: G90"
            
            failing_commands = [
                {
                    'description': 'Z-axis negative jog (original failing command)',
                    'axis': 'z',
                    'distance': -1.0,
                    'feedrate': 10.0,
                    'expected_time': 1.0  # Should complete in under 1 second
                },
                {
                    'description': 'Z-axis positive jog (return)',
                    'axis': 'z', 
                    'distance': 1.0,
                    'feedrate': 10.0,
                    'expected_time': 1.0
                },
                {
                    'description': 'X-axis small jog',
                    'axis': 'x',
                    'distance': 0.1,
                    'feedrate': 10.0, 
                    'expected_time': 1.0
                },
                {
                    'description': 'X-axis return',
                    'axis': 'x',
                    'distance': -0.1,
                    'feedrate': 10.0,
                    'expected_time': 1.0
                },
                {
                    'description': 'Y-axis small jog',
                    'axis': 'y',
                    'distance': 0.1,
                    'feedrate': 10.0,
                    'expected_time': 1.0
                },
                {
                    'description': 'Y-axis return',
                    'axis': 'y',
                    'distance': -0.1,
                    'feedrate': 10.0,
                    'expected_time': 1.0
                },
                {
                    'description': 'C-axis rotation',
                    'axis': 'c',
                    'distance': 2.0,
                    'feedrate': 10.0,
                    'expected_time': 1.0
                },
                {
                    'description': 'C-axis return',
                    'axis': 'c',
                    'distance': -2.0,
                    'feedrate': 10.0,
                    'expected_time': 1.0
                }
            ]
            
            all_passed = True
            
            logger.info(f"Running {len(failing_commands)} jog command tests...")
            logger.info("")
            
            for i, test in enumerate(failing_commands):
                logger.info(f"Test {i+1}/{len(failing_commands)}: {test['description']}")
                
                # Create delta position for the jog
                delta = Position4D()
                if test['axis'] == 'x':
                    delta.x = test['distance']
                elif test['axis'] == 'y':
                    delta.y = test['distance']
                elif test['axis'] == 'z':
                    delta.z = test['distance']
                elif test['axis'] == 'c':
                    delta.c = test['distance']
                
                # Record start time
                start_time = time.time()
                
                # Execute the move that was failing
                try:
                    success = await controller.move_relative(delta, test['feedrate'])
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    if not success:
                        logger.error(f"  ❌ FAILED: Command returned False")
                        self.test_results.append({
                            'test': test['description'],
                            'success': False,
                            'duration': duration,
                            'error': 'Command returned False'
                        })
                        all_passed = False
                        continue
                    
                    if duration > 5.0:  # Original problem was >5 second timeouts
                        logger.error(f"  ❌ TIMEOUT: Took {duration:.2f}s (expected <{test['expected_time']}s)")
                        self.test_results.append({
                            'test': test['description'],
                            'success': False,
                            'duration': duration,
                            'error': f'Timeout: {duration:.2f}s'
                        })
                        all_passed = False
                        continue
                    
                    logger.info(f"  ✅ SUCCESS: Completed in {duration:.3f}s")
                    self.test_results.append({
                        'test': test['description'],
                        'success': True,
                        'duration': duration,
                        'error': None
                    })
                    
                    # Add delay between tests to let system settle
                    await asyncio.sleep(0.5)
                    
                except asyncio.TimeoutError:
                    end_time = time.time()
                    duration = end_time - start_time
                    logger.error(f"  ❌ TIMEOUT: AsyncIO timeout after {duration:.2f}s")
                    self.test_results.append({
                        'test': test['description'],
                        'success': False,
                        'duration': duration,
                        'error': 'AsyncIO timeout'
                    })
                    all_passed = False
                    
                except Exception as e:
                    end_time = time.time()
                    duration = end_time - start_time
                    logger.error(f"  ❌ ERROR: {str(e)} (after {duration:.2f}s)")
                    self.test_results.append({
                        'test': test['description'],
                        'success': False,
                        'duration': duration,
                        'error': str(e)
                    })
                    all_passed = False
            
            await controller.disconnect()
            
            # Print detailed results
            self.print_jog_test_results()
            
            return all_passed
            
        except Exception as e:
            logger.error(f"❌ Test setup failed: {e}")
            return False
    
    async def test_rapid_jog_sequence(self) -> bool:
        """Test rapid sequence of jog commands like a user clicking quickly"""
        logger.info("\n🧪 Testing Rapid Jog Sequence (User Clicking Quickly)")
        logger.info("-" * 50)
        
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
                logger.error("❌ Failed to connect to FluidNC")
                return False
            
            # Simulate user rapidly clicking jog buttons
            rapid_jogs = [
                ('z', -0.1), ('z', -0.1), ('z', -0.1),  # Z down 3 clicks
                ('x', 0.1), ('x', 0.1),                  # X right 2 clicks  
                ('y', 0.1), ('y', 0.1),                  # Y up 2 clicks
                ('c', 1.0), ('c', 1.0),                  # C rotate 2 clicks
                ('z', 0.1), ('z', 0.1), ('z', 0.1),    # Z up 3 clicks (return)
                ('x', -0.1), ('x', -0.1),               # X left 2 clicks (return)
                ('y', -0.1), ('y', -0.1),               # Y down 2 clicks (return)
                ('c', -1.0), ('c', -1.0),               # C return 2 clicks
            ]
            
            logger.info(f"Executing {len(rapid_jogs)} rapid jog commands...")
            
            total_start = time.time()
            rapid_success = True
            
            for i, (axis, distance) in enumerate(rapid_jogs):
                delta = Position4D()
                if axis == 'x':
                    delta.x = distance
                elif axis == 'y':
                    delta.y = distance
                elif axis == 'z':
                    delta.z = distance
                elif axis == 'c':
                    delta.c = distance
                
                start = time.time()
                success = await controller.move_relative(delta, feedrate=20.0)
                end = time.time()
                
                if not success or (end - start) > 3.0:
                    logger.error(f"  Command {i+1} failed: {axis}{distance:+.1f} ({end-start:.2f}s)")
                    rapid_success = False
                else:
                    logger.info(f"  Command {i+1}: {axis}{distance:+.1f} ✅ ({end-start:.3f}s)")
                
                # Minimal delay between commands (simulate quick clicking)
                await asyncio.sleep(0.1)
            
            total_time = time.time() - total_start
            
            if rapid_success:
                logger.info(f"✅ Rapid jog sequence completed successfully in {total_time:.2f}s")
            else:
                logger.error(f"❌ Rapid jog sequence had failures (total time: {total_time:.2f}s)")
            
            await controller.disconnect()
            return rapid_success
            
        except Exception as e:
            logger.error(f"❌ Rapid jog test failed: {e}")
            return False
    
    async def test_stress_jog_commands(self) -> bool:
        """Stress test with many jog commands"""
        logger.info("\n🧪 Stress Testing Jog Commands (50 commands)")
        logger.info("-" * 50)
        
        try:
            from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
            from motion.base import Position4D
            import random
            
            config = {
                'port': '/dev/ttyUSB0',
                'baud_rate': 115200,
                'command_timeout': 10.0
            }
            
            controller = SimplifiedFluidNCController(config)
            
            if not await controller.connect():
                logger.error("❌ Failed to connect to FluidNC")
                return False
            
            # Generate 50 random small jog commands
            axes = ['x', 'y', 'z', 'c']
            distances = {
                'x': [-0.1, -0.05, 0.05, 0.1],
                'y': [-0.1, -0.05, 0.05, 0.1], 
                'z': [-0.5, -0.2, 0.2, 0.5],
                'c': [-1.0, -0.5, 0.5, 1.0]
            }
            
            stress_commands = []
            for _ in range(50):
                axis = random.choice(axes)
                distance = random.choice(distances[axis])
                feedrate = random.choice([10.0, 20.0, 30.0])
                stress_commands.append((axis, distance, feedrate))
            
            logger.info("Executing 50 stress test jog commands...")
            
            start_time = time.time()
            success_count = 0
            timeout_count = 0
            error_count = 0
            
            for i, (axis, distance, feedrate) in enumerate(stress_commands):
                delta = Position4D()
                if axis == 'x':
                    delta.x = distance
                elif axis == 'y':  
                    delta.y = distance
                elif axis == 'z':
                    delta.z = distance
                elif axis == 'c':
                    delta.c = distance
                
                cmd_start = time.time()
                try:
                    success = await controller.move_relative(delta, feedrate)
                    cmd_end = time.time()
                    cmd_duration = cmd_end - cmd_start
                    
                    if success and cmd_duration < 5.0:
                        success_count += 1
                        if (i + 1) % 10 == 0:  # Progress every 10 commands
                            logger.info(f"  Progress: {i+1}/50 commands completed")
                    elif cmd_duration >= 5.0:
                        timeout_count += 1
                        logger.warning(f"  Command {i+1} timeout: {cmd_duration:.2f}s")
                    else:
                        error_count += 1
                        logger.warning(f"  Command {i+1} failed")
                        
                except Exception as e:
                    error_count += 1
                    logger.warning(f"  Command {i+1} error: {e}")
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.05)
            
            total_time = time.time() - start_time
            
            logger.info(f"\nStress Test Results:")
            logger.info(f"  Total Commands: 50")
            logger.info(f"  ✅ Successful: {success_count}")
            logger.info(f"  ⏰ Timeouts: {timeout_count}")
            logger.info(f"  ❌ Errors: {error_count}")
            logger.info(f"  Total Time: {total_time:.2f}s")
            logger.info(f"  Average Time/Command: {total_time/50:.3f}s")
            logger.info(f"  Success Rate: {success_count/50*100:.1f}%")
            
            await controller.disconnect()
            
            # Consider success if >90% success rate and no timeouts
            success_rate = success_count / 50
            stress_passed = success_rate > 0.9 and timeout_count == 0
            
            if stress_passed:
                logger.info("✅ Stress test PASSED")
            else:
                logger.error("❌ Stress test FAILED")
            
            return stress_passed
            
        except Exception as e:
            logger.error(f"❌ Stress test failed: {e}")
            return False
    
    def print_jog_test_results(self):
        """Print detailed jog test results"""
        logger.info("\n" + "=" * 50)
        logger.info("📊 WEB INTERFACE JOG TEST RESULTS")
        logger.info("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"Total Jog Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        
        if total_tests > 0:
            success_rate = passed_tests / total_tests * 100
            logger.info(f"Success Rate: {success_rate:.1f}%")
            
            # Calculate timing statistics
            successful_times = [r['duration'] for r in self.test_results if r['success']]
            if successful_times:
                avg_time = sum(successful_times) / len(successful_times)
                max_time = max(successful_times)
                min_time = min(successful_times)
                
                logger.info(f"\n⚡ Timing Statistics (Successful Commands):")
                logger.info(f"  Average Time: {avg_time:.3f}s")
                logger.info(f"  Fastest Time: {min_time:.3f}s")
                logger.info(f"  Slowest Time: {max_time:.3f}s")
                
                under_1s = sum(1 for t in successful_times if t < 1.0)
                logger.info(f"  Commands under 1s: {under_1s}/{len(successful_times)} ({under_1s/len(successful_times)*100:.1f}%)")
        
        logger.info("\nDetailed Results:")
        for i, result in enumerate(self.test_results):
            status = "✅" if result['success'] else "❌"
            logger.info(f"  {status} Test {i+1}: {result['test']}")
            logger.info(f"       Duration: {result['duration']:.3f}s")
            if result['error']:
                logger.info(f"       Error: {result['error']}")
        
        logger.info("\n🎯 Web Interface Integration Assessment:")
        
        if failed_tests == 0:
            logger.info("✅ EXCELLENT - All jog commands work perfectly!")
            logger.info("   The timeout issues have been completely resolved.")
            logger.info("   Web interface should work flawlessly with this system.")
        elif failed_tests <= 2:
            logger.info("⚠️  GOOD - Most jog commands work with minor issues")
            logger.info("   Web interface should work much better than before.")
        else:
            logger.info("❌ ISSUES REMAIN - Multiple jog commands still failing")
            logger.info("   Additional work needed before web interface integration.")


async def main():
    """Run web interface focused tests"""
    logger.info("🎯 Web Interface Jog Command Testing")
    logger.info("This test reproduces the exact commands that were timing out in your web interface")
    logger.info("")
    
    test_suite = WebJogTestSuite()
    
    # Test the original failing commands
    original_test = await test_suite.test_original_failing_commands()
    
    # Test rapid jog sequence  
    rapid_test = await test_suite.test_rapid_jog_sequence()
    
    # Stress test
    stress_test = await test_suite.test_stress_jog_commands()
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 FINAL ASSESSMENT")
    logger.info("=" * 60)
    
    if original_test and rapid_test and stress_test:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("")
        logger.info("The simplified FluidNC system has successfully resolved the")
        logger.info("timeout issues that were affecting your web interface.")
        logger.info("")
        logger.info("✅ Original failing jog commands now work")
        logger.info("✅ Rapid jog sequences work reliably")  
        logger.info("✅ System handles stress testing well")
        logger.info("")
        logger.info("🚀 READY FOR INTEGRATION")
        logger.info("You can now safely integrate this into your main system.")
        
    elif original_test:
        logger.info("⚠️  PARTIAL SUCCESS")
        logger.info("")
        logger.info("The core jog commands now work, but some stress tests failed.")
        logger.info("This is still a major improvement over the timeout issues.")
        logger.info("")
        logger.info("🔶 READY FOR CAREFUL INTEGRATION")
        logger.info("Integrate with monitoring for any remaining edge cases.")
        
    else:
        logger.info("❌ TESTS FAILED")
        logger.info("")
        logger.info("The jog commands are still not working reliably.")
        logger.info("Additional debugging and fixes are needed.")
        logger.info("")
        logger.info("🔧 NOT READY FOR INTEGRATION")
        logger.info("Please review the test results and error messages.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())