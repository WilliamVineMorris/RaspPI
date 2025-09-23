#!/usr/bin/env python3
"""
Web Interface Testing Script

Tests the current web interface implementation to ensure all
current elements are working properly as intended.

This script focuses on validating existing functionality:
- Motion control APIs (4DOF positioning)
- Camera management
- Lighting control  
- Scanning operations
- System monitoring
- Phase 5 enhancements
"""

import json
import logging
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(message)s'
)
logger = logging.getLogger("web_test")

class CurrentWebInterfaceTest:
    """Test current web interface functionality"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_details = []

    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        if success:
            logger.info(f"✅ {test_name}")
            self.passed_tests += 1
        else:
            logger.error(f"❌ {test_name}: {details}")
            self.failed_tests += 1
        
        self.test_details.append({
            'test': test_name,
            'passed': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })

    def api_call(self, endpoint: str, method: str = "GET", data: Optional[dict] = None) -> Tuple[bool, dict]:
        """Make API call and return (success, response_data)"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method == "GET":
                response = self.session.get(url, timeout=10)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=10)
            else:
                return False, {"error": f"Unsupported method: {method}"}
            
            response.raise_for_status()
            return True, response.json()
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}
        except json.JSONDecodeError as e:
            return False, {"error": f"Invalid JSON response: {e}"}

    def test_web_pages(self):
        """Test that web pages are accessible"""
        logger.info("🌐 Testing Web Pages...")
        
        pages = [
            ("Dashboard", "/"),
            ("Manual Control", "/manual"), 
            ("Scan Management", "/scans"),
            ("Settings", "/settings")
        ]
        
        for page_name, url in pages:
            try:
                response = self.session.get(f"{self.base_url}{url}", timeout=10)
                success = response.status_code == 200
                details = f"Status: {response.status_code}" if not success else ""
                self.log_test_result(f"{page_name} Page", success, details)
            except Exception as e:
                self.log_test_result(f"{page_name} Page", False, str(e))

    def test_system_status(self):
        """Test system status API"""
        logger.info("📊 Testing System Status...")
        
        success, data = self.api_call("/api/status")
        if not success:
            self.log_test_result("System Status API", False, data.get("error", "Unknown error"))
            return
        
        # Check required status fields
        required_fields = ["system", "motion", "cameras", "lighting", "scan"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            self.log_test_result("System Status Structure", False, f"Missing fields: {missing_fields}")
        else:
            self.log_test_result("System Status Structure", True)
        
        # Log current system state
        if data.get("system", {}).get("ready"):
            logger.info(f"   📍 System Ready: {data['system'].get('status', 'unknown')}")
        if data.get("motion", {}).get("connected"):
            position = data['motion'].get('position', {})
            logger.info(f"   🔧 Motion: X={position.get('x', 0):.1f}, Y={position.get('y', 0):.1f}, Z={position.get('z', 0):.1f}, C={position.get('c', 0):.1f}")
        if data.get("cameras", {}).get("available", 0) > 0:
            logger.info(f"   📷 Cameras: {data['cameras']['available']} available")
        
        self.log_test_result("System Status API", True)

    def test_motion_control(self):
        """Test motion control APIs"""
        logger.info("🔧 Testing Motion Control...")
        
        # Test relative movement
        success, data = self.api_call("/api/move", "POST", {"axis": "x", "distance": 1.0})
        self.log_test_result("Relative Movement", success, data.get("error", ""))
        
        # Test absolute positioning  
        success, data = self.api_call("/api/position", "POST", {"x": 10.0, "y": 10.0, "z": 0.0, "c": 0.0})
        self.log_test_result("Absolute Positioning", success, data.get("error", ""))
        
        # Test homing
        success, data = self.api_call("/api/home", "POST", {"axes": ["x", "y"]})
        self.log_test_result("Axis Homing", success, data.get("error", ""))
        
        # Test emergency stop
        success, data = self.api_call("/api/emergency_stop", "POST")
        self.log_test_result("Emergency Stop", success, data.get("error", ""))

    def test_camera_system(self):
        """Test camera control APIs"""
        logger.info("📷 Testing Camera System...")
        
        # Test camera capture
        success, data = self.api_call("/api/camera/capture", "POST", {"camera_id": "camera_1"})
        self.log_test_result("Camera Capture", success, data.get("error", ""))
        
        # Test camera controls
        success, data = self.api_call("/api/camera/controls", "POST", {
            "camera_id": "camera_1", 
            "controls": {"exposure": 100, "iso": 200}
        })
        self.log_test_result("Camera Controls", success, data.get("error", ""))
        
        # Test autofocus
        success, data = self.api_call("/api/camera/autofocus", "POST", {"camera_id": "camera_1"})
        self.log_test_result("Camera Autofocus", success, data.get("error", ""))
        
        # Test camera status
        success, data = self.api_call("/api/camera/status?camera_id=camera_1")
        self.log_test_result("Camera Status", success, data.get("error", ""))

    def test_lighting_system(self):
        """Test lighting control APIs"""
        logger.info("💡 Testing Lighting System...")
        
        # Test lighting flash
        success, data = self.api_call("/api/lighting/flash", "POST", {
            "zones": ["zone_1", "zone_2"],
            "intensity": 0.8,
            "duration": 100
        })
        self.log_test_result("Lighting Flash", success, data.get("error", ""))

    def test_scanning_system(self):
        """Test scanning operation APIs"""
        logger.info("🔬 Testing Scanning System...")
        
        # Test scan start with grid pattern
        scan_config = {
            "pattern_type": "grid",
            "x_range": [0, 50],
            "y_range": [0, 50], 
            "spacing": 10.0,
            "z_height": 25.0
        }
        success, data = self.api_call("/api/scan/start", "POST", scan_config)
        self.log_test_result("Scan Start", success, data.get("error", ""))
        
        if success:
            # Small delay for scan to initialize
            time.sleep(1)
            
            # Test scan pause
            success, data = self.api_call("/api/scan/pause", "POST")
            self.log_test_result("Scan Pause", success, data.get("error", ""))
            
            # Test scan stop
            success, data = self.api_call("/api/scan/stop", "POST")
            self.log_test_result("Scan Stop", success, data.get("error", ""))
        else:
            self.log_test_result("Scan Pause", False, "Scan start failed")
            self.log_test_result("Scan Stop", False, "Scan start failed")

    def test_phase5_features(self):
        """Test Phase 5 enhancement features"""
        logger.info("🚀 Testing Phase 5 Features...")
        
        # Test file browsing
        success, data = self.api_call("/api/files/browse?path=/home/user/scanner_data")
        self.log_test_result("File Browsing", success, data.get("error", ""))
        
        # Test scan queue
        success, data = self.api_call("/api/scan/queue")
        self.log_test_result("Scan Queue", success, data.get("error", ""))
        
        # Test adding to scan queue
        queue_item = {
            "name": "Test Queue Scan",
            "pattern_type": "grid",
            "parameters": {"x_range": [0, 50], "y_range": [0, 50], "spacing": 10}
        }
        success, data = self.api_call("/api/scan/queue/add", "POST", queue_item)
        self.log_test_result("Add to Scan Queue", success, data.get("error", ""))
        
        # Test settings API
        success, data = self.api_call("/api/settings/get")
        self.log_test_result("Settings API", success, data.get("error", ""))
        
        # Test storage statistics
        success, data = self.api_call("/api/storage/stats")
        self.log_test_result("Storage Statistics", success, data.get("error", ""))

    def test_error_handling(self):
        """Test API error handling"""
        logger.info("⚠️  Testing Error Handling...")
        
        # Test invalid movement command
        success, data = self.api_call("/api/move", "POST", {"axis": "invalid", "distance": "not_a_number"})
        # Should fail gracefully (return success=False or 4xx status)
        if success and data.get("success") is True:
            self.log_test_result("Invalid Command Handling", False, "Invalid command was accepted")
        else:
            self.log_test_result("Invalid Command Handling", True)
        
        # Test non-existent endpoint
        try:
            response = self.session.get(f"{self.base_url}/api/nonexistent", timeout=10)
            success = response.status_code != 200  # Should return 404 or similar
            self.log_test_result("Non-existent Endpoint", success)
        except:
            self.log_test_result("Non-existent Endpoint", True)  # Connection error is expected

    def run_comprehensive_test(self):
        """Run all web interface tests"""
        logger.info("🧪 Web Interface Comprehensive Testing")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Run all test categories
        test_categories = [
            ("Web Pages", self.test_web_pages),
            ("System Status", self.test_system_status),
            ("Motion Control", self.test_motion_control), 
            ("Camera System", self.test_camera_system),
            ("Lighting System", self.test_lighting_system),
            ("Scanning System", self.test_scanning_system),
            ("Phase 5 Features", self.test_phase5_features),
            ("Error Handling", self.test_error_handling)
        ]
        
        for category_name, test_func in test_categories:
            logger.info("")  # Add spacing
            try:
                test_func()
            except Exception as e:
                logger.error(f"❌ {category_name} test failed with exception: {e}")
                self.failed_tests += 1
        
        # Calculate results
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        test_duration = time.time() - start_time
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Passed: {self.passed_tests}")
        logger.info(f"❌ Failed: {self.failed_tests}")
        logger.info(f"📈 Success Rate: {success_rate:.1f}%")
        logger.info(f"⏱️  Duration: {test_duration:.1f}s")
        
        if self.failed_tests == 0:
            logger.info("")
            logger.info("🎉 ALL TESTS PASSED!")
            logger.info("✅ Web interface is operating as expected")
            logger.info("✅ All current elements implemented properly")
        else:
            logger.info("")
            logger.warning(f"⚠️  {self.failed_tests} test(s) failed")
            logger.warning("❌ Some elements need attention")
        
        return self.failed_tests == 0

def check_web_server():
    """Check if web server is running"""
    try:
        response = requests.get("http://localhost:5000", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Main test execution"""
    print("🧪 Current Web Interface Testing")
    print("Testing all current features to ensure proper operation")
    print("=" * 60)
    
    # Check if web server is running
    if not check_web_server():
        print("❌ Web server not running at http://localhost:5000")
        print("")
        print("🚀 To start the web server:")
        print("   Option 1 - Basic web interface:")
        print("   python run_web_interface.py")
        print("")
        print("   Option 2 - Enhanced interface with Phase 5:")
        print("   python demo_phase5_web_interface.py")
        print("")
        print("   Option 3 - Development mode:")
        print("   cd web && python web_interface.py")
        return False
    
    print("✅ Web server detected")
    print("")
    
    # Run tests
    tester = CurrentWebInterfaceTest()
    success = tester.run_comprehensive_test()
    
    if success:
        print("")
        print("🎯 VALIDATION COMPLETE")
        print("✅ Web interface is working properly")
        print("✅ All current elements operate as intended")
        print("")
        print("🎮 Try the web interface:")
        print("   🔗 http://localhost:5000")
        print("   📱 Dashboard: Real-time monitoring")
        print("   🎛️  Manual: 4DOF motion control")
        print("   🔬 Scans: Pattern creation and management")
        print("   ⚙️  Settings: System configuration")
    else:
        print("")
        print("⚠️  ISSUES DETECTED")
        print("❌ Some web interface elements need attention")
        print("📋 Review failed tests above for details")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)