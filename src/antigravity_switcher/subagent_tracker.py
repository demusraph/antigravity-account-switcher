import os
import json
import time
import glob
import re
from datetime import datetime

USERPROFILE = os.environ.get("USERPROFILE", "")
BRAIN_DIR = os.path.join(USERPROFILE, ".gemini", "antigravity", "brain")

DEPARTMENTS_META = {
    "executive": {
        "id": "executive",
        "name": "Executive Suite & Strategy",
        "room": "Suite 401 — Strategic Command",
        "badge": "Leadership",
        "icon": "briefcase",
        "color": "#2B7FFF",
        "border": "border-blue-500/30",
        "bg_glow": "bg-blue-500/10",
        "text": "text-blue-400"
    },
    "intelligence": {
        "id": "intelligence",
        "name": "R&D & Intelligence Lab",
        "room": "Lab 302 — Recon & Discovery",
        "badge": "Intelligence",
        "icon": "flask-conical",
        "color": "#10B981",
        "border": "border-emerald-500/30",
        "bg_glow": "bg-emerald-500/10",
        "text": "text-emerald-400"
    },
    "engineering": {
        "id": "engineering",
        "name": "Engineering & Construction Bay",
        "room": "Bay 204 — Systems & Build",
        "badge": "Engineering",
        "icon": "code-2",
        "color": "#8B5CF6",
        "border": "border-purple-500/30",
        "bg_glow": "bg-purple-500/10",
        "text": "text-purple-400"
    },
    "secops": {
        "id": "secops",
        "name": "SecOps & Quality Assurance Floor",
        "room": "Floor 105 — Operations & Audit",
        "badge": "Security & QA",
        "icon": "shield-check",
        "color": "#F59E0B",
        "border": "border-amber-500/30",
        "bg_glow": "bg-amber-500/10",
        "text": "text-amber-400"
    }
}

def assign_department(role="", type_name="", last_tool=None, prompt=""):
    """
    Classifies an agent into one of 4 functional virtual office departments.
    """
    r = (role or "").lower()
    t = (type_name or "").lower()
    p = (prompt or "").lower()
    tool_name = (last_tool.get("name") if isinstance(last_tool, dict) else "") or ""
    tool_name = tool_name.lower()

    # Executive
    if any(k in r or k in t for k in ["orchestrat", "director", "lead", "planner", "executive", "root", "coordinator", "supervisor"]):
        return "executive"

    # SecOps & QA
    if any(k in r or k in t for k in ["sec", "audit", "hunt", "pentest", "redteam", "vuln", "test", "qa", "lint", "validator", "remediat"]):
        return "secops"
    if tool_name in ["run_command", "manage_task"]:
        if any(k in p for k in ["test", "audit", "check", "verify", "lint", "validate"]):
            return "secops"

    # Intelligence & R&D
    if any(k in r or k in t for k in ["research", "intel", "search", "recon", "explore", "read", "miner", "analyst", "crawl", "osint", "investigat", "doc-writer", "prd", "architecture author"]):
        if "writer" in r and any(k in r for k in ["code", "script", "ui", "page"]):
            pass
        else:
            return "intelligence"
    if tool_name in ["search_web", "read_url_content", "grep_search", "find_by_name", "list_dir", "view_file"]:
        if any(k in r for k in ["research", "explore", "doc", "study", "investigat"]):
            return "intelligence"

    # Engineering & Construction Bay (builders, coders, dev)
    if any(k in r or k in t for k in ["dev", "engineer", "build", "code", "refactor", "component", "ui", "page", "backend", "frontend", "fullstack", "constructor"]):
        return "engineering"
    if tool_name in ["write_to_file", "replace_file_content", "generate_image"]:
        return "engineering"

    # Fallback heuristics
    if any(k in p for k in ["create", "build", "implement", "write", "code", "page", "component"]):
        return "engineering"
    if any(k in p for k in ["find", "search", "investigate", "explain", "research"]):
        return "intelligence"

    return "engineering"

