#!/usr/bin/env python3
"""
Simple Flask route test to verify route registration
"""
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return "Route test server running"

@app.route('/test_move_simple/<float:x>/<float:y>/<float:z>')
def test_move_simple(x, y, z):
    return jsonify({"message": f"Test move to X{x} Y{y} Z{z}", "status": "success"})

@app.route('/move_to/<float:x>/<float:y>/<float:z>', methods=['GET', 'POST'])
def move_to_position(x, y, z):
    return jsonify({"message": f"Move to X{x} Y{y} Z{z}", "status": "success"})

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
    
    app.run(host='0.0.0.0', port=5001, debug=True)
