"""
Antigravity Control Center - Root Launcher
"""
import os
import sys

# Ensure src/ is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from antigravity_switcher.app import main

if __name__ == "__main__":
    main()
