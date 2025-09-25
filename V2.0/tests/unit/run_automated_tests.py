#!/usr/bin/env python3
"""
Automated Test Runner for Core Infrastructure

Runs the core infrastructure tests with default responses to all prompts
for non-interactive testing.

Author: Scanner System Development
Created: September 2025
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_automated_tests():
    """Run tests with automated responses"""
    
    # Mock the input function to always return default
    original_input = input
    def mock_input(prompt):
        # Extract default value from prompt
        if '[' in prompt and ']:' in prompt:
            default = prompt.split('[')[1].split(']:')[0]
            print(f"{prompt} {default}")
            return default
        print(f"{prompt} y")
        return "y"
    
    # Replace input function
    import builtins
    builtins.input = mock_input
    
    try:
        # Import and run the main test function
        from test_core_infrastructure import main
        
        print("============================================================")
        print("AUTOMATED Core Infrastructure Test Suite")
        print("============================================================")
        print("Running all tests with default responses...")
        print()
        
        # Run the tests
        success = main()
        
        if success:
            print()
            print("============================================================")
            print("✅ ALL TESTS PASSED!")
            print("============================================================")
            print("Core infrastructure is working correctly.")
            return True
        else:
            print()
            print("============================================================")
            print("❌ SOME TESTS FAILED!")
            print("============================================================")
            print("Please check the output above for details.")
            return False
            
    except Exception as e:
        print(f"❌ TEST RUNNER ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original input function
        builtins.input = original_input

if __name__ == "__main__":
    success = run_automated_tests()
    sys.exit(0 if success else 1)