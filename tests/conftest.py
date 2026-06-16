"""Shared fixtures and path setup for tests."""
import os
import sys

# Ensure the plugin root is on sys.path for all test files
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
