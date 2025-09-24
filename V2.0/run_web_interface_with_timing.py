#!/usr/bin/env python3
"""
Web Interface with Enhanced Timing Analysis

This script runs the web interface with comprehensive timing logging
to identify exactly where command delays are occurring.

Usage:
    python run_web_interface_with_timing.py
    
Then open: http://localhost:8080
Check timing_analysis.log for detailed timing breakdown
"""

import os
import sys
import logging
import time

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to see timing information
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s,%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# Import and start timing logger
from timing_logger import timing_logger, log_startup

# Import web interface
from web.web_interface import ScannerWebInterface

if __name__ == "__main__":
    print("🚀 Starting Web Interface with Enhanced Timing Analysis")
    print("=" * 60)
    print("📊 Timing logs will be written to: timing_analysis.log")
    print("🌐 Web interface will be available at: http://localhost:8080")
    print("🔍 Use jog controls to generate timing data")
    print("=" * 60)
    
    try:
        # Create web interface
        web_interface = ScannerWebInterface()
        
        # Start the web server
        print("🌐 Starting web server...")
        web_interface.start_web_server(host='0.0.0.0', port=8080, debug=False)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        
        # Generate performance report
        try:
            report = timing_logger.generate_performance_report()
            print("\n📊 PERFORMANCE SUMMARY:")
            print(f"Total Commands: {report.get('total_commands', 0)}")
            
            total_stats = report.get('total_duration_stats', {})
            if total_stats.get('count', 0) > 0:
                print(f"Average Command Duration: {total_stats.get('avg', 0):.1f}ms")
                print(f"Min/Max Duration: {total_stats.get('min', 0):.1f}ms / {total_stats.get('max', 0):.1f}ms")
            
            print("\n🔍 Check timing_analysis.log for detailed breakdown")
            
        except Exception as e:
            print(f"Could not generate performance report: {e}")
    
    except Exception as e:
        print(f"❌ Error starting web interface: {e}")
        sys.exit(1)