#!/usr/bin/env python3
"""
Current Web Interface Validation Script

Tests the existing web interface implementation to ensure all current
features are working properly and all elements are implemented as intended.
"""

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(name)-15s | %(message)s'
)
logger = logging.getLogger("web_validation")

def test_web_interface_components():
    """Test that all web interface components are properly implemented"""
    logger.info("🔄 Testing Web Interface Components")
    
    try:
        # Test core web interface imports
        from web.web_interface import ScannerWebInterface
        logger.info("   ✅ Core web interface imports working")
        
        # Test Phase 5 enhancements
        from phase5_web_enhancements import enhance_web_interface
        logger.info("   ✅ Phase 5 enhancements imports working")
        
        # Test that templates exist
        templates_path = Path(__file__).parent / "web" / "templates"
        required_templates = ["base.html", "dashboard.html", "manual.html", "scans.html", "settings.html"]
        
        for template in required_templates:
            template_file = templates_path / template
            if not template_file.exists():
                logger.error(f"   ❌ Missing template: {template}")
                return False
            logger.info(f"   ✅ Template found: {template}")
        
        # Test that static files exist
        static_path = Path(__file__).parent / "web" / "static"
        required_static = ["css", "js"]
        
        for static_dir in required_static:
            static_directory = static_path / static_dir
            if not static_directory.exists():
                logger.error(f"   ❌ Missing static directory: {static_dir}")
                return False
            logger.info(f"   ✅ Static directory found: {static_dir}")
        
        # Test JavaScript files
        js_path = static_path / "js"
        required_js = ["scanner-base.js", "manual-control.js", "settings.js"]
        
        for js_file in required_js:
            js_file_path = js_path / js_file
            if not js_file_path.exists():
                logger.error(f"   ❌ Missing JavaScript file: {js_file}")
                return False
            logger.info(f"   ✅ JavaScript file found: {js_file}")
        
        return True
        
    except ImportError as e:
        logger.error(f"   ❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"   ❌ Component test failed: {e}")
        return False

def test_orchestrator_integration():
    """Test web interface integration with scan orchestrator"""
    logger.info("🔄 Testing Orchestrator Integration")
    
    try:
        # Test orchestrator imports
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        logger.info("   ✅ Orchestrator imports working")
        
        # Create mock configuration for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            test_config = """
system:
  simulation_mode: true

motion:
  fluidnc:
    port: '/dev/ttyUSB0'
    baud_rate: 115200
  axes:
    x: {type: 'linear', range: [0, 200]}
    y: {type: 'linear', range: [0, 200]}
    z: {type: 'rotational', range: [-180, 180]}
    c: {type: 'rotational', range: [-90, 90]}

cameras:
  camera_1: {port: 0, resolution: [1920, 1080]}
  camera_2: {port: 1, resolution: [1920, 1080]}

lighting:
  zones:
    zone_1: {gpio_pin: 18, name: 'Front Light'}
    zone_2: {gpio_pin: 19, name: 'Side Light'}
"""
            f.write(test_config)
            config_file = f.name
        
        # Test orchestrator creation
        config_manager = ConfigManager(config_file)
        orchestrator = ScanOrchestrator(config_manager)
        logger.info("   ✅ Orchestrator created successfully")
        
        # Test web interface with orchestrator
        from web.web_interface import ScannerWebInterface
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        logger.info("   ✅ Web interface created with orchestrator")
        
        # Test that Flask app was created
        if not hasattr(web_interface, 'app') or web_interface.app is None:
            logger.error("   ❌ Flask app not created")
            return False
        logger.info("   ✅ Flask app created")
        
        # Clean up
        Path(config_file).unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Orchestrator integration test failed: {e}")
        return False

def test_api_routes():
    """Test that all expected API routes are defined"""
    logger.info("🔄 Testing API Routes")
    
    try:
        from web.web_interface import ScannerWebInterface
        
        # Create web interface without orchestrator for route testing
        web_interface = ScannerWebInterface(orchestrator=None)
        app = web_interface.app
        
        # Expected API routes
        expected_routes = [
            '/api/status',
            '/api/move',
            '/api/position', 
            '/api/home',
            '/api/emergency_stop',
            '/api/scan/start',
            '/api/scan/stop',
            '/api/scan/pause',
            '/api/camera/capture',
            '/api/camera/controls',
            '/api/camera/autofocus',
            '/api/camera/focus',
            '/api/camera/stabilize',
            '/api/camera/white_balance',
            '/api/camera/status',
            '/api/lighting/flash'
        ]
        
        # Get all registered routes
        registered_routes = []
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/api/'):
                registered_routes.append(rule.rule)
        
        # Check each expected route
        missing_routes = []
        for route in expected_routes:
            if not any(registered_route.startswith(route) for registered_route in registered_routes):
                missing_routes.append(route)
            else:
                logger.info(f"   ✅ Route found: {route}")
        
        if missing_routes:
            logger.error(f"   ❌ Missing routes: {missing_routes}")
            return False
        
        logger.info(f"   ✅ All {len(expected_routes)} expected API routes found")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ API routes test failed: {e}")
        return False

def test_phase5_integration():
    """Test Phase 5 enhancement integration"""
    logger.info("🔄 Testing Phase 5 Integration")
    
    try:
        from web.web_interface import ScannerWebInterface
        from phase5_web_enhancements import enhance_web_interface
        
        # Create base web interface
        web_interface = ScannerWebInterface(orchestrator=None)
        logger.info("   ✅ Base web interface created")
        
        # Apply Phase 5 enhancements
        enhanced_interface = enhance_web_interface(web_interface)
        logger.info("   ✅ Phase 5 enhancements applied")
        
        # Check for Phase 5 routes
        phase5_routes = [
            '/api/files/browse',
            '/api/files/download',
            '/api/files/export',
            '/api/scan/queue',
            '/api/scan/queue/add',
            '/api/scan/queue/remove',
            '/api/scan/queue/clear',
            '/api/settings/get',
            '/api/settings/update',
            '/api/settings/backup',
            '/api/storage/sessions',
            '/api/storage/stats'
        ]
        
        # Get enhanced routes
        enhanced_routes = []
        for rule in enhanced_interface.app.url_map.iter_rules():
            if rule.rule.startswith('/api/'):
                enhanced_routes.append(rule.rule)
        
        # Check Phase 5 routes
        missing_phase5_routes = []
        for route in phase5_routes:
            if not any(enhanced_route.startswith(route) for enhanced_route in enhanced_routes):
                missing_phase5_routes.append(route)
            else:
                logger.info(f"   ✅ Phase 5 route found: {route}")
        
        if missing_phase5_routes:
            logger.error(f"   ❌ Missing Phase 5 routes: {missing_phase5_routes}")
            return False
        
        logger.info(f"   ✅ All {len(phase5_routes)} Phase 5 routes found")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Phase 5 integration test failed: {e}")
        return False

def test_configuration_validation():
    """Test configuration and setup validation"""
    logger.info("🔄 Testing Configuration Validation")
    
    try:
        # Test config manager
        from core.config_manager import ConfigManager
        
        # Create temporary config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
system:
  simulation_mode: true

motion:
  fluidnc:
    port: '/dev/ttyUSB0'
    baud_rate: 115200

cameras:
  camera_1: {port: 0}
  camera_2: {port: 1}
""")
            config_file = f.name
        
        # Test config loading
        config_manager = ConfigManager(config_file)
        logger.info("   ✅ Configuration manager working")
        
        # Test config access
        system_config = config_manager.get('system', {})
        if 'simulation_mode' not in system_config:
            logger.error("   ❌ System config access failed")
            return False
        logger.info("   ✅ System config access working")
        
        motion_config = config_manager.get('motion', {})
        if 'fluidnc' not in motion_config:
            logger.error("   ❌ Motion config access failed")
            return False
        logger.info("   ✅ Motion config access working")
        
        # Clean up
        Path(config_file).unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Configuration validation failed: {e}")
        return False

