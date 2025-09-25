"""
Phase 2: Integrated System Orchestrator with Standardized Adapters

This orchestrator integrates all Phase 2 standardized adapters with explicit
support for Z-axis as rotational motion throughout the system.

Key Features:
- Standardized adapter integration
- Z-axis rotational motion coordination
- Cross-adapter communication
- Position-aware operations
- Safety-first design
- Event-driven coordination

Author: Scanner System Development - Phase 2
Created: September 2025
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from core.config_manager import ConfigManager
from core.events import EventBus, ScannerEvent, EventPriority
from core.logging_setup import setup_logging

# Import base controllers
from motion.fluidnc_controller import create_fluidnc_controller
from camera.pi_camera_controller import create_pi_camera_controller
from lighting.gpio_led_controller import create_lighting_controller

# Import Phase 2 adapters
from motion.adapter import create_motion_adapter, FluidNCMotionAdapter
from camera.adapter import create_camera_adapter, PiCameraAdapter
from lighting.adapter import create_lighting_adapter, PiGPIOLightingAdapter

# Import storage system
from storage.session_manager import SessionManager

# Import scanning components
from scanning.scan_orchestrator import MockStorageManager

from motion.base import Position4D


class Phase2SystemOrchestrator:
    """
    Phase 2 System Orchestrator with Standardized Adapters
    
    Integrates all system components using standardized adapter interfaces
    with explicit support for Z-axis rotational motion.
    """
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # Core systems
        self.config_manager: Optional[ConfigManager] = None
        self.event_bus: Optional[EventBus] = None
        
        # Base controllers
        self.motion_controller = None
        self.camera_controller = None
        self.lighting_controller = None
        
        # Phase 2 Adapters
        self.motion_adapter: Optional[FluidNCMotionAdapter] = None
        self.camera_adapter: Optional[PiCameraAdapter] = None
        self.lighting_adapter: Optional[PiGPIOLightingAdapter] = None
        
        # Storage system
        self.storage_manager: Optional[SessionManager] = None
        
        # System state
        self.is_initialized = False
        self.is_homed = False
        self.current_session = None
        
    async def initialize(self) -> bool:
        """
        Initialize all system components with Phase 2 adapters
        
        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("🚀 Starting Phase 2 System Initialization")
            
            # 1. Initialize core systems
            self.logger.info("Phase 2 - Step 1: Core Systems")
            if not await self._initialize_core_systems():
                return False
            
            # 2. Initialize base controllers
            self.logger.info("Phase 2 - Step 2: Base Controllers")
            if not await self._initialize_base_controllers():
                return False
            
            # 3. Initialize Phase 2 adapters
            self.logger.info("Phase 2 - Step 3: Standardized Adapters")
            if not await self._initialize_adapters():
                return False
            
            # 4. Cross-connect adapters
            self.logger.info("Phase 2 - Step 4: Adapter Cross-Connection")
            self._connect_adapters()
            
            # 5. Initialize storage system
            self.logger.info("Phase 2 - Step 5: Storage System")
            if not await self._initialize_storage():
                return False
            
            self.is_initialized = True
            self.logger.info("✅ Phase 2 System Initialization Complete")
            
            # Notify initialization complete
            await self.event_bus.emit(ScannerEvent(
                event_type="system.phase2_initialized",
                data={
                    "motion_adapter": type(self.motion_adapter).__name__,
                    "camera_adapter": type(self.camera_adapter).__name__,
                    "lighting_adapter": type(self.lighting_adapter).__name__,
                    "z_axis_rotational": True
                },
                source_module="phase2_orchestrator",
                priority=EventPriority.HIGH
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Phase 2 system initialization failed: {e}")
            return False
    
    async def _initialize_core_systems(self) -> bool:
        """Initialize core configuration and event systems"""
        try:
            # Configuration manager
            self.config_manager = ConfigManager(self.config_path)
            
            # Event bus
            self.event_bus = EventBus()
            
            self.logger.info("✅ Core systems initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Core systems initialization failed: {e}")
            return False
    
    async def _initialize_base_controllers(self) -> bool:
        """Initialize base hardware controllers"""
        try:
            # Motion controller (FluidNC)
            self.logger.info("Initializing FluidNC motion controller...")
            self.motion_controller = create_fluidnc_controller(self.config_manager)
            motion_init = await self.motion_controller.initialize()
            if not motion_init:
                self.logger.error("FluidNC controller initialization failed")
                return False
            
            # Camera controller (Pi Camera)
            self.logger.info("Initializing Pi camera controller...")
            self.camera_controller = create_pi_camera_controller(self.config_manager)
            camera_init = await self.camera_controller.initialize()
            if not camera_init:
                self.logger.error("Pi camera controller initialization failed")
                return False
            
            # Lighting controller (GPIO)
            self.logger.info("Initializing GPIO lighting controller...")
            lighting_config = self.config_manager.get('lighting', {})
            self.lighting_controller = create_lighting_controller(lighting_config)
            lighting_init = await self.lighting_controller.initialize()
            if not lighting_init:
                self.logger.error("GPIO lighting controller initialization failed")
                return False
            
            self.logger.info("✅ Base controllers initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Base controllers initialization failed: {e}")
            return False
    
    async def _initialize_adapters(self) -> bool:
        """Initialize Phase 2 standardized adapters"""
        try:
            motion_config = self.config_manager.get('motion', {})
            camera_config = self.config_manager.get('camera', {})
            lighting_config = self.config_manager.get('lighting', {})
            
            # Motion adapter with Z-axis rotational support
            self.logger.info("Creating motion adapter with Z-axis rotational support...")
            self.motion_adapter = create_motion_adapter(self.motion_controller, motion_config)
            motion_adapter_init = await self.motion_adapter.initialize_controller()
            if not motion_adapter_init:
                self.logger.error("Motion adapter initialization failed")
                return False
            
            # Log Z-axis configuration
            z_axis_info = self.motion_adapter.get_axis_info('z')
            if z_axis_info:
                self.logger.info(
                    f"✅ Z-axis configured as {z_axis_info.move_type.value} "
                    f"({z_axis_info.axis_type.value}) - continuous: {z_axis_info.continuous}"
                )
            
            # Camera adapter with motion coordination
            self.logger.info("Creating camera adapter with motion coordination...")
            self.camera_adapter = create_camera_adapter(self.camera_controller, camera_config)
            camera_adapter_init = await self.camera_adapter.initialize_controller()
            if not camera_adapter_init:
                self.logger.error("Camera adapter initialization failed")
                return False
            
            # Lighting adapter with safety measures
            self.logger.info("Creating lighting adapter with GPIO safety...")
            self.lighting_adapter = create_lighting_adapter(self.lighting_controller, lighting_config)
            lighting_adapter_init = await self.lighting_adapter.initialize_controller()
            if not lighting_adapter_init:
                self.logger.error("Lighting adapter initialization failed")
                return False
            
            self.logger.info("✅ Phase 2 adapters initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Adapter initialization failed: {e}")
            return False
    
    def _connect_adapters(self):
        """Cross-connect adapters for coordinated operations"""
        try:
            # Connect motion adapter to camera for position-aware captures
            if self.camera_adapter and self.motion_adapter:
                self.camera_adapter.set_motion_adapter(self.motion_adapter)
                self.logger.info("✅ Camera adapter connected to motion adapter")
            
            # Connect motion adapter to lighting for rotation tracking
            if self.lighting_adapter and self.motion_adapter:
                self.lighting_adapter.set_motion_adapter(self.motion_adapter)
                self.logger.info("✅ Lighting adapter connected to motion adapter")
            
            self.logger.info("✅ Adapter cross-connections established")
            
        except Exception as e:
            self.logger.error(f"Adapter cross-connection failed: {e}")
    
    async def _initialize_storage(self) -> bool:
        """Initialize storage system"""
        try:
            # Initialize storage manager
            storage_config = self.config_manager.get('storage', {})
            self.storage_manager = SessionManager(
                config=storage_config,
                event_bus=self.event_bus
            )
            
            storage_init = await self.storage_manager.initialize()
            if not storage_init:
                self.logger.error("Storage manager initialization failed")
                return False
            
            self.logger.info("✅ Storage system initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Storage initialization failed: {e}")
            return False
    
    async def home_system(self) -> bool:
        """
        Home the motion system with Z-axis awareness
        
        Returns:
            True if homing successful
        """
        try:
            if not self.is_initialized:
                self.logger.error("System not initialized")
                return False
            
            self.logger.info("🏠 Starting system homing with Z-axis rotational support")
            
            # Home using motion adapter
            result = await self.motion_adapter.home_axes()
            
            if result:
                self.is_homed = True
                self.logger.info("✅ System homing completed")
                
                # Get post-homing position
                position = await self.motion_adapter.get_current_position()
                self.logger.info(f"Home position: {position}")
                
                # Verify Z-axis understanding
                z_axis_info = self.motion_adapter.get_axis_info('z')
                if z_axis_info:
                    self.logger.info(
                        f"Z-axis operational: {z_axis_info.move_type.value} rotation, "
                        f"current angle: {position.z:.1f}°"
                    )
                
                # Notify homing complete
                await self.event_bus.emit(ScannerEvent(
                    event_type="motion.homing_completed",
                    data={
                        "home_position": position.to_dict(),
                        "z_axis_rotational": True,
                        "z_current_degrees": position.z
                    },
                    source_module="phase2_orchestrator",
                    priority=EventPriority.HIGH
                ))
            else:
                self.logger.error("System homing failed")
            
            return result
            
        except Exception as e:
            self.logger.error(f"System homing failed: {e}")
            return False
    
    async def start_scan_session(self, session_name: str) -> bool:
        """
        Start a new scanning session with Phase 2 capabilities
        
        Args:
            session_name: Name for the scanning session
            
        Returns:
            True if session started successfully
        """
        try:
            if not self.is_initialized or not self.is_homed:
                self.logger.error("System must be initialized and homed before scanning")
                return False
            
            self.logger.info(f"📸 Starting Phase 2 scan session: {session_name}")
            
            # Create session using storage manager
            session_metadata = {
                "phase": "Phase 2",
                "adapters": {
                    "motion": type(self.motion_adapter).__name__,
                    "camera": type(self.camera_adapter).__name__,
                    "lighting": type(self.lighting_adapter).__name__
                },
                "z_axis_rotational": True,
                "position_aware_capture": True,
                "safety_enabled": True
            }
            
            self.current_session = await self.storage_manager.create_session(
                session_name, 
                session_metadata
            )
            
            if self.current_session:
                self.logger.info(f"✅ Scan session created: {self.current_session.session_id}")
                return True
            else:
                self.logger.error("Failed to create scan session")
                return False
                
        except Exception as e:
            self.logger.error(f"Scan session creation failed: {e}")
            return False
    
    async def capture_at_rotation(self, z_degrees: float, capture_settings: Dict[str, Any]) -> bool:
        """
        Capture images at specific Z rotation with full Phase 2 coordination
        
        Args:
            z_degrees: Target Z rotation in degrees
            capture_settings: Camera capture settings
            
        Returns:
            True if capture successful
        """
        try:
            if not self.current_session:
                self.logger.error("No active scan session")
                return False
            
            self.logger.info(f"📸 Phase 2 capture at Z={z_degrees:.1f}°")
            
            # Get current position for X,Y,C coordinates
            current_pos = await self.motion_adapter.get_current_position()
            target_pos = Position4D(
                x=current_pos.x,
                y=current_pos.y,
                z=z_degrees,
                c=current_pos.c
            )
            
            # Enable position-based lighting
            await self.lighting_adapter.set_lighting_for_position(target_pos, intensity=0.8)
            
            # Move to target rotation and capture
            from camera.base import CameraSettings, ImageFormat
            camera_settings = CameraSettings(
                resolution=capture_settings.get('resolution', (1920, 1080)),
                format=ImageFormat.JPEG,
                quality=capture_settings.get('quality', 95)
            )
            
            # Execute position-aware capture with lighting coordination
            capture_result = await self.camera_adapter.capture_at_position(
                target_pos, 
                camera_settings,
                flash_enabled=True
            )
            
            if capture_result and capture_result.capture_result.success:
                # Store capture in session
                await self.storage_manager.store_capture_result(
                    self.current_session.session_id,
                    capture_result.capture_result,
                    {
                        "z_rotation_degrees": z_degrees,
                        "actual_position": capture_result.actual_position.to_dict(),
                        "phase2_capture": True,
                        "timing_accuracy_ms": capture_result.timing_accuracy
                    }
                )
                
                self.logger.info(f"✅ Capture completed at Z={z_degrees:.1f}°")
                return True
            else:
                self.logger.error(f"Capture failed at Z={z_degrees:.1f}°")
                return False
                
        except Exception as e:
            self.logger.error(f"Rotation capture failed: {e}")
            return False
    
    async def perform_360_scan(self, step_degrees: float = 10.0) -> bool:
        """
        Perform 360-degree rotational scan with Phase 2 coordination
        
        Args:
            step_degrees: Angular step between captures
            
        Returns:
            True if scan completed successfully
        """
        try:
            if not self.current_session:
                self.logger.error("No active scan session")
                return False
            
            self.logger.info(f"🔄 Starting 360° Phase 2 scan (step: {step_degrees}°)")
            
            # Calculate capture positions
            capture_angles = []
            current_angle = 0.0
            while current_angle < 360.0:
                capture_angles.append(current_angle)
                current_angle += step_degrees
            
            self.logger.info(f"Planned {len(capture_angles)} captures")
            
            # Perform captures at each angle
            successful_captures = 0
            for i, angle in enumerate(capture_angles):
                self.logger.info(f"Capture {i+1}/{len(capture_angles)} at {angle:.1f}°")
                
                capture_settings = {
                    'resolution': (1920, 1080),
                    'quality': 95
                }
                
                if await self.capture_at_rotation(angle, capture_settings):
                    successful_captures += 1
                else:
                    self.logger.warning(f"Failed capture at {angle:.1f}°")
                
                # Small delay between captures
                await asyncio.sleep(0.5)
            
            success_rate = successful_captures / len(capture_angles) * 100
            self.logger.info(
                f"✅ 360° scan completed: {successful_captures}/{len(capture_angles)} "
                f"successful ({success_rate:.1f}%)"
            )
            
            return success_rate > 80.0  # Consider successful if >80% captures worked
            
        except Exception as e:
            self.logger.error(f"360° scan failed: {e}")
            return False
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive Phase 2 system status"""
        try:
            status = {
                "phase": "Phase 2",
                "initialized": self.is_initialized,
                "homed": self.is_homed,
                "active_session": self.current_session.session_id if self.current_session else None,
                "adapters": {},
                "z_axis_status": {}
            }
            
            if self.motion_adapter:
                motion_status = await self.motion_adapter.get_motion_status()
                position = await self.motion_adapter.get_current_position()
                z_axis_info = self.motion_adapter.get_axis_info('z')
                
                status["adapters"]["motion"] = {
                    "type": type(self.motion_adapter).__name__,
                    "status": motion_status.value if motion_status else "unknown",
                    "current_position": position.to_dict() if position else None
                }
                
                if z_axis_info:
                    status["z_axis_status"] = {
                        "type": z_axis_info.axis_type.value,
                        "move_type": z_axis_info.move_type.value,
                        "continuous": z_axis_info.continuous,
                        "current_degrees": position.z if position else 0.0,
                        "limits": {
                            "min": z_axis_info.limits.min_limit,
                            "max": z_axis_info.limits.max_limit
                        }
                    }
            
            if self.camera_adapter:
                camera_status = await self.camera_adapter.get_camera_status()
                status["adapters"]["camera"] = {
                    "type": type(self.camera_adapter).__name__,
                    "status": camera_status
                }
            
            if self.lighting_adapter:
                lighting_status = await self.lighting_adapter.get_lighting_status()
                status["adapters"]["lighting"] = {
                    "type": type(self.lighting_adapter).__name__,
                    "status": lighting_status
                }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get system status: {e}")
            return {"error": str(e)}
    
    async def shutdown(self) -> bool:
        """Shutdown all Phase 2 system components"""
        try:
            self.logger.info("🔄 Starting Phase 2 system shutdown")
            
            # Stop any active lighting
            if self.lighting_adapter:
                await self.lighting_adapter.stop_rotation_tracking()
                await self.lighting_adapter.shutdown_controller()
            
            # Shutdown adapters
            if self.camera_adapter:
                await self.camera_adapter.shutdown_controller()
            
            if self.motion_adapter:
                await self.motion_adapter.shutdown_controller()
            
            # Close session if active
            if self.current_session and self.storage_manager:
                await self.storage_manager.close_session(self.current_session.session_id)
            
            # Shutdown storage
            if self.storage_manager:
                await self.storage_manager.shutdown()
            
            self.logger.info("✅ Phase 2 system shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Phase 2 system shutdown failed: {e}")
            return False


# Demo function for Phase 2 testing
async def demo_phase2_system():
    """Demo function to test Phase 2 system with Z-axis rotational support"""
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Phase 2 System Demo")
    
    # Initialize system
    config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
    orchestrator = Phase2SystemOrchestrator(config_path)
    
    try:
        # Initialize
        if not await orchestrator.initialize():
            logger.error("System initialization failed")
            return False
        
        # Home system
        if not await orchestrator.home_system():
            logger.error("System homing failed")
            return False
        
        # Get system status
        status = await orchestrator.get_system_status()
        logger.info(f"System Status: {status}")
        
        # Start scan session
        if not await orchestrator.start_scan_session("phase2_demo"):
            logger.error("Scan session creation failed")
            return False
        
        # Test single rotation capture
        logger.info("Testing single rotation capture...")
        if await orchestrator.capture_at_rotation(45.0, {'resolution': (1920, 1080)}):
            logger.info("✅ Single rotation capture successful")
        
        # Test partial rotational scan
        logger.info("Testing partial rotational scan...")
        if await orchestrator.perform_360_scan(step_degrees=30.0):  # 12 captures
            logger.info("✅ Partial rotational scan successful")
        
        logger.info("✅ Phase 2 System Demo Completed Successfully")
        return True
        
    except Exception as e:
        logger.error(f"Phase 2 demo failed: {e}")
        return False
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    import sys
    
    # Run demo
    success = asyncio.run(demo_phase2_system())
    sys.exit(0 if success else 1)