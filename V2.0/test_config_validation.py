#!/usr/bin/env python3
"""
Test configuration validation with null Z-axis limits
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

def test_config_validation():
    """Test that config loads with null Z-axis limits"""
    
    print("=== Configuration Validation Test ===")
    
    try:
        from core.config_manager import ConfigManager
        
        # Load the config with null Z-axis limits
        config_file = project_root / "config" / "scanner_config.yaml"
        print(f"Loading config from: {config_file}")
        
        config_manager = ConfigManager(config_file)
        print("✅ Configuration loaded successfully")
        
        # Get motion config and check Z-axis limits
        motion_config = config_manager.get('motion', {})
        z_axis = motion_config.get('axes', {}).get('z_axis', {})
        
        min_limit = z_axis.get('min_limit')
        max_limit = z_axis.get('max_limit')
        
        print(f"Z-axis min_limit: {min_limit}")
        print(f"Z-axis max_limit: {max_limit}")
        
        if min_limit is None and max_limit is None:
            print("✅ Z-axis configured for continuous rotation (no limits)")
        else:
            print(f"❌ Z-axis still has limits: {min_limit} to {max_limit}")
            
        # Test validation
        config_manager.validate()
        print("✅ Configuration validation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_config_validation()
    sys.exit(0 if success else 1)