import os
import json
import time
import glob
from datetime import datetime

USERPROFILE = os.environ.get("USERPROFILE", "")
BRAIN_DIR = os.path.join(USERPROFILE, ".gemini", "antigravity", "brain")

def get_recent_conversations(limit=8):
    """
    Finds the most recent Antigravity conversations sorted by last transcript update.
    """
    if not os.path.exists(BRAIN_DIR):
        return []

    sessions = []
    try:
        subdirs = [d for d in os.listdir(BRAIN_DIR) if os.path.isdir(os.path.join(BRAIN_DIR, d))]
        for cid in subdirs:
            if cid in ["tempmediaStorage", "scratch"]:
                continue
            tpath = os.path.join(BRAIN_DIR, cid, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(tpath):
                mtime = os.path.getmtime(tpath)
                size = os.path.getsize(tpath)
                sessions.append({
                    "id": cid,
                    "mtime": mtime,
                    "size": size,
                    "path": tpath
                })
        
        sessions.sort(key=lambda s: s["mtime"], reverse=True)
    except Exception as e:
        print(f"[Tracker] Error listing sessions: {e}")

    return sessions[:limit]

def parse_conversation_dag(conversation_id=None):
    """
    Parses conversation tree & subagent DAG for a given conversation ID, or the most recent one.
    """
    recent = get_recent_conversations(limit=5)
    if not recent:
        return {"sessions": [], "active_session": None, "subagents": [], "tokens": 0}

    target_session = None
    if conversation_id:
        for s in recent:
            if s["id"] == conversation_id:
                target_session = s
                break
    
    if not target_session:
        target_session = recent[0]

    tpath = target_session["path"]
    cid = target_session["id"]

    steps = []
    subagents = []
    initial_prompt = ""
    last_tool = None
    current_status = "IDLE"
    total_chars = 0
    now = time.time()

    try:
        with open(tpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_chars += len(line)
                try:
                    step = json.loads(line)
                    steps.append(step)
                except Exception:
                    continue

        if steps:
            # First user prompt
            for step in steps:
                if step.get("type") == "USER_INPUT" and step.get("content"):
                    raw_content = step.get("content", "")
                    if "<USER_REQUEST>" in raw_content:
                        parts = raw_content.split("<USER_REQUEST>")
                        if len(parts) > 1:
                            initial_prompt = parts[1].split("</USER_REQUEST>")[0].strip()
                    else:
                        initial_prompt = raw_content[:200].strip()
                    break

            # Analyze last step
            last_step = steps[-1]
            last_type = last_step.get("type", "")
            last_status = last_step.get("status", "")

            # Tool calls extraction & subagents
            for step in steps:
                tcalls = step.get("tool_calls", [])
                if isinstance(tcalls, list):
                    for tc in tcalls:
                        tname = tc.get("name")
                        last_tool = {
                            "name": tname,
                            "summary": tc.get("args", {}).get("toolSummary", ""),
                            "action": tc.get("args", {}).get("toolAction", ""),
                            "step": step.get("step_index", 0)
                        }
                        if tname == "invoke_subagent":
                            args = tc.get("args", {})
                            sub_list = args.get("Subagents", [])
                            if isinstance(sub_list, list):
                                for sa in sub_list:
                                    subagents.append({
                                        "role": sa.get("Role", "Subagent"),
                                        "type": sa.get("TypeName", "subagent"),
                                        "prompt": sa.get("Prompt", "")[:140],
                                        "model": sa.get("Model", "inherit"),
                                        "status": "RUNNING" if (now - target_session["mtime"] < 120) else "DONE",
                                        "invoked_at_step": step.get("step_index", 0)
                                    })

            # Check if active / stuck
            delta = now - target_session["mtime"]
            if delta < 15:
                current_status = "RUNNING"
            elif delta < 180:
                current_status = "WAITING" if last_type != "USER_INPUT" else "IDLE"
            elif delta > 180 and last_status == "RUNNING":
                current_status = "STUCK"
            else:
                current_status = "IDLE"

    except Exception as e:
        print(f"[Tracker] Error parsing transcript {tpath}: {e}")

    # Estimate tokens: roughly 3.8 chars per token for JSONL mix of code & text
    estimated_tokens = int(total_chars / 3.8)
    last_active_str = datetime.fromtimestamp(target_session["mtime"]).strftime("%H:%M:%S")

    return {
        "sessions": [{"id": s["id"], "last_active": datetime.fromtimestamp(s["mtime"]).strftime("%H:%M:%S"), "size_kb": int(s["size"] / 1024)} for s in recent],
        "active_session": {
            "id": cid,
            "prompt": initial_prompt or "(Active Session)",
            "status": current_status,
            "total_steps": len(steps),
            "estimated_tokens": estimated_tokens,
            "last_active": last_active_str,
            "age_seconds": int(now - target_session["mtime"]),
            "last_tool": last_tool
        },
        "subagents": subagents,
        "token_burn": {
            "total": estimated_tokens,
            "rate_label": "Normal" if current_status != "RUNNING" else "Active Burn"
        }
    }

if __name__ == "__main__":
    dag = parse_conversation_dag()
    print("=== Subagent Tracker Test ===")
    print(json.dumps(dag, indent=2))
