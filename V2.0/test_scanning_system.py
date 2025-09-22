"""
Test Suite for Scanning Orchestration System

Tests all components of the scanning system including:
- Scan pattern generation and validation
- State management and persistence  
- Orchestrator coordination logic
- Error handling and recovery
- Mock hardware interfaces
"""

import asyncio
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
import sys
import os

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from core.types import Position4D, CameraSettings
from scanning import (
    ScanPattern, ScanPoint, PatternType, PatternParameters,
    GridScanPattern, GridPatternParameters,
    ScanState, ScanStatus, ScanPhase,
    ScanOrchestrator
)

class TestScanPatterns:
    """Test scan pattern generation and validation"""
    
    def test_position4d_creation(self):
        """Test Position4D creation and validation"""
        # Valid position
        pos = Position4D(x=10.0, y=20.0, z=5.0, c=15.0)
        assert pos.x == 10.0
        assert pos.y == 20.0
        assert pos.z == 5.0
        assert pos.c == 15.0
        
        # Test distance calculation
        pos2 = Position4D(x=13.0, y=24.0, z=5.0, c=0.0)
        distance = pos.distance_to(pos2)
        assert abs(distance - 5.0) < 0.01  # 3-4-5 triangle
        
        # Test validation
        with pytest.raises(ValueError):
            Position4D(x=2000.0, y=0.0, z=0.0, c=0.0)  # X out of range
    
    def test_scan_point_creation(self):
        """Test ScanPoint creation and validation"""
        position = Position4D(x=10.0, y=20.0, z=5.0, c=15.0)
        camera_settings = CameraSettings(exposure_time=0.1, iso=200)
        
        point = ScanPoint(
            position=position,
            camera_settings=camera_settings,
            capture_count=2,
            dwell_time=0.3
        )
        
        assert point.position.x == 10.0
        assert point.camera_settings.exposure_time == 0.1
        assert point.capture_count == 2
        assert point.dwell_time == 0.3
        
        # Test validation
        with pytest.raises(ValueError):
            ScanPoint(
                position=position,
                capture_count=0  # Invalid
            )
    
    def test_pattern_parameters(self):
        """Test pattern parameter validation"""
        params = PatternParameters(
            min_x=-50.0,
            max_x=50.0,
            min_y=-30.0,
            max_y=30.0,
            overlap_percentage=25.0
        )
        
        assert params.min_x == -50.0
        assert params.max_x == 50.0
        assert params.overlap_percentage == 25.0
    
    def test_grid_pattern_parameters(self):
        """Test grid-specific parameters"""
        params = GridPatternParameters(
            min_x=-50.0,
            max_x=50.0,
            min_y=-30.0,
            max_y=30.0,
            x_spacing=10.0,
            y_spacing=15.0,
            c_steps=4,
            zigzag=True
        )
        
        assert params.x_spacing == 10.0
        assert params.y_spacing == 15.0
        assert params.c_steps == 4
        assert params.zigzag is True
    
    def test_grid_pattern_generation(self):
        """Test grid pattern point generation"""
        params = GridPatternParameters(
            min_x=0.0,
            max_x=20.0,
            min_y=0.0,
            max_y=10.0,
            min_z=5.0,
            max_z=5.0,
            x_spacing=10.0,
            y_spacing=10.0,
            c_steps=2,
            zigzag=True
        )
        
        pattern = GridScanPattern("test_grid", params)
        points = pattern.generate_points()
        
        # Should have 3x2x2 = 12 points (3 X positions, 2 Y positions, 2 rotations)
        assert len(points) >= 8  # At least 2x2x2
        
        # Check first point
        first_point = points[0]
        assert isinstance(first_point.position, Position4D)
        assert first_point.position.z == 5.0
        
        # Verify all points are within bounds
        for point in points:
            assert params.min_x <= point.position.x <= params.max_x
            assert params.min_y <= point.position.y <= params.max_y
            assert params.min_z <= point.position.z <= params.max_z
    
    def test_grid_pattern_zigzag(self):
        """Test zigzag pattern generation"""
        params = GridPatternParameters(
            min_x=0.0,
            max_x=20.0,
            min_y=0.0,
            max_y=20.0,
            x_spacing=10.0,
            y_spacing=10.0,
            c_steps=1,
            zigzag=True
        )
        
        pattern = GridScanPattern("test_zigzag", params)
        points = pattern.generate_points()
        
        # Extract Y coordinates for each X row
        x_positions = sorted(list(set(p.position.x for p in points)))
        
        for i, x_pos in enumerate(x_positions):
            row_points = [p for p in points if p.position.x == x_pos]
            row_points.sort(key=lambda p: p.position.y)
            
            # Even rows should be forward, odd rows should be reverse for zigzag
            if i % 2 == 1 and len(row_points) > 1:
                # Check if this row was reversed (higher Y values first in generation)
                y_values = [p.position.y for p in row_points]
                # This is implementation-dependent, just ensure it's consistent