def parse_child_subagent_transcript(child_cid):
    """
    Attempts to read child subagent's actual transcript to get real step count, tokens, and active tool.
    """
    if not child_cid or not os.path.exists(BRAIN_DIR):
        return None
    child_dir = os.path.join(BRAIN_DIR, child_cid, ".system_generated", "logs")
    tpath = os.path.join(child_dir, "transcript.jsonl")
    if not os.path.exists(tpath):
        return None

    try:
        mtime = os.path.getmtime(tpath)
        steps = 0
        total_chars = 0
        last_tool = None
        last_step_status = "IDLE"

        with open(tpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_chars += len(line)
                steps += 1
                try:
                    d = json.loads(line)
                    tcalls = d.get("tool_calls", [])
                    if isinstance(tcalls, list):
                        for tc in tcalls:
                            tname = tc.get("name")
                            args = tc.get("args", {})
                            last_tool = {
                                "name": tname,
                                "summary": str(args.get("toolSummary", "")),
                                "action": str(args.get("toolAction", "")),
                                "step": d.get("step_index", steps)
                            }
                    if d.get("status"):
                        last_step_status = d.get("status")
                except Exception:
                    pass

        now = time.time()
        delta = now - mtime
        est_tokens = int(total_chars / 3.8)

        if delta < 25:
            desk_status = "WORKING"
            desk_label = "In Deep Focus"
        elif delta < 90:
            desk_status = "IN_MEETING"
            desk_label = "In Sync Meeting"
        elif delta > 120 and last_step_status == "RUNNING":
            desk_status = "BLOCKED"
            desk_label = "Desk Obstacle"
        else:
            desk_status = "STANDBY"
            desk_label = "Task Finished"

        return {
            "steps": steps,
            "tokens": est_tokens,
            "last_tool": last_tool,
            "desk_status": desk_status,
            "desk_status_label": desk_label,
            "mtime": mtime,
            "last_active": datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
        }
    except Exception as e:
        return None

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
    Parses conversation tree, subagents, departmental grouping, and office KPIs for a given session.
    """
    recent = get_recent_conversations(limit=6)
    if not recent:
        return {
            "sessions": [],
            "active_session": None,
            "subagents": [],
            "departments": {k: {**v, "staff": []} for k, v in DEPARTMENTS_META.items()},
            "office_kpis": {
                "total_headcount": 0,
                "active_workers": 0,
                "in_meeting": 0,
                "standby_staff": 0,
                "blocked_staff": 0,
                "total_tokens": 0,
                "token_burn_label": "Normal",
                "office_status": "OFFLINE"
            },
            "tokens": 0
        }

    target_session = None
    if conversation_id:
        for s in recent:
            if s["id"] == conversation_id:
                target_session = s
                break
        if not target_session:
            custom_tpath = os.path.join(BRAIN_DIR, conversation_id, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(custom_tpath):
                target_session = {
                    "id": conversation_id,
                    "mtime": os.path.getmtime(custom_tpath),
                    "size": os.path.getsize(custom_tpath),
                    "path": custom_tpath
                }

    if not target_session and recent:
        target_session = recent[0]

    tpath = target_session["path"]
    cid = target_session["id"]

    # Prefer transcript_full.jsonl for untruncated subagents and tools if available
    full_path = os.path.join(BRAIN_DIR, cid, ".system_generated", "logs", "transcript_full.jsonl")
    read_path = full_path if os.path.exists(full_path) else tpath

    steps = []
    subagents = []
    initial_prompt = ""
    last_tool = None
    current_status = "IDLE"
    total_chars = 0
    now = time.time()

    try:
        with open(read_path, "r", encoding="utf-8", errors="ignore") as f:
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
            # First user prompt extraction
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

            # Tool calls extraction & subagent invocations
            for i, step in enumerate(steps):
                tcalls = step.get("tool_calls", [])
                if isinstance(tcalls, list):
                    for tc in tcalls:
                        tname = tc.get("name")
                        args = tc.get("args", {})
                        last_tool = {
                            "name": tname,
                            "summary": str(args.get("toolSummary", "")),
                            "action": str(args.get("toolAction", "")),
                            "step": step.get("step_index", 0)
                        }
                        if tname == "invoke_subagent":
                            sub_list = args.get("Subagents", [])
                            if isinstance(sub_list, str):
                                try:
                                    sub_list = json.loads(sub_list, strict=False)
                                except Exception:
                                    sub_list = []

                            # Check next step for created conversation IDs
                            child_ids = []
                            if i + 1 < len(steps):
                                next_c = str(steps[i+1].get("content", ""))
                                child_ids = re.findall(r'"conversationId":\s*"([a-f0-9\-]+)"', next_c)

                            if isinstance(sub_list, list):
                                for idx, sa in enumerate(sub_list):
                                    if not isinstance(sa, dict):
                                        continue
                                    child_cid = child_ids[idx] if idx < len(child_ids) else None
                                    child_telemetry = parse_child_subagent_transcript(child_cid) if child_cid else None

                                    role = sa.get("Role", "Specialist Subagent")
                                    type_name = sa.get("TypeName", "subagent")
                                    prompt_text = sa.get("Prompt", "")
                                    model = sa.get("Model", "inherit")

                                    # Child telemetry or fallback
                                    if child_telemetry:
                                        sa_status = child_telemetry["desk_status"]
                                        sa_label = child_telemetry["desk_status_label"]
                                        sa_tool = child_telemetry["last_tool"]
                                        sa_steps = child_telemetry["steps"]
                                        sa_tokens = child_telemetry["tokens"]
                                        sa_last_active = child_telemetry["last_active"]
                                    else:
                                        delta_sec = now - target_session["mtime"]
                                        if delta_sec < 30:
                                            sa_status = "WORKING"
                                            sa_label = "In Deep Focus"
                                        elif delta_sec < 180:
                                            sa_status = "IN_MEETING"
                                            sa_label = "In Sync Meeting"
                                        else:
                                            sa_status = "STANDBY"
                                            sa_label = "Shift Completed"
                                        sa_tool = None
                                        sa_steps = 1
                                        sa_tokens = int(len(prompt_text) / 3.8)
                                        sa_last_active = datetime.fromtimestamp(target_session["mtime"]).strftime("%H:%M:%S")

                                    dept_id = assign_department(role, type_name, sa_tool, prompt_text)

                                    subagents.append({
                                        "id": child_cid or f"subagent-{step.get('step_index', 0)}-{idx}",
                                        "conversation_id": child_cid,
                                        "role": role,
                                        "type": type_name,
                                        "prompt": prompt_text[:280],
                                        "full_prompt": prompt_text,
                                        "model": model,
                                        "department": dept_id,
                                        "desk_status": sa_status,
                                        "desk_status_label": sa_label,
                                        "status": sa_status,
                                        "active_tool": sa_tool,
                                        "steps_count": sa_steps,
                                        "tokens_count": sa_tokens,
                                        "last_active": sa_last_active,
                                        "invoked_at_step": step.get("step_index", 0),
                                        "is_parent": False
                                    })

            # Check root active / stuck status
            delta = now - target_session["mtime"]
            if delta < 20:
                current_status = "RUNNING"
                parent_desk_status = "WORKING"
                parent_desk_label = "In Deep Focus"
            elif delta < 180:
                current_status = "WAITING" if last_type != "USER_INPUT" else "IDLE"
                parent_desk_status = "IN_MEETING" if last_type != "USER_INPUT" else "STANDBY"
                parent_desk_label = "In Sync Meeting" if last_type != "USER_INPUT" else "On Standby"
            elif delta > 180 and last_status == "RUNNING":
                current_status = "STUCK"
                parent_desk_status = "BLOCKED"
                parent_desk_label = "Desk Obstacle"
            else:
                current_status = "IDLE"
                parent_desk_status = "STANDBY"
                parent_desk_label = "On Standby"

    except Exception as e:
        print(f"[Tracker] Error parsing transcript {read_path}: {e}")
        parent_desk_status = "STANDBY"
        parent_desk_label = "On Standby"

    # Estimate tokens
    estimated_tokens = int(total_chars / 3.8)
    last_active_str = datetime.fromtimestamp(target_session["mtime"]).strftime("%H:%M:%S")

    # Parent Orchestrator (Executive Agent)
    parent_agent = {
        "id": "parent-orchestrator",
        "conversation_id": cid,
        "role": "Lead Orchestrator (Root)",
        "type": "parent_orchestrator",
        "prompt": initial_prompt or "(Active Primary Loop)",
        "full_prompt": initial_prompt,
        "model": "Primary Loop",
        "department": "executive",
        "desk_status": parent_desk_status,
        "desk_status_label": parent_desk_label,
        "status": current_status,
        "active_tool": last_tool,
        "steps_count": len(steps),
        "tokens_count": estimated_tokens,
        "last_active": last_active_str,
        "invoked_at_step": 0,
        "is_parent": True
    }

    # Group into departments
    departments = {}
    for d_id, d_meta in DEPARTMENTS_META.items():
        departments[d_id] = {
            **d_meta,
            "staff": []
        }

    # Add Parent Orchestrator to Executive Suite
    departments["executive"]["staff"].append(parent_agent)

    # Add Subagents to their respective departments
    for sa in subagents:
        dept_key = sa.get("department", "engineering")
        if dept_key not in departments:
            dept_key = "engineering"
        departments[dept_key]["staff"].append(sa)

    # Compute Office KPIs
    all_staff = [parent_agent] + subagents
    total_headcount = len(all_staff)
    active_workers = sum(1 for a in all_staff if a.get("desk_status") == "WORKING")
    in_meeting_count = sum(1 for a in all_staff if a.get("desk_status") == "IN_MEETING")
    standby_count = sum(1 for a in all_staff if a.get("desk_status") == "STANDBY")
    blocked_count = sum(1 for a in all_staff if a.get("desk_status") == "BLOCKED")
    total_tokens_office = estimated_tokens + sum(sa.get("tokens_count", 0) for sa in subagents)

    office_status = "FULL OPERATION" if active_workers > 0 else ("IN SYNC" if in_meeting_count > 0 else "STANDBY")
    token_burn_label = "Active Burn" if active_workers > 0 else "Normal"

    office_kpis = {
        "total_headcount": total_headcount,
        "active_workers": active_workers,
        "in_meeting": in_meeting_count,
        "standby_staff": standby_count,
        "blocked_staff": blocked_count,
        "total_tokens": total_tokens_office,
        "token_burn_label": token_burn_label,
        "office_status": office_status
    }

    return {
        "sessions": [
            {
                "id": s["id"],
                "last_active": datetime.fromtimestamp(s["mtime"]).strftime("%H:%M:%S"),
                "size_kb": int(s["size"] / 1024)
            }
            for s in recent
        ],
        "active_session": {
            "id": cid,
            "prompt": initial_prompt or "(Active Session)",
            "status": current_status,
            "desk_status": parent_desk_status,
            "desk_status_label": parent_desk_label,
            "total_steps": len(steps),
            "estimated_tokens": estimated_tokens,
            "last_active": last_active_str,
            "age_seconds": int(now - target_session["mtime"]),
            "last_tool": last_tool
        },
        "subagents": subagents,
        "departments": departments,
        "office_kpis": office_kpis,
        "token_burn": {
            "total": total_tokens_office,
            "rate_label": token_burn_label
        }
    }

if __name__ == "__main__":
    dag = parse_conversation_dag()
    print("=== Subagent & Office Tracker Test ===")
    print(f"Headcount: {dag['office_kpis']['total_headcount']}, Active Workers: {dag['office_kpis']['active_workers']}")
    for d_id, dept in dag["departments"].items():
        print(f"[{dept['name']}] Staff count: {len(dept['staff'])}")
        for st in dept["staff"]:
            print(f"  * {st['role']} ({st['desk_status']}) - Tool: {st.get('active_tool', {}).get('name') if st.get('active_tool') else 'None'}")

