"""
Updated Scan Orchestrator - Simplified Version
Uses the MotionControllerAdapter with SimpleWorkingFluidNCController.
Focuses on basic functionality for web UI integration testing.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from core.config_manager import ConfigManager
from core.events import EventBus, ScannerEvent, EventPriority
from motion.base import Position4D
from simple_working_fluidnc_controller import SimpleWorkingFluidNCController, Position4D as SimplePosition4D

class UpdatedScanOrchestrator:
    """
    Simplified orchestrator for testing web UI integration.
    Uses working motion controller via adapter pattern.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the scan orchestrator."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_manager = config_manager
        self.event_bus = EventBus()
        
        # Component instances (initially None)
        self.motion_controller: Optional[SimpleWorkingFluidNCController] = None
        self.camera_controller = None
        self.lighting_controller = None
        self.storage_manager = None
        
        # System status
        self.is_initialized = False
        self.hardware_status = {
            'motion': False,
            'cameras': False,
            'lighting': False,
            'storage': False
        }
        
        self.logger.info("UpdatedScanOrchestrator initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize system components with graceful fallback.
        Returns True if at least some components are available.
        """
        self.logger.info("🔄 Starting system initialization...")
        success_count = 0
        
        # 1. Initialize Motion Controller
        try:
            self.logger.info("Initializing motion controller...")
            self.motion_controller = SimpleWorkingFluidNCController()
            success_count += 1  # Controller created successfully
            
            # Test connection
            if self.motion_controller.connect():
                self.hardware_status['motion'] = True
                self.logger.info("✅ Motion controller connected")
                
                # Get status
                status = self.motion_controller.get_status()
                self.logger.info(f"📊 Motion status: {status}")
            else:
                self.logger.warning("⚠️ Motion controller connection failed (hardware not available)")
                self.logger.info("🔧 Motion controller instance created but not connected")
                
        except Exception as e:
            self.logger.error(f"Motion controller error: {e}")
            # Keep motion_controller as None if creation fails
        
        # 2. Mock Camera Controller (for testing)
        try:
            self.logger.info("Setting up camera controller (mock for testing)...")
            self.camera_controller = MockCameraController()
            self.hardware_status['cameras'] = True
            success_count += 1
            self.logger.info("✅ Camera controller ready (mock)")
            
        except Exception as e:
            self.logger.error(f"Camera controller error: {e}")
        
        # 3. Mock Lighting Controller (for testing)
        try:
            self.logger.info("Setting up lighting controller (mock for testing)...")
            self.lighting_controller = MockLightingController()
            self.hardware_status['lighting'] = True
            success_count += 1
            self.logger.info("✅ Lighting controller ready (mock)")
            
        except Exception as e:
            self.logger.error(f"Lighting controller error: {e}")
        
        # 4. Mock Storage Manager (for testing)
        try:
            self.logger.info("Setting up storage manager (mock for testing)...")
            self.storage_manager = MockStorageManager()
            self.hardware_status['storage'] = True
            success_count += 1
            self.logger.info("✅ Storage manager ready (mock)")
            
        except Exception as e:
            self.logger.error(f"Storage manager error: {e}")
        
        # Summary
        self.is_initialized = success_count > 0
        
        self.logger.info(f"\n🔧 Initialization Summary:")
        for component, status in self.hardware_status.items():
            icon = "✅" if status else "❌"
            self.logger.info(f"   {component.capitalize()}: {icon}")
        
        if self.is_initialized:
            mode = "Full system" if success_count == 4 else f"Partial system ({success_count}/4 components)"
            self.logger.info(f"🚀 {mode} ready for operation")
        else:
            self.logger.error("❌ System initialization failed - no components available")
        
        return self.is_initialized
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        status = {
            'initialized': self.is_initialized,
            'hardware_status': self.hardware_status.copy(),
            'motion_status': None,
            'timestamp': datetime.now().isoformat()
        }
        
        # Get motion status if available
        if self.motion_controller and self.hardware_status['motion']:
            try:
                motion_status = self.motion_controller.get_status()
                status['motion_status'] = {
                    'connected': True,
                    'status': motion_status,
                    'can_home': True,
                    'can_move': motion_status != 'Alarm',
                    'is_homed': self.motion_controller.is_homed()
                }
            except Exception as e:
                status['motion_status'] = {
                    'connected': False,
                    'error': str(e)
                }
        
        return status
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status for compatibility with test suite."""
        status = {
            'initialized': self.is_initialized,
            'motion_available': self.hardware_status['motion'],
            'cameras_available': self.hardware_status['cameras'],
            'motion_status': None,
            'motion_homed': False
        }
        
        # Get motion status if available
        if self.motion_controller and self.hardware_status['motion']:
            try:
                motion_status = self.motion_controller.get_status()
                status['motion_status'] = motion_status
                status['motion_homed'] = self.motion_controller.is_homed()
            except Exception as e:
                self.logger.debug(f"Could not get motion status: {e}")
        
        return status
    
    def clear_alarm(self) -> bool:
        """Clear alarm state from motion controller."""
        if not self.hardware_status['motion'] or not self.motion_controller:
            self.logger.error("Motion controller not available for alarm clear")
            return False
        
        self.logger.info("🔓 Clearing alarm state...")
        
        try:
            result = self.motion_controller.clear_alarm()
            if result:
                self.logger.info("✅ Alarm cleared successfully")
                return True
            else:
                self.logger.error("❌ Failed to clear alarm")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error clearing alarm: {e}")
            return False
    
    def home_system(self) -> bool:
        """Home the motion system - alias for home_all_axes for test compatibility."""
        return self.home_all_axes()
    
    def home_all_axes(self) -> bool:
        """Home all motion axes using the proven working controller."""
        if not self.hardware_status['motion'] or not self.motion_controller:
            self.logger.error("Motion controller not available for homing")
            return False
        
        self.logger.info("🏠 Starting homing sequence...")
        
        try:
            # Use the proven working home method directly
            result = self.motion_controller.home()
            if result:
                self.logger.info("✅ Homing completed successfully")
                return True
            else:
                self.logger.error("❌ Homing failed")
                return False
                
        except KeyboardInterrupt:
            self.logger.warning("🛑 Homing interrupted by user")
            # Try to stop motion gracefully
            try:
                self.motion_controller.stop_motion()
                self.logger.info("✅ Motion stopped")
            except Exception as e:
                self.logger.debug(f"Could not stop motion: {e}")
            raise  # Re-raise the KeyboardInterrupt
            
        except Exception as e:
            self.logger.error(f"❌ Homing error: {e}")
            return False
    
    async def move_to_position(self, position: Position4D) -> bool:
        """Move to specified position."""
        if not self.hardware_status['motion'] or not self.motion_controller:
            self.logger.error("Motion controller not available for movement")
            return False
        
        self.logger.info(f"🎯 Moving to position: {position}")
        
        try:
            # Convert Position4D to SimplePosition4D
            simple_pos = SimplePosition4D(x=position.x, y=position.y, z=position.z, c=position.c)
            result = self.motion_controller.move_to_position(simple_pos)
            if result:
                self.logger.info("✅ Move completed successfully")
                return True
            else:
                self.logger.error("❌ Move failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Move error: {e}")
            return False
    
    async def capture_image(self) -> Optional[str]:
        """Capture image with current system setup."""
        if not self.hardware_status['cameras'] or not self.camera_controller:
            self.logger.error("Camera controller not available")
            return None
        
        self.logger.info("📸 Capturing image...")
        
        try:
            # Enable lighting if available
            if self.hardware_status['lighting'] and self.lighting_controller:
                await self.lighting_controller.set_brightness(100)
            
            # Capture image
            image_path = await self.camera_controller.capture()
            
            if image_path:
                self.logger.info(f"✅ Image captured: {image_path}")
                return image_path
            else:
                self.logger.error("❌ Image capture failed")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Capture error: {e}")
            return None
        
        finally:
            # Reset lighting
            if self.hardware_status['lighting'] and self.lighting_controller:
                try:
                    await self.lighting_controller.set_brightness(0)
                except Exception:
                    pass
    
    async def capture_single_image(self) -> Dict[str, Any]:
        """Capture single image with result details for test compatibility."""
        result = {
            'success': False,
            'images': {},
            'error': None
        }
        
        if not self.hardware_status['cameras'] or not self.camera_controller:
            result['error'] = "Camera controller not available"
            return result
        
        try:
            # Enable lighting if available
            if self.hardware_status['lighting'] and self.lighting_controller:
                await self.lighting_controller.set_brightness(100)
            
            # Capture image using mock controller
            image_path = await self.camera_controller.capture()
            
            if image_path:
                result['success'] = True
                result['images'] = {
                    'camera_0': image_path,
                    'camera_1': image_path  # Mock has same path for both cameras
                }
                self.logger.info(f"✅ Image captured: {image_path}")
            else:
                result['error'] = "Image capture failed"
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"❌ Capture error: {e}")
        
        finally:
            # Reset lighting
            if self.hardware_status['lighting'] and self.lighting_controller:
                try:
                    await self.lighting_controller.set_brightness(0)
                except Exception:
                    pass
        
        return result
    
    async def emergency_stop(self) -> bool:
        """Emergency stop all operations."""
        self.logger.warning("🚨 EMERGENCY STOP ACTIVATED")
        
        # Stop motion
        if self.hardware_status['motion'] and self.motion_controller:
            try:
                self.motion_controller.stop_motion()
                self.logger.info("✅ Motion emergency stop executed")
            except Exception as e:
                self.logger.error(f"Motion emergency stop failed: {e}")
        
        # Turn off lighting
        if self.hardware_status['lighting'] and self.lighting_controller:
            try:
                await self.lighting_controller.set_brightness(0)
                self.logger.info("✅ Lighting turned off")
            except Exception as e:
                self.logger.error(f"Lighting shutdown failed: {e}")
        
        return True
    
    async def shutdown(self) -> None:
        """Graceful system shutdown."""
        self.logger.info("🔄 Shutting down scan orchestrator...")
        
        # Disconnect motion controller
        if self.motion_controller:
            try:
                self.motion_controller.disconnect()
                self.logger.info("✅ Motion controller disconnected")
            except Exception as e:
                self.logger.debug(f"Motion disconnect error: {e}")
        
        self.is_initialized = False
        self.logger.info("✅ Scan orchestrator shutdown complete")
    
    # Web UI Compatibility Properties
    @property
    def camera_manager(self):
        """Compatibility property for web UI."""
        return self.camera_controller
    
    @property 
    def lighting_manager(self):
        """Compatibility property for web UI."""
        return self.lighting_controller
    
    @property
    def storage_controller(self):
        """Compatibility property for web UI."""
        return self.storage_manager
    
    # Web UI Compatibility Methods
    def get_camera_status(self) -> Dict[str, Any]:
        """Get camera status for web UI compatibility."""
        if self.hardware_status['cameras'] and self.camera_controller:
            return {
                'available': True,
                'camera_0': {'connected': True, 'resolution': '1920x1080'},
                'camera_1': {'connected': True, 'resolution': '1920x1080'}
            }
        else:
            return {'available': False}


