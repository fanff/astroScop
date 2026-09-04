# wasp

Vue 3 + Vite UI for the astroScop telescope hub (`ws://host:8765`).

Emits canonical `CameraSettings` (`params`) and motor `ctlparams` per
`backapp/docs/camera-settings-contract.md`.

## Setup

```
npm install
```

### Dev server

```
npm run serve
```

Connects to `ws://<page-hostname>:8765` by default (override in the toolbar).

### Production build

```
npm run build
```

## Deploy to the Pi (`piscope`, port 80)

The UI is compiled on the host, copied to the Pi, and served by nginx on
port 80. The browser talks to the hub on the **same hostname** as the page
(`ws://piscope:8765` when you open `http://piscope/`).

From Windows (PowerShell), in `webapp/wasp`:

```
npm run package:pi    # npm ci + production build → dist/
npm run deploy:pi     # package, then install on piscope
```

From bash:

```
./deploy/package.sh
./deploy/deploy.sh
```

Override the SSH host with `ASTROSCOP_PI_HOST` (default `piscope`).

On the Pi, `deploy/install_on_pi.sh` installs nginx, publishes
`/var/www/astroscop`, and enables the site. Re-run `deploy.ps1` / `deploy.sh`
after UI changes.

`./buildandpush.sh` remains a wrapper around `deploy/deploy.sh`.
