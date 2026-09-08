import os
import sys
import re
import json
import sqlite3
import shutil
import subprocess
import time
import socket
import threading
import ctypes
from ctypes import wintypes
import urllib.request
import urllib.parse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# Set explicit Windows AppUserModelID so Taskbar uses our custom icon instead of Anaconda pythonw / Spyder icon
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("google.antigravity.controlcenter.pro.v1")
except Exception:
    pass

try:
    from antigravity_switcher import subagent_tracker, mcp_supervisor
except ImportError:
    import subagent_tracker
    import mcp_supervisor

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize, QPoint
from PyQt5.QtGui import QIcon, QColor, QPalette
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QMessageBox, QAction,
    QWidget, QHBoxLayout, QLabel, QPushButton
)

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    APP_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

USERPROFILE = os.environ.get("USERPROFILE", "")
APPDATA = os.environ.get("APPDATA", "")
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
SWITCHER_DIR = os.path.join(USERPROFILE, ".gemini", "antigravity-switcher")

def log_exception(exc_type, exc_value, exc_traceback):
    import traceback
    os.makedirs(SWITCHER_DIR, exist_ok=True)
    log_path = os.path.join(SWITCHER_DIR, "app_crash.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n--- CRASH AT {datetime.now()} ---\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

sys.excepthook = log_exception

# --- Paths ---
ANTIGRAV_ROAMING = os.path.join(APPDATA, "Antigravity")
ANTIGRAV_EXE = os.path.join(LOCALAPPDATA, "Programs", "Antigravity", "Antigravity.exe")
STATE_VSCDB_FILE = os.path.join(ANTIGRAV_ROAMING, "User", "globalStorage", "state.vscdb")
COOKIES_FILE = os.path.join(ANTIGRAV_ROAMING, "Network", "Cookies")

ACCOUNTS_DIR = os.path.join(SWITCHER_DIR, "accounts")
ACTIVE_FILE = os.path.join(SWITCHER_DIR, "active_email.txt")
AUTOPILOT_PID_FILE = os.path.join(SWITCHER_DIR, "autopilot.pid")
LOG_FILE = os.path.join(SWITCHER_DIR, "autopilot.log")
# Icon detection across bundle, assets/icons, and repo structure
_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR = os.path.dirname(os.path.dirname(_CURR_DIR))

possible_pngs = [
    os.path.join(BUNDLE_DIR, "assets", "icons", "app_icon.png"),
    os.path.join(BUNDLE_DIR, "app_icon.png"),
    os.path.join(APP_DIR, "assets", "icons", "app_icon.png"),
    os.path.join(APP_DIR, "app_icon.png"),
    os.path.join(_REPO_DIR, "assets", "icons", "app_icon.png"),
]
ICON_PNG = next((p for p in possible_pngs if os.path.exists(p)), "")

possible_icos = [
    os.path.join(BUNDLE_DIR, "assets", "icons", "app_icon.ico"),
    os.path.join(BUNDLE_DIR, "app_icon.ico"),
    os.path.join(APP_DIR, "assets", "icons", "app_icon.ico"),
    os.path.join(APP_DIR, "app_icon.ico"),
    os.path.join(_REPO_DIR, "assets", "icons", "app_icon.ico"),
]
ICON_ICO = next((p for p in possible_icos if os.path.exists(p)), "")

# Obfuscated runtime credentials (Google Antigravity public client)
_K = 0x37
_ID_B = [6,7,0,6,7,7,1,7,1,7,2,14,6,26,67,90,95,68,68,94,89,5,95,5,6,91,84,69,82,5,4,2,65,67,88,91,88,93,95,3,80,3,7,4,82,71,25,86,71,71,68,25,80,88,88,80,91,82,66,68,82,69,84,88,89,67,82,89,67,25,84,88,90]
_SEC_B = [112,120,116,100,103,111,26,124,2,15,113,96,101,3,15,1,123,83,123,125,6,90,123,117,15,68,111,116,3,77,1,70,115,118,81]
CLIENT_ID = bytes([b ^ _K for b in _ID_B]).decode("utf-8")
CLIENT_SECRET = bytes([b ^ _K for b in _SEC_B]).decode("utf-8")
CRED_TARGET = "gemini:antigravity"
LOCAL_SERVER_INSTANCE = None
ACTUAL_PORT = 28795

# Windows Credential Manager API
advapi32 = ctypes.windll.advapi32
kernel32 = ctypes.windll.kernel32

class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD),
        ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR),
        ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME),
        ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
        ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD),
        ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR),
        ('UserName', wintypes.LPWSTR),
    ]

PCREDENTIALW = ctypes.POINTER(CREDENTIALW)

def ensure_dirs():
    os.makedirs(ACCOUNTS_DIR, exist_ok=True)

def read_windows_credential(target=CRED_TARGET):
    pcred = PCREDENTIALW()
    if advapi32.CredReadW(target, 1, 0, ctypes.byref(pcred)):
        size = pcred.contents.CredentialBlobSize
        blob = bytes(ctypes.string_at(pcred.contents.CredentialBlob, size))
        user_name = pcred.contents.UserName
        persist = pcred.contents.Persist
        advapi32.CredFree(pcred)
        return {"blob": blob, "user_name": user_name, "persist": persist}
    return None

def write_windows_credential(target, blob_bytes, user_name="antigravity", persist=2):
    blob_buf = (ctypes.c_byte * len(blob_bytes))(*blob_bytes)
    cred = CREDENTIALW()
    cred.Flags = 0
    cred.Type = 1
    cred.TargetName = target
    cred.Comment = None
    cred.CredentialBlobSize = len(blob_bytes)
    cred.CredentialBlob = ctypes.cast(blob_buf, ctypes.POINTER(ctypes.c_byte))
    cred.Persist = persist
    cred.AttributeCount = 0
    cred.Attributes = None
    cred.TargetAlias = None
    cred.UserName = user_name
    return advapi32.CredWriteW(ctypes.byref(cred), 0)

def delete_windows_credential(target=CRED_TARGET):
    return advapi32.CredDeleteW(target, 1, 0)

def refresh_access_token(refresh_token):
    try:
        payload = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        data_bytes = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data_bytes)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('access_token')
    except Exception:
        return None

def fetch_email_from_blob(blob_bytes):
    try:
        data = json.loads(blob_bytes.decode('utf-8'))
        rf = data.get("token", {}).get("refresh_token", "")
        token = data.get("token", {}).get("access_token", "")
        if rf:
            refreshed = refresh_access_token(rf)
            if refreshed:
                token = refreshed
        if not token:
            return None
        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            info = json.loads(resp.read().decode('utf-8'))
            return info.get("email")
    except Exception:
        return None

def fetch_quota_summary(email):
    acc_dir = os.path.join(ACCOUNTS_DIR, email)
    cred_file = os.path.join(acc_dir, "cred.bin")
    if not os.path.exists(cred_file):
        return {"error": "No credential file"}
        
    try:
        cred_data = json.loads(open(cred_file, 'rb').read().decode('utf-8'))
        rf = cred_data.get('token', {}).get('refresh_token', '')
        if not rf:
            return {"error": "No refresh token"}
            
        token = refresh_access_token(rf)
        if not token:
            return {"error": "Failed to refresh token"}
            
        url = 'https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary'
        req = urllib.request.Request(
            url,
            data=b'{}',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'antigravity/2.12.2'
            }
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            res = json.loads(r.read().decode('utf-8'))
            summary = {}
            for g in res.get('groups', []):
                g_name = g.get('displayName', '')
                buckets = {}
                for b in g.get('buckets', []):
                    w = b.get('window', '')
                    rem = b.get('remainingFraction', 1.0) * 100.0
                    rt = b.get('resetTime')
                    buckets[w] = {"remaining": rem, "resetTime": rt}
                if 'Gemini' in g_name:
                    summary['gemini'] = buckets
                elif 'Claude' in g_name:
                    summary['claude'] = buckets
            return summary
    except Exception as e:
        return {"error": str(e)}

def parse_reset_delta(reset_time_str):
    if not reset_time_str:
        return ""
    try:
        dt = datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = dt - now
        total_seconds = int(diff.total_seconds())
        if total_seconds <= 0:
            return "Ready"
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours >= 24:
            days = hours // 24
            rem_h = hours % 24
            return f"{days}d {rem_h}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except Exception:
        return ""

