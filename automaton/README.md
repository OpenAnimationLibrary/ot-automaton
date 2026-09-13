# OT-Automaton infrastructure

This directory contains automation-only metadata, launch tools, tests, and
future capability profiles. See [`../AUTOMATON_SCOPE.md`](../AUTOMATON_SCOPE.md)
before proposing a change.

Phase 0 establishes an exact OpenToonz baseline and a machine-verifiable delta.
Phase 1 builds and launches that unmodified baseline in controlled Windows and
Linux environments, collecting a comparable resource report.

## Baseline measurement

The measurement tool deliberately does not claim that the GUI is ready. Until
the semantic readiness endpoint exists, it verifies that the process survives
a fixed observation interval and records its memory behavior.

Example:

```text
python automaton/tools/measure_launch.py \
  --executable /path/to/OpenToonz \
  --working-directory /path/to/portable-package \
  --software-rendering \
  --duration-seconds 15 \
  --output baseline.json
```

The `full` profile is metadata-only during Phase 1. Restricted profiles are not
considered implemented until their excluded subsystems are actually skipped,
rather than merely hidden.
