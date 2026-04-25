#!/usr/bin/env bash
# preflight-reminder.sh — Stop hook
# Reminds the user to re-run /preflight if it was used earlier in the session
# and Edit/Write/NotebookEdit tool calls have happened since the last invocation.
#
# Design (after preflight panel self-review, 2026-04-25):
#   - Nudge, not gate. Soft reminder via stderr at Stop event.
#   - No override channel in the message: the assistant must not be able to
#     suggest a bypass to the user (self-defeating-override class of bugs
#     surfaced by the security expert during the panel review).
#   - Logs every reminder firing to ~/.claude/state/preflight-reminder/events.jsonl
#     so the user can review actual frequency before deciding whether to upgrade
#     to a hard PreToolUse-deny variant.
# Convention: matches compact-threshold.sh — Stop event, stderr output, fail-open.
#
# Install:
#   1. Copy this script to ~/.claude/hooks/preflight-reminder.sh (or symlink).
#   2. chmod +x.
#   3. Wire into ~/.claude/settings.json under hooks.Stop:
#        { "type": "command", "command": "bash /Users/<you>/.claude/hooks/preflight-reminder.sh" }
#   4. Reload Claude Code.
#
# Disable temporarily without touching config:
#   PREFLIGHT_REMINDER_DISABLE=1
#
# Localize the reminder message:
#   PREFLIGHT_REMINDER_MESSAGE='ваш текст с переводом строки в конце\n'
#   (set in your shell or wrap the hook command in settings.json with
#    "command": "PREFLIGHT_REMINDER_MESSAGE='...' bash <path>")

set -uo pipefail

[ "${PREFLIGHT_REMINDER_DISABLE:-0}" = "1" ] && exit 0

if ! command -v jq >/dev/null 2>&1; then exit 0; fi

INPUT=""
if [ ! -t 0 ]; then INPUT=$(cat); fi
[ -z "$INPUT" ] && exit 0

TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -z "$TRANSCRIPT" ] && exit 0
[ -r "$TRANSCRIPT" ] || exit 0

# Path-traversal defense: session_id must be UUID-shaped.
SID=$(basename "$TRANSCRIPT" .jsonl)
if ! [[ "$SID" =~ ^[a-f0-9-]{36}$ ]]; then exit 0; fi

# Most recent /preflight invocation line (1-indexed).
LAST_PREFLIGHT=$(grep -n '<command-name>/preflight</command-name>' "$TRANSCRIPT" 2>/dev/null \
                 | tail -1 | cut -d: -f1)
[ -z "$LAST_PREFLIGHT" ] && exit 0

# Edit/Write/NotebookEdit tool_use strictly after that line?
HAS_EDIT_AFTER=$(awk -v start="$LAST_PREFLIGHT" 'NR > start' "$TRANSCRIPT" 2>/dev/null \
                 | grep -cE '"name":"(Edit|Write|NotebookEdit)"' || true)
[ "${HAS_EDIT_AFTER:-0}" -eq 0 ] && exit 0

# Anti-spam: if we already reminded this preflight epoch AND no new edits
# happened since the last reminder, stay silent. State is per session_id.
LOG_DIR="$HOME/.claude/state/preflight-reminder"
STATE_FILE="$LOG_DIR/$SID.state"
if [ -r "$STATE_FILE" ]; then
    PREV=$(cat "$STATE_FILE" 2>/dev/null || echo "")
    PREV_EPOCH=$(printf '%s' "$PREV" | cut -d: -f1)
    PREV_LAST_LINE=$(printf '%s' "$PREV" | cut -d: -f2)
    if [ "$PREV_EPOCH" = "$LAST_PREFLIGHT" ]; then
        NEW_EDITS=$(awk -v start="${PREV_LAST_LINE:-$LAST_PREFLIGHT}" 'NR > start' \
                    "$TRANSCRIPT" 2>/dev/null \
                    | grep -cE '"name":"(Edit|Write|NotebookEdit)"' || true)
        [ "${NEW_EDITS:-0}" -eq 0 ] && exit 0
    fi
fi

# Persist state (best-effort, atomic via tmp+rename).
LAST_LINE=$(wc -l < "$TRANSCRIPT" 2>/dev/null | tr -d ' ')
if mkdir -p "$LOG_DIR" 2>/dev/null; then
    printf '%s:%s\n' "$LAST_PREFLIGHT" "${LAST_LINE:-$LAST_PREFLIGHT}" \
        > "$STATE_FILE.tmp" 2>/dev/null \
        && mv "$STATE_FILE.tmp" "$STATE_FILE" 2>/dev/null
    printf '{"ts":"%s","sid":"%s","preflight_line":%s,"reminder":1}\n' \
        "$(date -u +%FT%TZ)" "$SID" "$LAST_PREFLIGHT" \
        >> "$LOG_DIR/events.jsonl" 2>/dev/null
fi

MSG="${PREFLIGHT_REMINDER_MESSAGE:-🛂 /preflight was used earlier this session and Edit/Write happened since. If you extended the plan, re-run /preflight. If the task changed entirely, /clear.\n}"
printf "%b" "$MSG" >&2

exit 0
