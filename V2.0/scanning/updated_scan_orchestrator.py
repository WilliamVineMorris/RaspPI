"""
Updated Scan Orchestrator
Uses the MotionControllerAdapter with SimpleWorkingFluidNCController.
Handles initialization gracefully even if motion controller is in alarm state.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from core.config_manager import ConfigManager
from core.events import EventBus, Event, EventPriority
from motion.motion_adapter import MotionControllerAdapter
from camera.pi_camera_controller import PiCameraController
from lighting.mock_led_controller import MockLEDController
from storage.local_storage_manager import LocalStorageManager
from motion.base import Position4D

class UpdatedScanOrchestrator:
    """
    Orchestrates scanning operations with graceful initialization.
    Cameras work even if motion controller is in alarm state.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the scan orchestrator."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config_manager
        
        # Create event bus
        self.event_bus = EventBus()
        
        # Initialize components (will be created in initialize())
        self.motion_controller = None
        self.camera_controller = None
        self.lighting_controller = None
        self.storage_manager = None
        
        # Status flags
        self.motion_available = False
        self.cameras_available = False
        self.initialized = False
        
        self.logger.info("Scan orchestrator created")
    
    async def initialize(self) -> bool:
        """
        Initialize all components with graceful degradation.
        Cameras initialize even if motion fails.
        """
        self.logger.info("Initializing scan orchestrator...")
        
        success_count = 0
        total_components = 4
        
        # 1. Initialize Motion Controller (don't fail if in alarm)
        try:
            self.logger.info("Initializing motion controller...")
            self.motion_controller = MotionControllerAdapter(self.config)
            
            if await self.motion_controller.initialize():
                self.motion_available = True
                success_count += 1
                
                # Check if homing is needed
                status = await self.motion_controller.get_status()
                if str(status) == "MotionStatus.ALARM":
                    self.logger.warning("⚠️ Motion controller in ALARM state")
                    self.logger.info("💡 Homing required - use web interface Home button")
                else:
                    self.logger.info("✅ Motion controller ready")
            else:
                self.logger.warning("⚠️ Motion controller not available")
                self.logger.info("💡 System will operate with limited functionality")
                
        except Exception as e:
            self.logger.error(f"Motion controller error: {e}")
            self.logger.info("💡 Continuing without motion control")
        
        # 2. Initialize Camera Controller (independent of motion)
        try:
            self.logger.info("Initializing camera controller...")
            self.camera_controller = PiCameraController(self.config)
            
            if await self.camera_controller.initialize():
                self.cameras_available = True
                success_count += 1
                self.logger.info("✅ Cameras initialized")
            else:
                self.logger.warning("⚠️ Cameras not available")
                
        except Exception as e:
            self.logger.error(f"Camera controller error: {e}")
        
        # 3. Initialize Lighting Controller
        try:
            self.logger.info("Initializing lighting controller...")
            
            # Check if in simulation mode
            if self.config.get_system_config().get('simulation_mode', False):
                self.lighting_controller = MockLEDController(self.config)
            else:
                # Try real GPIO controller
                try:
                    from lighting.gpio_led_controller import GPIOLEDController
                    self.lighting_controller = GPIOLEDController(self.config)
                except ImportError:
                    self.logger.warning("GPIO not available, using mock controller")
                    self.lighting_controller = MockLEDController(self.config)
            
            if await self.lighting_controller.initialize():
                success_count += 1
                self.logger.info("✅ Lighting controller initialized")
            else:
                self.logger.warning("⚠️ Lighting controller not available")
                
        except Exception as e:
            self.logger.error(f"Lighting controller error: {e}")
        
        # 4. Initialize Storage Manager
        try:
            self.logger.info("Initializing storage manager...")
            self.storage_manager = LocalStorageManager(self.config)
            
            if await self.storage_manager.initialize():
                success_count += 1
                self.logger.info("✅ Storage manager initialized")
            else:
                self.logger.warning("⚠️ Storage manager not available")
                
        except Exception as e:
            self.logger.error(f"Storage manager error: {e}")
        
        # Summary
        self.initialized = success_count > 0
        
        if self.initialized:
            self.logger.info(f"✅ Orchestrator initialized ({success_count}/{total_components} components)")
            
            if not self.motion_available:
                self.logger.warning("⚠️ Motion control unavailable - limited functionality")
            if not self.cameras_available:
                self.logger.warning("⚠️ Cameras unavailable - no image capture")
        else:
            self.logger.error("❌ Orchestrator initialization failed")
        
        return self.initialized
    
    async def shutdown(self) -> None:
        """Shutdown all components gracefully."""
        self.logger.info("Shutting down scan orchestrator...")
        
        # Shutdown in reverse order
        if self.storage_manager:
            await self.storage_manager.shutdown()
            
        if self.lighting_controller:
            await self.lighting_controller.shutdown()
            
        if self.camera_controller:
            await self.camera_controller.shutdown()
            
        if self.motion_controller:
            await self.motion_controller.shutdown()
        
        self.initialized = False
        self.logger.info("✅ Orchestrator shutdown complete")
    
    async def home_system(self) -> bool:
        """Home the motion system."""
        if not self.motion_available:
            self.logger.error("Motion controller not available")
            return False
        
        try:
            self.logger.info("Starting homing sequence...")
            success = await self.motion_controller.home()
            
            if success:
                self.logger.info("✅ Homing completed successfully")
            else:
                self.logger.error("❌ Homing failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Homing error: {e}")
            return False
    
    async def capture_single_image(self, position: Optional[Position4D] = None) -> Dict[str, Any]:
        """Capture a single image at current or specified position."""
        result = {
            'success': False,
            'position': None,
            'images': None,
            'error': None
        }
        
        try:
            # Move to position if specified
            if position and self.motion_available:
                self.logger.info(f"Moving to position {position}")
                if not await self.motion_controller.move_to_position(position):
                    result['error'] = "Failed to move to position"
                    return result
                    
                # Wait for motion to complete
                await self.motion_controller.wait_for_motion_complete()
            
            # Get current position
            if self.motion_available:
                result['position'] = self.motion_controller.get_position()
            
            # Capture images
            if self.cameras_available:
                self.logger.info("Capturing images...")
                
                # Turn on lights
                if self.lighting_controller:
                    await self.lighting_controller.set_brightness(0.5)  # 50% brightness
                
                # Capture
                capture_result = await self.camera_controller.capture_single()
                
                # Turn off lights
                if self.lighting_controller:
                    await self.lighting_controller.set_brightness(0.0)
                
                if capture_result.success:
                    result['success'] = True
                    result['images'] = {
                        'camera_0': capture_result.images.get('camera_0'),
                        'camera_1': capture_result.images.get('camera_1')
                    }
                else:
                    result['error'] = f"Capture failed: {capture_result.error}"
            else:
                result['error'] = "Cameras not available"
                
        except Exception as e:
            self.logger.error(f"Capture error: {e}")
            result['error'] = str(e)
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        status = {
            'initialized': self.initialized,
            'motion_available': self.motion_available,
            'cameras_available': self.cameras_available,
            'motion_status': None,
            'motion_position': None,
            'motion_homed': False
        }
        
        if self.motion_available and self.motion_controller:
            try:
                # Get motion status synchronously
                loop = asyncio.get_event_loop()
                status['motion_status'] = loop.run_until_complete(
                    self.motion_controller.get_status()
                )
                status['motion_position'] = self.motion_controller.get_position()
                status['motion_homed'] = self.motion_controller.is_homed()
            except:
                pass
        
        return status