#!/usr/bin/env python3
"""
Route Registration Test Script

This script tests if the parameterized Flask routes can be registered properly.
Run this to isolate route registration issues.
"""

from flask import Flask, jsonify

app = Flask(__name__)

# Test basic routes first
@app.route('/')
def index():
    return "Test server running"

@app.route('/ping')
def ping():
    return jsonify({"status": "alive", "message": "Server is responding"})

# Test parameterized routes
print("Registering parameterized routes...")

try:
    @app.route('/test_move_simple/<float:x>/<float:y>/<float:z>')
    def test_move_simple(x, y, z):
        return jsonify({"message": f"Test move to X{x} Y{y} Z{z}", "status": "success"})
    print("✓ test_move_simple route registered")
except Exception as e:
    print(f"✗ test_move_simple route failed: {e}")

try:
    @app.route('/move_to/<float:x>/<float:y>/<float:z>', methods=['GET', 'POST'])
    def move_to_position(x, y, z):
        return jsonify({"message": f"Move to X{x} Y{y} Z{z}", "status": "success"})
    print("✓ move_to route registered")
except Exception as e:
    print(f"✗ move_to route failed: {e}")

try:
    @app.route('/start_grid_scan/<float:x1>/<float:y1>/<float:x2>/<float:y2>/<int:grid_x>/<int:grid_y>')
    def start_grid_scan(x1, y1, x2, y2, grid_x, grid_y):
        return jsonify({"message": f"Grid scan from ({x1},{y1}) to ({x2},{y2}) with {grid_x}x{grid_y} grid", "status": "success"})
    print("✓ start_grid_scan route registered")
except Exception as e:
    print(f"✗ start_grid_scan route failed: {e}")

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

if __name__ == '__main__':
    print("=== REGISTERED FLASK ROUTES ===")
    for rule in app.url_map.iter_rules():
        methods = list(rule.methods) if rule.methods else []
        print(f"Route: {rule.rule} -> {rule.endpoint} ({methods})")
    print("=== END ROUTES ===")
    
    print(f"\nStarting test server on port 5001...")
    print(f"Test URLs:")
    print(f"  http://localhost:5001/debug_routes")
    print(f"  http://localhost:5001/test_move_simple/5/0/5")
    print(f"  http://localhost:5001/move_to/5/0/5")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
