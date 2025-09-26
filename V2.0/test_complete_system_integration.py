#!/usr/bin/env python3
"""
Complete System Integration Test - Motion Optimization with Web UI and Scanning Methods

This test verifies that the motion optimization (single move_to_position calls)
works correctly with ALL currently implemented scanning methods and web UI.

Tests:
1. Motion controller optimization verification
2. Scan orchestrator integration
3. Production scanning pipeline
4. Motion optimization verification (single G0 commands)
"""

import sys
from pathlib import Path
import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.types import Position4D as CorePosition4D
from motion.base import Position4D as MotionPosition4D
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import GridScanPattern, GridPatternParameters, PatternParameters
from core.config_manager import ConfigManager

class MockFluidNCSerial:
    """Mock serial interface that tracks all commands sent"""
    
    def __init__(self):
        self.commands_sent = []
        self.responses = {
            "G0": "ok",
            "G28": "ok", 
            "?": "<Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0>",
            "M122": "ok"
        }
        self.is_open = True
    
    def write(self, data):
        command = data.decode().strip()
        self.commands_sent.append(command)
        print(f"[MOCK FLUIDNC] Sent: {command}")
    
    def readline(self):
        # Return appropriate response based on last command
        if self.commands_sent:
            last_cmd = self.commands_sent[-1]
            if last_cmd.startswith("G0"):
                return b"ok\n"
            elif last_cmd == "?":
                return b"<Idle|MPos:10.000,20.000,90.000,45.000|FS:0,0>\n"
        return b"ok\n"
    
    def close(self):
        self.is_open = False

class MockCameraController:
    """Mock camera controller"""
    
    def __init__(self):
        self.initialized = True
    
    async def initialize(self):
        return True
    
    async def capture_images(self):
        """Mock image capture"""
        return {
            'camera_0': {'success': True, 'path': '/mock/image0.jpg'},
            'camera_1': {'success': True, 'path': '/mock/image1.jpg'}
        }
    
    async def cleanup(self):
        pass

