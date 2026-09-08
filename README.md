<div align="center">

  <img src="assets/icons/app_icon.png" width="96" height="96" alt="Antigravity Control Center Logo">

  # Antigravity Control Center

  **Autonomous Multi-Account Orchestrator, Quota Radar & Overnight Task Continuity**

  [![Release](https://img.shields.io/github/v/release/demusraph/antigravity-account-switcher?style=flat-square&color=2B7FFF)](https://github.com/demusraph/antigravity-account-switcher/releases)
  [![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011%20(x64)-0078D6?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com)
  [![macOS Roadmap](https://img.shields.io/badge/macOS-Planned%20v1.1.0-orange?style=flat-square&logo=apple&logoColor=white)](#-roadmap)
  [![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
  [![Design System](https://img.shields.io/badge/Design%20System-Obsidian%20Dark%20(%23101010)-101010?style=flat-square)](#-antigravity-native-obsidian-design)
  [![Security](https://img.shields.io/badge/Security-Local%20DPAPI%20%7C%20Zero%20Cloud-10B981?style=flat-square)](SECURITY.md)
  [![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)

  <br>

  <img src="assets/screenshots/showcase.png" alt="Antigravity Control Center Interface" width="680">

</div>

<br>

## ⚡ Overview

**Antigravity Control Center** is an enterprise-grade desktop management system designed to eliminate quota exhaustion barriers (`RESOURCE_EXHAUSTED` / HTTP 429) across Gemini and Claude AI models.

Rather than forcing developers to manually log out, restart applications, or interrupt long-running coding tasks, Antigravity Control Center provides instantaneous **hot-swapping via Windows Credential Manager**, live **multi-account quota radar telemetry**, and an **autonomous overnight auto-pilot** that intercepts rate limits and resumes unfinished AI tasks via Chrome DevTools Protocol (CDP).

---

## ✨ Key Capabilities

### 🔄 Zero-Loss Credential Hot-Swapping
- Swaps active authentication tokens directly inside the Windows Credential Manager (`gemini:antigravity`) via native Win32 DPAPI (`advapi32.dll`).
- **Preserves Editor State**: Open tabs, SQLite caches (`state.vscdb`), prompt histories, and terminal workspaces remain completely undisturbed during switches.

### 🤖 Autonomous Overnight Auto-Pilot (CDP Integration)
- A decoupled, low-overhead background daemon that monitors language server diagnostics in real time.
- **Self-Healing Execution Cycle**:
  1. Detects `RESOURCE_EXHAUSTED` (429) exceptions in `language_server.log`.
  2. Evaluates the multi-account pool and selects the account with the highest available quota.
  3. Hot-swaps the active OS credentials in milliseconds.
  4. Interfaces with the local **Chrome DevTools Protocol (CDP)** endpoint to automatically trigger task resumption—enabling autonomous, uninterrupted overnight agent runs while you sleep.
  5. Emits unobtrusive native Windows toast notifications upon state transitions.

### 📊 Real-Time Multi-Account Quota Radar
- Live telemetry calculation querying official OAuth endpoints for:
  - **Gemini Models** (5-Hour Sliding Window & Weekly Token Limit)
  - **Claude & GPT Models** (5-Hour Window & Weekly Quota)
  - **Dynamic Reset Deltas** (e.g., `3h 48m`, `5d 12h`)
- Algorithmic score ranking that automatically flags the optimal backup account with a `Recommended` badge and enables a 1-click quick-switch action.

### 🖤 Antigravity Native Obsidian Design
- Precision UI adhering 1:1 to official Antigravity dark obsidian design tokens:
  - Canvas: `#101010`
  - Elevated Surfaces: `#191919`
  - Dividers & Outlines: `#222222` hairline borders
  - Interactive Accent: `#2B7FFF` Antigravity Electric Blue
- **Zero-Emoji Discipline**: Professional, clutter-free typography and vector iconography.
- System Tray integration with silent background minimization (`Hide to Tray`).

---

## 🏗️ Technical Architecture

```mermaid
flowchart TD
    subgraph Antigravity Workspace
        IDE[Antigravity IDE Window]
        LS[Language Server Diagnostics Log]
        CDP[CDP DevTools Active Port]
    end

    subgraph Windows Subsystem
        WCM[Windows Credential Manager\ngemini:antigravity - DPAPI]
        TOAST[Windows Action Center Toasts]
    end

    subgraph Antigravity Control Center
        APP[AntigravityControlCenter.exe\nStandalone GUI Host]
        CLI[Terminal CLI Switcher\n--cli Mode]
        DAEMON[Auto-Pilot Watcher Daemon\n--daemon Mode]
        STORE[~/.gemini/antigravity-switcher\nPer-User Profile Vault]
    end

    APP -->|Hot-Swap Token| WCM
    CLI -->|Hot-Swap Token| WCM
    DAEMON -->|Monitor 429| LS
    DAEMON -->|Auto-Swap Best Account| WCM
    DAEMON -->|Resume Active Session| CDP
    DAEMON -->|Dispatch Alert| TOAST
    APP <--> STORE
    CLI <--> STORE
```

---

## 🚀 Quick Start

### Option 1: Standalone Executable (No Python Required)
1. Download **`AntigravityControlCenter-Windows-x64.zip`** from [Latest Releases](https://github.com/demusraph/antigravity-account-switcher/releases).
2. Extract the ZIP archive anywhere on your system.
3. Run **`AntigravityControlCenter.exe`**.

> [!NOTE]
> #### 🛡️ Windows SmartScreen Notice
> Because Antigravity Control Center is a newly released, independent open-source project without a commercial Microsoft EV Code Signing Certificate ($500+/year), Windows Defender SmartScreen may display an alert:
> 
> **"Windows protected your PC / Unknown Publisher"**
> 
> 1. Click **More info** (*Informasi selengkapnya*).
> 2. Click **Run anyway** (*Tetap jalankan*).
> 
> All source code and build pipelines are 100% transparent, auditable, and compiled publicly via GitHub Actions.

### Option 2: Run from Source (Python 3.10+)
```bash
# 1. Clone the repository
git clone https://github.com/demusraph/antigravity-account-switcher.git
cd antigravity-account-switcher

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch Desktop GUI
python main.py
# or via batch launcher:
scripts\Launch-GUI.bat

# 4. Launch Interactive CLI
python main.py --cli
# or via batch launcher:
scripts\Launch-CLI.bat
```

### Option 3: Install Desktop Shortcut
Run **`scripts\Create-Desktop-Shortcut.bat`** to instantly create a shortcut with the official Obsidian iridescent icon on your Windows Desktop.

---

## 🔒 Security & Privacy Guarantees

1. **Native DPAPI Encryption**:
   - Accounts are stored locally on your machine using Windows Data Protection API (DPAPI).
   - Sensitive tokens are **never** written in plain text to disk or synced to third-party servers.
2. **Zero Cloud Telemetry**:
   - 100% offline-capable and localhost-bound (`127.0.0.1`).
   - No external trackers, analytics, or telemetry beacons.
3. **Transparent & Auditable**:
   - Fully open-source codebase with minimal dependencies. See [`SECURITY.md`](SECURITY.md) and [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) for full architecture details.

---

## 📁 Repository Structure

```text
antigravity-account-switcher/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml          # Structured GitHub Issue Form for bug triage
│   │   └── feature_request.yml     # Structured Feature Request template
│   ├── workflows/
│   │   └── build-exe.yml           # Automated Windows CI/CD Release pipeline
│   └── PULL_REQUEST_TEMPLATE.md    # Pull Request checklist & guidelines
├── assets/
│   ├── icons/
│   │   ├── app_icon.ico            # Multi-resolution Windows executable icon
│   │   └── app_icon.png            # High-res Obsidian branding logo
│   └── screenshots/
│       └── showcase.png            # Clean UI preview screenshot
├── docs/
│   └── SECURITY_MODEL.md           # Local DPAPI & credential security details
├── scripts/
│   ├── Create-Desktop-Shortcut.bat # 1-Click desktop shortcut installer
│   ├── Launch-CLI.bat              # Fast headless terminal launcher
│   └── Launch-GUI.bat              # Direct desktop GUI launcher
├── src/
│   └── antigravity_switcher/
│       ├── __init__.py             # Package metadata & exports
│       ├── __main__.py             # Package execution dispatcher
│       ├── app.py                  # PyQt5 Native Obsidian GUI & WebEngine radar
│       ├── daemon.py               # Auto-Pilot & CDP auto-resume daemon
│       └── switcher.py             # Win32 Credential Manager hot-swapper & CLI
├── main.py                         # Root execution entry point
├── pyproject.toml                  # Modern PEP 517/621 packaging configuration
├── requirements.txt                # Python dependencies (PyQt5, PyQtWebEngine)
├── .gitignore                      # Filter for caches, logs, and session profiles
├── CHANGELOG.md                    # Keep a Changelog semantic release notes
├── CONTRIBUTING.md                 # Contributor onboarding & development guide
├── LICENSE                         # MIT Open Source License
├── README.md                       # Master technical documentation
└── SECURITY.md                     # Responsible disclosure & privacy policy
```

---

## 🗺️ Roadmap

- [x] **v1.0.0**: Windows 10/11 x64 support, PyQt5 Obsidian GUI, Dual Quota Radar, CDP Auto-Resume, Standalone Executable, GitHub Actions CI/CD.
- [ ] **v1.1.0**: Cross-platform **macOS Keychain** integration (`/usr/bin/security`) & Apple Silicon M-series DMG bundle.
- [ ] **v1.2.0**: Linux Secret Service / Keyring integration.
- [ ] **v1.3.0**: Encrypted cross-device profile export/import.

---

## 🤝 Contributing

Contributions are welcome! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting a pull request.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.