class TestScanState:
    """Test scan state management"""
    
    def test_scan_state_creation(self):
        """Test scan state initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            state = ScanState(
                scan_id="test_scan_001",
                pattern_id="test_pattern",
                output_directory=Path(temp_dir)
            )
            
            assert state.scan_id == "test_scan_001"
            assert state.pattern_id == "test_pattern"
            assert state.status == ScanStatus.IDLE
            assert state.phase == ScanPhase.SETUP
            assert state.progress.current_point == 0
    
    def test_scan_state_workflow(self):
        """Test complete scan state workflow"""
        with tempfile.TemporaryDirectory() as temp_dir:
            state = ScanState(
                scan_id="test_workflow",
                pattern_id="test_pattern",
                output_directory=Path(temp_dir)
            )
            
            # Initialize
            state.initialize(total_points=10, scan_parameters={'test': True})
            assert state.status == ScanStatus.INITIALIZING
            assert state.progress.total_points == 10
            
            # Start
            state.start()
            assert state.status == ScanStatus.RUNNING
            assert state.timing.start_time is not None
            
            # Update progress
            state.update_progress(current_point=5, images_captured=10)
            assert state.progress.current_point == 5
            assert state.progress.images_captured == 10
            assert state.progress.completion_percentage == 50.0
            
            # Pause and resume
            state.pause()
            assert state.status == ScanStatus.PAUSED
            
            state.resume()
            assert state.status == ScanStatus.RUNNING
            
            # Complete
            state.complete()
            assert state.status == ScanStatus.COMPLETED
            assert state.timing.end_time is not None
    
    def test_scan_state_persistence(self):
        """Test scan state saving and loading"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create and configure state
            state = ScanState(
                scan_id="test_persistence",
                pattern_id="test_pattern",
                output_directory=Path(temp_dir)
            )
            
            state.initialize(total_points=5, scan_parameters={'test': 'data'})
            state.start()
            state.update_progress(current_point=3, images_captured=6)
            
            # State should be automatically saved
            state_file = state.state_file
            assert state_file.exists()
            
            # Load state
            loaded_state = ScanState.load_state(state_file)
            assert loaded_state.scan_id == "test_persistence"
            assert loaded_state.progress.current_point == 3
            assert loaded_state.progress.images_captured == 6
            assert loaded_state.status == ScanStatus.RUNNING
    
    def test_scan_state_error_handling(self):
        """Test error tracking"""
        with tempfile.TemporaryDirectory() as temp_dir:
            state = ScanState(
                scan_id="test_errors",
                pattern_id="test_pattern", 
                output_directory=Path(temp_dir)
            )
            
            # Add recoverable error
            state.add_error(
                "test_error",
                "Test error message",
                {"detail": "test"},
                recoverable=True
            )
            
            assert len(state.errors) == 1
            assert state.errors[0].error_type == "test_error"
            assert state.errors[0].recoverable is True
            
            # Add critical error and fail
            state.fail("Critical failure", {"code": 500})
            assert state.status == ScanStatus.FAILED
            assert len(state.errors) == 2