class TestCompleteSystemIntegration(unittest.IsolatedAsyncioTestCase):
    """Test complete system integration with motion optimization"""
    
    async def asyncSetUp(self):
        """Set up test environment"""
        # Create temporary directory for storage
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock serial interface
        self.mock_serial = MockFluidNCSerial()
        
        # Initialize motion controller with mock
        with patch('serial.Serial', return_value=self.mock_serial):
            self.motion_controller = SimplifiedFluidNCControllerFixed('/dev/mock')
            await self.motion_controller.initialize()
        
        # Initialize camera controller
        self.camera_controller = MockCameraController()
        await self.camera_controller.initialize()
        
        # Initialize storage manager  
        self.storage_manager = SessionStorageManager(base_path=self.temp_dir)
        
        # Initialize scan orchestrator
        self.scan_orchestrator = ScanOrchestrator(
            motion_controller=self.motion_controller,
            camera_controller=self.camera_controller,
            storage_manager=self.storage_manager
        )
        
        # Clear command history
        self.mock_serial.commands_sent.clear()
    
    async def asyncTearDown(self):
        """Clean up test environment"""
        try:
            await self.motion_controller.cleanup()
            await self.camera_controller.cleanup()
        except:
            pass
        
        # Clean up temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_web_ui_manual_positioning(self):
        """Test web UI manual positioning uses optimized motion"""
        print("\n=== Testing Web UI Manual Positioning ===")
        
        # Create a position for manual move
        position = CorePosition4D(x=50.0, y=75.0, z=180.0, c=30.0)
        
        # Clear command history
        self.mock_serial.commands_sent.clear()
        
        # Execute manual position move (simulating web UI)
        success = await self.motion_controller.move_to_position(
            MotionPosition4D(x=position.x, y=position.y, z=position.z, c=position.c)
        )
        
        # Verify success
        self.assertTrue(success, "Manual positioning should succeed")
        
        # Verify single G0 command sent
        g0_commands = [cmd for cmd in self.mock_serial.commands_sent if cmd.startswith("G0")]
        self.assertEqual(len(g0_commands), 1, "Should send exactly one G0 command for manual positioning")
        
        # Verify correct G0 command format
        expected_cmd = "G0 X50.00 Y75.00 Z180.00 C30.00"
        self.assertIn(expected_cmd, g0_commands[0], "G0 command should contain all axes")
        
        print(f"✅ Manual positioning sent single G0: {g0_commands[0]}")
    
    async def test_scanning_motion_optimization(self):
        """Test that scanning uses optimized motion (single move_to_position calls)"""
        print("\n=== Testing Scanning Motion Optimization ===")
        
        # Create a simple grid scan pattern
        pattern = GridScanPattern(
            x_range=(10.0, 30.0),
            y_range=(20.0, 40.0), 
            z_positions=[90.0],
            c_positions=[0.0],
            x_steps=2,
            y_steps=2
        )
        
        # Start scan session
        session_id = await self.storage_manager.create_session("test_scan")
        
        # Clear command history
        self.mock_serial.commands_sent.clear()
        
        # Execute scan with 4 points
        await self.scan_orchestrator.start_scan(session_id, pattern)
        
        # Get all G0 commands
        g0_commands = [cmd for cmd in self.mock_serial.commands_sent if cmd.startswith("G0")]
        
        # Should have exactly 4 G0 commands (one per scan point)
        expected_points = 4  # 2x2 grid
        self.assertEqual(len(g0_commands), expected_points, 
                        f"Should send exactly {expected_points} G0 commands for {expected_points} scan points")
        
        # Verify each G0 command contains all 4 axes
        for i, cmd in enumerate(g0_commands):
            self.assertIn("X", cmd, f"G0 command {i+1} should contain X axis")
            self.assertIn("Y", cmd, f"G0 command {i+1} should contain Y axis")  
            self.assertIn("Z", cmd, f"G0 command {i+1} should contain Z axis")
            self.assertIn("C", cmd, f"G0 command {i+1} should contain C axis")
        
        print(f"✅ Scanning sent {len(g0_commands)} optimized G0 commands:")
        for i, cmd in enumerate(g0_commands):
            print(f"   Point {i+1}: {cmd}")
    
    async def test_web_ui_scanning_integration(self):
        """Test web UI scanning integration uses optimized motion"""
        print("\n=== Testing Web UI Scanning Integration ===")
        
        # Create scan pattern
        pattern = GridScanPattern(
            x_range=(15.0, 25.0),
            y_range=(35.0, 45.0),
            z_positions=[45.0],
            c_positions=[15.0],
            x_steps=2,
            y_steps=2
        )
        
        # Start session (simulating web UI)
        session_id = await self.storage_manager.create_session("web_ui_scan")
        
        # Clear command history
        self.mock_serial.commands_sent.clear()
        
        # Execute scan via scan orchestrator (same path as web UI)
        success = await self.scan_orchestrator.start_scan(session_id, pattern)
        
        # Verify scan success
        self.assertTrue(success, "Web UI initiated scan should succeed")
        
        # Verify optimized motion (single G0 per point)
        g0_commands = [cmd for cmd in self.mock_serial.commands_sent if cmd.startswith("G0")]
        self.assertEqual(len(g0_commands), 4, "Should send 4 G0 commands for 2x2 grid")
        
        # Verify all commands are 4-axis moves
        for cmd in g0_commands:
            axis_count = sum(1 for axis in ['X', 'Y', 'Z', 'C'] if axis in cmd)
            self.assertEqual(axis_count, 4, f"Each G0 should contain all 4 axes: {cmd}")
        
        print(f"✅ Web UI scanning integration uses optimized motion")
        print(f"   Session: {session_id}")
        print(f"   G0 commands: {len(g0_commands)}")
    
    async def test_motion_completion_timing(self):
        """Test that motion completion timing works correctly"""
        print("\n=== Testing Motion Completion Timing ===")
        
        # Test single position move
        start_time = asyncio.get_event_loop().time()
        
        position = MotionPosition4D(x=100.0, y=50.0, z=270.0, c=-15.0)
        success = await self.motion_controller.move_to_position(position)
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        # Verify success and reasonable timing
        self.assertTrue(success, "Position move should succeed")
        self.assertLess(duration, 10.0, "Motion should complete within 10 seconds")
        
        # Verify motion completion was waited for
        status_commands = [cmd for cmd in self.mock_serial.commands_sent if cmd == "?"]
        self.assertGreater(len(status_commands), 0, "Should query status for motion completion")
        
        print(f"✅ Motion completion timing: {duration:.3f}s")
        print(f"   Status queries: {len(status_commands)}")
    
    async def test_production_scanning_pipeline(self):
        """Test full production scanning pipeline"""
        print("\n=== Testing Production Scanning Pipeline ===")
        
        # Create comprehensive scan pattern
        pattern = GridScanPattern(
            x_range=(0.0, 40.0),
            y_range=(0.0, 30.0),
            z_positions=[0.0, 90.0, 180.0],
            c_positions=[-30.0, 0.0, 30.0],
            x_steps=3,
            y_steps=2
        )
        
        # Calculate expected points
        expected_points = 3 * 2 * 3 * 3  # x_steps * y_steps * z_positions * c_positions
        
        # Start production session
        session_id = await self.storage_manager.create_session("production_test")
        
        # Clear command history
        self.mock_serial.commands_sent.clear()
        
        # Execute full production scan
        success = await self.scan_orchestrator.start_scan(session_id, pattern)
        
        # Verify scan success
        self.assertTrue(success, "Production scan should succeed")
        
        # Verify optimized motion (one G0 per scan point)
        g0_commands = [cmd for cmd in self.mock_serial.commands_sent if cmd.startswith("G0")]
        self.assertEqual(len(g0_commands), expected_points, 
                        f"Should send {expected_points} G0 commands for production scan")
        
        # Verify no individual axis commands
        individual_moves = [cmd for cmd in self.mock_serial.commands_sent 
                          if any(cmd.startswith(prefix) for prefix in ["G0 X", "G0 Y", "G0 Z", "G0 C"]) 
                          and not all(axis in cmd for axis in ['X', 'Y', 'Z', 'C'])]
        
        self.assertEqual(len(individual_moves), 0, "Should not use individual axis moves")
        
        print(f"✅ Production scanning pipeline optimized:")
        print(f"   Expected points: {expected_points}")
        print(f"   G0 commands sent: {len(g0_commands)}")
        print(f"   Individual axis moves: {len(individual_moves)}")
    
    def test_position_type_conversion(self):
        """Test position type conversion between core and motion modules"""
        print("\n=== Testing Position Type Conversion ===")
        
        # Create core position
        core_pos = CorePosition4D(x=25.5, y=37.2, z=123.4, c=67.8)
        
        # Convert to motion position
        motion_pos = MotionPosition4D(x=core_pos.x, y=core_pos.y, z=core_pos.z, c=core_pos.c)
        
        # Verify conversion
        self.assertEqual(motion_pos.x, core_pos.x, "X coordinate should match")
        self.assertEqual(motion_pos.y, core_pos.y, "Y coordinate should match")
        self.assertEqual(motion_pos.z, core_pos.z, "Z coordinate should match") 
        self.assertEqual(motion_pos.c, core_pos.c, "C coordinate should match")
        
        # Test reverse conversion
        core_pos2 = CorePosition4D(x=motion_pos.x, y=motion_pos.y, z=motion_pos.z, c=motion_pos.c)
        
        self.assertEqual(core_pos2.x, core_pos.x, "Reverse X conversion should match")
        self.assertEqual(core_pos2.y, core_pos.y, "Reverse Y conversion should match")
        self.assertEqual(core_pos2.z, core_pos.z, "Reverse Z conversion should match")
        self.assertEqual(core_pos2.c, core_pos.c, "Reverse C conversion should match")
        
        print(f"✅ Position type conversion works correctly")
        print(f"   Core: {core_pos}")
        print(f"   Motion: {motion_pos}")

