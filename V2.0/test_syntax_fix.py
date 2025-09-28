#!/usr/bin/env python3
"""
Quick syntax test to validate scan_orchestrator.py imports correctly
"""

try:
    print("Testing scan_orchestrator import...")
    from scanning.scan_orchestrator import ScanOrchestrator
    print("✅ ScanOrchestrator imported successfully!")
    
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    print(f"   File: {e.filename}")
    print(f"   Line: {e.lineno}")
    print(f"   Text: {e.text}")
    
except Exception as e:
    print(f"❌ Import error: {e}")
