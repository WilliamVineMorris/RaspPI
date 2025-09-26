#!/usr/bin/env python3
"""
Cylindrical Scanning Example

This script demonstrates how to perform cylindrical scanning with multiple
height passes at different Y positions, rotating the object (Z-axis) while
maintaining optimal camera positions.

The cylindrical scan pattern is ideal for objects that can be rotated on a
turntable, providing comprehensive coverage through systematic rotation
and height variation.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# Add the current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.events import EventBus
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import CylindricalPatternParameters, CylindricalScanPattern

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CylindricalScanDemo:
    """Demonstration of cylindrical scanning functionality"""
    
    def __init__(self):
        self.orchestrator = None
        self.config_manager = None
        self.event_bus = EventBus()
        
    async def initialize(self):
        """Initialize the scanning system"""
        logger.info("🔧 Initializing cylindrical scan demo...")
        
        try:
            # Initialize configuration
            config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
            self.config_manager = ConfigManager(config_file)
            
            # Initialize orchestrator (no event_bus parameter)
            self.orchestrator = ScanOrchestrator(
                config_manager=self.config_manager
            )
            
            # Initialize hardware components
            await self.orchestrator.initialize()
            logger.info("✅ System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize system: {e}")
            return False
    
    def create_basic_cylindrical_pattern(self) -> CylindricalScanPattern:
        """
        Create a basic cylindrical scan pattern
        
        This creates a simple cylindrical pattern with:
        - Multiple height levels (Y-axis)
        - Full 360° rotation (Z-axis) 
        - Fixed camera position (X-axis)
        - Multiple camera angles (C-axis)
        """
        logger.info("📐 Creating basic cylindrical scan pattern...")
        
        # Define scan parameters
        parameters = CylindricalPatternParameters(
            # Horizontal camera position (fixed for basic scan)
            x_start=0.0,    # Center position
            x_end=0.0,      # No X movement for basic scan
            x_step=1.0,     # Not used when start=end
            
            # Vertical scanning heights
            y_start=50.0,   # Start height (mm)
            y_end=150.0,    # End height (mm)  
            y_step=25.0,    # Height increment (mm) -> 5 levels
            
            # Turntable rotation
            z_rotations=[0, 45, 90, 135, 180, 225, 270, 315],  # 8 angles
            
            # Camera pivot angles
            c_angles=[-15, 0, 15],  # 3 camera angles
            
            # Scanning parameters
            overlap_percentage=30.0,
            max_feedrate=800.0,
            safety_margin=0.5
        )
        
        pattern_id = f"basic_cylindrical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pattern = CylindricalScanPattern(pattern_id, parameters)
        
        # Log pattern info
        points = pattern.get_points()
        duration = pattern.estimated_duration
        
        logger.info(f"📊 Pattern created:")
        logger.info(f"   • Total scan points: {len(points)}")
        logger.info(f"   • Height levels: {len(list(range(int(parameters.y_start), int(parameters.y_end) + 1, int(parameters.y_step))))}")
        logger.info(f"   • Rotation angles: {len(parameters.z_rotations or [])}")
        logger.info(f"   • Camera angles: {len(parameters.c_angles or [])}")
        logger.info(f"   • Estimated duration: {duration:.1f} minutes")
        
        return pattern
    
    def create_advanced_cylindrical_pattern(self) -> CylindricalScanPattern:
        """
        Create an advanced cylindrical scan pattern
        
        This creates a more comprehensive pattern with:
        - Multiple X positions for different radii
        - Dense height coverage
        - High angular resolution
        - Multiple camera perspectives
        """
        logger.info("📐 Creating advanced cylindrical scan pattern...")
        
        # Define scan parameters
        parameters = CylindricalPatternParameters(
            # Multiple horizontal positions (different radii)
            x_start=-30.0,  # Closer to object
            x_end=30.0,     # Further from object
            x_step=20.0,    # Step between positions -> 4 positions
            
            # Dense vertical coverage
            y_start=20.0,   # Lower start
            y_end=180.0,    # Higher end
            y_step=20.0,    # Smaller steps -> 9 levels
            
            # High angular resolution
            z_rotations=list(range(0, 360, 30)),  # Every 30° -> 12 angles
            
            # Multiple camera perspectives
            c_angles=[-20, -10, 0, 10, 20],  # 5 camera angles
            
            # Quality parameters
            overlap_percentage=40.0,  # Higher overlap
            max_feedrate=600.0,       # Slower for precision
            safety_margin=1.0         # Larger safety margin
        )
        
        pattern_id = f"advanced_cylindrical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pattern = CylindricalScanPattern(pattern_id, parameters)
        
        # Log pattern info
        points = pattern.get_points()
        duration = pattern.estimated_duration
        
        logger.info(f"📊 Advanced pattern created:")
        logger.info(f"   • Total scan points: {len(points)}")
        logger.info(f"   • X positions: {len(list(range(int(parameters.x_start), int(parameters.x_end) + 1, int(parameters.x_step))))}")
        logger.info(f"   • Height levels: {len(list(range(int(parameters.y_start), int(parameters.y_end) + 1, int(parameters.y_step))))}")
        logger.info(f"   • Rotation angles: {len(parameters.z_rotations or [])}")
        logger.info(f"   • Camera angles: {len(parameters.c_angles or [])}")
        logger.info(f"   • Estimated duration: {duration:.1f} minutes")
        
        return pattern
    
    def create_custom_cylindrical_pattern(self, 
                                        radius_range: tuple[float, float] = (-25.0, 25.0),
                                        height_range: tuple[float, float] = (40.0, 160.0),
                                        height_steps: int = 6,
                                        rotation_steps: int = 16,
                                        camera_angles: Optional[List[float]] = None) -> CylindricalScanPattern:
        """
        Create a custom cylindrical scan pattern
        
        Args:
            radius_range: (min_x, max_x) range for camera positions
            height_range: (min_y, max_y) range for scan heights
            height_steps: Number of height levels
            rotation_steps: Number of rotation angles (360°/steps)
            camera_angles: List of camera pivot angles (default: [-15, 0, 15])
        """
        logger.info("📐 Creating custom cylindrical scan pattern...")
        
        # Calculate step sizes
        if radius_range[0] == radius_range[1]:
            x_step = 1.0  # Single position
        else:
            x_step = (radius_range[1] - radius_range[0]) / max(1, height_steps - 1)
            
        y_step = (height_range[1] - height_range[0]) / max(1, height_steps - 1)
        z_step = 360.0 / rotation_steps
        
        # Default camera angles if not provided
        if camera_angles is None:
            camera_angles = [-15, 0, 15]
        
        # Create rotation angles
        z_rotations = [i * z_step for i in range(rotation_steps)]
        
        parameters = CylindricalPatternParameters(
            x_start=radius_range[0],
            x_end=radius_range[1],
            x_step=x_step,
            y_start=height_range[0],
            y_end=height_range[1],
            y_step=y_step,
            z_rotations=z_rotations,
            c_angles=camera_angles,
            overlap_percentage=35.0,
            max_feedrate=700.0,
            safety_margin=0.8
        )
        
        pattern_id = f"custom_cylindrical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pattern = CylindricalScanPattern(pattern_id, parameters)
        
        # Log pattern info
        points = pattern.get_points()
        duration = pattern.estimated_duration
        
        logger.info(f"📊 Custom pattern created:")
        logger.info(f"   • Radius range: {radius_range[0]:.1f} to {radius_range[1]:.1f} mm")
        logger.info(f"   • Height range: {height_range[0]:.1f} to {height_range[1]:.1f} mm")
        logger.info(f"   • Height levels: {height_steps}")
        logger.info(f"   • Rotation steps: {rotation_steps} ({z_step:.1f}° each)")
        logger.info(f"   • Camera angles: {camera_angles}")
        logger.info(f"   • Total scan points: {len(points)}")
        logger.info(f"   • Estimated duration: {duration:.1f} minutes")
        
        return pattern
    
    async def execute_cylindrical_scan(self, pattern: CylindricalScanPattern, scan_name: str = "cylindrical_scan"):
        """Execute a cylindrical scan pattern"""
        
        # Create output directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(f"scans/{scan_name}_{timestamp}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🚀 Starting cylindrical scan: {scan_name}")
        logger.info(f"📁 Output directory: {output_dir}")
        
        try:
            # Start the scan
            scan_state = await self.orchestrator.start_scan(
                pattern=pattern,
                output_directory=output_dir,
                scan_id=f"{scan_name}_{timestamp}"
            )
            
            logger.info(f"📸 Scan started with ID: {scan_state.scan_id}")
            
            # Monitor scan progress
            while True:
                status = self.orchestrator.get_scan_status()
                if not status:
                    break
                    
                logger.info(f"📊 Progress: {status['progress_percentage']:.1f}% "
                          f"({status['completed_points']}/{status['total_points']} points)")
                
                if status['status'] in ['completed', 'failed', 'cancelled']:
                    break
                    
                await asyncio.sleep(5)  # Update every 5 seconds
                
            # Final status
            final_status = self.orchestrator.get_scan_status()
            if final_status and final_status['status'] == 'completed':
                logger.info(f"✅ Scan completed successfully!")
                logger.info(f"📈 Final statistics:")
                logger.info(f"   • Total points: {final_status['total_points']}")
                logger.info(f"   • Images captured: {final_status.get('images_captured', 'N/A')}")
                logger.info(f"   • Duration: {final_status.get('duration', 'N/A'):.1f} minutes")
            else:
                logger.error(f"❌ Scan failed or was cancelled")
                
        except Exception as e:
            logger.error(f"❌ Scan execution failed: {e}")
            if self.orchestrator:
                await self.orchestrator.stop_scan()
    
    async def demo_basic_scan(self):
        """Demonstrate basic cylindrical scanning"""
        logger.info("🎯 === BASIC CYLINDRICAL SCAN DEMO ===")
        
        pattern = self.create_basic_cylindrical_pattern()
        await self.execute_cylindrical_scan(pattern, "basic_cylindrical")
    
    async def demo_advanced_scan(self):
        """Demonstrate advanced cylindrical scanning"""
        logger.info("🎯 === ADVANCED CYLINDRICAL SCAN DEMO ===")
        
        pattern = self.create_advanced_cylindrical_pattern()
        await self.execute_cylindrical_scan(pattern, "advanced_cylindrical")
    
    async def demo_custom_scan(self):
        """Demonstrate custom cylindrical scanning"""
        logger.info("🎯 === CUSTOM CYLINDRICAL SCAN DEMO ===")
        
        # Custom scan for medium-sized object
        pattern = self.create_custom_cylindrical_pattern(
            radius_range=(-20.0, 20.0),     # Moderate radius range
            height_range=(30.0, 120.0),     # Medium height range
            height_steps=4,                  # 4 height levels
            rotation_steps=12,               # Every 30 degrees
            camera_angles=[-10, 5, 20]      # Asymmetric camera angles
        )
        
        await self.execute_cylindrical_scan(pattern, "custom_cylindrical")

    async def cleanup(self):
        """Clean up resources"""
        if self.orchestrator:
            await self.orchestrator.shutdown()
        logger.info("🧹 Cleanup completed")

async def main():
    """Main demonstration function"""
    logger.info("🔄 Starting Cylindrical Scanning Demo")
    
    demo = CylindricalScanDemo()
    
    try:
        # Initialize system
        if not await demo.initialize():
            logger.error("Failed to initialize system")
            return 1
        
        # Choose which demo to run
        print("\n" + "="*60)
        print("CYLINDRICAL SCANNING DEMO OPTIONS")
        print("="*60)
        print("1. Basic Cylindrical Scan (simple, fast)")
        print("2. Advanced Cylindrical Scan (comprehensive)")
        print("3. Custom Cylindrical Scan (configurable)")
        print("4. All Demos (sequential)")
        print("="*60)
        
        choice = input("\nSelect demo (1-4) [1]: ").strip() or "1"
        
        if choice == "1":
            await demo.demo_basic_scan()
        elif choice == "2":
            await demo.demo_advanced_scan()
        elif choice == "3":
            await demo.demo_custom_scan()
        elif choice == "4":
            await demo.demo_basic_scan()
            await asyncio.sleep(2)
            await demo.demo_advanced_scan()
            await asyncio.sleep(2)
            await demo.demo_custom_scan()
        else:
            logger.warning("Invalid choice, running basic demo")
            await demo.demo_basic_scan()
            
    except KeyboardInterrupt:
        logger.info("🛑 Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        return 1
    finally:
        await demo.cleanup()
    
    logger.info("✅ Cylindrical Scanning Demo completed")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)