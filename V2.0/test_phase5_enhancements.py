#!/usr/bin/env python3
"""
Test Phase 5 Web Interface Enhancements

Validates the enhanced web interface functionality including:
- File management endpoints
- Scan queue operations
- Settings management  
- Storage integration

Tests both the API endpoints and integration with existing web interface.
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from web.web_interface import ScannerWebInterface
    from phase5_web_enhancements import enhance_web_interface
    from web.start_web_interface import create_mock_orchestrator
    WEB_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Web modules not available: {e}")
    WEB_MODULES_AVAILABLE = False


def setup_test_environment():
    """Setup test environment with temporary directories"""
    logger.info("Setting up test environment...")
    
    # Create test data directory
    test_data_dir = Path('/tmp/test_scanner_data')
    test_data_dir.mkdir(exist_ok=True)
    
    # Create sample session directories
    for i in range(3):
        session_dir = test_data_dir / f"test_session_{i:02d}"
        session_dir.mkdir(exist_ok=True)
        
        # Create sample files
        (session_dir / 'scan_config.json').write_text(json.dumps({
            'pattern': 'grid',
            'points': 25,
            'timestamp': f"2025-09-23T1{i}:00:00"
        }))
        
        (session_dir / f'image_{i:03d}.jpg').write_bytes(b"fake_image_data" * 100)
        (session_dir / 'scan_results.csv').write_text("x,y,z\n10,20,30\n15,25,35")
    
    logger.info(f"✅ Test environment created at {test_data_dir}")
    return test_data_dir


def test_file_management_api():
    """Test file management endpoints"""
    logger.info("🔄 Testing file management API...")
    
    try:
        # Create mock web interface
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        
        # Enhance with Phase 5 functionality
        enhanced_interface = enhance_web_interface(web_interface)
        
        # Test with Flask test client
        client = enhanced_interface.app.test_client()
        
        # Test file browsing
        response = client.get('/api/files/browse?path=/tmp/test_scanner_data')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'directories' in data['data']
        logger.info("✅ File browsing endpoint working")
        
        # Test storage sessions
        response = client.get('/api/storage/sessions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert isinstance(data['data'], list)
        logger.info("✅ Storage sessions endpoint working")
        
        # Test storage stats
        response = client.get('/api/storage/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'total_space' in data['data']
        logger.info("✅ Storage stats endpoint working")
        
        logger.info("✅ File management API tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ File management API test failed: {e}")
        return False


def test_scan_queue_api():
    """Test scan queue management endpoints"""
    logger.info("🔄 Testing scan queue API...")
    
    try:
        # Create mock web interface
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        
        # Enhance with Phase 5 functionality
        enhanced_interface = enhance_web_interface(web_interface)
        
        # Test with Flask test client
        client = enhanced_interface.app.test_client()
        
        # Test empty queue
        response = client.get('/api/scan/queue')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert data['data']['count'] == 0
        logger.info("✅ Empty queue check working")
        
        # Test adding to queue
        scan_config = {
            'name': 'Test Grid Scan',
            'pattern_type': 'grid',
            'parameters': {
                'x_range': [0, 100],
                'y_range': [0, 100],
                'spacing': 10
            }
        }
        
        response = client.post('/api/scan/queue/add', 
                             data=json.dumps(scan_config),
                             content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        queue_id = data['data']['id']
        logger.info("✅ Add to queue working")
        
        # Test queue with item
        response = client.get('/api/scan/queue')
        data = json.loads(response.data)
        assert data['data']['count'] == 1
        logger.info("✅ Queue with items working")
        
        # Test removing from queue
        response = client.post('/api/scan/queue/remove',
                             data=json.dumps({'queue_id': queue_id}),
                             content_type='application/json')
        assert response.status_code == 200
        logger.info("✅ Remove from queue working")
        
        # Test clearing queue
        response = client.post('/api/scan/queue/clear')
        assert response.status_code == 200
        logger.info("✅ Clear queue working")
        
        logger.info("✅ Scan queue API tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Scan queue API test failed: {e}")
        return False


def test_settings_api():
    """Test settings management endpoints"""
    logger.info("🔄 Testing settings API...")
    
    try:
        # Create mock web interface
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        
        # Enhance with Phase 5 functionality
        enhanced_interface = enhance_web_interface(web_interface)
        
        # Test with Flask test client
        client = enhanced_interface.app.test_client()
        
        # Test getting settings
        response = client.get('/api/settings/get')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'motion' in data['data']
        assert 'camera' in data['data']
        logger.info("✅ Get settings working")
        
        # Test updating settings
        update_data = {
            'motion': {'test_setting': True},
            'camera': {'test_resolution': [1920, 1080]}
        }
        
        response = client.post('/api/settings/update',
                             data=json.dumps(update_data),
                             content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'restart_required' in data['data']
        logger.info("✅ Update settings working")
        
        # Test backup creation
        response = client.post('/api/settings/backup')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        logger.info("✅ Settings backup working")
        
        logger.info("✅ Settings API tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Settings API test failed: {e}")
        return False


def test_integration_compatibility():
    """Test integration with existing web interface"""
    logger.info("🔄 Testing integration compatibility...")
    
    try:
        # Create mock web interface
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        
        # Test original functionality still works
        client = web_interface.app.test_client()
        
        # Test dashboard
        response = client.get('/')
        assert response.status_code == 200
        logger.info("✅ Original dashboard still working")
        
        # Test API status
        response = client.get('/api/status')
        assert response.status_code == 200
        logger.info("✅ Original API status still working")
        
        # Enhance with Phase 5 functionality
        enhanced_interface = enhance_web_interface(web_interface)
        
        # Test original functionality still works after enhancement
        response = client.get('/')
        assert response.status_code == 200
        logger.info("✅ Dashboard working after enhancement")
        
        response = client.get('/api/status')
        assert response.status_code == 200
        logger.info("✅ API status working after enhancement")
        
        # Test new functionality works
        response = client.get('/api/storage/sessions')
        assert response.status_code == 200
        logger.info("✅ New storage endpoints working")
        
        response = client.get('/api/scan/queue')
        assert response.status_code == 200
        logger.info("✅ New queue endpoints working")
        
        logger.info("✅ Integration compatibility tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration compatibility test failed: {e}")
        return False


def test_error_handling():
    """Test error handling in enhanced endpoints"""
    logger.info("🔄 Testing error handling...")
    
    try:
        # Create mock web interface
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        enhanced_interface = enhance_web_interface(web_interface)
        
        client = enhanced_interface.app.test_client()
        
        # Test invalid file path
        response = client.get('/api/files/download/nonexistent/file.txt')
        assert response.status_code == 404
        logger.info("✅ File not found error handling working")
        
        # Test invalid session export
        response = client.get('/api/files/export/nonexistent_session')
        assert response.status_code == 404
        logger.info("✅ Session not found error handling working")
        
        # Test malformed queue add request
        response = client.post('/api/scan/queue/add',
                             data="invalid json",
                             content_type='application/json')
        assert response.status_code == 400
        logger.info("✅ Malformed request error handling working")
        
        # Test missing queue ID
        response = client.post('/api/scan/queue/remove',
                             data=json.dumps({}),
                             content_type='application/json')
        assert response.status_code == 400
        logger.info("✅ Missing parameter error handling working")
        
        logger.info("✅ Error handling tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 5 enhancement tests"""
    print("🚀 Phase 5 Web Interface Enhancement Tests")
    print("=" * 50)
    
    if not WEB_MODULES_AVAILABLE:
        print("❌ Web modules not available - skipping tests")
        return False
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-5s | %(name)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    global logger
    logger = logging.getLogger('phase5_test')
    
    # Setup test environment
    test_data_dir = setup_test_environment()
    
    try:
        # Run all tests
        tests = [
            ("File Management API", test_file_management_api),
            ("Scan Queue API", test_scan_queue_api),
            ("Settings API", test_settings_api),
            ("Integration Compatibility", test_integration_compatibility),
            ("Error Handling", test_error_handling)
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n🔄 Running {test_name}...")
            try:
                result = test_func()
                results.append((test_name, result))
                if result:
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
            except Exception as e:
                print(f"❌ {test_name} FAILED with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} | {test_name}")
        
        print("-" * 50)
        print(f"📈 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All Phase 5 enhancement tests PASSED!")
            print("✅ Web interface enhancements ready for production!")
            return True
        else:
            print("⚠️  Some tests failed - review issues before deployment")
            return False
            
    finally:
        # Cleanup test environment
        try:
            import shutil
            if test_data_dir.exists():
                shutil.rmtree(test_data_dir)
            logger.info("✅ Test environment cleaned up")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)