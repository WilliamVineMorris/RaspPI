#!/usr/bin/env python3
"""
Debug script to capture raw FluidNC messages during homing
This will show us exactly what FluidNC sends during the homing process
"""

import time
import serial
import threading
from datetime import datetime

class HomingMessageCapture:
    def __init__(self, port="/dev/ttyUSB0", baud_rate=115200):
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection = None
        self.capturing = False
        self.messages = []
        
    def connect(self):
        """Connect to FluidNC"""
        try:
            print(f"🔌 Connecting to FluidNC at {self.port}")
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=0.1,
                write_timeout=1.0
            )
            
            # Clear buffers
            time.sleep(0.5)
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            print("✅ Connected to FluidNC")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def start_message_capture(self):
        """Start capturing all FluidNC messages"""
        self.capturing = True
        self.messages = []
        
        def capture_loop():
            print("📡 Starting message capture...")
            while self.capturing:
                try:
                    if self.serial_connection and self.serial_connection.in_waiting > 0:
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            message = f"[{timestamp}] RECEIVED: {line}"
                            print(message)
                            self.messages.append(message)
                    
                    time.sleep(0.01)  # Small delay to prevent excessive CPU usage
                    
                except Exception as e:
                    print(f"❌ Capture error: {e}")
                    break
        
        # Start capture thread
        capture_thread = threading.Thread(target=capture_loop, daemon=True)
        capture_thread.start()
        
        return capture_thread
    
    def send_command(self, command):
        """Send command to FluidNC and log it"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] SENDING: {command}")
            
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()
            
            self.messages.append(f"[{timestamp}] SENT: {command}")
            return True
            
        except Exception as e:
            print(f"❌ Send error: {e}")
            return False
    
    def run_homing_capture(self):
        """Run homing and capture all messages"""
        if not self.connect():
            return
        
        print("\n" + "="*60)
        print("🏠 HOMING MESSAGE CAPTURE SESSION")
        print("="*60)
        
        # Start message capture
        capture_thread = self.start_message_capture()
        
        try:
            # Wait a moment for initial status
            print("\n⏳ Waiting for initial status...")
            time.sleep(2)
            
            # Request initial status
            self.send_command("?")
            time.sleep(1)
            
            print("\n🏠 STARTING HOMING SEQUENCE...")
            print("📝 Watch for state changes: Idle → Home → Idle")
            
            # Send homing command
            self.send_command("$H")
            
            # Capture for 45 seconds (longer than current 30s timeout)
            print(f"📡 Capturing messages for 45 seconds...")
            
            for i in range(45):
                # Request status every 2 seconds
                if i % 2 == 0:
                    self.send_command("?")
                
                time.sleep(1)
                print(f"⏱️  {i+1}/45 seconds elapsed...")
            
            print("\n✅ Capture complete!")
            
        except KeyboardInterrupt:
            print("\n⚠️ Capture interrupted by user")
        
        finally:
            # Stop capture
            self.capturing = False
            
            # Save results
            self.save_results()
            self.disconnect()
    
    def save_results(self):
        """Save captured messages to file"""
        try:
            filename = f"homing_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            
            with open(filename, 'w') as f:
                f.write("FluidNC Homing Message Capture\n")
                f.write("="*50 + "\n\n")
                
                for message in self.messages:
                    f.write(message + "\n")
            
            print(f"💾 Messages saved to: {filename}")
            
            # Also print summary
            print("\n" + "="*60)
            print("📊 CAPTURE SUMMARY")
            print("="*60)
            
            states_seen = set()
            for message in self.messages:
                if "RECEIVED:" in message and "<" in message and ">" in message:
                    # Extract state from status reports
                    try:
                        status_part = message.split("RECEIVED: ")[1]
                        if status_part.startswith('<') and '|' in status_part:
                            state = status_part.split('|')[0][1:]  # Remove < and get state
                            states_seen.add(state)
                    except:
                        pass
            
            print(f"📋 Total messages captured: {len(self.messages)}")
            print(f"🔄 States observed: {sorted(states_seen)}")
            
            # Look for key patterns
            homing_patterns = []
            for message in self.messages:
                if any(keyword in message.lower() for keyword in ['home', 'homing', 'idle', 'alarm', 'error']):
                    homing_patterns.append(message)
            
            if homing_patterns:
                print(f"\n🎯 KEY HOMING PATTERNS:")
                for pattern in homing_patterns[-10:]:  # Last 10 relevant messages
                    print(f"   {pattern}")
            
        except Exception as e:
            print(f"❌ Save error: {e}")
    
    def disconnect(self):
        """Disconnect from FluidNC"""
        try:
            if self.serial_connection:
                self.serial_connection.close()
                print("🔌 Disconnected from FluidNC")
        except:
            pass

if __name__ == "__main__":
    # Usage
    print("🏠 FluidNC Homing Message Capture Tool")
    print("📝 This will capture ALL messages during homing for analysis")
    print("⚠️  Make sure your machine is ready for homing!")
    
    input("\n🔶 Press Enter to start homing capture (Ctrl+C to abort)...")
    
    capture = HomingMessageCapture()
    capture.run_homing_capture()
    
    print("\n✅ Done! Check the log file for detailed analysis.")