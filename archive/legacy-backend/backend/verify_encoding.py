# -*- coding: utf-8 -*-
"""
Script to verify UTF-8 encoding configuration
Run this to ensure all Python files are properly configured for UTF-8
"""
import sys
import os
import io

def check_encoding():
    """Verify UTF-8 encoding is properly configured"""
    print("=" * 60)
    print("UTF-8 Encoding Verification")
    print("=" * 60)
    
    # Check Python default encoding
    print(f"\n1. Python Default Encoding: {sys.getdefaultencoding()}")
    if sys.getdefaultencoding() != 'utf-8':
        print("   ⚠️  WARNING: Default encoding is not UTF-8")
    else:
        print("   ✅ OK")
    
    # Check stdout encoding
    print(f"\n2. stdout Encoding: {sys.stdout.encoding}")
    if sys.stdout.encoding != 'utf-8':
        print("   ⚠️  WARNING: stdout encoding is not UTF-8")
        print("   ℹ️  utf8_config.py should fix this on import")
    else:
        print("   ✅ OK")
    
    # Check stderr encoding
    print(f"\n3. stderr Encoding: {sys.stderr.encoding}")
    if sys.stderr.encoding != 'utf-8':
        print("   ⚠️  WARNING: stderr encoding is not UTF-8")
        print("   ℹ️  utf8_config.py should fix this on import")
    else:
        print("   ✅ OK")
    
    # Check environment variable
    print(f"\n4. PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'Not set')}")
    if os.environ.get('PYTHONIOENCODING') != 'utf-8':
        print("   ⚠️  WARNING: PYTHONIOENCODING not set to utf-8")
    else:
        print("   ✅ OK")
    
    # Test UTF-8 output
    print("\n5. UTF-8 Output Test:")
    try:
        test_chars = "Test: é, è, à, ç, ñ, ü, °, →"
        print(f"   Output: {test_chars}")
        print("   ✅ UTF-8 characters displayed correctly")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)

if __name__ == '__main__':
    # Import utf8_config first to apply encoding fixes
    try:
        import utf8_config  # noqa: F401
    except ImportError:
        print("⚠️  utf8_config.py not found, skipping automatic fix")
    
    check_encoding()

