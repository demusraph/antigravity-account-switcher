"""
Entry point for running module via `python -m antigravity_switcher`
"""
import os
import sys

# Ensure src parent directory is in sys.path if invoked directly
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from antigravity_switcher.app import main
except ImportError:
    from .app import main

if __name__ == "__main__":
    main()
