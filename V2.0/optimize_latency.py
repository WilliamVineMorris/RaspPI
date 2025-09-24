#!/usr/bin/env python3
"""
FluidNC Latency Analysis and Optimization Tool

Identifies and fixes latency issues in position detection and movement completion
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def analyze_fluidnc_latency():
    """Analyze FluidNC communication latency sources"""
    print("🔍 Analyzing FluidNC Communication Latency...")
    
    latency_issues = []
    
    try:
        fluidnc_file = Path(__file__).parent / "motion" / "fluidnc_controller.py"
        
        if fluidnc_file.exists():
            content = fluidnc_file.read_text()
            
            # Check background monitor sleep intervals
            if 'await asyncio.sleep(0.05)' in content:
                latency_issues.append({
                    'issue': 'Background monitor 50ms idle sleep',
                    'impact': 'Position updates delayed by up to 50ms when no messages',
                    'current': '50ms',
                    'suggested': '10-20ms'
                })
                
            if 'await asyncio.sleep(0.01)' in content:
                print("✅ Fast 10ms sleep found for message processing")
            
            # Check movement completion polling
            if 'await asyncio.sleep(0.1)' in content:
                latency_issues.append({
                    'issue': 'Movement completion polling at 100ms',
                    'impact': 'Movement finish detection delayed by up to 100ms',
                    'current': '100ms',
                    'suggested': '50ms'
                })
                
            # Check status update staleness threshold
            if 'data_age > 8.0' in content:
                print("✅ Reasonable 8s staleness threshold for background data")
            elif 'data_age > 3.0' in content:
                latency_issues.append({
                    'issue': 'Too aggressive staleness checking (3s)',
                    'impact': 'Frequent manual queries interfering with background monitor',
                    'current': '3s',
                    'suggested': '8s'
                })
                
            # Check timeout values
            if 'timeout=0.2' in content:
                print("✅ Fast 200ms timeout for message reading")
            elif 'timeout=1.0' in content:
                latency_issues.append({
                    'issue': 'Slow 1s timeout for message reading', 
                    'impact': 'Background monitor blocks for up to 1s on no data',
                    'current': '1s',
                    'suggested': '200ms'
                })
                
        else:
            print("❌ FluidNC controller file not found")
            
    except Exception as e:
        print(f"❌ FluidNC analysis failed: {e}")
        
    return latency_issues

def analyze_web_interface_latency():
    """Analyze web interface update latency"""
    print("\n🔍 Analyzing Web Interface Update Latency...")
    
    latency_issues = []
    
    try:
        # Check JavaScript polling interval
        js_file = Path(__file__).parent / "web" / "static" / "js" / "scanner-base.js"
        
        if js_file.exists():
            content = js_file.read_text()
            
            if 'updateInterval: 2000' in content:
                latency_issues.append({
                    'issue': 'Web UI polling every 2 seconds',
                    'impact': 'Position updates in UI delayed by up to 2 seconds',
                    'current': '2000ms',
                    'suggested': '500-1000ms'
                })
                
            if 'requestTimeout: 10000' in content:
                print("✅ Reasonable 10s request timeout")
                
        # Check Python status updater
        web_file = Path(__file__).parent / "web" / "web_interface.py"
        
        if web_file.exists():
            content = web_file.read_text()
            
            if 'time.sleep(5.0)' in content:
                latency_issues.append({
                    'issue': 'Python status updater sleeps 5 seconds',
                    'impact': 'Backend status processing every 5 seconds',
                    'current': '5000ms', 
                    'suggested': '1000-2000ms'
                })
                
    except Exception as e:
        print(f"❌ Web interface analysis failed: {e}")
        
    return latency_issues

def create_latency_optimizations():
    """Generate optimized configurations for latency reduction"""
    print("\n🚀 Creating Latency Optimizations...")
    
    optimizations = {
        'fluidnc_controller': {
            'background_monitor_idle_sleep': 0.02,  # 20ms instead of 50ms
            'movement_completion_polling': 0.05,     # 50ms instead of 100ms 
            'message_read_timeout': 0.1,             # 100ms instead of 200ms
            'position_stability_checks': 2           # 2 checks (100ms) instead of 3 (300ms)
        },
        'web_interface': {
            'javascript_polling_interval': 1000,     # 1s instead of 2s
            'python_status_update_interval': 2.0,    # 2s instead of 5s
            'api_request_timeout': 5000               # 5s instead of 10s for faster failures
        }
    }
    
    return optimizations

def apply_fluidnc_optimizations():
    """Apply FluidNC latency optimizations"""
    print("\n⚡ Applying FluidNC Latency Optimizations...")
    
    try:
        fluidnc_file = Path(__file__).parent / "motion" / "fluidnc_controller.py"
        
        if not fluidnc_file.exists():
            print("❌ FluidNC controller file not found")
            return False
            
        content = fluidnc_file.read_text()
        
        # Optimize background monitor idle sleep
        if 'await asyncio.sleep(0.05)  # 50ms when idle' in content:
            content = content.replace(
                'await asyncio.sleep(0.05)  # 50ms when idle - still very responsive',
                'await asyncio.sleep(0.02)  # 20ms when idle - optimized for lower latency'
            )
            print("✅ Optimized background monitor idle sleep: 50ms → 20ms")
            
        # Optimize movement completion polling
        if 'await asyncio.sleep(0.1)  # Check every 100ms' in content:
            content = content.replace(
                'await asyncio.sleep(0.1)  # Check every 100ms - fast response while avoiding CPU waste',
                'await asyncio.sleep(0.05)  # Check every 50ms - optimized for faster movement detection'
            )
            print("✅ Optimized movement completion polling: 100ms → 50ms")
            
        # Reduce position stability requirement
        if 'stable_count >= 3' in content:
            content = content.replace(
                'stable_count >= 3',
                'stable_count >= 2'
            )
            content = content.replace(
                '# 1. Movement was detected AND position stable for 3+ checks (300ms)',
                '# 1. Movement was detected AND position stable for 2+ checks (100ms)'
            )
            print("✅ Optimized position stability: 3 checks (300ms) → 2 checks (100ms)")
            
        # Write optimized file
        fluidnc_file.write_text(content)
        print("✅ FluidNC optimizations applied successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to apply FluidNC optimizations: {e}")
        return False

def apply_web_interface_optimizations():
    """Apply web interface latency optimizations"""
    print("\n⚡ Applying Web Interface Latency Optimizations...")
    
    success = True
    
    try:
        # Optimize JavaScript polling interval
        js_file = Path(__file__).parent / "web" / "static" / "js" / "scanner-base.js"
        
        if js_file.exists():
            content = js_file.read_text()
            
            if 'updateInterval: 2000,' in content:
                content = content.replace(
                    'updateInterval: 2000,           // Status update interval (ms) - increased for HTTP polling',
                    'updateInterval: 1000,           // Status update interval (ms) - optimized for responsiveness'
                )
                print("✅ Optimized JavaScript polling: 2000ms → 1000ms")
                
            if 'requestTimeout: 10000,' in content:
                content = content.replace(
                    'requestTimeout: 10000,          // API request timeout (ms)',
                    'requestTimeout: 5000,           // API request timeout (ms) - faster failure detection'
                )
                print("✅ Optimized request timeout: 10000ms → 5000ms")
                
            js_file.write_text(content)
            
        else:
            print("⚠️  JavaScript file not found - skipping JS optimizations")
            
    except Exception as e:
        print(f"❌ Failed to apply JavaScript optimizations: {e}")
        success = False
        
    try:
        # Optimize Python status updater
        web_file = Path(__file__).parent / "web" / "web_interface.py"
        
        if web_file.exists():
            content = web_file.read_text()
            
            if 'time.sleep(5.0)  # Update every 5 seconds' in content:
                content = content.replace(
                    'time.sleep(5.0)  # Update every 5 seconds',
                    'time.sleep(2.0)  # Update every 2 seconds - optimized for responsiveness'
                )
                print("✅ Optimized Python status updater: 5000ms → 2000ms")
                
            if 'time.sleep(10.0)' in content and 'error' in content:
                content = content.replace(
                    'time.sleep(10.0)',
                    'time.sleep(5.0)  # Faster recovery from errors'
                )
                print("✅ Optimized error recovery sleep: 10000ms → 5000ms")
                
            web_file.write_text(content)
            
        else:
            print("⚠️  Web interface file not found - skipping Python optimizations")
            
    except Exception as e:
        print(f"❌ Failed to apply Python optimizations: {e}")
        success = False
        
    return success

def create_latency_test_script():
    """Create a test script to measure latency improvements"""
    
    test_script = '''#!/usr/bin/env python3
"""
Real-time latency testing for FluidNC position updates and movement completion
"""

import asyncio
import time
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_position_update_latency():
    """Test position update latency from FluidNC"""
    print("🧪 Testing Position Update Latency...")
    
    try:
        from motion.fluidnc_controller import FluidNCController
        from core.config_manager import ConfigManager
        
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(str(config_file))
        motion_config = config_manager.get_motion_config() 
        
        controller = FluidNCController(motion_config)
        
        if await controller.initialize():
            print("✅ FluidNC connected")
            
            # Test position query latency
            latencies = []
            for i in range(10):
                start_time = time.time()
                position = await controller.get_current_position()
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # Convert to ms
                latencies.append(latency)
                print(f"Position query {i+1}: {latency:.1f}ms - {position}")
                await asyncio.sleep(0.1)
                
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            print(f"\\n📊 Position Query Latency Results:")
            print(f"   Average: {avg_latency:.1f}ms")
            print(f"   Min: {min_latency:.1f}ms")
            print(f"   Max: {max_latency:.1f}ms")
            
            await controller.shutdown()
            
        else:
            print("❌ Failed to connect to FluidNC")
            
    except Exception as e:
        print(f"❌ Position latency test failed: {e}")

async def test_movement_completion_latency():
    """Test movement completion detection latency"""
    print("\\n🧪 Testing Movement Completion Latency...")
    
    try:
        from motion.fluidnc_controller import FluidNCController
        from core.config_manager import ConfigManager
        from core.exceptions import Position4D
        
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(str(config_file))
        motion_config = config_manager.get_motion_config()
        
        controller = FluidNCController(motion_config)
        
        if await controller.initialize():
            print("✅ FluidNC connected for movement test")
            
            # Test small movement completion detection
            start_pos = await controller.get_current_position()
            target_pos = Position4D(
                x=start_pos.x + 1.0,  # Small 1mm movement
                y=start_pos.y,
                z=start_pos.z,
                c=start_pos.c
            )
            
            print(f"Testing 1mm movement: {start_pos} → {target_pos}")
            
            movement_start = time.time()
            success = await controller.move_to_position(target_pos)
            movement_end = time.time()
            
            movement_latency = (movement_end - movement_start) * 1000
            
            if success:
                print(f"✅ Movement completed in {movement_latency:.1f}ms")
                
                final_pos = await controller.get_current_position()
                print(f"Final position: {final_pos}")
                
            else:
                print("❌ Movement failed")
                
            await controller.shutdown()
            
        else:
            print("❌ Failed to connect to FluidNC for movement test")
            
    except Exception as e:
        print(f"❌ Movement latency test failed: {e}")

if __name__ == "__main__":
    async def main():
        await test_position_update_latency()
        await test_movement_completion_latency()
    
    asyncio.run(main())
'''
    
    test_file = Path(__file__).parent / "test_latency_improvements.py"
    test_file.write_text(test_script)
    print(f"✅ Created latency test script: {test_file}")

def main():
    """Analyze and optimize FluidNC and web interface latency"""
    print("⚡ FluidNC and Web Interface Latency Analysis & Optimization\n")
    
    # Analyze current latency issues
    fluidnc_issues = analyze_fluidnc_latency()
    web_issues = analyze_web_interface_latency()
    
    all_issues = fluidnc_issues + web_issues
    
    if all_issues:
        print(f"\n🐌 Found {len(all_issues)} latency issues:")
        for i, issue in enumerate(all_issues, 1):
            print(f"\n{i}. {issue['issue']}")
            print(f"   Impact: {issue['impact']}")
            print(f"   Current: {issue['current']} → Suggested: {issue['suggested']}")
            
        print(f"\n⚡ Applying optimizations...")
        
        # Apply optimizations
        fluidnc_success = apply_fluidnc_optimizations()
        web_success = apply_web_interface_optimizations()
        
        if fluidnc_success and web_success:
            print("\n🎉 All optimizations applied successfully!")
            
            # Create test script
            create_latency_test_script()
            
            print("\n📊 Expected Improvements:")
            print("   • Position update latency: ~100-200ms reduction")
            print("   • Movement completion detection: ~50-250ms faster")
            print("   • Web UI responsiveness: ~1000ms faster updates")
            print("   • Overall system responsiveness: Significantly improved")
            
            print("\n🚀 Ready to test optimized system:")
            print("   cd /home/user/Documents/RaspPI/V2.0")
            print("   python3 run_web_flask.py")
            print("   # Test latency improvements:")
            print("   python3 test_latency_improvements.py")
            
            print("\n⚠️  Note: Restart the web interface to apply all changes")
            
        else:
            print("\n❌ Some optimizations failed - check the logs above")
            
    else:
        print("\n✅ No significant latency issues found!")
        print("Current configuration appears optimized for responsiveness")
        
    return len(all_issues) == 0 or (fluidnc_success and web_success)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)