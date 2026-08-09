# astroScop camera docs

Docs for the Raspberry Pi HQ (IMX477) camera path used by agents and operators.

| Document | Purpose |
|----------|---------|
| **[`camera-settings-contract.md`](camera-settings-contract.md)** | **Start here for rootserver + UI work** — wire format, slow/fast fields, forbidden keys, WS messages |
| [`pi-hq-camera.md`](pi-hq-camera.md) | Hardware, sensor modes, science notes, safe live testing on `piscope` |
| [`hq-camera-capability-report.md`](hq-camera-capability-report.md) | Verified capability suite results (modes, exposure trust, ScalerCrop behaviour) |
| [`cam-settings-bench-report.md`](cam-settings-bench-report.md) | Latest typed-settings / spectrum / reconfig bench (must stay PASS) |

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
| [`../scripts/run_cam_settings_bench.ps1`](../scripts/run_cam_settings_bench.ps1) | Sync + run bench on Pi |
| [`../deploy/astroscop-camera.service`](../deploy/astroscop-camera.service) | Production worker unit |