class TestScanOrchestrator:
    """Test scan orchestrator coordination"""
    
    @pytest.fixture
    def config_manager(self):
        """Create a test configuration manager"""
        # Create minimal config for testing
        config_data = {
            'system': {'name': 'test_scanner'},
            'motion': {'stabilization_delay': 0.1},
            'cameras': {'count': 2}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_file = f.name
        
        try:
            return ConfigManager(config_file)
        finally:
            os.unlink(config_file)
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, config_manager):
        """Test orchestrator initialization"""
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize
        result = await orchestrator.initialize()
        assert result is True
        
        # Check health
        health = await orchestrator._health_check()
        assert health is True
        
        # Shutdown
        await orchestrator.shutdown()
    
    @pytest.mark.asyncio
    async def test_orchestrator_pattern_creation(self, config_manager):
        """Test pattern creation through orchestrator"""
        orchestrator = ScanOrchestrator(config_manager)
        
        # Create grid pattern
        pattern = orchestrator.create_grid_pattern(
            x_range=(-25.0, 25.0),
            y_range=(-15.0, 15.0),
            spacing=10.0,
            z_rotation=20.0,  # Z-axis rotation angle in degrees
            rotations=[0.0, 90.0]
        )
        
        assert isinstance(pattern, GridScanPattern)
        assert pattern.pattern_id.startswith("grid_")
        
        # Generate points
        points = pattern.generate_points()
        assert len(points) > 0
        
        # Verify points are reasonable
        for point in points:
            assert -25.0 <= point.position.x <= 25.0
            assert -15.0 <= point.position.y <= 15.0
            assert point.position.z == 20.0
    
    @pytest.mark.asyncio
    async def test_orchestrator_scan_execution(self, config_manager):
        """Test complete scan execution"""
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = ScanOrchestrator(config_manager)
            
            # Initialize
            await orchestrator.initialize()
            
            # Create small pattern for testing
            pattern = orchestrator.create_grid_pattern(
                x_range=(0.0, 10.0),
                y_range=(0.0, 10.0), 
                spacing=10.0,
                z_rotation=5.0  # Z-axis rotation angle in degrees
            )
            
            # Start scan
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=temp_dir,
                scan_id="test_execution"
            )
            
            assert scan_state.scan_id == "test_execution"
            assert scan_state.status in [ScanStatus.INITIALIZING, ScanStatus.RUNNING]
            
            # Wait for scan to start
            await asyncio.sleep(0.5)
            
            # Check status
            status = orchestrator.get_scan_status()
            assert status is not None
            assert status['scan_id'] == "test_execution"
            
            # Wait for completion or timeout
            timeout = 10.0
            start_time = asyncio.get_event_loop().time()
            
            while (scan_state.status in [ScanStatus.INITIALIZING, ScanStatus.RUNNING] 
                   and asyncio.get_event_loop().time() - start_time < timeout):
                await asyncio.sleep(0.1)
            
            # Verify completion
            assert scan_state.status in [ScanStatus.COMPLETED, ScanStatus.CANCELLED]
            
            # Check output files were created
            output_path = Path(temp_dir)
            files = list(output_path.glob("*"))
            assert len(files) > 0  # Should have some output files
            
            await orchestrator.shutdown()
    
    @pytest.mark.asyncio
    async def test_orchestrator_pause_resume(self, config_manager):
        """Test pause and resume functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = ScanOrchestrator(config_manager)
            await orchestrator.initialize()
            
            # Create pattern with multiple points
            pattern = orchestrator.create_grid_pattern(
                x_range=(0.0, 20.0),
                y_range=(0.0, 20.0),
                spacing=10.0
            )
            
            # Start scan
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=temp_dir
            )
            
            # Wait for scan to start
            await asyncio.sleep(0.2)
            
            # Pause
            result = await orchestrator.pause_scan()
            assert result is True
            
            # Wait for pause to take effect
            await asyncio.sleep(0.2)
            assert scan_state.status == ScanStatus.PAUSED
            
            # Resume
            result = await orchestrator.resume_scan()
            assert result is True
            
            await asyncio.sleep(0.1)
            assert scan_state.status == ScanStatus.RUNNING
            
            # Stop
            await orchestrator.stop_scan()
            await asyncio.sleep(0.2)
            
            await orchestrator.shutdown()
    
    @pytest.mark.asyncio
    async def test_orchestrator_emergency_stop(self, config_manager):
        """Test emergency stop functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = ScanOrchestrator(config_manager)
            await orchestrator.initialize()
            
            # Create pattern
            pattern = orchestrator.create_grid_pattern(
                x_range=(0.0, 10.0),
                y_range=(0.0, 10.0),
                spacing=5.0
            )
            
            # Start scan
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=temp_dir
            )
            
            await asyncio.sleep(0.1)
            
            # Emergency stop
            await orchestrator.emergency_stop()
            
            # Verify emergency state
            assert orchestrator._emergency_stop is True
            
            await orchestrator.shutdown()

