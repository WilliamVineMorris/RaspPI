#!/usr/bin/env python3
"""
Quick Route Registration Check
"""

import requests
import json

def check_current_routes():
    """Check what routes are currently registered"""
    base_url = "http://192.168.1.169:5000"
    
    try:
        resp = requests.get(f"{base_url}/debug_routes", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get("routes", [])
            
            print("📋 CURRENTLY REGISTERED ROUTES:")
            print("=" * 40)
            
            # Look for our target routes
            target_routes = ["/move_to", "/test_move_simple", "/start_grid_scan", "/start_circular_scan"]
            
            old_style_found = []
            new_style_found = []
            
            for route in routes:
                rule = route["rule"]
                methods = route.get("methods", [])
                
                for target in target_routes:
                    if rule.startswith(target):
                        if "<" in rule:  # Old URL parameter style
                            old_style_found.append((rule, methods))
                        elif rule == target:  # New JSON style
                            new_style_found.append((rule, methods))
            
            print(f"🔴 OLD URL PARAMETER ROUTES FOUND: {len(old_style_found)}")
            for rule, methods in old_style_found:
                print(f"   - {rule} (Methods: {methods})")
            
            print(f"\n🟢 NEW JSON ROUTES FOUND: {len(new_style_found)}")
            for rule, methods in new_style_found:
                print(f"   - {rule} (Methods: {methods})")
            
            print(f"\n🎯 ANALYSIS:")
            if len(old_style_found) > 0 and len(new_style_found) == 0:
                print("❌ Only old routes registered - server needs restart")
                print("🔄 Please restart integrated_camera_system.py")
            elif len(new_style_found) > 0 and len(old_style_found) == 0:
                print("✅ New JSON routes are registered correctly")
            elif len(new_style_found) > 0 and len(old_style_found) > 0:
                print("⚠️ Both old and new routes registered - potential conflicts")
            else:
                print("❓ No target routes found - check registration")
                
        else:
            print(f"❌ Failed to get routes: {resp.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking routes: {e}")

if __name__ == "__main__":
    check_current_routes()