# Mock classes for testing without full hardware
class MockCameraController:
    """Mock camera controller for testing."""
    
    async def capture(self) -> str:
        """Mock capture that returns a fake image path."""
        await asyncio.sleep(0.1)  # Simulate capture time
        return f"/tmp/mock_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    
    def get_preview_frame(self, camera_key: str = 'primary'):
        """Get preview frame for web streaming - returns mock numpy array."""
        import numpy as np
        # Return a mock 640x480x3 RGB image (black with "MOCK CAMERA" text area)
        height, width = 480, 640
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Add some pattern so it's not completely black
        frame[100:200, 200:400] = [64, 64, 64]  # Gray rectangle in center
        return frame
    
    async def trigger_autofocus(self, camera_key: str = 'primary') -> bool:
        """Mock autofocus trigger."""
        await asyncio.sleep(0.1)  # Simulate autofocus time
        return True


class MockLightingController:
    """Mock lighting controller for testing."""
    
    async def set_brightness(self, brightness: int) -> bool:
        """Mock brightness setting."""
        await asyncio.sleep(0.05)  # Simulate GPIO operations
        return True


class MockStorageManager:
    """Mock storage manager for testing."""
    
    async def store_image(self, image_path: str) -> str:
        """Mock image storage."""
        return image_path


# Factory function for web interface integration
def create_scan_orchestrator(config_manager: ConfigManager) -> UpdatedScanOrchestrator:
    """Factory function to create properly configured scan orchestrator."""
    return UpdatedScanOrchestrator(config_manager)