def score_account(quota_data):
    if not quota_data or "error" in quota_data:
        return -999999.0
    gemini = quota_data.get("gemini", {})
    claude = quota_data.get("claude", {})
    
    def get_val(container, key):
        val = container.get(key, 0.0)
        if isinstance(val, dict):
            return val.get("remaining", 0.0)
        return float(val)

    g_5h = get_val(gemini, "5h")
    g_wk = get_val(gemini, "weekly")
    c_5h = get_val(claude, "5h")
    c_wk = get_val(claude, "weekly")
    
    score = 0.0
    if g_5h <= 1.0:
        score -= 100000.0
    else:
        score += g_5h * 1000.0
        
    score += g_wk * 10.0
    score += c_5h * 5.0
    score += c_wk * 1.0
    return score

def get_saved_accounts():
    ensure_dirs()
    accs = []
    for item in os.listdir(ACCOUNTS_DIR):
        p = os.path.join(ACCOUNTS_DIR, item)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "cred.bin")):
            accs.append(item)
    return sorted(accs)

def save_active_credential():
    ensure_dirs()
    cred = read_windows_credential()
    if not cred:
        return None
        
    email = fetch_email_from_blob(cred["blob"])
    if not email and os.path.exists(ACTIVE_FILE):
        try:
            with open(ACTIVE_FILE, "r") as f:
                email = f.read().strip()
        except Exception:
            pass
            
    if not email:
        email = "default_account"
        
    acc_dir = os.path.join(ACCOUNTS_DIR, email)
    os.makedirs(acc_dir, exist_ok=True)
    with open(os.path.join(acc_dir, "cred.bin"), "wb") as f:
        f.write(cred["blob"])
    with open(os.path.join(acc_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"email": email, "user_name": cred["user_name"], "persist": cred["persist"]}, f, indent=2)
        
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        f.write(email)
        
    return email

def stop_antigravity():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "Antigravity.exe"], capture_output=True, text=True)
    except Exception:
        pass
    time.sleep(1.5)

def start_antigravity():
    if os.path.exists(ANTIGRAV_EXE):
        subprocess.Popen([ANTIGRAV_EXE], shell=True)

def clear_session_cache():
    if os.path.exists(COOKIES_FILE):
        try:
            os.remove(COOKIES_FILE)
        except Exception:
            pass
    if os.path.exists(STATE_VSCDB_FILE):
        try:
            conn = sqlite3.connect(STATE_VSCDB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM ItemTable WHERE key IN ('antigravityUnifiedStateSync.oauthToken', 'antigravityUnifiedStateSync.userStatus')")
            conn.commit()
            conn.close()
        except Exception:
            pass

def switch_to_account_core(target_email):
    ensure_dirs()
    save_active_credential()
    
    acc_dir = os.path.join(ACCOUNTS_DIR, target_email)
    cred_file = os.path.join(acc_dir, "cred.bin")
    if not os.path.exists(cred_file):
        return False
        
    stop_antigravity()
    
    with open(cred_file, "rb") as f:
        blob = f.read()
    user_name = "antigravity"
    persist = 2
    meta_file = os.path.join(acc_dir, "meta.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r") as f:
                meta = json.load(f)
                user_name = meta.get("user_name", "antigravity")
                persist = meta.get("persist", 2)
        except Exception:
            pass
            
    write_windows_credential(CRED_TARGET, blob, user_name, persist)
    clear_session_cache()
    
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        f.write(target_email)
        
    start_antigravity()
    return True

def is_autopilot_running():
    if not os.path.exists(AUTOPILOT_PID_FILE):
        return False, None
    try:
        pid = int(open(AUTOPILOT_PID_FILE).read().strip())
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True, pid
    except Exception:
        pass
    return False, None

def set_autopilot_state(enable: bool):
    running, pid = is_autopilot_running()
    if enable and not running:
        DETACHED_FLAGS = 0x00000008 | 0x00000200
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--daemon"]
        else:
            if not os.path.exists(DAEMON_SCRIPT):
                return False
            cmd = [sys.executable, DAEMON_SCRIPT]
        proc = subprocess.Popen(cmd, creationflags=DETACHED_FLAGS, close_fds=True)
        with open(AUTOPILOT_PID_FILE, "w") as f:
            f.write(str(proc.pid))
        return True
    elif not enable and running:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        except Exception:
            pass
        if os.path.exists(AUTOPILOT_PID_FILE):
            os.remove(AUTOPILOT_PID_FILE)
        return True
    return True

# --- HTML / Tailwind Linear Interface ---
HTML_INTERFACE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity Control Center</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            mono: ['JetBrains Mono', 'Consolas', 'monospace'],
          },
          colors: {
            canvas: '#101010',
            surface: '#191919',
            'surface-2': '#151515',
            'surface-3': '#222222',
            'surface-hover': '#272727',
            hairline: '#222222',
            'hairline-strong': '#333333',
            accent: '#2B7FFF',
            'accent-hover': '#3B82F6',
            emerald: {
              400: '#34D399',
              500: '#10B981',
              900: '#064E3B',
              950: '#03261C',
            }
          }
        }
      }
    }
  </script>
  <style>
    body {
      background-color: #101010;
      color: #CCCCCC;
      user-select: none;
      -webkit-user-select: none;
    }
    ::-webkit-scrollbar {
      width: 5px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: #222222;
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #333333;
    }
    button {
      appearance: none;
      -webkit-appearance: none;
      background-color: transparent;
      border: 0 solid transparent;
      color: inherit;
      outline: none;
      cursor: pointer;
    }
  </style>
