#!/usr/bin/env python3
"""
Route Registration Test Script

This script tests if the parameterized Flask routes can be registered properly.
Run this to isolate route registration issues.
"""

import traceback
from flask import Flask, jsonify

print(f"Python version: {__import__('sys').version}")
print(f"Flask version: {__import__('flask').__version__}")

app = Flask(__name__)

# Test basic routes first
@app.route('/')
def index():
    return "Test server running"

@app.route('/ping')
def ping():
    return jsonify({"status": "alive", "message": "Server is responding"})

# Test parameterized routes with detailed debugging
print("\n=== TESTING PARAMETERIZED ROUTES ===")

print("1. Testing simple parameterized route...")
try:
    @app.route('/test_move_simple/<float:x>/<float:y>/<float:z>')
    def test_move_simple(x, y, z):
        return jsonify({"message": f"Test move to X{x} Y{y} Z{z}", "status": "success"})
    print("✓ test_move_simple route registered successfully")
except Exception as e:
    print(f"✗ test_move_simple route failed: {e}")
    print(f"Traceback: {traceback.format_exc()}")

print("2. Testing move_to route...")
try:
    @app.route('/move_to/<float:x>/<float:y>/<float:z>', methods=['GET', 'POST'])
    def move_to_position(x, y, z):
        return jsonify({"message": f"Move to X{x} Y{y} Z{z}", "status": "success"})
    print("✓ move_to route registered successfully")
except Exception as e:
    print(f"✗ move_to route failed: {e}")
    print(f"Traceback: {traceback.format_exc()}")

print("3. Testing grid scan route...")
try:
    @app.route('/start_grid_scan/<float:x1>/<float:y1>/<float:x2>/<float:y2>/<int:grid_x>/<int:grid_y>')
    def start_grid_scan(x1, y1, x2, y2, grid_x, grid_y):
        return jsonify({"message": f"Grid scan from ({x1},{y1}) to ({x2},{y2}) with {grid_x}x{grid_y} grid", "status": "success"})
    print("✓ start_grid_scan route registered successfully")
except Exception as e:
    print(f"✗ start_grid_scan route failed: {e}")
    print(f"Traceback: {traceback.format_exc()}")

print("4. Testing simple string parameter route...")
try:
    @app.route('/test_string/<string:name>')
    def test_string(name):
        return jsonify({"message": f"Hello {name}", "status": "success"})
    print("✓ test_string route registered successfully")
except Exception as e:
    print(f"✗ test_string route failed: {e}")
    print(f"Traceback: {traceback.format_exc()}")

print("5. Testing simple int parameter route...")
try:
    @app.route('/test_int/<int:number>')
    def test_int(number):
        return jsonify({"message": f"Number is {number}", "status": "success"})
    print("✓ test_int route registered successfully")
except Exception as e:
    print(f"✗ test_int route failed: {e}")
    print(f"Traceback: {traceback.format_exc()}")

@app.route('/debug_routes')
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'rule': str(rule),
            'methods': list(rule.methods) if rule.methods else [],
            'endpoint': rule.endpoint
        })
    return jsonify({"routes": routes})

@app.route('/test_flask_routing')
def test_flask_routing():
    """Test if Flask routing works at all"""
    return jsonify({
        "flask_version": __import__('flask').__version__,
        "app_name": app.name,
        "url_map_size": len(list(app.url_map.iter_rules())),
        "status": "Flask routing is working"
    })

if __name__ == '__main__':
    print("\n=== FINAL ROUTE SUMMARY ===")
    total_routes = 0
    parameterized_routes = 0
    
    for rule in app.url_map.iter_rules():
        total_routes += 1
        methods = list(rule.methods) if rule.methods else []
        has_params = '<' in str(rule.rule) and '>' in str(rule.rule)
        if has_params:
            parameterized_routes += 1
            print(f"PARAM Route: {rule.rule} -> {rule.endpoint} ({methods})")
        else:
            print(f"BASIC Route: {rule.rule} -> {rule.endpoint} ({methods})")
    
    print(f"\nRoute Summary:")
    print(f"  Total routes: {total_routes}")
    print(f"  Parameterized routes: {parameterized_routes}")
    print(f"  Basic routes: {total_routes - parameterized_routes}")
    
    if parameterized_routes == 0:
        print("❌ WARNING: No parameterized routes were registered!")
        print("This indicates a Flask configuration or version issue.")
    else:
        print(f"✅ {parameterized_routes} parameterized routes registered successfully")
    
    print(f"\nStarting test server on port 5001...")
    print(f"Test URLs:")
    print(f"  Basic routes:")
    print(f"    http://localhost:5001/ping")
    print(f"    http://localhost:5001/debug_routes")
    print(f"    http://localhost:5001/test_flask_routing")
    if parameterized_routes > 0:
        print(f"  Parameterized routes:")
        print(f"    http://localhost:5001/test_move_simple/5/0/5")
        print(f"    http://localhost:5001/move_to/5/0/5")
        print(f"    http://localhost:5001/test_string/hello")
        print(f"    http://localhost:5001/test_int/42")
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=True)
    except Exception as e:
        print(f"Failed to start Flask server: {e}")
        print(f"Traceback: {traceback.format_exc()}")
