# -*- coding: utf-8 -*-
"""
UTF-8 Encoding Configuration
Must be imported FIRST before any other modules to ensure all outputs use UTF-8
"""
import sys
import io
import os

# Set environment variable for Python's default encoding FIRST
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Force UTF-8 encoding for all outputs BEFORE any other imports
if hasattr(sys.stdout, 'buffer'):
    try:
        # Check current encoding
        current_encoding = getattr(sys.stdout, 'encoding', None)
        if current_encoding != 'utf-8':
            # Replace with UTF-8 wrapper
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding='utf-8', 
                errors='replace',
                line_buffering=True
            )
    except (AttributeError, ValueError):
        pass

if hasattr(sys.stderr, 'buffer'):
    try:
        current_encoding = getattr(sys.stderr, 'encoding', None)
        if current_encoding != 'utf-8':
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, 
                encoding='utf-8', 
                errors='replace',
                line_buffering=True
            )
    except (AttributeError, ValueError):
        pass

