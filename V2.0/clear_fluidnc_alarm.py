#!/usr/bin/env python3
"""
Clear FluidNC Alarm State
Helps recover from alarm states that prevent system initialization
"""
import serial
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def clear_fluidnc_alarm(port="/dev/ttyUSB0", baudrate=115200):
    """Clear FluidNC alarm state and show status."""
    print("🔧 FluidNC Alarm Clear & Homing Utility")
    print("=" * 50)
    
    try:
        # Connect to FluidNC
        print(f"📡 Connecting to FluidNC at {port}...")
        ser = serial.Serial(port, baudrate, timeout=2)
        time.sleep(2)  # Wait for connection
        
        # Clear any pending data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Get current status
        print("📊 Checking current status...")
        ser.write(b"?\n")
        time.sleep(0.1)
        response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        print(f"   Current state: {response.strip()}")
        
        if "Alarm" in response:
            print("⚠️  FluidNC is in ALARM state (normal after boot)")
            
            # Clear alarm first
            print("🔓 Step 1: Clearing alarm with unlock command ($X)...")
            ser.write(b"$X\n")
            time.sleep(0.5)
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            print(f"   Response: {response.strip()}")
            
            # Check status after unlock
            ser.write(b"?\n")
            time.sleep(0.1)
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            print(f"   Status after unlock: {response.strip()}")
            
            if "Idle" in response or "Jog" in response:
                print("✅ Alarm unlocked - now ready for homing")
                
                # Prompt for homing
                print("\n🏠 Step 2: Homing Required")
                print("   FluidNC needs to be homed to know its position")
                print("   This will move all axes to their home positions")
                
                response = input("\n   Proceed with automatic homing? (y/N): ").strip().lower()
                
                if response == 'y':
                    print("🏠 Starting homing sequence ($H)...")
                    ser.write(b"$H\n")
                    
                    print("   ⏳ Homing in progress - please wait...")
                    print("   ⚠️  SAFETY: Ensure axes can move freely")
                    
                    # Monitor homing progress
                    start_time = time.time()
                    timeout = 60  # 60 second timeout for homing
                    
                    while time.time() - start_time < timeout:
                        time.sleep(1)
                        ser.write(b"?\n")
                        time.sleep(0.1)
                        status = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                        
                        if "Idle" in status:
                            print("✅ Homing completed successfully!")
                            print(f"   Final status: {status.strip()}")
                            break
                        elif "Home" in status:
                            print("   🔄 Homing in progress...")
                        elif "Alarm" in status:
                            print("❌ Homing failed - returned to alarm state")
                            print("   Possible causes:")
                            print("   - Limit switch not triggered")
                            print("   - Mechanical obstruction")
                            print("   - Incorrect wiring")
                            break
                    else:
                        print("⏰ Homing timeout - check manually")
                        
                else:
                    print("⚠️  Manual homing required")
                    print("   Use the web interface or send $H command manually")
                    
            else:
                print("⚠️  Alarm persists after unlock")
                print("   Manual intervention required")
                
        elif "Idle" in response:
            print("✅ FluidNC is ready (Idle state)")
            print("💡 System should initialize normally")
            
        elif "Home" in response:
            print("🏠 FluidNC is currently homing")
            print("⏳ Wait for homing to complete")
            
        else:
            print(f"📊 FluidNC state: {response.strip()}")
            print("💡 May need manual attention")
        
        ser.close()
        return True
        
    except serial.SerialException as e:
        print(f"❌ Could not connect to FluidNC: {e}")
        print("   Check:")
        print("   - Is FluidNC connected to USB?")
        print("   - Is the correct port being used? Try:")
        print("     ls /dev/ttyUSB* or ls /dev/ttyACM*")
        print("   - Do you have permission to access the port?")
        print("     sudo usermod -a -G dialout $USER")
        return False
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def find_fluidnc_port():
    """Try to find FluidNC on common ports"""
    common_ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]
    
    print("🔍 Searching for FluidNC...")
    for port in common_ports:
        try:
            ser = serial.Serial(port, 115200, timeout=1)
            time.sleep(1)
            ser.write(b"?\n")
            time.sleep(0.5)
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            ser.close()
            
            if any(keyword in response for keyword in ["Idle", "Alarm", "Run", "Home", "Jog"]):
                print(f"✅ Found FluidNC at {port}")
                return port
        except:
            continue
    
    print("❌ FluidNC not found on common ports")
    return None

if __name__ == "__main__":
    # Try to find port automatically or use provided argument
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_fluidnc_port()
        if not port:
            port = "/dev/ttyUSB0"  # Default fallback
    
    print(f"🎯 Using port: {port}")
    
    if clear_fluidnc_alarm(port):
        print("\n🎯 Next steps:")
        print("1. If homing completed: Run 'python run_web_interface.py'")
        print("2. If homing needed: Use web interface to home manually")
        print("3. Check web interface motion controls work")
    else:
        print("\n❌ Could not clear alarm - check connections and try again")