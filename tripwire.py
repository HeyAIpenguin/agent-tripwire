#!/usr/bin/env python3
"""agent-tripwire: a Claude Code PreToolUse hook that stops the agent from editing its own guardrails.

Blocks (and logs) any attempt by the agent to change:
  - Claude Code settings and permission rules (.claude/settings*.json, ~/.claude/settings*.json)
  - hooks, including this tripwire (.claude/hooks/)
  - secrets files (.env, .env.*)

It never reads file contents and never prints secrets. Stdlib only, Python 3.8+.
Exit code 2 = block the tool call; the reason goes back to the agent on stderr.
"""
import json, os, re, sys, time, subprocess

LOG = os.path.expanduser(os.environ.get("TRIPWIRE_LOG", "~/.agent-tripwire/alerts.log"))
NOTIFY = os.environ.get("TRIPWIRE_NOTIFY", "1") == "1"

# paths the agent may read but never change
PROTECTED = [
    r"(^|/)\.claude/settings(\.local)?\.json$",
    r"(^|/)\.claude/hooks(/|$)",
    r"(^|/)\.env(\.[\w.-]+)?$",
    r"(^|/)tripwire\.py$",
]
# substrings that mark a protected path inside a shell command
PROTECTED_IN_CMD = re.compile(r"\.claude/settings[\w.]*\.json|\.claude/hooks|(^|[\s/'\"=])\.env(\.[\w.-]+)?($|[\s'\";|&>])|tripwire\.py")
# shell verbs that write, move, delete or change permissions
WRITES = re.compile(r"(^|[\s;|&(])(rm|mv|cp|tee|truncate|chmod|chown|ln|unlink|dd|install|rsync)\s|sed\s+(-[a-zA-Z]*i|--in-place)|perl\s+-[a-zA-Z]*i|(?<![0-9&>])>>?(?!\s*&|\s*/dev/null)|\bjq\b.*>|python3?\s+-c|node\s+-e|git\s+(checkout|restore|rm|mv|stash)\b")

def protected(path):
    p = os.path.normpath(os.path.expanduser(path or ""))
    return any(re.search(rx, p) for rx in PROTECTED)

def verdict(tool, inp):
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        if protected(path):
            return f"{tool} on {path}"
    if tool == "Bash":
        cmd = inp.get("command", "")
        if PROTECTED_IN_CMD.search(cmd) and WRITES.search(cmd):
            return f"shell write touching a guardrail: {cmd[:160]}"
    return None

def alert(reason, data):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "session": data.get("session_id", "")[:8],
                       "cwd": data.get("cwd", ""), "tool": data.get("tool_name"), "blocked": reason})
    with open(LOG, "a") as f:
        f.write(line + "\n")
    if NOTIFY and sys.platform == "darwin":
        msg = reason.replace('"', "'")[:120]
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "agent-tripwire" subtitle "Blocked a guardrail change"'],
                       capture_output=True)

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0                      # never break the session on bad input
    reason = verdict(data.get("tool_name", ""), data.get("tool_input") or {})
    if not reason:
        return 0
    alert(reason, data)
    sys.stderr.write(
        "agent-tripwire: BLOCKED. You are not allowed to change your own guardrails "
        f"({reason}). This attempt was logged and the user was notified. "
        "If the user really wants this change, they must make it themselves.\n")
    return 2

if __name__ == "__main__":
    sys.exit(main())
