#!/usr/bin/env bash
export PATH=$HOME/.bun/bin:$PATH NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
cd ~/acs/reference-implementations/agt
for u in 'https://metadata?x=@docs.anthropic.com' 'https://internal-api#@docs.anthropic.com' 'https://metadata/x' 'https://docs.anthropic.com\@evil.test/steal'; do
  printf '%-48s ' "$u"
  python3 -c 'import json,sys;print(json.dumps({"session_id":"probe","hook_event_name":"PreToolUse","tool_name":"WebFetch","tool_use_id":"t2","tool_input":{"url":sys.argv[1],"prompt":"x"}}))' "$u" \
   | bun run hosts/claude-code/acs-hook.ts | python3 -c 'import sys,json;print(json.loads(sys.stdin.read().splitlines()[-1])["hookSpecificOutput"]["permissionDecision"])'
done
echo "--- envelopes logged: $(wc -l < .acs/envelopes.jsonl)"
