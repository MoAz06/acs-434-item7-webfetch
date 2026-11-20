#!/usr/bin/env bash
# Every scenario once (REPS to repeat). Controls first, then the shapes that
# README.md:503 records as passing the egress gate on the fetch route.
set -u
REPS="${REPS:-1}"
H="$HOME/acs-434/harness"
declare -a S=(
  "c1-allowlisted|https://docs.anthropic.com/en/docs"
  "c2-offlist|https://evil.test/x"
  "c3-localhost-plain|https://localhost/x"
  "s1-userinfo-port|https://docs.anthropic.com:pw@localhost:8443/steal"
  "s2-query-at|https://localhost?x=@docs.anthropic.com"
  "s3-fragment-at|https://localhost#@docs.anthropic.com"
  "s4-http-query-at|http://localhost?x=@docs.anthropic.com"
  "c4-dotted-plain|https://localtest.me:8443/plain"
  "s5-userinfo-dotted|https://docs.anthropic.com:pw@localtest.me:8443/steal"
  "s6-userinfo-ip|https://docs.anthropic.com:pw@127.0.0.1:8443/steal"
  "s7-userinfo-dotted-443|https://docs.anthropic.com:pw@127.0.0.1.nip.io/steal"
)
for r in $(seq 1 "$REPS"); do
  for s in "${S[@]}"; do
    "$H/run_scenario.sh" "${s%%|*}-r$r" "${s#*|}"
  done
done