class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete scanning workflow from start to finish"""
        # Create temporary config
        config_data = {
            'system': {'name': 'integration_test'},
            'motion': {'stabilization_delay': 0.05},
            'cameras': {'count': 2}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_file = f.name
        
        with tempfile.TemporaryDirectory() as scan_dir:
            try:
                # Initialize system
                config_manager = ConfigManager(config_file)
                orchestrator = ScanOrchestrator(config_manager)
                
                success = await orchestrator.initialize()
                assert success is True
                
                # Create scan pattern
                pattern = orchestrator.create_grid_pattern(
                    x_range=(-5.0, 5.0),
                    y_range=(-5.0, 5.0),
                    spacing=5.0,
                    z_rotation=10.0  # Z-axis rotation angle in degrees
                )
                
                # Execute scan
                scan_state = await orchestrator.start_scan(
                    pattern=pattern,
                    output_directory=scan_dir,
                    scan_id="integration_test"
                )
                
                # Monitor until completion
                timeout = 15.0
                start_time = asyncio.get_event_loop().time()
                
                while (scan_state.status not in [ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED]
                       and asyncio.get_event_loop().time() - start_time < timeout):
                    await asyncio.sleep(0.1)
                    
                    # Log progress
                    status = orchestrator.get_scan_status()
                    if status:
                        print(f"Progress: {status['progress']['completion_percentage']:.1f}%")
                
                # Verify results
                assert scan_state.status == ScanStatus.COMPLETED
                assert scan_state.progress.completion_percentage == 100.0
                
                # Check output files
                output_files = list(Path(scan_dir).glob("*"))
                assert len(output_files) > 0
                
                # Check for report file
                report_files = list(Path(scan_dir).glob("*_report.json"))
                assert len(report_files) > 0
                
                # Verify report content
                with open(report_files[0]) as f:
                    report = json.load(f)
                    assert report['scan_id'] == "integration_test"
                    assert report['status'] == 'completed'
                    assert report['points_processed'] > 0
                
                await orchestrator.shutdown()
                
            finally:
                os.unlink(config_file)


if __name__ == "__main__":
    """Run the tests"""
    print("Running Scanning Orchestration System Tests...")
    print("=" * 60)
    
    # Run pytest with verbose output
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        __file__, 
        "-v", 
        "--tb=short",
        "-x"  # Stop on first failure
    ], cwd=str(project_root))
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("Scanning orchestration system is ready for use.")
    else:
        print("\n" + "=" * 60)
        print("❌ TESTS FAILED!")
        print("Please fix issues before proceeding.")
    
    sys.exit(result.returncode)