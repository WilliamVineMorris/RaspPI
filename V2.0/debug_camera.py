#!/usr/bin/env python3
"""
Camera Capture Diagnostic Tool

Test camera capture and JPEG generation independently
to isolate image corruption issues.

Usage:
    python debug_camera.py
    python debug_camera.py --test-mock
    python debug_camera.py --test-real

Author: Scanner System Development
Created: September 2025
"""

import sys
import asyncio
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from camera.pi_camera_controller import PiCameraController
from camera.base import CameraSettings, ImageFormat
from core.config_manager import ConfigManager


def analyze_image_file(file_path: Path):
    """Analyze image file for corruption"""
    print(f"\n🔍 Analyzing Image File: {file_path}")
    
    if not file_path.exists():
        print(f"   ❌ File does not exist")
        return False
    
    # Check file size
    file_size = file_path.stat().st_size
    print(f"   📏 File size: {file_size} bytes")
    
    if file_size == 0:
        print(f"   ❌ File is empty")
        return False
    
    # Read first few bytes to check format
    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)
        
        print(f"   🔗 File header: {header.hex() if header else 'empty'}")
        
        # Check for JPEG magic bytes
        if header.startswith(b'\xff\xd8'):
            print(f"   ✅ Valid JPEG header detected")
            
            # Check for JPEG end marker
            with open(file_path, 'rb') as f:
                content = f.read()
            
            if content.endswith(b'\xff\xd9'):
                print(f"   ✅ Valid JPEG end marker detected")
                return True
            else:
                print(f"   ⚠️  Missing JPEG end marker")
                return False
        else:
            print(f"   ❌ Invalid JPEG header")
            
            # Try to identify what format it might be
            if header.startswith(b'\x89PNG'):
                print(f"   ℹ️  Appears to be PNG format")
            elif header.startswith(b'BM'):
                print(f"   ℹ️  Appears to be BMP format")
            elif header.startswith(b'GIF'):
                print(f"   ℹ️  Appears to be GIF format")
            else:
                print(f"   ❓ Unknown image format")
            
            return False
            
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        return False


