"""
Test FluidNC Motion Controller

Basic tests for FluidNC controller implementation.
Uses mocking to avoid requiring actual hardware.

Author: Scanner System Development
Created: September 2025
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import serial

from motion.fluidnc_controller import FluidNCController, create_fluidnc_controller
from motion.base import Position4D, MotionStatus, MotionLimits, MotionCapabilities
from core.exceptions import FluidNCConnectionError, MotionControlError
from core.config_manager import ConfigManager


class TestFluidNCController:
    """Test FluidNC controller implementation"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        return {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 5.0,
            'axes': {
                'x_axis': {'min_limit': -150.0, 'max_limit': 150.0, 'max_feedrate': 8000.0},
                'y_axis': {'min_limit': -100.0, 'max_limit': 100.0, 'max_feedrate': 8000.0},
                'z_axis': {'min_limit': -180.0, 'max_limit': 180.0, 'max_feedrate': 3600.0},
                'c_axis': {'min_limit': -45.0, 'max_limit': 45.0, 'max_feedrate': 1800.0}
            }
        }
    
    @pytest.fixture
    def controller(self, mock_config):
        """Create FluidNC controller for testing"""
        return FluidNCController(mock_config)
    
    def test_controller_initialization(self, controller):
        """Test controller initializes correctly"""
        assert controller.port == '/dev/ttyUSB0'
        assert controller.baudrate == 115200
        assert controller.timeout == 5.0
        assert controller.current_position == Position4D()
        assert controller.status == MotionStatus.DISCONNECTED
        assert not controller.is_homed
        
        # Check axis limits are loaded
        assert 'x' in controller.axis_limits
        assert 'y' in controller.axis_limits
        assert 'z' in controller.axis_limits
        assert 'c' in controller.axis_limits
    
    def test_position_validation(self, controller):
        """Test position validation against limits"""
        # Valid position
        valid_pos = Position4D(x=100.0, y=50.0, z=90.0, c=30.0)
        assert controller._validate_position(valid_pos)
        
        # Invalid position - X out of range
        invalid_pos_x = Position4D(x=200.0, y=50.0, z=90.0, c=30.0)
        assert not controller._validate_position(invalid_pos_x)
        
        # Invalid position - C out of range
        invalid_pos_c = Position4D(x=100.0, y=50.0, z=90.0, c=60.0)
        assert not controller._validate_position(invalid_pos_c)
    
    @pytest.mark.asyncio
    async def test_get_capabilities(self, controller):
        """Test getting controller capabilities"""
        capabilities = await controller.get_capabilities()
        
        assert isinstance(capabilities, MotionCapabilities)
        assert capabilities.axes_count == 4
        assert capabilities.supports_homing
        assert capabilities.supports_soft_limits
        assert capabilities.supports_probe
        assert capabilities.max_feedrate > 0
        assert capabilities.position_resolution == 0.001
    
    @pytest.mark.asyncio
    @patch('serial.Serial')
    async def test_initialization_success(self, mock_serial_class, controller):
        """Test successful controller initialization"""
        mock_serial = Mock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial
        
        # Mock successful responses
        controller._send_command = AsyncMock(return_value='ok')
        
        result = await controller.initialize()
        assert result is True
        assert controller.serial_connection is not None
    
    @pytest.mark.asyncio
    @patch('serial.Serial')
    async def test_initialization_failure(self, mock_serial_class, controller):
        """Test controller initialization failure"""
        mock_serial_class.side_effect = serial.SerialException("Port not found")
        
        result = await controller.initialize()
        assert result is False
        assert controller.serial_connection is None
    
    @pytest.mark.asyncio
    async def test_move_to_position_validation(self, controller):
        """Test move to position with validation"""
        controller._validate_position = Mock(return_value=False)
        controller.execute_gcode = AsyncMock(return_value=True)
        
        position = Position4D(x=1000.0, y=0.0, z=0.0, c=0.0)  # Out of limits
        result = await controller.move_to_position(position)
        
        assert result is False
        controller._validate_position.assert_called_once_with(position)
        controller.execute_gcode.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_move_to_position_success(self, controller):
        """Test successful move to position"""
        controller._validate_position = Mock(return_value=True)
        controller.execute_gcode = AsyncMock(return_value=True)
        
        position = Position4D(x=100.0, y=50.0, z=90.0, c=30.0)
        result = await controller.move_to_position(position, feedrate=1000.0)
        
        assert result is True
        controller._validate_position.assert_called_once_with(position)
        controller.execute_gcode.assert_called_once()
        
        # Check G-code command format
        call_args = controller.execute_gcode.call_args[0][0]
        assert 'G0' in call_args
        assert 'X100.000' in call_args
        assert 'Y50.000' in call_args
        assert 'Z90.000' in call_args
        assert 'C30.000' in call_args
        assert 'F1000' in call_args
    
    @pytest.mark.asyncio
    async def test_move_relative(self, controller):
        """Test relative movement"""
        controller.current_position = Position4D(x=50.0, y=25.0, z=45.0, c=15.0)
        controller._validate_position = Mock(return_value=True)
        controller._send_command = AsyncMock(return_value='ok')
        controller.execute_gcode = AsyncMock(return_value=True)
        
        delta = Position4D(x=10.0, y=5.0, z=15.0, c=5.0)
        result = await controller.move_relative(delta, feedrate=500.0)
        
        assert result is True
        
        # Check that relative mode was set and restored
        command_calls = controller._send_command.call_args_list
        assert any('G91' in str(call) for call in command_calls)  # Relative mode
        assert any('G90' in str(call) for call in command_calls)  # Absolute mode restored
    
    @pytest.mark.asyncio
    async def test_home_axis(self, controller):
        """Test homing specific axis"""
        controller.execute_gcode = AsyncMock(return_value=True)
        
        result = await controller.home_axis('X')
        assert result is True
        controller.execute_gcode.assert_called_once_with('$HX')
        
        # Test invalid axis
        result = await controller.home_axis('invalid')
        assert result is False
    
    @pytest.mark.asyncio
    async def test_emergency_stop(self, controller):
        """Test emergency stop functionality"""
        mock_serial = Mock()
        controller.serial_connection = mock_serial
        
        result = await controller.emergency_stop()
        assert result is True
        
        # Check that emergency stop commands were sent
        assert mock_serial.write.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_motion_limits(self, controller):
        """Test setting and getting motion limits"""
        new_limits = MotionLimits(-200.0, 200.0, 10000.0)
        
        # Set limits
        result = await controller.set_motion_limits('x', new_limits)
        assert result is True
        
        # Get limits
        retrieved_limits = await controller.get_motion_limits('x')
        assert retrieved_limits == new_limits
        
        # Test invalid axis
        with pytest.raises(MotionControlError):
            await controller.get_motion_limits('invalid')


class TestFluidNCControllerCreation:
    """Test FluidNC controller factory function"""
    
    @patch('motion.fluidnc_controller.ConfigManager')
    def test_create_fluidnc_controller(self, mock_config_manager_class):
        """Test controller creation from config manager"""
        mock_config_manager = Mock()
        mock_config_manager.get.side_effect = lambda key, default=None: {
            'motion': {
                'controller': {
                    'port': '/dev/ttyUSB0',
                    'baudrate': 115200
                }
            },
            'motion.axes': {
                'x_axis': {'min_limit': -100.0, 'max_limit': 100.0, 'max_feedrate': 5000.0}
            }
        }.get(key, default)
        
        controller = create_fluidnc_controller(mock_config_manager)
        
        assert isinstance(controller, FluidNCController)
        assert controller.port == '/dev/ttyUSB0'
        assert controller.baudrate == 115200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])