# Independent C online Fyne pair: status (2026-09-19)

The minimal online comparison has been prepared and launched with fresh run
identities:

- `independent-c-fyne-2.2.0-roadmap-c_off-r3`
- `independent-c-fyne-2.2.0-roadmap-c_on-r3` (serially after C-off)

The C-off runner is currently still executing. No native result or method
effect claim exists yet. The earlier concurrent launch was invalidated by a
shared OTEL container-name collision and is not part of this pair.

The only intended difference is `GA_MONITOR_INDEPENDENT_C=0` versus `1`.
Both runs use the same Fyne 2.2 task, model, memory, compression, concurrency,
completion strategy, no-checker isolation, source hash and execution harness.
The C-on run has a six-request total probe budget, with at most three requests
per local check; probe usage is recorded in the monitor audit.
