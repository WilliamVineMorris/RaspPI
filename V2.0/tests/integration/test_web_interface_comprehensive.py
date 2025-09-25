#!/usr/bin/env python3
"""
Comprehensive Web Interface Testing Suite

Tests all current web interface features to ensure proper operation
and validates that all implemented elements work as intended.
"""

import asyncio
import json
import logging
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(name)-15s | %(message)s'
)
logger = logging.getLogger("web_test")

class WebInterfaceValidator:
    """Comprehensive web interface testing and validation"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        
    def run_test(self, test_name: str, test_func, *args, **kwargs) -> bool:
        """Run individual test with error handling"""
        try:
            logger.info(f"🔄 Running {test_name}...")
            result = test_func(*args, **kwargs)
            if result:
                logger.info(f"✅ {test_name} PASSED")
                self.test_results.append((test_name, True, None))
                return True
            else:
                logger.error(f"❌ {test_name} FAILED - Test returned False")
                self.test_results.append((test_name, False, "Test returned False"))
                return False
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED - {e}")
            self.test_results.append((test_name, False, str(e)))
            return False

    def api_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, timeout=10)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    # =====================================
    # CORE WEB INTERFACE TESTS
    # =====================================

    def test_web_pages_accessible(self) -> bool:
        """Test that all main web pages are accessible"""
        pages = ['/', '/manual', '/scans', '/settings']
        
        for page in pages:
            try:
                response = self.session.get(f"{self.base_url}{page}", timeout=10)
                if response.status_code != 200:
                    logger.error(f"Page {page} returned status {response.status_code}")
                    return False
                logger.info(f"   ✓ Page {page} accessible")
            except Exception as e:
                logger.error(f"Page {page} failed: {e}")
                return False
        
        return True

    def test_system_status_api(self) -> bool:
        """Test system status API endpoint"""
        try:
            data = self.api_request('/api/status')
            
            # Validate required fields
            required_fields = ['system', 'motion', 'cameras', 'lighting', 'scan']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate system status structure
            system = data['system']
            if 'status' not in system or 'ready' not in system:
                logger.error("Invalid system status structure")
                return False
            
            logger.info(f"   ✓ System status: {system.get('status', 'unknown')}")
            logger.info(f"   ✓ Motion connected: {data['motion'].get('connected', False)}")
            logger.info(f"   ✓ Cameras available: {data['cameras'].get('available', 0)}")
            
            return True
            
        except Exception as e:
            logger.error(f"System status test failed: {e}")
            return False

    # =====================================
    # MOTION CONTROL TESTS
    # =====================================

    def test_motion_control_apis(self) -> bool:
        """Test motion control API endpoints"""
        try:
            # Test relative movement
            move_data = {'axis': 'x', 'distance': 1.0}
            response = self.api_request('/api/move', 'POST', move_data)
            if not response.get('success'):
                logger.error(f"Move command failed: {response.get('error')}")
                return False
            logger.info("   ✓ Relative movement API working")
            
            # Test absolute positioning
            position_data = {'x': 10.0, 'y': 10.0, 'z': 0.0, 'c': 0.0}
            response = self.api_request('/api/position', 'POST', position_data)
            if not response.get('success'):
                logger.error(f"Position command failed: {response.get('error')}")
                return False
            logger.info("   ✓ Absolute positioning API working")
            
            # Test homing
            home_data = {'axes': ['x', 'y']}
            response = self.api_request('/api/home', 'POST', home_data)
            if not response.get('success'):
                logger.error(f"Home command failed: {response.get('error')}")
                return False
            logger.info("   ✓ Homing API working")
            
            # Test emergency stop
            response = self.api_request('/api/emergency_stop', 'POST')
            if not response.get('success'):
                logger.error(f"Emergency stop failed: {response.get('error')}")
                return False
            logger.info("   ✓ Emergency stop API working")
            
            return True
            
        except Exception as e:
            logger.error(f"Motion control test failed: {e}")
            return False

    # =====================================
    # CAMERA SYSTEM TESTS
    # =====================================

    def test_camera_apis(self) -> bool:
        """Test camera control API endpoints"""
        try:
            # Test camera capture
            capture_data = {'camera_id': 'camera_1'}
            response = self.api_request('/api/camera/capture', 'POST', capture_data)
            if not response.get('success'):
                logger.error(f"Camera capture failed: {response.get('error')}")
                return False
            logger.info("   ✓ Camera capture API working")
            
            # Test camera controls
            controls_data = {
                'camera_id': 'camera_1',
                'controls': {'exposure': 100, 'iso': 200}
            }
            response = self.api_request('/api/camera/controls', 'POST', controls_data)
            if not response.get('success'):
                logger.error(f"Camera controls failed: {response.get('error')}")
                return False
            logger.info("   ✓ Camera controls API working")
            
            # Test autofocus
            autofocus_data = {'camera_id': 'camera_1'}
            response = self.api_request('/api/camera/autofocus', 'POST', autofocus_data)
            if not response.get('success'):
                logger.error(f"Autofocus failed: {response.get('error')}")
                return False
            logger.info("   ✓ Autofocus API working")
            
            # Test camera status
            response = self.api_request('/api/camera/status?camera_id=camera_1')
            if not response.get('success'):
                logger.error(f"Camera status failed: {response.get('error')}")
                return False
            logger.info("   ✓ Camera status API working")
            
            return True
            
        except Exception as e:
            logger.error(f"Camera test failed: {e}")
            return False

    # =====================================
    # LIGHTING SYSTEM TESTS
    # =====================================

    def test_lighting_apis(self) -> bool:
        """Test lighting control API endpoints"""
        try:
            # Test lighting flash
            flash_data = {
                'zones': ['zone_1', 'zone_2'],
                'intensity': 0.8,
                'duration': 100
            }
            response = self.api_request('/api/lighting/flash', 'POST', flash_data)
            if not response.get('success'):
                logger.error(f"Lighting flash failed: {response.get('error')}")
                return False
            logger.info("   ✓ Lighting flash API working")
            
            return True
            
        except Exception as e:
            logger.error(f"Lighting test failed: {e}")
            return False

    # =====================================
    # SCANNING SYSTEM TESTS
    # =====================================

    def test_scanning_apis(self) -> bool:
        """Test scanning operation API endpoints"""
        try:
            # Test scan start
            scan_data = {
                'pattern_type': 'grid',
                'x_range': [0, 50],
                'y_range': [0, 50],
                'spacing': 10.0,
                'z_height': 25.0
            }
            response = self.api_request('/api/scan/start', 'POST', scan_data)
            if not response.get('success'):
                logger.error(f"Scan start failed: {response.get('error')}")
                return False
            logger.info("   ✓ Scan start API working")
            
            # Small delay to let scan initialize
            time.sleep(1)
            
            # Test scan pause
            response = self.api_request('/api/scan/pause', 'POST')
            if not response.get('success'):
                logger.error(f"Scan pause failed: {response.get('error')}")
                return False
            logger.info("   ✓ Scan pause API working")
            
            # Test scan stop
            response = self.api_request('/api/scan/stop', 'POST')
            if not response.get('success'):
                logger.error(f"Scan stop failed: {response.get('error')}")
                return False
            logger.info("   ✓ Scan stop API working")
            
            return True
            
        except Exception as e:
            logger.error(f"Scanning test failed: {e}")
            return False

    # =====================================
    # PHASE 5 ENHANCEMENT TESTS
    # =====================================

    def test_phase5_enhancements(self) -> bool:
        """Test Phase 5 web interface enhancements"""
        try:
            # Test file browsing
            response = self.api_request('/api/files/browse?path=/home/user/scanner_data')
            if not response.get('success'):
                logger.error(f"File browsing failed: {response.get('error')}")
                return False
            logger.info("   ✓ File browsing API working")
            
            # Test scan queue
            response = self.api_request('/api/scan/queue')
            if not response.get('success'):
                logger.error(f"Scan queue failed: {response.get('error')}")
                return False
            logger.info("   ✓ Scan queue API working")
            
            # Test settings API
            response = self.api_request('/api/settings/get')
            if not response.get('success'):
                logger.error(f"Settings API failed: {response.get('error')}")
                return False
            logger.info("   ✓ Settings API working")
            
            # Test storage statistics
            response = self.api_request('/api/storage/stats')
            if not response.get('success'):
                logger.error(f"Storage stats failed: {response.get('error')}")
                return False
            logger.info("   ✓ Storage statistics API working")
            
            return True
            
        except Exception as e:
            logger.error(f"Phase 5 enhancements test failed: {e}")
            return False

    # =====================================
    # WEB UI FUNCTIONALITY TESTS
    # =====================================

    def test_web_ui_elements(self) -> bool:
        """Test that web UI elements are properly implemented"""
        try:
            # Test dashboard page has required elements
            response = self.session.get(f"{self.base_url}/")
            if response.status_code != 200:
                return False
            
            html_content = response.text
            
            # Check for key UI elements
            required_elements = [
                'System Status',           # Status panel
                'Motion Control',          # Motion section
                'Camera',                 # Camera section
                'scanner-base.js',        # JavaScript base
                'api/status'              # API calls
            ]
            
            for element in required_elements:
                if element not in html_content:
                    logger.error(f"Missing UI element: {element}")
                    return False
                logger.info(f"   ✓ Found UI element: {element}")
            
            return True
            
        except Exception as e:
            logger.error(f"Web UI test failed: {e}")
            return False

    # =====================================
    # ERROR HANDLING TESTS
    # =====================================

    def test_error_handling(self) -> bool:
        """Test API error handling and validation"""
        try:
            # Test invalid movement command
            invalid_move = {'axis': 'invalid', 'distance': 'not_a_number'}
            response = self.session.post(f"{self.base_url}/api/move", json=invalid_move)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') is True:
                    logger.error("Invalid command was accepted - validation failed")
                    return False
            logger.info("   ✓ Invalid command properly rejected")
            
            # Test non-existent endpoint
            response = self.session.get(f"{self.base_url}/api/nonexistent")
            if response.status_code == 200:
                logger.error("Non-existent endpoint returned 200 - routing failed")
                return False
            logger.info("   ✓ Non-existent endpoint properly handled")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            return False

    # =====================================
    # MAIN TEST EXECUTION
    # =====================================

    def run_comprehensive_tests(self) -> bool:
        """Run all web interface tests"""
        logger.info("🚀 Starting Comprehensive Web Interface Tests")
        logger.info("=" * 60)
        
        test_suite = [
            ("Web Pages Accessibility", self.test_web_pages_accessible),
            ("System Status API", self.test_system_status_api),
            ("Motion Control APIs", self.test_motion_control_apis),
            ("Camera APIs", self.test_camera_apis),
            ("Lighting APIs", self.test_lighting_apis),
            ("Scanning APIs", self.test_scanning_apis),
            ("Phase 5 Enhancements", self.test_phase5_enhancements),
            ("Web UI Elements", self.test_web_ui_elements),
            ("Error Handling", self.test_error_handling),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in test_suite:
            if self.run_test(test_name, test_func):
                passed += 1
            else:
                failed += 1
            print()  # Add spacing between tests
        
        # Print comprehensive results
        logger.info("=" * 60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        
        for test_name, success, error in self.test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} | {test_name}")
            if not success and error:
                logger.info(f"         Error: {error}")
        
        logger.info("=" * 60)
        logger.info(f"📈 Overall: {passed}/{len(test_suite)} tests passed ({passed/len(test_suite)*100:.1f}%)")
        
        if failed == 0:
            logger.info("🎉 All web interface tests PASSED!")
            logger.info("✅ Web interface is operating as expected")
        else:
            logger.warning(f"⚠️  {failed} test(s) failed - review issues before deployment")
        
        return failed == 0

def check_web_server_running(url: str) -> bool:
    """Check if web server is running"""
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Main test execution"""
    print("🧪 Web Interface Comprehensive Testing Suite")
    print("=" * 50)
    
    # Check if web server is running
    base_url = "http://localhost:5000"
    if not check_web_server_running(base_url):
        print(f"❌ Web server not running at {base_url}")
        print("\n🚀 To start the web server, run:")
        print("   cd ~/Documents/RaspPI/V2.0")
        print("   python run_web_interface.py")
        print("   # or")
        print("   python demo_phase5_web_interface.py")
        return False
    
    print(f"✅ Web server detected at {base_url}")
    print()
    
    # Run comprehensive tests
    validator = WebInterfaceValidator(base_url)
    success = validator.run_comprehensive_tests()
    
    if success:
        print("\n🎉 WEB INTERFACE VALIDATION COMPLETE")
        print("✅ All current elements are implemented as intended")
        print("✅ System operates as expected")
    else:
        print("\n⚠️  VALIDATION ISSUES DETECTED")
        print("❌ Some elements need attention before deployment")
    
    return success

if __name__ == "__main__":
    main()