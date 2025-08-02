#!/usr/bin/env python3
"""
Simple test script to verify the web interface and JavaScript functionality
"""

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# Simple HTML template to test JavaScript functions
TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>JavaScript Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .button { margin: 10px; padding: 10px 20px; cursor: pointer; }
        .btn-primary { background: #007bff; color: white; border: none; border-radius: 4px; }
        .btn-secondary { background: #6c757d; color: white; border: none; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>JavaScript Function Test</h1>
    
    <div>
        <h2>Basic Tests</h2>
        <button class="button btn-primary" onclick="simpleAlert()">Simple Alert</button>
        <button class="button btn-primary" onclick="buttonTest()">Button Test</button>
        <button class="button btn-primary" onclick="consoleTest()">Console Test</button>
    </div>
    
    <div>
        <h2>Server Communication Tests</h2>
        <button class="button btn-secondary" onclick="ping()">Ping Server</button>
        <button class="button btn-secondary" onclick="testJSON()">Test JSON</button>
    </div>
    
    <div>
        <h2>Status</h2>
        <div id="status">Ready for testing...</div>
    </div>

    <script>
        console.log('=== JAVASCRIPT LOADING ===');
        
        // Simple test functions
        function simpleAlert() {
            alert('Simple alert working!');
        }
        
        function buttonTest() {
            console.log('Button test function called');
            document.getElementById('status').innerHTML = 'Button test executed at ' + new Date().toLocaleTimeString();
        }
        
        function consoleTest() {
            console.log('Console test - JavaScript is working!');
            console.log('Current time:', new Date());
            console.log('User agent:', navigator.userAgent);
        }
        
        // Server communication tests
        function ping() {
            console.log('Pinging server...');
            fetch('/ping')
                .then(function(response) {
                    console.log('Ping response status: ' + response.status);
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                    }
                    return response.json();
                })
                .then(function(data) {
                    console.log('Ping response data:', data);
                    alert('Server ping successful: ' + data.message);
                })
                .catch(function(error) {
                    console.error('Ping error:', error);
                    alert('Server ping failed: ' + error.message);
                });
        }
        
        function testJSON() {
            console.log('Testing JSON response...');
            fetch('/test_json')
                .then(function(response) {
                    console.log('Test JSON response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Test JSON response data:', data);
                    alert('JSON test successful: ' + data.message);
                })
                .catch(function(error) {
                    console.error('Test JSON error:', error);
                    alert('JSON test failed: ' + error.message);
                });
        }
        
        // Page initialization
        document.addEventListener('DOMContentLoaded', function() {
            console.log('=== PAGE LOADED ===');
            console.log('Current URL:', window.location.href);
            
            // Verify functions are available
            console.log('=== FUNCTION VERIFICATION ===');
            console.log('simpleAlert function available:', typeof simpleAlert === 'function');
            console.log('buttonTest function available:', typeof buttonTest === 'function');
            console.log('consoleTest function available:', typeof consoleTest === 'function');
            console.log('ping function available:', typeof ping === 'function');
            console.log('testJSON function available:', typeof testJSON === 'function');
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main test page"""
    return render_template_string(TEST_HTML)

@app.route('/ping')
def ping():
    """Test ping endpoint"""
    return jsonify({"status": "success", "message": "Pong! Server is responding."})

@app.route('/test_json')
def test_json():
    """Test JSON response"""
    return jsonify({"status": "success", "message": "JSON response is working correctly!"})

if __name__ == '__main__':
    print("Starting test web interface...")
    print("Open your browser to: http://localhost:5000")
    print("Test the JavaScript functions using the buttons")
    app.run(host='0.0.0.0', port=5000, debug=True)
