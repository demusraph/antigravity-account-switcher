# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.2] - 2026-09-08

### Fixed
- **Anti-Wrapping Layout Hardening**: Enforced strict `whitespace-nowrap` and `shrink-0` across all Mission Control Toolbar items (Auto-Pilot toggle button, account count badge, quick recommendation action, and navigation tabs), completely eliminating ugly multi-line text wrapping on narrow viewports.
- **Responsive Active Email Truncation**: Added responsive CSS truncation (`truncate max-w-[170px] sm:max-w-[260px] md:max-w-[340px]`) with dynamic `title` tooltip so long email addresses never push neighboring control buttons into awkward line-breaks.
- **Window Geometry Optimization**: Expanded default window proportions from `680x780` to an ergonomic `840x800` (minimum `660x680`) with updated restore fallback geometry and fine-tuned Win32 `HTCAPTION` hit-test boundaries for flawless high-DPI Windows display scaling (125%-150%).

---

## [1.2.1] - 2026-09-08

### Fixed
- **Auto-Pilot Daemon Toggle Lifecycle**: Fixed `NameError` path resolution bug in `set_autopilot_state()` with dynamic entrypoint discovery (`main.py --daemon` / `daemon.py` / `-m antigravity_switcher.daemon`).
- **Realtime Win32 Process Validation**: Replaced naive PID file checks with `kernel32.GetExitCodeProcess == 259 (STILL_ACTIVE)` and automated stale PID cleanup.
- **Headless Stream Guard**: Added fallback redirection for `sys.stdout` and `sys.stderr` to `os.devnull` in `daemon.py` when executed via `pythonw.exe`.
- **Clean Typography & Effect Removal**: Removed ShinyText gradient shimmer animation from the topbar brand name, restoring solid crisp `#FFFFFF` white typography; purged ClickSpark canvas particle engine from the DOM.

---

## [1.2.0] - 2026-09-08

### Added
- **PyQt5 Window Physics Animations**: Implemented `QPropertyAnimation` easing for window maximize (`OutCubic`, 220ms), minimize opacity fade (`InQuad`, 140ms), and tray restore fade-in (`OutQuad`, 160ms) to eliminate abrupt jumping on Windows 11 frameless windows.
- **React Bits Micro-Interactions**: Integrated `SpotlightCard` cursor-following radial glow on account & DAG cards, `DecryptedText` cyber scramble on email initialization, `CountUp` smooth quota number animations, `ButtonSpring` tactile haptics, and `TabAnimatedEnter` view transitions.
- **1:1 Antigravity 2.0 Obsidian Window Frame**: Removed white frameless border artifact with DWM dark mode attribute synchronization (`DWMWA_USE_IMMERSIVE_DARK_MODE`, `DWMWA_WINDOW_CORNER_PREFERENCE`).

---

## [1.1.0] - 2026-09-08

### Added
- **Live Subagent DAG & Execution Trace (`subagent_tracker.py`)**: Real-time hierarchical visualization of active conversation threads: Parent Orchestrator $\rightarrow$ Child Subagents, step telemetry, active tool execution chips, and token burn estimation.
- **MCP Server Matrix & Health Supervisor (`mcp_supervisor.py`)**: Auto-discovery of all 5 local MCP servers (`Roblox_Studio`, `Excel_Cowork`, `Google_Slides`, `Blender`, `MS_Project`) from `~/.gemini/config/mcp_config.json`.
- **1-Click MCP JSON-RPC Ping Probe**: Fast non-blocking handshake probe verifying stdio responsiveness and measuring latency in milliseconds.
- **1-Click MCP Process Self-Heal**: Safely resets broken pipes and zombie child processes to clean standby without restarting Antigravity.
- **Explicit Windows AppUserModelID**: Fixed Windows taskbar icon binding (`google.antigravity.controlcenter.pro.v1`) to prevent defaulting to Anaconda/Spyder host icons.

---

## [1.0.0] - 2026-09-08

### Added
- **Zero-Loss Hot Switching**: Swap Antigravity Google accounts in real time without closing the IDE or losing editor tabs and context.
- **Real-Time Quota Radar**: Dual-metric monitoring for Gemini Models (Flash/Pro) and Claude/GPT Models with live progress bars and reset deltas.
- **Autonomous Overnight Auto-Pilot**: Background watchdog daemon monitoring `language_server.log` for 429 / `RESOURCE_EXHAUSTED` events.
- **CDP Auto-Resume Protocol**: Automated task resumption via Chrome DevTools Protocol WebSocket evaluation upon account swap.
- **Native Obsidian Dark UI**: PyQt5 + QWebEngine interface with dark system tokens, zero-emoji SVG typography, and system tray integration.
- **Dual Execution Engine**: Supports interactive GUI, headless terminal CLI (`--cli`), and silent background daemon (`--daemon`).
- **Standalone Windows Distribution**: Pre-compiled standalone Windows x64 binary (`AntigravityControlCenter.exe`) requiring zero Python host installation.
- **GitHub Actions Automated CI/CD**: Automatic PyInstaller compilation and release packaging on tag push (`v*`).

---

## [Unreleased] - Planned for v1.1.0

### Planned
- Cross-platform macOS Keychain adapter (`/usr/bin/security`) for MacBook M-series / Intel support.
- Automated notification sound triggers for quota depletion events.
- Export / import encrypted backup of saved account configurations.
