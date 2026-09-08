import os
import sys
import json
import time
import psutil
import subprocess

USERPROFILE = os.environ.get("USERPROFILE", "")
GLOBAL_MCP_CONFIG = os.path.join(USERPROFILE, ".gemini", "config", "mcp_config.json")
ALT_MCP_CONFIG = os.path.join(USERPROFILE, ".gemini", "antigravity-cli", "mcp_config.json")

def get_mcp_config_path():
    if os.path.exists(GLOBAL_MCP_CONFIG):
        return GLOBAL_MCP_CONFIG
    if os.path.exists(ALT_MCP_CONFIG):
        return ALT_MCP_CONFIG
    return None

def load_mcp_servers():
    cfg_path = get_mcp_config_path()
    if not cfg_path or not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mcpServers", {})
    except Exception as e:
        print(f"[MCP Supervisor] Error reading config: {e}")
        return {}

def inspect_running_processes():
    """
    Finds running processes associated with configured MCP servers.
    """
    matches = {}
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'create_time']):
        try:
            cmdline_list = proc.info.get('cmdline') or []
            cmdline_str = " ".join(cmdline_list).lower()
            pname = (proc.info.get('name') or "").lower()

            # Identify Roblox Studio MCP
            if "studiomcp" in pname or "studiomcp" in cmdline_str:
                matches["Roblox_Studio"] = proc
            elif "excel_mcp_server" in cmdline_str:
                matches["Excel_Cowork"] = proc
            elif "google_slides_mcp_server" in cmdline_str:
                matches["Google_Slides"] = proc
            elif "msproject_mcp_server" in cmdline_str:
                matches["MS_Project"] = proc
            elif "blender-mcp" in cmdline_str or "blender_mcp" in cmdline_str:
                matches["Blender"] = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return matches

def get_mcp_matrix():
    """
    Returns a unified matrix of all configured MCP servers and their real-time process state.
    """
    servers = load_mcp_servers()
    running_procs = inspect_running_processes()
    now = time.time()
    result = []

    for name, s_cfg in servers.items():
        cmd = s_cfg.get("command", "")
        args = s_cfg.get("args", [])
        full_cmd_str = f"{cmd} {' '.join(args)}"

        proc = running_procs.get(name)
        if proc and proc.is_running():
            try:
                mem_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
                cpu = proc.cpu_percent(interval=None)
                uptime_sec = int(now - proc.create_time())
                uptime_str = f"{uptime_sec // 60}m {uptime_sec % 60}s" if uptime_sec > 60 else f"{uptime_sec}s"
                status = "ONLINE"
                pid = proc.pid
            except Exception:
                status = "ONLINE"
                mem_mb = 0
                cpu = 0
                uptime_str = "Active"
                pid = proc.pid
        else:
            status = "STANDBY" # Antigravity lazy-loads MCP on tool call
            mem_mb = 0
            cpu = 0
            uptime_str = "-"
            pid = None

        result.append({
            "name": name,
            "status": status,
            "pid": pid,
            "memory_mb": mem_mb,
            "cpu_percent": cpu,
            "uptime": uptime_str,
            "command": cmd,
            "args": args,
            "preview_cmd": (full_cmd_str[:65] + "...") if len(full_cmd_str) > 65 else full_cmd_str
        })

    return result

def ping_mcp_server(name):
    """
    Performs a 2-second JSON-RPC ping probe to test stdio responsiveness.
    """
    servers = load_mcp_servers()
    s_cfg = servers.get(name)
    if not s_cfg:
        return {"success": False, "error": f"Server {name} not found in config"}

    cmd = s_cfg.get("command", "")
    args = s_cfg.get("args", [])
    full_cmd = [cmd] + args

    t0 = time.time()
    try:
        p = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )

        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Antigravity-Radar", "version": "1.0"}
            }
        }) + "\n"

        p.stdin.write(init_req)
        p.stdin.flush()

        # Non-blocking or quick read
        resp_line = ""
        for _ in range(25):
            time.sleep(0.1)
            if p.poll() is not None:
                break
            # Try read line
            resp_line = p.stdout.readline()
            if resp_line:
                break

        latency_ms = int((time.time() - t0) * 1000)
        p.terminate()
        try:
            p.wait(timeout=1)
        except Exception:
            p.kill()

        if resp_line:
            try:
                resp_json = json.loads(resp_line)
                return {
                    "success": True,
                    "latency_ms": latency_ms,
                    "response": resp_json.get("result", {})
                }
            except Exception:
                return {
                    "success": True,
                    "latency_ms": latency_ms,
                    "raw_response": resp_line.strip()[:100]
                }
        else:
            return {
                "success": False,
                "latency_ms": latency_ms,
                "error": "Timeout waiting for JSON-RPC initialize response"
            }

    except Exception as e:
        return {
            "success": False,
            "latency_ms": int((time.time() - t0) * 1000),
            "error": str(e)
        }

def restart_mcp_server(name):
    """
    Terminates running process of the MCP server to clear broken pipes/zombies.
    """
    running_procs = inspect_running_processes()
    proc = running_procs.get(name)
    killed = False
    if proc and proc.is_running():
        try:
            proc.kill()
            killed = True
        except Exception as e:
            return {"success": False, "error": f"Failed to terminate: {e}"}

    return {"success": True, "killed": killed, "message": f"{name} process reset to clean standby."}

if __name__ == "__main__":
    print("=== MCP Supervisor Matrix ===")
    matrix = get_mcp_matrix()
    print(json.dumps(matrix, indent=2))
