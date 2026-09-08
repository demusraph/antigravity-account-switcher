"""
Antigravity Control Center - Root Launcher
"""
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for std_id in (-10, -11, -12):
            h = kernel32.GetStdHandle(std_id)
            if not h or h == -1:
                h_nul = kernel32.CreateFileW("NUL", 0xC0000000, 3, None, 3, 0, None)
                kernel32.SetStdHandle(std_id, h_nul)
    except Exception:
        pass

# Ensure src/ is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from antigravity_switcher.app import main

if __name__ == "__main__":
    main()
