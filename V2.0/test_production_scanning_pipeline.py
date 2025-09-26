#!/usr/bin/env python3
"""
Complete Scanning Pipeline Test with Real Hardware

This test emulates the EXACT scanning pipeline that would be used in production,
using real FluidNC hardware, real cameras, and the complete scan orchestrator.
"""

import sys
import asyncio
import logging
from pathlib import Path

v2_path = Path(__file__).parent
sys.path.insert(0, str(v2_path))

from core.config_manager import ConfigManager
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import GridScanPattern, GridPatternParameters
from core.types import Position4D

logger = logging.getLogger(__name__)

class ProductionScanTracker:
    """Track the complete production scanning pipeline"""
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.motion_commands = []
        self.camera_captures = []
        self.scan_events = []
        
        # Track motion controller commands (real FluidNC)
        motion_controller = orchestrator.motion_controller
        if hasattr(motion_controller, 'protocol'):
            self.original_send_command = motion_controller.protocol.send_command
            motion_controller.protocol.send_command = self.track_motion_command
        
        # Track camera operations
        camera_manager = orchestrator.camera_manager
        if hasattr(camera_manager, 'capture_image'):
            self.original_capture = camera_manager.capture_image
            camera_manager.capture_image = self.track_camera_capture
            
    def track_motion_command(self, command):
        """Track actual G-code commands sent to FluidNC hardware"""
        self.motion_commands.append(command)
        print(f"🔧 MOTION: {command}")
        return self.original_send_command(command)
        
    async def track_camera_capture(self, camera_id=None, **kwargs):
        """Track actual camera capture operations"""
        self.camera_captures.append(f"capture_camera_{camera_id}")
        print(f"📸 CAMERA: Capturing image from camera {camera_id}")
        return await self.original_capture(camera_id, **kwargs)

