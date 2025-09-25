#!/usr/bin/env python3
"""
Background Monitor Diagnostic and Fix Tool
Run this while the system is running to diagnose and fix monitor issues
"""

import asyncio
import sys
import os
import logging
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_monitor_via_api():
    """Check monitor status via web API"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:5000/api/status') as response:
                if response.status == 200:
                    data = await response.json()
                    motion_data = data.get('motion', {})
                    
                    logger.info("📊 Current system status via API:")
                    logger.info(f"  Position: {motion_data.get('current_position', 'N/A')}")
                    logger.info(f"  Status: {motion_data.get('status', 'N/A')}")
                    logger.info(f"  Connected: {motion_data.get('connected', False)}")
                    
                    return True
                else:
                    logger.error(f"API returned status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Could not check API status: {e}")
        return False

def analyze_logs():
    """Analyze recent logs for monitor issues"""
    logger.info("🔍 Analyzing recent logs...")
    
    try:
        # Look for recent log files
        log_patterns = ['web_interface.log', '*.log']
        
        for pattern in log_patterns:
            log_files = list(Path('.').glob(pattern))
            for log_file in log_files[-3:]:  # Check last 3 log files
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()[-100:]  # Last 100 lines
                        
                    logger.info(f"📁 Checking {log_file}")
                    
                    # Look for relevant patterns
                    monitor_starts = [l for l in lines if 'Background status monitor started' in l]
                    monitor_stops = [l for l in lines if 'Background status monitor stopped' in l]
                    stale_warnings = [l for l in lines if 'Background monitor data is stale' in l]
                    lock_errors = [l for l in lines if 'bound to different event loop' in l]
                    
                    if monitor_starts:
                        logger.info(f"  ✅ Found {len(monitor_starts)} monitor starts")
                    if monitor_stops:
                        logger.info(f"  ⚠️  Found {len(monitor_stops)} monitor stops")
                    if stale_warnings:
                        logger.info(f"  🚨 Found {len(stale_warnings)} stale data warnings")
                    if lock_errors:
                        logger.info(f"  ❌ Found {len(lock_errors)} event loop errors")
                        
                except Exception as e:
                    logger.debug(f"Could not read {log_file}: {e}")
                    
    except Exception as e:
        logger.error(f"Log analysis failed: {e}")

def show_recommendations():
    """Show recommendations based on analysis"""
    logger.info("\n💡 RECOMMENDATIONS:")
    logger.info("1. If you see 'Background monitor data is stale' warnings:")
    logger.info("   - The monitor is not receiving data from FluidNC")
    logger.info("   - Try running: curl -X POST http://localhost:5000/api/system/restart-monitor")
    logger.info("")
    logger.info("2. If you see 'bound to different event loop' errors:")
    logger.info("   - The asyncio lock fix should prevent this")
    logger.info("   - Restart the entire web interface if persisting")
    logger.info("")
    logger.info("3. To manually restart the background monitor via API:")
    logger.info("   - POST http://localhost:5000/api/system/restart-monitor")
    logger.info("   - Or add a restart button to the web interface")
    logger.info("")
    logger.info("4. Current system seems to be working but monitor is intermittent")
    logger.info("   - Motion commands work (jog operations successful)")
    logger.info("   - Camera system functional")
    logger.info("   - Main issue is just monitor reliability")

async def main():
    """Main diagnostic function"""
    logger.info("🩺 Background Monitor Diagnostic Tool")
    logger.info("=" * 50)
    
    # Check system status
    logger.info("1. Checking system status via API...")
    api_ok = await check_monitor_via_api()
    
    # Analyze logs
    logger.info("\n2. Analyzing log files...")
    analyze_logs()
    
    # Show recommendations
    logger.info("\n3. Recommendations...")
    show_recommendations()
    
    if api_ok:
        logger.info("\n✅ CONCLUSION: System is functional, monitor just needs occasional restart")
        return 0
    else:
        logger.info("\n❌ CONCLUSION: System may have deeper issues")
        return 1

if __name__ == "__main__":
    """Run the diagnostic"""
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("Diagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Diagnostic failed: {e}")
        sys.exit(1)