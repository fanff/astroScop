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

### Production build

```
npm run build
```

Deploy with `./buildandpush.sh` (build + rsync to `scope`).