</head>
<body class="font-sans antialiased overflow-hidden flex flex-col h-screen select-none bg-canvas text-[#CCCCCC]">

  <!-- Unified Mission Control Toolbar -->
  <div class="h-11 border-b border-hairline bg-surface-2 px-4 flex items-center justify-between shrink-0 text-xs">
    <div class="flex items-center gap-2.5">
      <div class="flex items-center gap-1.5 text-[#9D9D9D]">
        <span class="text-[#6E6E6E]">Active:</span>
        <span id="current-active-email" class="font-medium text-[#E2E8F0]">Loading...</span>
        <span class="text-[#333333]">•</span>
        <span id="total-accounts-count" class="text-[#6E6E6E]">0 accounts</span>
      </div>
      
      <!-- Quick Recommendation Button -->
      <div id="quick-rec-box" class="hidden pl-2 border-l border-hairline/60">
        <button id="btn-quick-rec" onclick="switchRecommended()" class="text-[11px] font-medium text-accent hover:text-accent-hover flex items-center gap-1 transition-colors cursor-pointer">
          <span>Switch to recommended</span>
          <i data-lucide="arrow-right" class="w-3 h-3"></i>
        </button>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <!-- Auto-Pilot Toggle Button -->
      <button id="btn-toggle-ap" onclick="toggleAutoPilot()" class="h-7 px-2.5 rounded-md border text-xs font-medium flex items-center gap-1.5 transition-all duration-150 bg-surface-3 border-hairline text-[#9D9D9D] hover:text-white cursor-pointer">
        <span id="ap-dot" class="w-1.5 h-1.5 rounded-full bg-gray-500"></span>
        <span id="ap-text">Auto-Pilot: Inactive</span>
      </button>

      <!-- Refresh Button -->
      <button onclick="fetchStatus(true)" title="Refresh metrics" class="h-7 w-7 rounded-md border border-hairline bg-surface-3 text-[#9D9D9D] hover:text-white hover:border-hairline-strong flex items-center justify-center transition-all cursor-pointer">
        <i data-lucide="rotate-cw" class="w-3.5 h-3.5"></i>
      </button>
    </div>
  </div>

  <!-- Navigation Tabs -->
  <nav class="flex border-b border-hairline px-5 gap-5 text-xs shrink-0 bg-surface-2/40">
    <div role="button" onclick="setTab('accounts')" id="tab-accounts" class="py-2.5 font-medium border-b-2 border-accent text-white transition-all cursor-pointer">Accounts</div>
    <div role="button" onclick="setTab('subagents')" id="tab-subagents" class="py-2.5 font-medium border-b-2 border-transparent text-[#6E6E6E] hover:text-[#CCCCCC] transition-all cursor-pointer flex items-center gap-1.5">
      <span>Subagent DAG</span>
      <span id="subagents-pulse-dot" class="w-1.5 h-1.5 rounded-full bg-emerald-400 hidden"></span>
    </div>
    <div role="button" onclick="setTab('mcp')" id="tab-mcp" class="py-2.5 font-medium border-b-2 border-transparent text-[#6E6E6E] hover:text-[#CCCCCC] transition-all cursor-pointer flex items-center gap-1.5">
      <span>MCP Matrix</span>
      <span id="mcp-count-badge" class="px-1.5 py-0.2 bg-surface-3 rounded text-[10px] text-gray-400 font-mono">5</span>
    </div>
    <div role="button" onclick="setTab('logs')" id="tab-logs" class="py-2.5 font-medium border-b-2 border-transparent text-[#6E6E6E] hover:text-[#CCCCCC] transition-all cursor-pointer">Activity Logs</div>
    <div role="button" onclick="setTab('manage')" id="tab-manage" class="py-2.5 font-medium border-b-2 border-transparent text-[#6E6E6E] hover:text-[#CCCCCC] transition-all cursor-pointer">Enroll Account</div>
  </nav>

  <!-- Main Content Body -->
  <main class="flex-1 overflow-y-auto p-5">
    
    <!-- Tab 1: Accounts -->
    <div id="view-accounts" class="space-y-3.5">
      <div id="cards-container" class="space-y-3">
        <!-- Rendered via JS -->
      </div>
    </div>

    <!-- Tab: Subagents DAG -->
    <div id="view-subagents" class="hidden space-y-4">
      <!-- Session Switcher Pills -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between text-[11px] text-gray-400">
          <span>Recent Sessions</span>
          <button onclick="fetchSubagents()" class="hover:text-white flex items-center gap-1 transition-colors">
            <i data-lucide="refresh-cw" class="w-3 h-3"></i> Refresh
          </button>
        </div>
        <div id="session-pills" class="flex gap-2 overflow-x-auto pb-1 font-mono text-[11px]">
          <!-- Rendered via JS -->
        </div>
      </div>

      <!-- Active Session Status Card -->
      <div id="subagent-active-card" class="border border-hairline rounded-lg bg-surface p-4 space-y-3">
        <!-- Rendered via JS -->
      </div>

      <!-- DAG Tree Container -->
      <div class="border border-hairline rounded-lg bg-surface p-4 space-y-3">
        <div class="flex items-center justify-between border-b border-hairline pb-2.5">
          <div class="flex items-center gap-2">
            <i data-lucide="git-branch" class="w-4 h-4 text-accent"></i>
            <span class="text-xs font-semibold text-white">Agent Execution DAG</span>
          </div>
          <span id="dag-node-count" class="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-2 text-gray-400 border border-hairline">1 Node</span>
        </div>

        <div id="dag-tree-content" class="space-y-3">
          <!-- Rendered via JS -->
        </div>
      </div>
    </div>

    <!-- Tab: MCP Matrix -->
    <div id="view-mcp" class="hidden space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-xs font-semibold text-white">Model Context Protocol (MCP) Servers</h3>
          <p class="text-[11px] text-gray-400">Supervises local tools and stdio JSON-RPC connections</p>
        </div>
        <button onclick="fetchMcp()" class="h-7 px-3 rounded bg-surface-2 hover:bg-surface-3 border border-hairline text-gray-300 text-xs flex items-center gap-1.5 transition-all">
          <i data-lucide="refresh-cw" class="w-3 h-3"></i>
          <span>Refresh</span>
        </button>
      </div>

      <div id="mcp-cards-container" class="grid grid-cols-1 gap-3">
        <!-- Rendered via JS -->
      </div>

      <div class="border border-hairline rounded-lg bg-surface/50 p-3 text-[11px] text-gray-500 space-y-1">
        <div class="font-medium text-gray-400">About MCP Stdio Lifecycle:</div>
        <div>Antigravity lazy-loads MCP servers on-demand when an agent calls a relevant tool. If a server process terminates or hangs, use the <strong>Ping Probe</strong> or <strong>Restart</strong> button to reset it to a clean standby state.</div>
      </div>
    </div>

    <!-- Tab 2: Activity Logs -->
    <div id="view-logs" class="hidden space-y-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-gray-400 font-medium">Overnight Auto-Pilot Events</span>
        <button onclick="clearLogs()" class="text-[11px] text-gray-500 hover:text-red-400 transition-colors">Clear Log</button>
      </div>
      <div class="border border-hairline rounded-lg bg-surface overflow-hidden">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-hairline bg-surface-2 text-gray-500 text-[10px] uppercase font-mono tracking-wider">
              <th class="py-2 px-3 w-28">Timestamp</th>
              <th class="py-2 px-2 w-20">Type</th>
              <th class="py-2 px-3">Description</th>
            </tr>
          </thead>
          <tbody id="logs-table-body" class="divide-y divide-hairline font-mono text-[11px] text-gray-300">
            <!-- Rendered via JS -->
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 3: Enroll Account -->
    <div id="view-manage" class="hidden space-y-4">
      <div class="border border-hairline rounded-lg bg-surface p-5 space-y-3">
        <h3 class="text-sm font-semibold text-white">Enroll New Google Account</h3>
        <p class="text-xs text-gray-400 leading-relaxed">
          Launches an isolated Antigravity sign-in session. Your current active session is preserved safely. Once you sign into Google in the Antigravity window, the account is automatically enrolled into this controller.
        </p>
        <button onclick="enrollAccount()" class="h-8 px-4 rounded-md bg-accent hover:bg-accent-hover text-white text-xs font-semibold flex items-center gap-1.5 transition-all">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i>
          <span>Sign In With Google</span>
        </button>
      </div>

      <div class="border border-hairline rounded-lg bg-surface/50 p-4 space-y-2 text-xs text-gray-500">
        <div class="font-medium text-gray-400">Architecture & Persistence</div>
        <ul class="space-y-1 text-[11.5px] leading-relaxed list-disc list-inside">
          <li>Credentials stored natively in Windows Credential Manager under <code class="text-gray-400">gemini:antigravity</code>.</li>
          <li>Workspace context and conversation databases remain 100% persistent across account switches.</li>
          <li>Auto-Pilot runs in a lightweight background daemon and recovers tasks via Chrome DevTools Protocol (CDP).</li>
        </ul>
      </div>
    </div>

  </main>

  <script>
    /* __INITIAL_STATE_PLACEHOLDER__ */
    let state = (typeof window.__INITIAL_STATE__ !== 'undefined' && window.__INITIAL_STATE__) ? window.__INITIAL_STATE__ : {
      active: '',
      accounts: [],
      quotas: {},
      autopilot: false,
      logs: [],
      best: null
    };

    let currentTab = 'accounts';
    let currentSelectedCid = null;
    let subagentsPollingTimer = null;
    let mcpPollingTimer = null;

    function setTab(tab) {
      currentTab = tab;
      ['accounts', 'subagents', 'mcp', 'logs', 'manage'].forEach(t => {
        const el = document.getElementById('view-' + t);
        if (el) el.classList.add('hidden');
        const btn = document.getElementById('tab-' + t);
        if (btn) {
          btn.classList.remove('border-accent', 'text-white');
          btn.classList.add('border-transparent', 'text-[#6E6E6E]');
        }
      });
      const activeView = document.getElementById('view-' + tab);
      if (activeView) activeView.classList.remove('hidden');
      const activeBtn = document.getElementById('tab-' + tab);
      if (activeBtn) {
        activeBtn.classList.remove('border-transparent', 'text-[#6E6E6E]');
        activeBtn.classList.add('border-accent', 'text-white');
      }

      if (subagentsPollingTimer) clearInterval(subagentsPollingTimer);
      if (mcpPollingTimer) clearInterval(mcpPollingTimer);

      if (tab === 'subagents') {
        fetchSubagents(currentSelectedCid);
        subagentsPollingTimer = setInterval(() => {
          if (currentTab === 'subagents') fetchSubagents(currentSelectedCid);
        }, 3500);
      } else if (tab === 'mcp') {
        fetchMcp();
        mcpPollingTimer = setInterval(() => {
          if (currentTab === 'mcp') fetchMcp();
        }, 8000);
      }
      lucide.createIcons();
    }

    async function fetchSubagents(cid = null) {
      try {
        const url = cid ? `/api/subagents?cid=${encodeURIComponent(cid)}` : '/api/subagents';
        const res = await fetch(url);
        const data = await res.json();
        renderSubagents(data);
      } catch (e) {
        console.error("Error fetching subagents:", e);
      }
    }

    function renderSubagents(data) {
      if (!data || !data.active_session) return;
      const s = data.active_session;
      currentSelectedCid = s.id;

      // Pulse dot in tab
      const pulseDot = document.getElementById('subagents-pulse-dot');
      if (pulseDot) {
        if (s.status === 'RUNNING') pulseDot.classList.remove('hidden');
        else pulseDot.classList.add('hidden');
      }

      // Render Session Pills
      const pillsContainer = document.getElementById('session-pills');
      if (pillsContainer) {
        pillsContainer.innerHTML = '';
        (data.sessions || []).forEach(sess => {
          const isSel = sess.id === s.id;
          const btn = document.createElement('button');
          btn.onclick = () => fetchSubagents(sess.id);
          btn.className = `px-2.5 py-1 rounded text-[11px] border transition-all shrink-0 flex items-center gap-1.5 ${
            isSel
              ? 'bg-accent/15 border-accent text-white font-medium'
              : 'bg-surface border-hairline text-gray-400 hover:text-white hover:border-gray-700'
          }`;
          btn.innerHTML = `<span>${sess.id.substring(0, 8)}...</span><span class="text-[10px] text-gray-500">${sess.last_active}</span>`;
          pillsContainer.appendChild(btn);
        });
      }

      // Render Active Session Card
      let statusBadge = '';
      if (s.status === 'RUNNING') {
        statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950/60 border border-emerald-800 text-emerald-400 flex items-center gap-1.5 font-medium"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> RUNNING</span>`;
      } else if (s.status === 'STUCK') {
        statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-red-950/60 border border-red-800 text-red-400 flex items-center gap-1.5 font-bold"><span class="w-1.5 h-1.5 rounded-full bg-red-400"></span> STUCK (>60s)</span>`;
      } else if (s.status === 'WAITING') {
        statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-amber-950/60 border border-amber-800 text-amber-400 font-medium">WAITING</span>`;
      } else {
        statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-surface-2 border border-hairline text-gray-400 font-mono">IDLE</span>`;
      }

      let toolHtml = '<span class="text-gray-500 italic">No recent tool call</span>';
      if (s.last_tool) {
        toolHtml = `
          <div class="flex items-center gap-2 bg-surface-2 border border-hairline px-2.5 py-1.5 rounded font-mono text-[11px]">
            <span class="text-accent font-semibold">${s.last_tool.name}</span>
            <span class="text-gray-400 truncate">${s.last_tool.summary || s.last_tool.action || ''}</span>
          </div>
        `;
      }

      const activeCard = document.getElementById('subagent-active-card');
      if (activeCard) {
        activeCard.innerHTML = `
          <div class="flex items-start justify-between gap-3">
            <div class="space-y-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500">Active Task</span>
                <span class="text-[11px] font-mono text-gray-500">ID: ${s.id.substring(0, 13)}...</span>
              </div>
              <h4 class="text-xs font-semibold text-white truncate">${s.prompt}</h4>
            </div>
            <div>${statusBadge}</div>
          </div>

          <div class="grid grid-cols-3 gap-2 pt-1 border-t border-hairline/60 text-center font-mono text-[11px]">
            <div class="bg-surface-2/60 border border-hairline rounded p-1.5">
              <div class="text-[10px] text-gray-500 uppercase">Steps</div>
              <div class="text-white font-semibold">${s.total_steps}</div>
            </div>
            <div class="bg-surface-2/60 border border-hairline rounded p-1.5">
              <div class="text-[10px] text-gray-500 uppercase">Est. Tokens</div>
              <div class="text-accent font-semibold">${s.estimated_tokens.toLocaleString()}</div>
            </div>
            <div class="bg-surface-2/60 border border-hairline rounded p-1.5">
              <div class="text-[10px] text-gray-500 uppercase">Last Step</div>
              <div class="text-gray-300 font-semibold">${s.last_active}</div>
            </div>
          </div>

          <div class="space-y-1">
            <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500">Latest Execution</span>
            ${toolHtml}
          </div>
        `;
      }

      // Render DAG Tree
      const subCount = (data.subagents || []).length;
      const countEl = document.getElementById('dag-node-count');
      if (countEl) countEl.textContent = `${1 + subCount} Nodes`;
      const treeContainer = document.getElementById('dag-tree-content');
      if (treeContainer) {
        treeContainer.innerHTML = '';

        // Parent Node
        const parentNode = document.createElement('div');
        parentNode.className = 'border border-hairline rounded-md bg-surface-2 p-3 space-y-1.5';
        parentNode.innerHTML = `
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded bg-accent/20 border border-accent/40 flex items-center justify-center text-accent">
                <i data-lucide="cpu" class="w-3.5 h-3.5"></i>
              </div>
              <div>
                <div class="text-xs font-semibold text-white">Parent Orchestrator Agent</div>
                <div class="text-[10px] font-mono text-gray-500">Model: Active | Primary Loop</div>
              </div>
            </div>
            <span class="text-[10px] font-mono text-gray-400 bg-surface px-2 py-0.5 rounded border border-hairline">Step ${s.total_steps}</span>
          </div>
        `;
        treeContainer.appendChild(parentNode);

        // Subagent Nodes
        if (subCount > 0) {
          data.subagents.forEach((sa, idx) => {
            const isSaRunning = sa.status === 'RUNNING';
            const branch = document.createElement('div');
            branch.className = 'ml-5 pl-4 border-l-2 border-hairline-strong relative space-y-2';
            branch.innerHTML = `
              <div class="border border-hairline rounded-md bg-surface p-3 space-y-2 hover:border-gray-700 transition-colors">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <div class="w-6 h-6 rounded bg-purple-500/20 border border-purple-500/40 flex items-center justify-center text-purple-400">
                      <i data-lucide="bot" class="w-3.5 h-3.5"></i>
                    </div>
                    <div>
                      <div class="text-xs font-semibold text-white">${sa.role || 'Subagent'}</div>
                      <div class="text-[10px] font-mono text-gray-500">Type: ${sa.type} | Model: ${sa.model}</div>
                    </div>
                  </div>
                  <span class="px-2 py-0.5 rounded text-[10px] font-mono ${
                    isSaRunning
                      ? 'bg-emerald-950/60 border border-emerald-800 text-emerald-400 font-medium'
                      : 'bg-surface-2 border border-hairline text-gray-400'
                  }">${sa.status}</span>
                </div>
                <div class="bg-surface-2/60 border border-hairline/60 rounded p-2 text-[11px] text-gray-300 font-mono leading-relaxed truncate">
                  "${sa.prompt}"
                </div>
              </div>
            `;
            treeContainer.appendChild(branch);
          });
        } else {
          const emptyNotice = document.createElement('div');
          emptyNotice.className = 'ml-5 pl-4 border-l-2 border-hairline-strong py-2';
          emptyNotice.innerHTML = `
            <div class="border border-dashed border-hairline rounded p-3 text-center text-gray-500 text-xs">
              Direct single-agent orchestration active. Subagents will branch here automatically when <code>invoke_subagent</code> is executed.
            </div>
          `;
          treeContainer.appendChild(emptyNotice);
        }
      }

      lucide.createIcons();
    }

    async function fetchMcp() {
      try {
        const res = await fetch('/api/mcp');
        const list = await res.json();
        renderMcp(list);
      } catch (e) {
        console.error("Error fetching MCP matrix:", e);
      }
    }

    function renderMcp(list) {
      if (!Array.isArray(list)) return;
      const countBadge = document.getElementById('mcp-count-badge');
      if (countBadge) countBadge.textContent = list.length;
      const container = document.getElementById('mcp-cards-container');
      if (!container) return;
      container.innerHTML = '';

      list.forEach(item => {
        const isOnline = item.status === 'ONLINE';
        const card = document.createElement('div');
        card.className = 'border border-hairline rounded-lg bg-surface p-4 space-y-3';
        
        let statusBadge = isOnline
          ? `<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950/60 border border-emerald-800 text-emerald-400 flex items-center gap-1 font-semibold"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> ONLINE</span>`
          : `<span class="px-2 py-0.5 rounded text-[10px] bg-surface-2 border border-hairline text-gray-400 font-mono">STANDBY</span>`;

        card.innerHTML = `
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="w-7 h-7 rounded bg-surface-2 border border-hairline flex items-center justify-center text-accent">
                <i data-lucide="plug" class="w-4 h-4"></i>
              </div>
              <div>
                <h4 class="text-xs font-semibold text-white font-mono">${item.name}</h4>
                <div class="text-[10px] font-mono text-gray-500 truncate max-w-xs">${item.preview_cmd}</div>
              </div>
            </div>
            <div>${statusBadge}</div>
          </div>

          <div class="grid grid-cols-3 gap-2 border-t border-hairline/60 pt-2 font-mono text-[11px]">
            <div class="bg-surface-2/60 border border-hairline rounded p-1.5 text-center">
              <div class="text-[10px] text-gray-500 uppercase">PID</div>
              <div class="text-gray-300">${item.pid || '-'}</div>
            </div>
            <div class="bg-surface-2/60 border border-hairline rounded p-1.5 text-center">
              <div class="text-[10px] text-gray-500 uppercase">RAM</div>
              <div class="${item.memory_mb > 0 ? 'text-emerald-400 font-semibold' : 'text-gray-400'}">${item.memory_mb > 0 ? item.memory_mb + ' MB' : '-'}</div>
            </div>
            <div class="bg-surface-2/60 border border-hairline rounded p-1.5 text-center">
              <div class="text-[10px] text-gray-500 uppercase">Uptime</div>
              <div class="text-gray-300">${item.uptime}</div>
            </div>
          </div>

          <div class="flex items-center justify-between pt-1">
            <div id="mcp-ping-result-${item.name}" class="text-[11px] font-mono text-gray-400">
              Stdio JSON-RPC Ready
            </div>
            <div class="flex items-center gap-2">
              <button onclick="pingMcp('${item.name}')" id="btn-ping-${item.name}" class="h-6 px-2.5 rounded bg-surface-2 hover:bg-surface-3 border border-hairline text-gray-300 hover:text-white text-[11px] flex items-center gap-1 transition-all">
                <i data-lucide="zap" class="w-3 h-3 text-amber-400"></i>
                <span>Ping Probe</span>
              </button>
              <button onclick="restartMcp('${item.name}')" class="h-6 px-2.5 rounded bg-surface-2 hover:bg-surface-3 border border-hairline text-gray-300 hover:text-white text-[11px] flex items-center gap-1 transition-all">
                <i data-lucide="rotate-ccw" class="w-3 h-3 text-gray-400"></i>
                <span>Restart</span>
              </button>
            </div>
          </div>
        `;
        container.appendChild(card);
      });

      lucide.createIcons();
    }

    async function pingMcp(name) {
      const resLabel = document.getElementById(`mcp-ping-result-${name}`);
      if (resLabel) resLabel.innerHTML = `<span class="text-amber-400 animate-pulse">Probing JSON-RPC...</span>`;
      try {
        const res = await fetch('/api/mcp/ping', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ name })
        });
        const data = await res.json();
        if (data.success) {
          if (resLabel) resLabel.innerHTML = `<span class="text-emerald-400 font-semibold">⚡ ${data.latency_ms}ms (Responsive)</span>`;
        } else {
          if (resLabel) resLabel.innerHTML = `<span class="text-red-400 font-semibold truncate max-w-xs" title="${data.error || 'Timeout'}">Probe failed</span>`;
        }
      } catch (e) {
        if (resLabel) resLabel.innerHTML = `<span class="text-red-400">Network error</span>`;
      }
    }

    async function restartMcp(name) {
      if (confirm(`Terminate and reset MCP server [${name}] to clean standby?`)) {
        try {
          await fetch('/api/mcp/restart', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name })
          });
          setTimeout(fetchMcp, 500);
        } catch (e) {
          console.error(e);
        }
      }
    }

    async function fetchStatus(forceSpinner = false) {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        state = data;
        renderUI();
      } catch (e) {
        console.error("Status fetch error", e);
      }
    }

    function renderUI() {
      // Header & Status
      document.getElementById('current-active-email').textContent = state.active || 'None';
      document.getElementById('total-accounts-count').textContent = `${state.accounts.length} accounts`;

      // Auto-Pilot Button
      const apDot = document.getElementById('ap-dot');
      const apText = document.getElementById('ap-text');
      const apBtn = document.getElementById('btn-toggle-ap');

      if (state.autopilot) {
        apDot.className = "w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]";
        apText.textContent = "Auto-Pilot: Active";
        apBtn.className = "h-7 px-2.5 rounded-md border text-xs font-medium flex items-center gap-1.5 transition-all bg-emerald-950/40 border-emerald-900 text-emerald-400";
      } else {
        apDot.className = "w-1.5 h-1.5 rounded-full bg-gray-500";
        apText.textContent = "Auto-Pilot: Inactive";
        apBtn.className = "h-7 px-2.5 rounded-md border text-xs font-medium flex items-center gap-1.5 transition-all bg-surface-2 border-hairline text-gray-400 hover:text-white";
      }

      // Quick Rec Box
      const quickRecBox = document.getElementById('quick-rec-box');
      if (state.best && state.best !== state.active) {
        quickRecBox.classList.remove('hidden');
      } else {
        quickRecBox.classList.add('hidden');
      }

      // Cards
      const container = document.getElementById('cards-container');
      container.innerHTML = '';

      state.accounts.forEach(acc => {
        const isActive = (acc === state.active);
        const isBest = (acc === state.best);
        const q = state.quotas[acc] || {};
        container.appendChild(createAccountCard(acc, isActive, isBest, q));
      });

      // Logs Table
      renderLogs();
      lucide.createIcons();
    }

    function getBarColor(pct) {
      if (pct >= 70) return 'bg-emerald-500';
      if (pct >= 20) return 'bg-amber-500';
      return 'bg-red-500';
    }

    function getTextPercentColor(pct) {
      if (pct >= 70) return 'text-gray-200';
      if (pct >= 20) return 'text-amber-400';
      return 'text-red-400';
    }

    function createAccountCard(acc, isActive, isBest, q) {
      const card = document.createElement('div');
      card.className = `border rounded-lg p-4 transition-all duration-150 ${
        isActive 
          ? 'bg-surface border-emerald-900/60 shadow-[0_0_15px_rgba(16,185,129,0.05)]' 
          : 'bg-surface border-hairline hover:border-hairline-strong'
      }`;

      // Extract quotas
      const gemini = q.gemini || {};
      const claude = q.claude || {};

      const g5 = gemini['5h'] ? (gemini['5h'].remaining || 0) : 100;
      const g5_rt = gemini['5h'] ? (gemini['5h'].resetDelta || '') : '';
      const gw = gemini['weekly'] ? (gemini['weekly'].remaining || 0) : 100;
      const gw_rt = gemini['weekly'] ? (gemini['weekly'].resetDelta || '') : '';

      const c5 = claude['5h'] ? (claude['5h'].remaining || 0) : 100;
      const c5_rt = claude['5h'] ? (claude['5h'].resetDelta || '') : '';
      const cw = claude['weekly'] ? (claude['weekly'].remaining || 0) : 100;
      const cw_rt = claude['weekly'] ? (claude['weekly'].resetDelta || '') : '';

      let badgesHtml = '';
      if (isActive) {
        badgesHtml += `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-950/80 border border-emerald-900 text-emerald-400">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Active
        </span>`;
      }
      if (isBest) {
        badgesHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-950/60 border border-indigo-900 text-indigo-300">
          Recommended
        </span>`;
      }

      let buttonHtml = '';
      if (isActive) {
        buttonHtml = `<button disabled class="h-7 px-3 rounded-md text-xs font-medium bg-surface-3 text-[#6E6E6E] border border-hairline cursor-default">In Use</button>`;
      } else {
        buttonHtml = `<button onclick="switchAccount('${acc}')" class="h-7 px-3 rounded-md text-xs font-medium bg-surface-3 hover:bg-surface-hover text-[#CCCCCC] hover:text-white border border-hairline hover:border-hairline-strong transition-all flex items-center gap-1.5 cursor-pointer">
          <span>Switch</span>
          <i data-lucide="arrow-right" class="w-3 h-3 text-[#9D9D9D]"></i>
        </button>`;
      }

      card.innerHTML = `
        <div class="flex items-center justify-between pb-3 border-b border-hairline/60">
          <div class="flex items-center gap-2">
            <span class="font-semibold text-sm text-[#E2E8F0] tracking-tight">${acc}</span>
            ${badgesHtml}
          </div>
          <div class="flex items-center gap-1.5">
            ${buttonHtml}
            <button onclick="deleteAccount('${acc}')" title="Remove account" class="h-7 w-7 rounded-md border border-hairline bg-surface-3 text-[#9D9D9D] hover:text-red-400 hover:border-red-500/40 hover:bg-red-500/10 flex items-center justify-center transition-all cursor-pointer">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>

        <!-- Strict 2-Column Metrics Grid -->
        <div class="grid grid-cols-2 gap-4 pt-3 text-xs">
          <!-- Gemini Models -->
          <div class="space-y-2">
            <div class="text-[10px] font-mono font-semibold uppercase tracking-wider text-gray-500 flex items-center justify-between">
              <span>Gemini Models</span>
            </div>

            <!-- 5h -->
            <div class="space-y-1">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-gray-400">5-Hour Limit</span>
                <div class="flex items-center gap-1.5 font-mono">
                  <span class="${getTextPercentColor(g5)} font-medium">${g5.toFixed(0)}%</span>
                  ${g5 < 100 && g5_rt ? `<span class="text-[10px] text-gray-500">${g5_rt}</span>` : ''}
                </div>
              </div>
              <div class="h-1.5 w-full bg-surface-3 rounded-full overflow-hidden">
                <div class="h-full ${getBarColor(g5)} rounded-full" style="width: ${Math.max(2, g5)}%"></div>
              </div>
            </div>

            <!-- Weekly -->
            <div class="space-y-1 pt-0.5">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-gray-400">Weekly Limit</span>
                <div class="flex items-center gap-1.5 font-mono">
                  <span class="${getTextPercentColor(gw)} font-medium">${gw.toFixed(0)}%</span>
                  ${gw < 100 && gw_rt ? `<span class="text-[10px] text-gray-500">${gw_rt}</span>` : ''}
                </div>
              </div>
              <div class="h-1.5 w-full bg-surface-3 rounded-full overflow-hidden">
                <div class="h-full ${getBarColor(gw)} rounded-full" style="width: ${Math.max(2, gw)}%"></div>
              </div>
            </div>
          </div>

          <!-- Claude & GPT Models -->
          <div class="space-y-2 pl-4 border-l border-hairline/60">
            <div class="text-[10px] font-mono font-semibold uppercase tracking-wider text-gray-500 flex items-center justify-between">
              <span>Claude & GPT</span>
            </div>

            <!-- 5h -->
            <div class="space-y-1">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-gray-400">5-Hour Limit</span>
                <div class="flex items-center gap-1.5 font-mono">
                  <span class="${getTextPercentColor(c5)} font-medium">${c5.toFixed(0)}%</span>
                  ${c5 < 100 && c5_rt ? `<span class="text-[10px] text-gray-500">${c5_rt}</span>` : ''}
                </div>
              </div>
              <div class="h-1.5 w-full bg-surface-3 rounded-full overflow-hidden">
                <div class="h-full ${getBarColor(c5)} rounded-full" style="width: ${Math.max(2, c5)}%"></div>
              </div>
            </div>

            <!-- Weekly -->
            <div class="space-y-1 pt-0.5">
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-gray-400">Weekly Limit</span>
                <div class="flex items-center gap-1.5 font-mono">
                  <span class="${getTextPercentColor(cw)} font-medium">${cw.toFixed(0)}%</span>
                  ${cw < 100 && cw_rt ? `<span class="text-[10px] text-gray-500">${cw_rt}</span>` : ''}
                </div>
              </div>
              <div class="h-1.5 w-full bg-surface-3 rounded-full overflow-hidden">
                <div class="h-full ${getBarColor(cw)} rounded-full" style="width: ${Math.max(2, cw)}%"></div>
              </div>
            </div>
          </div>
        </div>
      `;
      return card;
    }

    function renderLogs() {
      const tbody = document.getElementById('logs-table-body');
      tbody.innerHTML = '';
      if (!state.logs || state.logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-gray-500">No events recorded.</td></tr>';
        return;
      }

      state.logs.forEach(log => {
        let typeBadge = `<span class="text-gray-500">INFO</span>`;
        if (log.type === 'LIMIT') typeBadge = `<span class="text-red-400 font-semibold">LIMIT</span>`;
        else if (log.type === 'SWITCH') typeBadge = `<span class="text-blue-400 font-semibold">SWITCH</span>`;
        else if (log.type === 'RESUMED') typeBadge = `<span class="text-emerald-400 font-semibold">RESUMED</span>`;
        else if (log.type === 'EVAL') typeBadge = `<span class="text-indigo-400 font-semibold">EVAL</span>`;

        const tr = document.createElement('tr');
        tr.className = 'hover:bg-surface-2 transition-colors';
        tr.innerHTML = `
          <td class="py-2 px-3 text-gray-500">${log.time}</td>
          <td class="py-2 px-2">${typeBadge}</td>
          <td class="py-2 px-3 text-gray-300 truncate max-w-xs">${log.desc}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function switchAccount(email) {
      try {
        await fetch('/api/switch', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ email })
        });
        setTimeout(fetchStatus, 800);
      } catch (e) {
        console.error(e);
      }
    }

    async function switchRecommended() {
      if (state.best) {
        await switchAccount(state.best);
      }
    }

    async function toggleAutoPilot() {
      try {
        await fetch('/api/toggle-autopilot', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ enable: !state.autopilot })
        });
        setTimeout(fetchStatus, 500);
      } catch (e) {
        console.error(e);
      }
    }

    async function deleteAccount(email) {
      if (confirm(`Remove account [${email}] from the switcher?`)) {
        await fetch('/api/delete', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ email })
        });
        setTimeout(fetchStatus, 500);
      }
    }

    async function enrollAccount() {
      if (confirm("Antigravity will restart with an empty session so you can log in. Proceed?")) {
        await fetch('/api/enroll', { method: 'POST' });
        setTimeout(fetchStatus, 1500);
      }
    }

    async function clearLogs() {
      if (confirm("Clear all overnight event logs?")) {
        await fetch('/api/clear-logs', { method: 'POST' });
        setTimeout(fetchStatus, 300);
      }
    }

    if (state.accounts && state.accounts.length > 0) {
      renderUI();
    }
    // Auto-poll status every 15 seconds
    setInterval(fetchStatus, 15000);
    fetchStatus();
  </script>
