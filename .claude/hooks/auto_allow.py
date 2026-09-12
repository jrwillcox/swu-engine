"""PreToolUse hook: auto-approve routine work in this project.

WHY THIS EXISTS
---------------
Claude Code's `Bash(foo:*)` allow-rules are PREFIX rules, and the matcher
deliberately refuses to apply them to any command containing shell
metacharacters -- `|`, `>`, `<<` (heredoc), `$(...)`, backticks -- because a
prefix rule cannot vouch for what comes after the pipe. In a measured
`/encode-next` batch, 149 of 153 bash calls contained one of those, so the
allow-list matched almost nothing and the user was prompted ~30 times.

This hook decides permission directly instead, so command SHAPE stops
mattering. It allows by default and keeps a short denylist of things that are
genuinely irreversible or outward-facing (those still get a normal prompt).

Contract: read the PreToolUse JSON payload on stdin, print a decision on
stdout, exit 0. Fail-safe: on ANY internal error we print nothing, which
falls back to Claude Code's normal permission flow.
"""

import json
import re
import sys

# --- things that must still ask ---------------------------------------------
# Irreversible, outward-facing, or touching the son's LIVE deployed game.
BASH_ASK = (
    # destructive filesystem
    r"\brm\s+-[a-zA-Z]*[rRf]",
    r"\brmdir\b",
    r"\bdel\s+/[sq]",
    r"Remove-Item\b",
    r"\bmkfs\b|\bformat\s+[a-zA-Z]:",
    r">\s*/dev/sd",
    # permissions / system
    r"\btakeown\b|\bicacls\b|\bshutdown\b|\breg\s+(add|delete)\b",
    r"Set-ExecutionPolicy\b",
    # outward facing / publishing
    r"\bgit\s+push\b",
    r"\bgh\s+(pr|release|issue)\s+(create|edit|merge|close)\b",
    r"\bnpm\s+publish\b|\btwine\s+upload\b",
    r"\bssh\b|\bscp\b|\brsync\b",
    r"\bcurl\b|\bwget\b|Invoke-WebRequest|Invoke-RestMethod",
    # the LIVE game and the family server
    r"swu-game-deployed",
    r"deploy\.ps1",
    r"setup-server\.ps1",
    r"\bdocker\b",
    # history rewriting
    r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f|rebase|filter-branch)\b",
)

# Paths that must still ask before being written.
PATH_ASK = (
    r"swu-game-deployed",
)

_BASH_ASK_RE = re.compile("|".join(BASH_ASK), re.IGNORECASE)
_PATH_ASK_RE = re.compile("|".join(PATH_ASK), re.IGNORECASE)

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
READ_TOOLS = {"Read", "Glob", "Grep"}


def decide(tool_name, tool_input):
    """Return (decision, reason) or None to defer to the normal flow."""
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        if _BASH_ASK_RE.search(cmd):
            return None  # let the user see it
        return "allow", "project bash (denylist clean)"

    if tool_name in WRITE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if _PATH_ASK_RE.search(path):
            return None
        return "allow", "project file edit"

    if tool_name in READ_TOOLS:
        return "allow", "read-only"

    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    try:
        verdict = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    except Exception:
        return
    if verdict is None:
        return
    decision, reason = verdict
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