def run_validation_tests():
    """Run all validation tests"""
    logger.info("🚀 Web Interface Implementation Validation")
    logger.info("=" * 60)
    
    tests = [
        ("Web Interface Components", test_web_interface_components),
        ("Orchestrator Integration", test_orchestrator_integration),
        ("API Routes", test_api_routes),
        ("Phase 5 Integration", test_phase5_integration),
        ("Configuration Validation", test_configuration_validation)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                logger.info(f"✅ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1
        
        print()  # Add spacing
    
    # Summary
    logger.info("=" * 60)
    logger.info("📊 VALIDATION RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info(f"📈 Overall: {passed}/{len(tests)} tests passed ({passed/len(tests)*100:.1f}%)")
    
    if failed == 0:
        logger.info("🎉 ALL IMPLEMENTATION TESTS PASSED!")
        logger.info("✅ Web interface is properly implemented")
        logger.info("✅ All current elements working as intended")
        print("\n🚀 Ready to test with live web server!")
        print("   Run: python test_web_interface_comprehensive.py")
    else:
        logger.warning(f"⚠️  {failed} test(s) failed - implementation issues detected")
        logger.warning("❌ Some elements need attention")
    
    return failed == 0

if __name__ == "__main__":
    print("🧪 Web Interface Implementation Validation")
    print("Testing all current elements are implemented as intended...")
    print()
    
    success = run_validation_tests()
    
    if success:
        print("\n" + "=" * 60)
        print("🎯 NEXT STEPS:")
        print("1. Start the web server:")
        print("   python run_web_interface.py")
        print("   # or for enhanced interface:")
        print("   python demo_phase5_web_interface.py")
        print()
        print("2. Run comprehensive live tests:")
        print("   python test_web_interface_comprehensive.py")
        print()
        print("3. Access web interface:")
        print("   http://localhost:5000")
        print("=" * 60)
    
    sys.exit(0 if success else 1)