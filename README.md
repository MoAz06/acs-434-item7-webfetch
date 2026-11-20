# ACS #434, item 7: WebFetch through the Claude Code host

A host-level measurement of the OWASP [Agent Control Standard](https://github.com/GenAI-Security-Project/agent-control-standard)
reference Guardian's egress gate on Claude Code's WebFetch tool, for
[#434](https://github.com/GenAI-Security-Project/agent-control-standard/issues/434), item 7.

**Read [REPORT.md](REPORT.md).** In one line: the three URL shapes that get past the gate's
`host_of()` (`annotate-egress.ts:36-38`), sent through WebFetch, were allowed by the
Guardian 35 times out of 35 and refused by Claude Code 2.1.329 itself 35 times out of 35,
with no connection reaching the target.

## What is here

| Path | Contents |
| --- | --- |
| [`REPORT.md`](REPORT.md) | The report: what ran, expected and observed behavior, reproduction, limits |
| [`harness/`](harness) | The fixture: scripted model, connection listener, run, analysis and aggregation scripts |
| [`run/`](run) | Evidence for the campaign: 11 scenarios x 5 repetitions, the Guardian's logs, the listener log, per-run and per-scenario joins |
| [`pilot/`](pilot) | A single-repetition pilot run from earlier the same day, with the same results |
| `probe-hooks.sh`, `probe-dotless.sh` | Shim-level probes that pipe hook payloads straight into the Guardian, without Claude Code, used before the host runs |

Measured on ACS `integration` at `394d6c0`, Claude Code 2.1.329, Bun 1.3.11, Ubuntu 26.04 under WSL2.
