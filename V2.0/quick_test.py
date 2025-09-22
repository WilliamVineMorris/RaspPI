#!/usr/bin/env python3
"""
Quick test to verify Position4D safety limits fix
"""

def test_position_validation():
    """Test that positions are now valid"""
    from scanning import GridScanPattern, GridPatternParameters
    
    print("🔍 Testing Position4D validation fix...")
    
    # Create parameters with smaller safety margin
    params = GridPatternParameters(
        min_x=0.0,
        max_x=20.0,
        min_y=0.0,
        max_y=10.0,
        min_z=5.0,
        max_z=15.0,
        min_c=-30.0,
        max_c=30.0,
        x_spacing=10.0,
        y_spacing=10.0,
        c_steps=2,
        zigzag=True,
        safety_margin=0.5  # Small safety margin
    )
    
    print(f"📐 Parameters: X=[{params.min_x}, {params.max_x}], Y=[{params.min_y}, {params.max_y}]")
    print(f"📐 Safety margin: {params.safety_margin}")
    print(f"📐 Effective X range: [{params.min_x + params.safety_margin}, {params.max_x - params.safety_margin}]")
    print(f"📐 Effective Y range: [{params.min_y + params.safety_margin}, {params.max_y - params.safety_margin}]")
    
    pattern = GridScanPattern("test_grid", params)
    points = pattern.generate_points()
    
    print(f"✅ Generated {len(points)} points successfully!")
    
    # Show first few points
    for i, point in enumerate(points[:3]):
        print(f"   Point {i+1}: {point.position}")
    
    return len(points) > 0

def test_orchestrator():
    """Test orchestrator with realistic coordinates"""
    import tempfile
    import asyncio
    from core.config_manager import ConfigManager
    from scanning import ScanOrchestrator
    
    print("\n🎯 Testing orchestrator with realistic coordinates...")
    
    # Create minimal config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
system:
  name: test_scanner
  log_level: INFO
motion:
  controller:
    port: /dev/ttyUSB0
    baud_rate: 115200
  axes:
    x_axis:
      type: linear
      units: mm
      min_limit: -50.0
      max_limit: 50.0
      max_feedrate: 1000.0
      home_position: 0.0
    y_axis:
      type: linear
      units: mm
      min_limit: -50.0
      max_limit: 50.0
      max_feedrate: 1000.0
      home_position: 0.0
    z_axis:
      type: linear
      units: mm
      min_limit: 0.0
      max_limit: 100.0
      max_feedrate: 500.0
      home_position: 0.0
    c_axis:
      type: rotational
      units: degrees
      min_limit: -180.0
      max_limit: 180.0
      max_feedrate: 100.0
      home_position: 0.0
      continuous: true
cameras:
  camera_1:
    port: 0
    resolution: [1920, 1080]
    name: main
  camera_2:
    port: 1
    resolution: [1920, 1080]
    name: secondary
lighting:
  led_zones:
    zone_1:
      gpio_pin: 18
      name: main_light
      max_intensity: 80
    zone_2:
      gpio_pin: 19
      name: secondary_light
      max_intensity: 80
web_interface:
  port: 8080
  host: 0.0.0.0
""")
        config_file = f.name
    
    async def test_async():
        try:
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            await orchestrator.initialize()
            print("✅ Orchestrator initialized")
            
            # Create pattern with reasonable coordinates
            pattern = orchestrator.create_grid_pattern(
                x_range=(-10.0, 10.0),  # Well within limits
                y_range=(-5.0, 5.0),   # Well within limits
                spacing=10.0,
                z_height=15.0
            )
            
            points = pattern.generate_points()
            print(f"✅ Created pattern with {len(points)} points")
            
            # Show first few points
            for i, point in enumerate(points[:3]):
                print(f"   Point {i+1}: {point.position}")
            
            await orchestrator.shutdown()
            return len(points) > 0
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        finally:
            import os
            os.unlink(config_file)
    
    return asyncio.run(test_async())

if __name__ == "__main__":
    print("🧪 Quick Position4D Safety Limits Test")
    print("=" * 50)
    
    success1 = test_position_validation()
    success2 = test_orchestrator()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 All quick tests passed! Safety limits are fixed.")
    else:
        print("❌ Some tests failed. Need more investigation.")