async def test_mock_camera():
    """Test mock camera capture"""
    print(f"\n🧪 Testing Mock Camera Capture")
    print("=" * 40)
    
    # Create mock config
    mock_config = {
        'camera_1': {
            'port': 0,
            'resolution': [640, 480],
            'name': 'test_camera'
        }
    }
    
    # Initialize mock camera controller
    from scanning.scan_orchestrator import MockCameraManager
    import tempfile
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        # Write complete YAML config with required system fields
        f.write("system:\n")
        f.write("  name: Test Scanner\n")
        f.write("  debug_mode: false\n")
        f.write("  simulation_mode: true\n")
        f.write("  log_level: INFO\n")
        f.write("platform:\n")
        f.write("  type: test\n")
        f.write("motion:\n")
        f.write("  controller:\n")
        f.write("    type: mock\n")
        f.write("    port: /dev/null\n")
        f.write("lighting:\n")
        f.write("  zones:\n")
        f.write("    zone_1:\n")
        f.write("      type: led_array\n")
        f.write("      pin: 18\n")
        f.write("      count: 60\n")
        f.write("cameras:\n")
        for cam_name, cam_config in mock_config.items():
            f.write(f"  {cam_name}:\n")
            f.write(f"    port: {cam_config['port']}\n")
            f.write(f"    resolution: {cam_config['resolution']}\n")
            f.write(f"    name: {cam_config['name']}\n")
        temp_config_file = f.name
    
    try:
        config_manager = ConfigManager(temp_config_file)
        mock_camera = MockCameraManager(config_manager)
        
        # Test capture using the mock camera's capture_all method
        test_output_dir = Path("/tmp/test_mock_capture")
        test_output_dir.mkdir(exist_ok=True)
        
        print(f"   📸 Capturing mock images to: {test_output_dir}")
        
        try:
            results = await mock_camera.capture_all(
                test_output_dir, 
                "test_capture", 
                {"test": True}
            )
            print(f"   📤 Capture results: {len(results)} files")
            
            for result in results:
                if result['success']:
                    file_path = Path(result['filepath'])
                    print(f"      📁 Generated: {file_path.name}")
                    analyze_image_file(file_path)
                else:
                    print(f"      ❌ Failed: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            print(f"   ❌ Mock capture error: {e}")
        
        finally:
            # Cleanup
            if test_output_dir.exists():
                for file in test_output_dir.glob("*"):
                    file.unlink()
                test_output_dir.rmdir()
    
    finally:
        # Cleanup temp config
        Path(temp_config_file).unlink()


async def test_real_camera():
    """Test real Pi camera capture"""
    print(f"\n🧪 Testing Real Pi Camera Capture")
    print("=" * 40)
    
    try:
        # Check if cameras are available
        config = {
            'camera_1': {
                'port': 0,
                'resolution': [1920, 1080],
                'name': 'real_camera'
            }
        }
        
        camera_controller = PiCameraController(config)
        
        # Initialize
        success = await camera_controller.initialize()
        if not success:
            print(f"   ❌ Failed to initialize camera controller")
            return
        
        print(f"   ✅ Camera controller initialized")
        
        # Test capture
        test_output = Path("/tmp/test_real_capture.jpg")
        settings = CameraSettings(
            resolution=(1920, 1080),
            format=ImageFormat.JPEG,
            quality=85
        )
        
        print(f"   📸 Capturing real image to: {test_output}")
        
        success = await camera_controller.capture_image(0, settings, test_output)
        print(f"   📤 Capture result: {'✅ Success' if success else '❌ Failed'}")
        
        if success and test_output.exists():
            analyze_image_file(test_output)
        
        # Shutdown
        await camera_controller.shutdown()
        
    except Exception as e:
        print(f"   ❌ Real camera test error: {e}")
        import traceback
        traceback.print_exc()


async def find_corrupt_images(directory: Path):
    """Find and analyze corrupt images in directory"""
    print(f"\n🔍 Scanning for corrupt images in: {directory}")
    
    if not directory.exists():
        print(f"   ❌ Directory does not exist")
        return
    
    image_files = []
    for pattern in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(directory.glob(pattern))
    
    if not image_files:
        print(f"   ℹ️  No image files found")
        return
    
    print(f"   📁 Found {len(image_files)} image files")
    
    corrupt_count = 0
    for img_file in image_files:
        if not analyze_image_file(img_file):
            corrupt_count += 1
    
    print(f"\n📊 Analysis Summary:")
    print(f"   Total files: {len(image_files)}")
    print(f"   Corrupt files: {corrupt_count}")
    print(f"   Healthy files: {len(image_files) - corrupt_count}")


async def main():
    """Main diagnostic function"""
    print("📷 Camera Capture Diagnostic Tool")
    print("=" * 50)
    
    if '--test-mock' in sys.argv:
        await test_mock_camera()
    elif '--test-real' in sys.argv:
        await test_real_camera()
    elif '--analyze' in sys.argv:
        if len(sys.argv) > sys.argv.index('--analyze') + 1:
            directory = Path(sys.argv[sys.argv.index('--analyze') + 1])
            await find_corrupt_images(directory)
        else:
            print("Usage: python debug_camera.py --analyze /path/to/directory")
    else:
        # Run all tests
        await test_mock_camera()
        
        # Try real camera if available
        try:
            await test_real_camera()
        except Exception as e:
            print(f"\n⚠️  Real camera test skipped: {e}")
        
        # Check for recent scan outputs
        scan_dirs = [
            Path("/tmp"),
            Path.cwd() / "test_output"
        ]
        
        for scan_dir in scan_dirs:
            if scan_dir.exists():
                recent_dirs = []
                for item in scan_dir.iterdir():
                    if item.is_dir() and any(x in item.name.lower() for x in ['scan', 'test', 'mock']):
                        recent_dirs.append(item)
                
                for recent_dir in recent_dirs[-3:]:  # Check last 3 recent dirs
                    await find_corrupt_images(recent_dir)


if __name__ == "__main__":
    asyncio.run(main())