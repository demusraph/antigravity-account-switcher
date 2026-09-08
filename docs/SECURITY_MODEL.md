# Antigravity Control Center - Security Model

This document outlines the security, data privacy, and isolation guarantees implemented in **Antigravity Control Center**.

---

## 1. Threat Model & Boundaries

| Asset / Boundary | Storage Location | Protection Mechanism |
| ---------------- | ---------------- | -------------------- |
| OAuth Refresh Tokens | `%USERPROFILE%\.gemini\antigravity-switcher\accounts\` | Local file ACLs + DPAPI in Credential Manager |
| Active IDE Token | Windows Credential Manager (`gemini:antigravity`) | Win32 DPAPI encryption bound to user SID |
| CDP Automation | `127.0.0.1:<random-port>` | Local loopback only, ephemeral port binding |
| Quota Metrics | In-memory cache | Ephemeral polling, zero persistence to remote servers |

---

## 2. Windows DPAPI Encryption

Windows Credential Manager stores credentials securely using the **CryptProtectData (DPAPI)** subsystem:
- Master encryption keys are derived from the user's login password.
- No other Windows user account on the machine can decrypt the stored `gemini:antigravity` target.
- Antigravity Control Center only reads or updates this target using Windows official API calls (`CredReadW` / `CredWriteW`).

---

## 3. Local Isolation vs Multi-Tenant Environments

When multiple developers or accounts use the same physical computer under different Windows profiles:
- Each user has their own independent `%USERPROFILE%\.gemini\antigravity-switcher\` folder.
- Account switching in User A does not affect or expose credentials to User B.