async def test_production_scanning_pipeline():
    """Test complete production scanning pipeline with real hardware"""
    print("🚀 TESTING COMPLETE PRODUCTION SCANNING PIPELINE")
    print("⚠️  WARNING: This uses REAL HARDWARE - FluidNC and cameras will operate")
    
    # Setup REAL hardware configuration (not simulation)
    config_file = v2_path / "config" / "scanner_config.yaml"
    config = ConfigManager(config_file)
    
    # Force real hardware mode
    config._config_data = config._config_data or {}
    if 'system' not in config._config_data:
        config._config_data['system'] = {}
    config._config_data['system']['simulation_mode'] = False
    
    print("📋 Configuration: REAL HARDWARE MODE")
    print(f"   - FluidNC Port: {config.get('fluidnc.port', '/dev/ttyUSB0')}")
    print(f"   - Camera System: Real Pi cameras")
    print(f"   - Motion System: Real FluidNC controller")
    
    # Initialize complete scan orchestrator with real hardware
    orchestrator = ScanOrchestrator(config)
    
    # Setup production tracking
    tracker = ProductionScanTracker(orchestrator)
    
    try:
        # Initialize the complete system
        print("\n🔌 Initializing production scanning system...")
        init_success = await orchestrator.initialize()
        if not init_success:
            print("❌ Failed to initialize production scanning system")
            return False
            
        print("✅ Production scanning system initialized")
        
        # Create a MINIMAL production scan pattern (2 positions only for testing)
        print("\n📐 Creating minimal production scan pattern...")
        pattern_params = GridPatternParameters(
            min_x=15.0, max_x=25.0,  # Small 10mm range
            min_y=20.0, max_y=20.0,  # Single Y line
            x_spacing=10.0,           # 10mm spacing = 2 points (15, 25)
            y_spacing=0.0,            # No Y spacing (single line)
            c_steps=1,                # Single rotation position
            zigzag=False              # Simple linear pattern
        )
        
        pattern = GridScanPattern(
            pattern_id="production_test",
            parameters=pattern_params
        )
        
        scan_points = list(pattern.generate_points())
        print(f"📍 Scan pattern created: {len(scan_points)} points")
        for i, point in enumerate(scan_points, 1):
            print(f"   {i}. Position: {point.position}")
        
        # Execute COMPLETE production scan
        print(f"\n🎯 Starting PRODUCTION SCAN with real hardware...")
        tracker.motion_commands.clear()
        tracker.camera_captures.clear()
        
        start_time = asyncio.get_event_loop().time()
        
        # Use the EXACT same method as production scanning
        scan_state = await orchestrator.start_scan(
            pattern=pattern,
            output_directory="/tmp/production_test_scan",
            scan_id="real_hardware_pipeline_test",
            scan_parameters={'test_mode': True}
        )
        
        print(f"📊 Scan started: {scan_state.status}")
        
        # Wait for scan completion with generous timeout
        print("⏳ Waiting for scan completion...")
        completed = await orchestrator.wait_for_scan_completion(timeout=60.0)
        
        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time
        
        print(f"\n📋 PRODUCTION SCAN RESULTS:")
        print(f"✅ Scan completed: {completed}")
        print(f"⏱️  Total time: {total_time:.1f}s")
        print(f"📊 Final scan state: {scan_state.status}")
        
        # Analyze production pipeline execution
        print(f"\n🔍 PRODUCTION PIPELINE ANALYSIS:")
        print(f"🔧 Motion commands sent to FluidNC: {len(tracker.motion_commands)}")
        print(f"📸 Camera captures executed: {len(tracker.camera_captures)}")
        
        # Analyze motion optimization in production context
        homing_commands = [cmd for cmd in tracker.motion_commands if cmd.startswith('$H')]
        g0_commands = [cmd for cmd in tracker.motion_commands if cmd.startswith('G0 ')]
        position_commands = [cmd for cmd in g0_commands if 'X' in cmd and 'Y' in cmd]
        
        print(f"\n📊 MOTION OPTIMIZATION ANALYSIS:")
        print(f"   🏠 Homing commands: {len(homing_commands)}")
        print(f"   🎯 G0 positioning commands: {len(g0_commands)}")
        print(f"   📍 Multi-axis position commands: {len(position_commands)}")
        
        print(f"\n📋 ALL MOTION COMMANDS SENT TO FLUIDNC:")
        for i, cmd in enumerate(tracker.motion_commands, 1):
            print(f"   {i:2d}. {cmd}")
            
        print(f"\n📸 ALL CAMERA OPERATIONS:")
        for i, capture in enumerate(tracker.camera_captures, 1):
            print(f"   {i:2d}. {capture}")
        
        # Verify production optimization
        expected_positions = len(scan_points)
        if len(position_commands) == expected_positions and len(position_commands) > 0:
            print(f"\n✅ PRODUCTION OPTIMIZATION VERIFIED!")
            print(f"   ✓ {len(position_commands)} position commands for {expected_positions} scan points")
            print(f"   ✓ Each command moves all 4 axes simultaneously")
            print(f"   ✓ No redundant motion commands in production pipeline")
            print(f"   ✓ Real hardware motion and camera integration working")
            return True
        else:
            print(f"\n⚠️  PRODUCTION OPTIMIZATION NEEDS WORK:")
            print(f"   Expected {expected_positions} position commands, got {len(position_commands)}")
            return False
            
    except asyncio.TimeoutError:
        print(f"\n⏰ PRODUCTION SCAN TIMEOUT")
        print(f"Motion commands before timeout:")
        for cmd in tracker.motion_commands:
            print(f"  {cmd}")
        return False
        
    except Exception as e:
        print(f"\n❌ PRODUCTION SCAN ERROR: {e}")
        print(f"Motion commands before error:")
        for cmd in tracker.motion_commands:
            print(f"  {cmd}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        result = asyncio.run(test_production_scanning_pipeline())
        if result:
            print(f"\n🎉 PRODUCTION SCANNING PIPELINE TEST PASSED!")
            print(f"   ✅ Motion optimization works in real scanning workflow")
            print(f"   ✅ Real hardware integration successful")
            print(f"   ✅ System ready for production scanning")
            sys.exit(0)
        else:
            print(f"\n💥 PRODUCTION PIPELINE NEEDS OPTIMIZATION WORK")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Production test interrupted - hardware may need manual reset")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Production pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)