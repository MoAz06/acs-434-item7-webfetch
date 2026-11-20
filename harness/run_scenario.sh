#!/usr/bin/env bash
# One scenario: a real Claude Code (-p) whose scripted model asks for one WebFetch
# of $2, with the ACS hook wired to the already-running Guardian on :8787.
#
# usage: run_scenario.sh LABEL URL
# Leaves everything under ~/acs-434/run/<LABEL>/ : claude stdout/stderr, the stub's
# request log, and the time window, so analyse.py can join it with the Guardian's
# envelope log and the listener log.
set -u
LABEL="$1"; URL="$2"
AGT="$HOME/acs/reference-implementations/agt"
H="$HOME/acs-434/harness"
OUT="$HOME/acs-434/run/$LABEL"
PROJ="$HOME/acs-434/project"
STUB_PORT=9100

export PATH="$HOME/.bun/bin:$HOME/.local/bin:$PATH"
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
rm -rf "$OUT"; mkdir -p "$OUT" "$PROJ/.claude"

# Project with the shipped hook settings, $CLAUDE_PROJECT_DIR replaced by the agt tree
sed "s#\$CLAUDE_PROJECT_DIR#$AGT#g" "$AGT/hosts/claude-code/settings.json" > "$PROJ/.claude/settings.json"

# Stub model for this scenario
STUB_FETCH_URL="$URL" STUB_PORT=$STUB_PORT STUB_LOG="$OUT/stub-requests.jsonl" \
  python3 -u "$H/stub_model.py" > "$OUT/stub.out" 2>&1 &
STUB_PID=$!
for i in $(seq 1 30); do (echo > /dev/tcp/127.0.0.1/$STUB_PORT) 2>/dev/null && break; sleep 0.2; done

ENV_LINE=$(python3 -c 'import time;print(time.time())')
echo "{\"label\":\"$LABEL\",\"url\":$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$URL"),\"start\":$ENV_LINE," > "$OUT/meta.json"

cd "$PROJ"
ANTHROPIC_BASE_URL="http://127.0.0.1:$STUB_PORT" \
ANTHROPIC_API_KEY="sk-ant-local-stub-not-a-real-key" \
CLAUDE_CONFIG_DIR="$HOME/acs-434/claude-config" \
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
DISABLE_AUTOUPDATER=1 \
timeout 150 claude -p "Fetch the page I gave you." \
  --allowedTools "WebFetch" --output-format json \
  > "$OUT/claude.stdout" 2> "$OUT/claude.stderr"
echo "\"claude_exit\":$?," >> "$OUT/meta.json"

sleep 1
echo "\"end\":$(python3 -c 'import time;print(time.time())')}" >> "$OUT/meta.json"
kill $STUB_PID 2>/dev/null; wait $STUB_PID 2>/dev/null
claude --version > "$OUT/claude-version.txt" 2>&1
git -C "$HOME/acs" rev-parse HEAD > "$OUT/acs-commit.txt"
echo "done: $LABEL"
