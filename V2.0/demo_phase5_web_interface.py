#!/usr/bin/env python3
"""
Phase 5 Web Interface Enhancement Demo

Demonstrates the complete enhanced web interface with:
- File management and downloads
- Scan queue management
- Settings configuration
- Storage integration

Run this to see the enhanced web interface in action.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from web.web_interface import ScannerWebInterface
    from phase5_web_enhancements import enhance_web_interface
    from web.start_web_interface import create_mock_orchestrator
    WEB_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Error: Web modules not available: {e}")
    WEB_MODULES_AVAILABLE = False


def setup_demo_environment():
    """Setup demonstration environment"""
    logger.info("Setting up demo environment...")
    
    # Create demo data directory
    demo_data_dir = Path('/home/user/scanner_data_demo')
    demo_data_dir.mkdir(exist_ok=True)
    
    # Create sample scan sessions
    sessions = [
        {
            'name': 'precision_gear_scan',
            'description': 'High precision gear component scan',
            'files': ['config.json', 'scan_001.jpg', 'scan_002.jpg', 'results.csv']
        },
        {
            'name': 'engine_block_survey',
            'description': 'Complete engine block 360° survey',
            'files': ['config.json', 'survey_data.csv', 'point_cloud.ply']
        },
        {
            'name': 'prototype_validation',
            'description': 'Prototype quality validation scan',
            'files': ['validation_config.json', 'quality_report.pdf', 'measurements.xlsx']
        }
    ]
    
    for session in sessions:
        session_dir = demo_data_dir / session['name']
        session_dir.mkdir(exist_ok=True)
        
        # Create sample files
        for filename in session['files']:
            file_path = session_dir / filename
            if filename.endswith('.json'):
                import json
                file_path.write_text(json.dumps({
                    'session_name': session['name'],
                    'description': session['description'],
                    'created': '2025-09-23T14:00:00',
                    'pattern': 'grid',
                    'points': 48
                }, indent=2))
            elif filename.endswith('.jpg'):
                file_path.write_bytes(b"fake_image_data" * 500)  # ~6KB fake image
            elif filename.endswith('.csv'):
                file_path.write_text("x,y,z,intensity\n10.5,20.3,30.1,255\n15.2,25.8,35.7,240")
            else:
                file_path.write_text(f"Demo file content for {filename}")
    
    logger.info(f"✅ Demo environment created at {demo_data_dir}")
    return demo_data_dir


def demonstrate_enhanced_features():
    """Demonstrate enhanced web interface features"""
    logger.info("🎯 Demonstrating Phase 5 enhanced features...")
    
    # Create enhanced web interface
    mock_orchestrator = create_mock_orchestrator()
    web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
    enhanced_interface = enhance_web_interface(web_interface)
    
    print("\n🌟 ENHANCED WEB INTERFACE FEATURES")
    print("=" * 50)
    
    # Test with client
    client = enhanced_interface.app.test_client()
    
    # 1. File Management Demo
    print("\n📁 FILE MANAGEMENT FEATURES:")
    print("-" * 30)
    
    # Browse files
    response = client.get('/api/files/browse?path=/home/user/scanner_data_demo')
    if response.status_code == 200:
        import json
        data = json.loads(response.data)
        directories = data['data']['directories']
        print(f"✅ Found {len(directories)} scan sessions:")
        for dir_info in directories[:3]:  # Show first 3
            print(f"   📂 {dir_info['name']} ({dir_info['size']} bytes)")
    else:
        print("❌ File browsing failed")
    
    # Storage statistics
    response = client.get('/api/storage/stats')
    if response.status_code == 200:
        data = json.loads(response.data)
        stats = data['data']
        print(f"✅ Storage: {stats.get('session_count', 0)} sessions, {stats.get('total_files', 0)} files")
    
    # 2. Scan Queue Demo
    print("\n📋 SCAN QUEUE MANAGEMENT:")
    print("-" * 30)
    
    # Add scans to queue
    sample_scans = [
        {'name': 'Quality Check Scan', 'pattern_type': 'grid', 'priority': 1},
        {'name': 'Detail Surface Scan', 'pattern_type': 'surface', 'priority': 2},
        {'name': 'Full 360° Survey', 'pattern_type': 'cylindrical', 'priority': 3}
    ]
    
    for scan in sample_scans:
        response = client.post('/api/scan/queue/add',
                             data=json.dumps(scan),
                             content_type='application/json')
        if response.status_code == 200:
            print(f"✅ Added: {scan['name']}")
    
    # Check queue status
    response = client.get('/api/scan/queue')
    if response.status_code == 200:
        data = json.loads(response.data)
        queue_count = data['data']['count']
        print(f"✅ Queue status: {queue_count} scans queued")
    
    # 3. Settings Management Demo
    print("\n⚙️  SETTINGS MANAGEMENT:")
    print("-" * 30)
    
    # Get current settings
    response = client.get('/api/settings/get')
    if response.status_code == 200:
        data = json.loads(response.data)
        config = data['data']
        print(f"✅ Configuration loaded:")
        print(f"   • Motion: {len(config.get('motion', {}).get('axes', {}))} axes configured")
        print(f"   • Camera: {len(config.get('camera', {}))} cameras configured")
        print(f"   • Storage: {config.get('storage', {}).get('base_path', 'default')}")
    
    # Test settings update
    update_data = {'system': {'debug_level': 'DEBUG'}}
    response = client.post('/api/settings/update',
                         data=json.dumps(update_data),
                         content_type='application/json')
    if response.status_code == 200:
        data = json.loads(response.data)
        print(f"✅ Settings update: restart_required = {data['data']['restart_required']}")
    
    # 4. Storage Integration Demo
    print("\n💾 STORAGE INTEGRATION:")
    print("-" * 30)
    
    # List sessions
    response = client.get('/api/storage/sessions')
    if response.status_code == 200:
        data = json.loads(response.data)
        sessions = data['data']
        print(f"✅ Found {len(sessions)} scan sessions:")
        for session in sessions[:3]:  # Show first 3
            print(f"   📊 {session['name']} - {session['image_count']} images")
    
    # Get detailed session info
    if sessions:
        session_id = sessions[0]['id']
        response = client.get(f'/api/storage/session/{session_id}')
        if response.status_code == 200:
            data = json.loads(response.data)
            session_info = data['data']
            print(f"✅ Session details: {session_info['file_count']} files, {session_info['total_size']} bytes")
    
    print("\n" + "=" * 50)
    print("🎉 ALL ENHANCED FEATURES DEMONSTRATED!")
    print("🌐 Ready to start web server with full functionality")
    
    return enhanced_interface


def start_demo_server():
    """Start the enhanced web interface server"""
    if not WEB_MODULES_AVAILABLE:
        print("❌ Web modules not available")
        return
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-5s | %(name)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    global logger
    logger = logging.getLogger('phase5_demo')
    
    print("🚀 PHASE 5 WEB INTERFACE DEMO")
    print("=" * 40)
    
    # Setup demo environment
    demo_data_dir = setup_demo_environment()
    
    # Demonstrate features
    enhanced_interface = demonstrate_enhanced_features()
    
    print("\n🌐 STARTING ENHANCED WEB SERVER")
    print("=" * 40)
    print("📍 URL: http://localhost:5000")
    print("🎯 Features Available:")
    print("   • Dashboard: Real-time system monitoring")
    print("   • Manual: 4DOF motion control")
    print("   • Scans: Complete scan management + queue")
    print("   • Settings: Configuration + backup/restore")
    print("   • API: Full REST API with file management")
    print("\n📋 Enhanced API Endpoints:")
    print("   • GET  /api/files/browse - File browser")
    print("   • GET  /api/files/download/<path> - File downloads")
    print("   • GET  /api/scan/queue - Queue management")
    print("   • POST /api/scan/queue/add - Add to queue")
    print("   • GET  /api/settings/get - Configuration")
    print("   • GET  /api/storage/sessions - Session list")
    print("   • GET  /api/storage/stats - Storage statistics")
    print("\n⚡ Press Ctrl+C to stop server")
    print("=" * 40)
    
    try:
        # Start the enhanced web server
        enhanced_interface.start_web_server(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
    finally:
        # Cleanup
        try:
            import shutil
            if demo_data_dir.exists():
                shutil.rmtree(demo_data_dir)
            logger.info("✅ Demo environment cleaned up")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")


if __name__ == "__main__":
    start_demo_server()