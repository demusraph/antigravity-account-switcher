# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
