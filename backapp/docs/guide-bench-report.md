# Guide loop — bench report

Generated: **2026-09-05 15:46:54 UTC**  
This pull: [`guide_worker_20260905T174603`](../cam_test_out/guide_worker_20260905T174603)  
Merged latest: [`guide-bench-latest`](guide-bench-latest)  
Host: **piscope** (`aarch64`)  
Overall: **PASS**

Pi is the timing authority (evolution §10). A section without `host=piscope` / `aarch64` is not a phase gate.

## Phase B — `guide_geom` (`pixels_to_axis_steps`)

- host: **piscope** (`aarch64`)
- iters: **10000**
- tile_size: n/a (scalar math)
- p50: **11.95 µs**
- p95: **12.22 µs**
- max: **37.59 µs**
- gate: p95 **< 0.5 ms** → **PASS**
- Pi host check: **PASS**

Raw: [`geom_bench.json`](guide-bench-latest/geom_bench.json)

## Phase C — `guide_isolate` (`isolate_star`)

- host: **piscope** (`aarch64`)
- Pi host check: **PASS**

| tile | SNR | iters | p50 | p95 | max | gate | result |
|------|-----|-------|-----|-----|-----|------|--------|
| 64² | high | 400 | 0.724 ms | 0.809 ms | 1.112 ms | < 5.0 ms | **PASS** |
| 64² | mid | 400 | 0.744 ms | 0.824 ms | 1.171 ms | < 5.0 ms | **PASS** |
| 64² | low | 400 | 0.737 ms | 0.815 ms | 0.934 ms | < 5.0 ms | **PASS** |
| 128² | high | 200 | 1.510 ms | 3.129 ms | 3.410 ms | < 15.0 ms | **PASS** |
| 128² | mid | 200 | 1.486 ms | 1.575 ms | 1.792 ms | < 15.0 ms | **PASS** |
| 128² | low | 200 | 1.487 ms | 1.573 ms | 1.667 ms | < 15.0 ms | **PASS** |

Timing: **PASS**. Raw: [`isolate_bench.json`](guide-bench-latest/isolate_bench.json)

## Phase D — `guide_handoff` (live RGB crop vs off)

- host: **piscope** (`aarch64`)
- Pi host check: **PASS**
- timing: **PASS**

- **crop off**: frame_time **59.29 ms**, emit_fps **2.437**
- **crop on 64²**: frame_time **58.84 ms**, emit_fps **2.514**, extract p95 **0.377 ms**, handoff p95 **0.444 ms**
- **crop on 128²**: frame_time **60.90 ms**, emit_fps **2.517**, extract p95 **0.501 ms**, handoff p95 **0.584 ms**

Raw: [`crop_bench.json`](guide-bench-latest/crop_bench.json)

## Phase E — `guideControl` (synthetic tile → PI)

- host: **piscope** (`aarch64`)
- Pi host check: **PASS**
- timing: **PASS**

| case | p50 | p95 | max | gen | proc | backlog | result |
|------|-----|-----|-----|-----|------|---------|--------|
| hz5_jpeg_off | 1.549 ms | 4.703 ms | 56.622 ms | 150 | 150 | 0 | **PASS** |
| hz10_jpeg_off | 1.533 ms | 3.884 ms | 6.539 ms | 100 | 100 | 0 | **PASS** |
| hz5_jpeg_on | 2.082 ms | 6.142 ms | 26.079 ms | 40 | 40 | 0 | **PASS** |

Raw: [`worker_bench.json`](guide-bench-latest/worker_bench.json)

Later phases append worker sections here.
