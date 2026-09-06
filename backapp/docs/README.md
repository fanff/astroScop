# astroScop camera docs

Docs for the Raspberry Pi HQ (IMX477) camera path used by agents and operators.

| Document | Purpose |
|----------|---------|
| **[`camera-settings-contract.md`](camera-settings-contract.md)** | **Start here for rootserver + UI work** — wire format, slow/fast fields, forbidden keys, WS messages |
| [`pi-hq-camera.md`](pi-hq-camera.md) | Hardware, sensor modes, science notes, safe live testing on `piscope` |
| [`hq-camera-capability-report.md`](hq-camera-capability-report.md) | Verified capability suite results (modes, exposure trust, ScalerCrop behaviour) |
| [`cam-settings-bench-report.md`](cam-settings-bench-report.md) | Latest typed-settings / spectrum / reconfig bench (must stay PASS) |
| [`guide-bench-report.md`](guide-bench-report.md) | Latest autoguide Pi timing benches (Phase B geom first; isolate/crop/worker later) |
| [`../../docs/evolution-vision-motor-control-loop.md`](../../docs/evolution-vision-motor-control-loop.md) | Autoguide loop evolution (phased A–H; Phase B geom is in code) |

## Code back-links

| Path | Role |
|------|------|
| [`../cam_settings.py`](../cam_settings.py) | Enforced `CameraSettings` model |
| [`../cam_spectrum.py`](../cam_spectrum.py) | Display RGB spectrum |
| [`../ws_messages.py`](../ws_messages.py) | Hub WS envelopes + params normalize |
| [`../cam_picamera2.py`](../cam_picamera2.py) | Camera worker |
| [`../cam_storage.py`](../cam_storage.py) | Bayer storage process (shm ring) |
| [`../test_cam_storage.py`](../test_cam_storage.py) | Storage process unit tests |
| [`../rootserver.py`](../rootserver.py) | WebSocket hub (typed params, passthrough preview) |
| [`../test_cam_settings_bench.py`](../test_cam_settings_bench.py) | Contract bench (on-Pi) |
| [`../test_rootserver_hub.py`](../test_rootserver_hub.py) | Camera-free hub live tests |
| [`../scripts/run_cam_settings_bench.ps1`](../scripts/run_cam_settings_bench.ps1) | Sync + run camera settings bench on Pi |
| [`../guide_geom.py`](../guide_geom.py) | Pixel error → arcsec / motor step-error (`cos δ`, pole gate) |
| [`../guide_roi.py`](../guide_roi.py) | Tracking lock → native RGB ROI rectangle |
| [`../guide_isolate.py`](../guide_isolate.py) | Star isolation on a small RGB tile |
| [`../guide_handoff.py`](../guide_handoff.py) | Native RGB crop + shm tile slot for the guide worker |
| [`../guide_pid.py`](../guide_pid.py) / [`../guideControl.py`](../guideControl.py) | PI worker (trims off until F/H) |
| [`../test_guide_geom.py`](../test_guide_geom.py) | Geometry unit tests (laptop) |
| [`../test_guide_roi.py`](../test_guide_roi.py) / [`../test_guide_isolate.py`](../test_guide_isolate.py) | ROI + isolation unit tests (laptop) |
| [`../scripts/run_guide_bench.ps1`](../scripts/run_guide_bench.ps1) | Sync + run guide benches on Pi (`-Stage geom\|isolate`) |
| [`../deploy/astroscop-camera.service`](../deploy/astroscop-camera.service) | Production worker unit |
