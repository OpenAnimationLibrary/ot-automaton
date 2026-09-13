# OT-Automaton Scope

OT-Automaton is a standalone, downstream mirror of OpenToonz for controlled
automation, diagnostics, reproducible testing, and virtual-machine operation.
It is not an alternate feature distribution of OpenToonz.

## Non-negotiable boundary

> If a change adds or improves an artist-facing capability, it belongs in
> OT-Dev. OT-Automaton may contain only automation, observability, diagnostics,
> reproducibility, and strictly necessary virtual-machine compatibility code.

No OT-Automaton branch or commit is eligible to be forwarded wholesale to
`opentoonz/opentoonz`. Product fixes discovered here must be reconstructed as a
clean OT-Dev change based on normal OpenToonz source.

## Allowed changes

- Local-only automation transport and semantic command handling.
- Structured state, readiness, error, and diagnostic reporting.
- Evidence capture: logs, screenshots, recordings, traces, and crash data.
- Deterministic test configuration and virtual-machine launch support.
- Capability profiles that avoid initializing unneeded subsystems.
- Build, packaging, synchronization, provenance, and scope enforcement.
- Test fixtures and scenarios used exclusively to verify the above.

## Prohibited changes

- New drawing, animation, compositing, rendering, or editing features.
- General user-interface enhancements unrelated to automation or diagnostics.
- New artist-facing import/export formats, effects, tools, or panels.
- Experimental features whose purpose is not stated and time-bounded.
- Direct staging or pull requests from this repository to OpenToonz master.

## Branch roles

- `upstream-master`: an exact history-preserving mirror of OpenToonz master.
- `main`: the synchronized upstream base plus the reviewed Automaton delta.
- `repository-bootstrap`: the repository's pre-import initialization history.
- `experiment/*`: disposable investigations with an explicit purpose and end.

## Review test

Every proposal must answer this question:

> Would we still want this change if automation, diagnostics, and virtual
> operation were removed?

If the answer is yes, the change normally belongs in OT-Dev instead.

## Source-level marker

Any necessary modification outside the `automaton/` and Automaton workflow
paths must be listed in `automaton/delta-manifest.json` and contain the marker:

```cpp
// OT_AUTOMATON_ONLY
```

The repository guard fails closed when it finds an undeclared source delta.