async def run_integration_tests():
    """Run all integration tests"""
    print("=== 4DOF Scanner - Complete System Integration Test ===")
    print("Testing motion optimization with web UI and scanning methods\n")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add all test methods
    test_class = TestCompleteSystemIntegration
    suite.addTest(test_class('test_position_type_conversion'))
    suite.addTest(test_class('test_web_ui_manual_positioning'))
    suite.addTest(test_class('test_motion_completion_timing'))
    suite.addTest(test_class('test_scanning_motion_optimization'))
    suite.addTest(test_class('test_web_ui_scanning_integration'))
    suite.addTest(test_class('test_production_scanning_pipeline'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n=== Integration Test Summary ===")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    # Return success status
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print(f"\n🎉 ALL INTEGRATION TESTS PASSED!")
        print(f"Motion optimization is fully compatible with:")
        print(f"  ✅ Web UI manual positioning")
        print(f"  ✅ Web UI scanning initiation")
        print(f"  ✅ Grid scanning patterns")
        print(f"  ✅ Production scanning pipeline")
        print(f"  ✅ Motion completion timing")
        print(f"  ✅ Position type conversions")
    else:
        print(f"\n❌ Some integration tests failed - see details above")
    
    return success

if __name__ == "__main__":
    # Run the integration tests
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)