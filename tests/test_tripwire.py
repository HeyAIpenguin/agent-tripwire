"""Run: python3 tests/test_tripwire.py  (stdlib only)"""
import json, os, subprocess, sys, tempfile
HOOK = os.path.join(os.path.dirname(__file__), "..", "tripwire.py")
CASES = [
    (2, "Edit", {"file_path": "/p/.claude/settings.json"}),
    (2, "Write", {"file_path": "/p/.claude/settings.local.json"}),
    (2, "Write", {"file_path": "/p/.claude/hooks/tripwire.py"}),
    (2, "Edit", {"file_path": "/p/.env"}),
    (2, "Edit", {"file_path": "/p/.env.production"}),
    (2, "Edit", {"file_path": os.path.expanduser("~/.claude/settings.json")}),
    (2, "Bash", {"command": "rm .claude/settings.json"}),
    (2, "Bash", {"command": "printf '{}' > .claude/settings.json"}),
    (2, "Bash", {"command": "sed -i '' s/a/b/ .claude/settings.local.json"}),
    (2, "Bash", {"command": "chmod -x .claude/hooks/tripwire.py"}),
    (2, "Bash", {"command": "echo X=1 >> .env"}),
    (0, "Bash", {"command": "cat .claude/settings.json 2>&1"}),
    (0, "Bash", {"command": "ls -la .claude 2>/dev/null"}),
    (0, "Bash", {"command": "npm test 2>&1 | tail"}),
    (0, "Edit", {"file_path": "/p/src/app.py"}),
    (0, "Edit", {"file_path": "/p/docs/environment.md"}),
    (0, "Read", {"file_path": "/p/.claude/settings.json"}),
]
env = dict(os.environ, TRIPWIRE_NOTIFY="0", TRIPWIRE_LOG=os.path.join(tempfile.mkdtemp(), "alerts.log"))
bad = 0
for want, tool, inp in CASES:
    r = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": tool, "tool_input": inp}), text=True, capture_output=True, env=env)
    ok = r.returncode == want
    bad += not ok
    print(("PASS" if ok else "FAIL"), "block" if want else "allow", tool, json.dumps(inp)[:70])
r = subprocess.run([sys.executable, HOOK], input="not json", text=True, capture_output=True, env=env)
bad += r.returncode != 0; print("PASS" if r.returncode == 0 else "FAIL", "allow bad input")
print(f"\n{len(CASES) + 1 - bad}/{len(CASES) + 1} passed"); sys.exit(1 if bad else 0)