</body>
</html>
"""

# --- Local API Server for QWebEngineView ---
class LocalApiHandler(BaseHTTPRequestHandler):
    cached_status = None
    last_fetch_time = 0

    def log_message(self, format, *args):
        pass # Silence console logging

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index.html"):
            now = time.time()
            if not LocalApiHandler.cached_status or (now - LocalApiHandler.last_fetch_time > 12):
                LocalApiHandler.cached_status = self.build_status_payload()
                LocalApiHandler.last_fetch_time = now
            state_json = json.dumps(LocalApiHandler.cached_status)
            injected_html = HTML_INTERFACE.replace(
                "/* __INITIAL_STATE_PLACEHOLDER__ */",
                f"window.__INITIAL_STATE__ = {state_json};"
            )
            html_bytes = injected_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
        elif self.path == "/api/status":
            now = time.time()
            if not LocalApiHandler.cached_status or (now - LocalApiHandler.last_fetch_time > 12):
                LocalApiHandler.cached_status = self.build_status_payload()
                LocalApiHandler.last_fetch_time = now
                
            data_bytes = json.dumps(LocalApiHandler.cached_status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)
        elif self.path == "/api/subagents" or self.path.startswith("/api/subagents"):
            query_cid = None
            if "?" in self.path:
                try:
                    params = urllib.parse.parse_qs(self.path.split("?")[1])
                    query_cid = params.get("cid", [None])[0]
                except Exception:
                    pass
            dag_data = subagent_tracker.parse_conversation_dag(query_cid)
            data_bytes = json.dumps(dag_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)
        elif self.path == "/api/mcp":
            mcp_data = mcp_supervisor.get_mcp_matrix()
            data_bytes = json.dumps(mcp_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)
        elif self.path == "/app_icon.png":
            if os.path.exists(ICON_PNG):
                png_bytes = open(ICON_PNG, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png_bytes)))
                self.end_headers()
                self.wfile.write(png_bytes)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len) if content_len > 0 else b'{}'
        try:
            req_data = json.loads(body.decode("utf-8"))
        except Exception:
            req_data = {}

        if self.path == "/api/switch":
            target = req_data.get("email")
            if target:
                switch_to_account_core(target)
                LocalApiHandler.cached_status = None
            resp_bytes = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        elif self.path == "/api/toggle-autopilot":
            enable = req_data.get("enable", True)
            set_autopilot_state(enable)
            LocalApiHandler.cached_status = None
            resp_bytes = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        elif self.path == "/api/delete":
            target = req_data.get("email")
            if target:
                acc_dir = os.path.join(ACCOUNTS_DIR, target)
                if os.path.exists(acc_dir):
                    shutil.rmtree(acc_dir)
                if os.path.exists(ACTIVE_FILE):
                    try:
                        cur = open(ACTIVE_FILE).read().strip()
                        if cur == target:
                            os.remove(ACTIVE_FILE)
                    except Exception:
                        pass
                LocalApiHandler.cached_status = None
            resp_bytes = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        elif self.path == "/api/enroll":
            save_active_credential()
            stop_antigravity()
            delete_windows_credential(CRED_TARGET)
            clear_session_cache()
            if os.path.exists(ACTIVE_FILE):
                os.remove(ACTIVE_FILE)
            start_antigravity()
            LocalApiHandler.cached_status = None
            resp_bytes = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        elif self.path == "/api/clear-logs":
            if os.path.exists(LOG_FILE):
                open(LOG_FILE, "w").close()
            LocalApiHandler.cached_status = None
            resp_bytes = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        elif self.path == "/api/mcp/ping":
            server_name = req_data.get("name")
            res = mcp_supervisor.ping_mcp_server(server_name) if server_name else {"success": False, "error": "Missing name"}
            resp_bytes = json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        elif self.path == "/api/mcp/restart":
            server_name = req_data.get("name")
            res = mcp_supervisor.restart_mcp_server(server_name) if server_name else {"success": False, "error": "Missing name"}
            resp_bytes = json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def build_status_payload(self):
        active = save_active_credential()
        accounts = get_saved_accounts()
        ap_running, _ = is_autopilot_running()

        quotas = {}
        with ThreadPoolExecutor(max_workers=min(len(accounts), 5) or 1) as executor:
            future_to_acc = {executor.submit(fetch_quota_summary, acc): acc for acc in accounts}
            for future in future_to_acc:
                acc = future_to_acc[future]
                try:
                    q = future.result()
                    # Pre-calculate delta strings for web view
                    for grp in ['gemini', 'claude']:
                        if grp in q:
                            for w in ['5h', 'weekly']:
                                if w in q[grp] and isinstance(q[grp][w], dict):
                                    rt = q[grp][w].get("resetTime")
                                    q[grp][w]["resetDelta"] = parse_reset_delta(rt)
                    quotas[acc] = q
                except Exception as e:
                    quotas[acc] = {"error": str(e)}

        ranked = sorted(accounts, key=lambda a: score_account(quotas.get(a)), reverse=True)
        best = ranked[0] if ranked else None

        # Parse logs
        parsed_logs = []
        if os.path.exists(LOG_FILE):
            try:
                lines = open(LOG_FILE, "r", encoding="utf-8", errors="ignore").readlines()
                recent = lines[-40:]
                recent.reverse()
                for raw in recent:
                    raw = raw.strip()
                    if not raw:
                        continue
                    m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)", raw)
                    ts = m.group(1) if m else "-"
                    body = m.group(2) if m else raw
                    
                    if "LIMIT TERDETEKSI" in body:
                        evt = "LIMIT"
                    elif "Auto-Switch" in body:
                        evt = "SWITCH"
                    elif "CDP" in body or "dilanjutkan" in body or "sukses" in body.lower():
                        evt = "RESUMED"
                    elif "Akun terbaik" in body:
                        evt = "EVAL"
                    else:
                        evt = "INFO"
                    parsed_logs.append({"time": ts.split(" ")[1] if " " in ts else ts, "type": evt, "desc": body})
            except Exception:
                pass

        return {
            "active": active,
            "accounts": accounts,
            "quotas": quotas,
            "autopilot": bool(ap_running),
            "best": best,
            "logs": parsed_logs
        }

class ReusableThreadingServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def start_local_server():
    global LOCAL_SERVER_INSTANCE, ACTUAL_PORT
    for p in range(28795, 28830):
        try:
            server = ReusableThreadingServer(("127.0.0.1", p), LocalApiHandler)
            LOCAL_SERVER_INSTANCE = server
            ACTUAL_PORT = p
            server.serve_forever()
            return
        except OSError:
            continue

def apply_dwm_frameless_styling(hwnd):
    try:
        dwm = ctypes.windll.dwmapi
        # Windows 11 rounded corners: DWMWA_WINDOW_CORNER_PREFERENCE = 33 (DWMWCP_ROUND = 2)
        corner = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), wintypes.DWORD(33), ctypes.byref(corner), ctypes.sizeof(corner))
        # Hairline obsidian border: DWMWA_BORDER_COLOR = 34 (0x00222222)
        border_color = ctypes.c_int(0x00222222)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), wintypes.DWORD(34), ctypes.byref(border_color), ctypes.sizeof(border_color))
    except Exception:
        pass

# --- Desktop 1:1 Antigravity 2.0 Custom TitleBar ---
class AntigravityProTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("antigravity_titlebar")
        self.setStyleSheet("""
            QWidget#antigravity_titlebar {
                background-color: #131313;
                border-bottom: 1px solid #222222;
            }
            QLabel {
                color: #8C8C8C;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                font-size: 12px;
                background: transparent;
            }
            QLabel#brand {
                color: #FAFAFA;
                font-weight: 600;
                font-size: 12px;
                padding-right: 12px;
            }
            QLabel#badge {
                color: #388BFD;
                background-color: rgba(56, 139, 253, 0.12);
                border: 1px solid rgba(56, 139, 253, 0.3);
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-family: 'JetBrains Mono', Consolas, monospace;
                font-weight: 500;
                margin-left: 6px;
            }
            QPushButton.menu-btn {
                background: transparent;
                border: none;
                color: #CCCCCC;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                font-size: 12px;
                padding: 0 8px;
                height: 32px;
            }
            QPushButton.menu-btn:hover {
                background-color: #222222;
                color: #FFFFFF;
            }
            QPushButton.menu-btn::menu-indicator {
                image: none;
            }
            QPushButton.win-btn {
                background: transparent;
                border: none;
                color: #CCCCCC;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                width: 46px;
                height: 32px;
            }
            QPushButton.win-btn:hover {
                background-color: #262626;
                color: #FFFFFF;
            }
            QPushButton#btnClose:hover {
                background-color: #E81123;
                color: #FFFFFF;
            }
            QMenu {
                background-color: #191919;
                color: #E2E8F0;
                border: 1px solid #222222;
                border-radius: 6px;
                padding: 4px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #272727;
                color: #FFFFFF;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Antigravity Logo
        icon_to_use = QIcon(ICON_ICO) if os.path.exists(ICON_ICO) else (QIcon(ICON_PNG) if os.path.exists(ICON_PNG) else None)
        if icon_to_use:
            lbl_ico = QLabel(self)
            lbl_ico.setPixmap(icon_to_use.pixmap(16, 16))
            lbl_ico.setStyleSheet("margin-right: 8px;")
            layout.addWidget(lbl_ico)
            
        # 2. Antigravity Brand Text
        lbl_brand = QLabel("Antigravity", self)
        lbl_brand.setObjectName("brand")
        layout.addWidget(lbl_brand)
        
        # 3. Application Menus (File, View, Window)
        self.btn_file = QPushButton("File", self)
        self.btn_file.setProperty("class", "menu-btn")
        m_file = QMenu(self)
        act_sync = m_file.addAction("Sync Credentials")
        act_sync.triggered.connect(self.sync_creds)
        m_file.addSeparator()
        act_quit = m_file.addAction("Quit Application")
        act_quit.triggered.connect(QApplication.instance().quit)
        self.btn_file.setMenu(m_file)
        layout.addWidget(self.btn_file)
        
        self.btn_view = QPushButton("View", self)
        self.btn_view.setProperty("class", "menu-btn")
        m_view = QMenu(self)
        m_view.addAction("Accounts Radar").triggered.connect(lambda: self.switch_view("accounts"))
        m_view.addAction("Subagent DAG").triggered.connect(lambda: self.switch_view("subagents"))
        m_view.addAction("MCP Matrix").triggered.connect(lambda: self.switch_view("mcp"))
        m_view.addAction("Activity Logs").triggered.connect(lambda: self.switch_view("logs"))
        m_view.addAction("Enroll Account").triggered.connect(lambda: self.switch_view("manage"))
        m_view.addSeparator()
        m_view.addAction("Reload Window").triggered.connect(lambda: self.window().browser.reload() if hasattr(self.window(), "browser") else None)
        self.btn_view.setMenu(m_view)
        layout.addWidget(self.btn_view)

        self.btn_window = QPushButton("Window", self)
        self.btn_window.setProperty("class", "menu-btn")
        m_window = QMenu(self)
        m_window.addAction("Minimize").triggered.connect(lambda: self.window().showMinimized())
        m_window.addAction("Toggle Maximize").triggered.connect(self.toggle_max)
        m_window.addSeparator()
        m_window.addAction("Hide to System Tray").triggered.connect(lambda: self.window().hide())
        self.btn_window.setMenu(m_window)
        layout.addWidget(self.btn_window)

        # 4. Control Center Pill
        lbl_badge = QLabel("CONTROL CENTER", self)
        lbl_badge.setObjectName("badge")
        layout.addWidget(lbl_badge)
        
        # 5. Drag region stretcher
        layout.addStretch()
        
        # 6. Window Controls (Minimize, Maximize, Close)
        self.btn_min = QPushButton("—", self)
        self.btn_min.setProperty("class", "win-btn")
        self.btn_min.clicked.connect(lambda: self.window().showMinimized())
        layout.addWidget(self.btn_min)
        
        self.btn_max = QPushButton("□", self)
        self.btn_max.setProperty("class", "win-btn")
        self.btn_max.clicked.connect(self.toggle_max)
        layout.addWidget(self.btn_max)
        
        self.btn_close = QPushButton("✕", self)
        self.btn_close.setProperty("class", "win-btn")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(lambda: self.window().close())
        layout.addWidget(self.btn_close)

    def toggle_max(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
            self.btn_max.setText("□")
        else:
            win.showMaximized()
            self.btn_max.setText("❐")

    def sync_creds(self):
        win = self.window()
        if hasattr(win, "browser"):
            win.browser.page().runJavaScript("if (typeof fetchStatus === 'function') fetchStatus(true);")

    def switch_view(self, tab_name):
        win = self.window()
        if hasattr(win, "browser"):
            win.browser.page().runJavaScript(f"if (typeof setTab === 'function') setTab('{tab_name}');")

# --- Desktop Window Host ---
class AntigravityProWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Antigravity Control Center")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.resize(680, 780)
        self.setMinimumSize(600, 680)
        
        self.titlebar = AntigravityProTitleBar(self)
        self.setMenuWidget(self.titlebar)

        icon_to_use = QIcon(ICON_ICO) if os.path.exists(ICON_ICO) else (QIcon(ICON_PNG) if os.path.exists(ICON_PNG) else None)
        if icon_to_use:
            self.setWindowIcon(icon_to_use)

        self.browser = QWebEngineView(self)
        self.browser.page().setBackgroundColor(QtGui.QColor("#101010"))
        self.setCentralWidget(self.browser)
        self.browser.load(QUrl(f"http://127.0.0.1:{ACTUAL_PORT}"))
        
        self.init_tray()

    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(message.__int__())
        if msg.message == 0x0084:  # WM_NCHITTEST
            x = msg.lParam & 0xFFFF
            if x > 32767: x -= 65536
            y = (msg.lParam >> 16) & 0xFFFF
            if y > 32767: y -= 65536
            
            p = self.mapFromGlobal(QPoint(x, y))
            w = self.width()
            h = self.height()
            border = 6
            
            left = p.x() < border
            right = p.x() > w - border
            top = p.y() < border
            bottom = p.y() > h - border
            
            if top and left: return True, 13     # HTTOPLEFT
            if top and right: return True, 14    # HTTOPRIGHT
            if bottom and left: return True, 16  # HTBOTTOMLEFT
            if bottom and right: return True, 17 # HTBOTTOMRIGHT
            if left: return True, 10             # HTLEFT
            if right: return True, 11            # HTRIGHT
            if bottom: return True, 15           # HTBOTTOM
            if top: return True, 12              # HTTOP
            
            # Titlebar drag region
            if p.y() < 32:
                child = self.childAt(p)
                if isinstance(child, QPushButton):
                    return False, 0 # Let Qt handle button clicks
                return True, 2      # HTCAPTION (native window drag + snap)
                
        return super().nativeEvent(eventType, message)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            if hasattr(self, "titlebar"):
                if self.isMaximized():
                    self.titlebar.btn_max.setText("❐")
                else:
                    self.titlebar.btn_max.setText("□")
        super().changeEvent(event)

    def init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        icon_to_use = QIcon(ICON_ICO) if os.path.exists(ICON_ICO) else (QIcon(ICON_PNG) if os.path.exists(ICON_PNG) else None)
        if icon_to_use:
            self.tray_icon.setIcon(icon_to_use)
            
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #191919;
                color: #E2E8F0;
                border: 1px solid #222222;
                border-radius: 6px;
                padding: 4px;
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #272727;
                color: #FFFFFF;
            }
        """)
        
        act_show = QAction("Open Control Center", self)
        act_show.triggered.connect(self.show_normal_window)
        menu.addAction(act_show)
        
        menu.addSeparator()
        
        act_quit = QAction("Quit Application", self)
        act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_normal_window()

    def show_normal_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()
        apply_dwm_frameless_styling(int(self.winId()))

    def showEvent(self, event):
        super().showEvent(event)
        apply_dwm_frameless_styling(int(self.winId()))

    def closeEvent(self, event):
        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
        else:
            event.accept()

def main():
    if "--daemon" in sys.argv:
        try:
            from antigravity_switcher import daemon
            daemon.main_loop()
        except ImportError:
            import daemon
            daemon.main_loop()
        sys.exit(0)

    if "--cli" in sys.argv:
        try:
            from antigravity_switcher import switcher
            switcher.main()
        except ImportError:
            import switcher
            switcher.main()
        sys.exit(0)

    ensure_dirs()
    
    server_thread = threading.Thread(target=start_local_server, daemon=True)
    server_thread.start()
    for _ in range(40):
        if LOCAL_SERVER_INSTANCE is not None:
            break
        time.sleep(0.05)
    
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon_to_use = QIcon(ICON_ICO) if os.path.exists(ICON_ICO) else (QIcon(ICON_PNG) if os.path.exists(ICON_PNG) else None)
    if icon_to_use:
        app.setWindowIcon(icon_to_use)
    
    win = AntigravityProWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    apply_dwm_frameless_styling(int(win.winId()))
    QTimer.singleShot(50, lambda: apply_dwm_frameless_styling(int(win.winId())))
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
