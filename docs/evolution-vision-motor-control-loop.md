# Evolution: camera ↔ motor autoguide loop

**Status:** plan only (no code in this change).  
**Audience:** next implementation pass on the Pi (`piscope`) + wasp UI.  
**Depends on:** current open-loop ASC/DEC path (`motorControl.py` → Pico 2 W) and HQ preview path (`cam_picamera2.py`).

This file is the evolution note for a closed control loop: keep a chosen star still on the IMX477 by trimming ASC and DEC rates. Polar alignment is *close*, not perfect, so DEC must move. ASC sidereal is *close* (−20 … −15 STEP/s; locked today at **−15.15**), not perfect, because of drivetrain / gear error.

---

## 1. Why this exists

Today the stack is open-loop:

```text
UI slider / “sidereal”
        │  ctlparams {k: ASC|DEC|ASC_SIDEREAL, v: steps/s}
        ▼
rootserver  →  motorControl  →  Pico (dir + step_us)
```

`MountTracker` in [`backapp/motorControl.py`](../backapp/motorControl.py) only *integrates* the commanded rate. It does not look at the sky.

What we actually have:

| Fact | Consequence |
|------|-------------|
| Polar alignment is “close” | residual field drift has a DEC component; DEC cannot stay at 0 forever |
| ASC sidereal is empirical (−15.15 STEP/s, see [`backapp/asc_rates.py`](../backapp/asc_rates.py)) | mean rate is usable as **feedforward**, not as the whole answer |
| Gears / belt / worm are imperfect | periodic + slowly varying ASC error; PID on a star can trim it |
| Camera rotation vs mount axes is known | pixel `(u, v)` can be rotated into mount `(ASC, DEC)` |
| Plant gain vs declination is *not* constant | same PID numbers, if they act on raw pixels, will be wrong as DEC changes |

The first closed loop should be a **two-axis rate PID on one lock star**, sitting on top of the existing sidereal feedforward. Not plate-solving, not PEC tables, not multi-star guiding — those can come later.

---

## 2. Goal (v1)

Hold one operator-chosen star near a lock pixel by continuously adjusting motor *speeds*:

```text
ω_asc = ω_sidereal + Δω_asc_pid
ω_dec = 0          + Δω_dec_pid
```

- `ω_sidereal` stays the current empirical command (`ASC_SIDEREAL_UI_SPEED = -15.15`).
- PID outputs are **small trims** (tenths of a STEP/s), not a replacement for sidereal.
- DEC trim absorbs polar-alignment residual and slow flexure.
- ASC trim absorbs gear PE and the sidereal calibration leftover.

Success on sky: after lock, the guide star’s centroid stays inside a few pixels for minutes, without oscillating, at both mid-DEC and near the equator. Near the pole, ASC guide is allowed to go quiet (see §5).

---

## 3. Assumptions we are taking as given

1. **Mount kinematics are equatorial and “close enough.”** Polar error is small compared with the FOV, but not zero. Hour-angle-dependent DEC drift is slow enough for an I-term.
2. **Camera ↔ mount orientation is known.** A constant 2×2 rotation (plus optional flips) maps image +u/+v onto “ASC-positive on the chip” and “DEC-positive on the chip.” This is a one-time calibration, not estimated every frame.
3. **Plate scale is roughly known or easily measured.** IMX477 pixel pitch is 1.55 µm ([`backapp/docs/pi-hq-camera.md`](../backapp/docs/pi-hq-camera.md)); arcsec/pixel = `206.265 × 1.55 / f_mm` at 1×1, ×2 in `bin2x2`. Exact focal length can stay a config constant and be refined by a “nudge ASC 1° and count pixels” bench.
4. **The operator points at the star.** UI click on the preview, *or* an approximate sky position (DEC at least; RA optional). We do not need a catalog in v1.
5. **Celestial DEC of the lock is known to a few degrees.** That is enough for `cos δ`. Sources, in order of preference: UI-entered / catalog DEC → “I zeroed DEC at a known park” + `newdecDeg` offset. Do **not** treat raw `newdecDeg` as celestial δ unless that offset is set.
6. **Only the camera worker owns the IMX477.** Guiding must not open a second `Picamera2()`. Exclusive access is already documented in the HQ camera notes.
7. **Pico rate changes are already ramped (~100 ms).** The guide loop should issue sparse setpoints, same as today’s UI, not pulse-level commands.

---

## 4. The DEC-dependent plant (the part we do not want to retune by hand)

### 4.1 What actually changes with declination

On an equatorial mount, one extra ASC step rotates the polar axis by a fixed angle `Δα` (today ≈ `1 / ASC_STEPS_PER_DEGREE` ≈ 0.99″ at 1/8 microstep — see `asc_rates.py`).

The star’s **on-sky** displacement from that ASC step is

```text
Δθ_sky_from_asc = Δα · cos δ
```

| Where | `δ` | `cos δ` | ASC step → pixels |
|-------|-----|---------|-------------------|
| Celestial equator | 0° | 1 | **maximum** |
| Mid-sky | ±45° | 0.71 | ~30% less |
| Near pole | ±80° | 0.17 | small |
| Pole | ±90° | 0 | **≈ 0** — ASC is invisible on the chip |

DEC steps do **not** pick up this `cos δ`. One DEC step is (to first order, small FOV) a constant on-sky angle, all night.

So: if the PID sees **pixel error** and outputs **ASC STEP/s**, the plant gain on ASC is proportional to `cos δ`. Tune it at the equator and it goes limp near the pole. Tune it near the pole and it oscillates at the equator.

DEC’s plant gain is roughly constant. DEC still needs its own PID because polar misalignment produces a real DEC drift; it just does not need the `cos δ` schedule.

### 4.2 Reconciling “zero at DEC zero / more at the equator”

Celestial **DEC = 0° is the equator** — that is where ASC motion on the chip is *largest*, not smallest.

If on the sky you saw “almost no star motion at DEC zero, much more toward the equator”, that almost certainly means **mount DEC-zero is a park / home near the pole**, and “going to the equator” is a large DEC slew from that home. The schedule below is in **celestial** `δ`. Map mount counts once:

```text
δ_celestial ≈ δ_park + sign · newdecDeg
```

Confirm the sign on the first night (slew DEC toward a known equatorial star; `newdecDeg` should move toward 0 celestial, not away).

### 4.3 Recommended trick: do *not* retune Kp per DEC

Do not keep a table of PID gains vs DEC for v1. Normalize the error into **equivalent motor steps**, then run one PID:

```text
# pixel error in the preview / guide ROI
e_u, e_v          [pixels, lock − current; sign: "where we want the star to go"]

# known camera orientation (constant)
[ e_asc_px ]     [  cosθ  sinθ ] [ e_u ]
[ e_dec_px ]  =  [ −sinθ  cosθ ] [ e_v ]     (+ optional axis flips)

# plate scale (config; depends on sensor_preset / binning)
e_asc_arcsec = e_asc_px · s
e_dec_arcsec = e_dec_px · s

# invert the plant so PID state is "steps of correction still needed"
cos_eff      = max(|cos δ|, cos_floor)          # see pole gate below
e_asc_steps  = e_asc_arcsec / (ASC_arcsec_per_step · cos_eff)
e_dec_steps  = e_dec_arcsec /  DEC_arcsec_per_step
```

Now both plants look like a simple integrator (speed error → position in steps). **One `(Kp, Ki, Kd)` pair per axis**, independent of DEC.

`ASC_arcsec_per_step` is already implied by `ASC_STEPS_PER_DEGREE` (3600 / 3626 ≈ 0.99″/step). DEC can start as the same number and be split later if the two gear trains differ.

### 4.4 Pole gate (do not divide by ~0)

When `|δ| > δ_freeze` (start at **80°**, `cos_floor ≈ 0.17`):

- keep using `cos_floor` in the divisor so numbers stay finite
- **freeze the ASC I-term** and scale ASC `Kp` down (or set `Δω_asc = 0`)
- leave the DEC loop running — DEC is still observable

ASC near the pole is barely visible in the image; cranking gain there only injects noise into RA.

### 4.5 If we ever want empirical schedules anyway

A 3-point table of *measured* `pixels_per_asc_step(δ)` (equator / 45° / 70°) can replace the analytic `cos δ` if the camera is slightly mis-rotated or the DEC axis is not a perfect polar. Fit `k · cos(δ − δ0)` rather than storing raw PID gains. Still convert to step-error before the PID.

---

## 5. Controller

### 5.1 Structure

Two independent PI-D (or PI) controllers after the rotation + step normalization:

```text
Δω_asc = sat( Kp_a · e_asc_steps + Ki_a · I_asc + Kd_a · d(e_asc_steps)/dt )
Δω_dec = sat( Kp_d · e_dec_steps + Ki_d · I_dec + Kd_d · d(e_dec_steps)/dt )

ω_asc_cmd = ω_ff_asc + Δω_asc
ω_dec_cmd = ω_ff_dec + Δω_dec
```

| Term | Role |
|------|------|
| Feedforward `ω_ff_asc` | empirical sidereal (−15.15). Operator can still nudge this. |
| Feedforward `ω_ff_dec` | 0, unless the UI is jogging DEC |
| P | kill the current offset (seeing + residual rate) |
| I | eat constant rate error: “sidereal is 0.3 STEP/s slow”, “polar error wants +0.05 STEP/s DEC” |
| D | optional, heavily low-pass; start at 0. Seeing will look like D-noise. |

Start **PI-only**. Add D only if a slow overshoot remains after I is modest.

### 5.2 Suggested starting limits (to be confirmed on sky)

These are *order-of-magnitude* so the first night cannot run away. Not final tunes.

| Parameter | Starting guess | Why |
|-----------|----------------|-----|
| Loop rate | 2–5 Hz | preview emit is already capped at 8 fps; seeing is faster than we can usefully chase |
| ASC trim `Δω` | ±2 STEP/s | sidereal is ~15 STEP/s; gears should not need more |
| DEC trim `Δω` | ±1 STEP/s | polar residual should be small if alignment is “close” |
| Deadband | ~0.3–0.8 px (after a 3-frame centroid EMA) | do not chase seeing |
| I clamp | same as trim limits, anti-windup on sat | lost-star / slew must not wind I |
| Min command Δ | ~0.02 STEP/s | Pico `step_us` is integer; skip no-op writes |
| Lost-star | N=8 misses → hold last `Δω`, do not slam to 0 | then after T=5 s revert to feedforward only |

Derivative on a 3-sample EMA of the centroid, never on raw pixels.

### 5.3 What the PID is *not*

- Not a position goto. We command **rates**, same as today.
- Not PEC. Periodic gear error will be reduced, not memorized.
- Not field-rotation correction. One star cannot de-rotate the frame; polar error will still rotate the field slowly. That is acceptable for v1 (spectro / single-object work).

---

## 6. Star lock (sensing)

### 6.1 Operator input

Two equivalent UI actions, both become a lock request:

1. **Click the preview** — [`imgDisplay.vue`](../webapp/wasp/src/components/imgDisplay.vue) already computes normalized `(pixx, pixy)` and only `console.log`s them. Wire that click to a `guideLock` message (fractional position in the *displayed* JPEG).
2. **Approximate position** — operator types DEC (and optional RA) of the target, or later a name. v1 only needs DEC for `cos δ` plus “search the brightest blob near the current FOV center” if no click is given.

Lock point on the chip can be:

- **stay-where-clicked** (star is already in the frame; lock = that pixel), or
- **hold-at-center** (optional; extra ASC/DEC slew, out of scope for the first loop).

v1 = stay-where-clicked.

### 6.2 Centroid (camera worker, not the browser)

The loop must run on the Pi, on the **capture RGB** (or a ROI of it), not on the JPEG the hub broadcasts and not in the Vue client.

Why:

- JPEG + WS + browser adds 100–300 ms and lossy ringing around stars
- `max_emit_fps` already drops frames when the hub is overwhelmed
- only one process may own the sensor

Proposed: inside [`cam_picamera2.py`](../backapp/cam_picamera2.py), after each captured RGB (or every Nth capture):

1. Map lock from display JPEG coords → capture-RGB coords (account for `preview_div` and `scaler_crop`).
2. Extract a small ROI (e.g. 32–64 px) around the last centroid.
3. Dark-subtract a local median, threshold, compute intensity centroid.
4. Emit a small `guideSample` (not a frame):

```json
{
  "msgtype": "guideSample",
  "t": 1710000000.12,
  "ok": true,
  "u": 1012.4,
  "v": 758.1,
  "lock_u": 1010.0,
  "lock_v": 760.0,
  "snr": 18.2,
  "preset": "bin2x2",
  "preview_div": 2
}
```

`ok: false` when the star is lost (SNR, saturation, or it left the ROI). The PID worker (or motor worker) consumes this; the UI only overlays a box / error vector.

Do **not** decode `srcimage` on a new process for v1. Optional later: shared-memory crop, same pattern as [`cam_storage.py`](../backapp/cam_storage.py).

### 6.3 Camera orientation

Store in config (not guessed online):

```text
GUIDE_THETA_RAD     # image +u toward ASC+
GUIDE_FLIP_U        # 0|1
GUIDE_FLIP_V
```

Measure once: pulse ASC +N steps with DEC held, fit the star’s pixel track; that vector *is* the ASC axis on the chip. Pulse DEC the same way. The two vectors should be ~90°; if not, record both as columns of `R` instead of a single `θ`.

---

## 7. Where the loop lives in *this* repo

Do not put the PID in the browser. Do not give the guide process a second camera handle. Do not let UI sliders and the PID fight over the same absolute `ASC`/`DEC` setpoint.

### 7.1 Rate mixer (motor worker) — required

[`motorControl.py`](../backapp/motorControl.py) today treats `ctlparams ASC` / `DEC` as **absolute** speeds. Guiding needs a mixer:

```text
commanded = feedforward  +  guide_trim
```

New `ctlparams` keys (names indicative):

| Key | Who sends it | Meaning |
|-----|--------------|---------|
| `ASC` / `DEC` | UI | **feedforward** while guiding is armed; absolute if guiding is off (today’s behavior) |
| `ASC_SIDEREAL` | UI | set ASC feedforward to −15.15 |
| `GUIDE_ENABLE` / `GUIDE_DISABLE` | UI | arm mixer |
| `GUIDE_DASC` / `GUIDE_DDEC` | guide loop | trims (STEP/s). Ignored if not enabled or star lost past timeout |
| `GUIDE_LOCK` / `GUIDE_UNLOCK` | UI | forwarded to camera worker (or guide module) |

`motorInfo` grows: `guideEnabled`, `dAsc`, `dDec`, `ffAsc`, `ffDec`, so the sliders can keep showing the *operator* feedforward while the Pico runs the sum.

When the operator disarms motors or hits axis stop/reset: drop trims, freeze I-terms, unlock.

### 7.2 PID placement

Two acceptable layouts; pick **A** for v1.

**A — PID inside the motor worker** (preferred)

- Camera emits `guideSample` → hub → motor WS (or a new `/guide` path that the motor process also listens on).
- Motor worker already owns serial + rate state.
- One place that writes `set_speed_asc` / `set_speed_dec`.

**B — dedicated `guideControl.py` + systemd unit**

- Cleaner separation, extra hop, another service to babysit.
- Only worth it if the PID grows PEC / multi-star later.

Hub changes in [`rootserver.py`](../backapp/rootserver.py):

- fan-out `guideSample` to the motor (or guide) socket
- fan-out `GUIDE_LOCK` to the camera socket
- broadcast `guideInfo` to UI (lock, error px, trims, `δ`, `cos δ`)

Camera worker stays the *only* place that touches pixels.

### 7.3 UI (wasp)

Minimal surface, night-operable, next to [`stepperControl.vue`](../webapp/wasp/src/components/stepperControl.vue):

- **Guide enable** (requires motor arm + Pico linked)
- Click-to-lock on [`imgDisplay.vue`](../webapp/wasp/src/components/imgDisplay.vue); draw lock mark + live centroid
- DEC field (pre-filled if we have it; editable) — this *is* the `cos δ` input
- Readout: `e_asc_px`, `e_dec_px`, `Δω_asc`, `Δω_dec`, lock SNR
- Unlock / lost-star banner

Do not hide the ASC/DEC sliders. They remain the feedforward (sidereal + jog). While guiding, moving a slider changes `ω_ff`, not a fight with the PID.

---

## 8. Geometry cheatsheet (implementation)

Signs must be proven on hardware once and then frozen in tests with synthetic tracks.

```text
sky, small FOV, camera aligned after R:

  d(u,v)/dt  ≈  s⁻¹ · R · [  (ω_asc_err · cos δ)  ]
                         [   ω_dec_err           ]

ω_*_err = commanded_rate − true_sky_rate   [STEP/s]
```

Polar misalignment adds a slowly varying `ω_dec_true ≠ 0` and a tiny extra ASC term. The I-terms eat the mean of that. We do not model the full alignment matrix in v1.

Hour angle does **not** change the `cos δ` factor. It *does* change polar-error DEC drift; that is why DEC has an I-term rather than a one-shot offset.

---

## 9. Safety and night-ops behavior

- Guiding never enables drivers by itself. Motor arm + Pico link stay as they are.
- Lost star / `ok: false`: hold last trim briefly, then feedforward-only. Do not command a search slew in v1.
- Exposure / preset change (`sensor_preset`, `scaler_crop`, `preview_div`): drop lock (coords are in a different space) and require a new click.
- Science save can keep running; centroid uses the same RGB the preview already has. Do not add a second capture.
- Clamp every command through the existing `speed_to_dir_step_us` limits (50 µs … 10 s).
- Log `δ`, `cos_eff`, `e_*_steps`, `Δω_*` at ~1 Hz for the first on-sky nights.

---

## 10. Phased delivery (when we implement)

Docs-only now. When coding starts, keep each phase mergeable and testable without the sky.

### Phase 0 — contracts and mixer

- `ctlparams` keys + `motorInfo` / `guideInfo` / `guideSample` shapes in `ws_messages.py` (and wasp `messages.js`)
- Motor mixer with guide disabled ≡ today’s ASC/DEC behavior (regression: `test_pico_motor.py` + hub tests)
- Unit tests: `commanded = ff + trim`, stop/disarm clears trim

### Phase 1 — geometry module (no hardware)

New `backapp/guide_geom.py` (name flexible):

- `pixels_to_axis_steps(e_u, e_v, δ, *, theta, scale, flips)`
- pole gate
- inverse: steps → expected pixel motion (for tests)

Tests with δ = 0°, 45°, 80°, 89°: same on-sky error → ASC step-error grows as `1/cos δ`; DEC step-error stays flat; 89° ASC trim disabled.

### Phase 2 — centroid on RGB

- Pure functions over numpy tiles (no picamera2)
- Synthetic Gaussian star + noise; lock click; ROI walk; lost-star
- Hook into the camera worker behind a flag so default capture path is unchanged

### Phase 3 — PI loop

- `backapp/guide_pid.py`: two axes, anti-windup, EMA
- Drive the mixer from synthetic `guideSample` streams (constant rate error should be eaten by I; step offset by P)
- Still no Pico required

### Phase 4 — UI lock + overlay

- Click → `GUIDE_LOCK`
- DEC number box
- Overlay + guide enable
- Manual-only until Phase 5

### Phase 5 — on-sky bring-up (`piscope`)

1. Confirm ASC axis on chip (pulse ASC, watch track) → freeze `θ` / flips
2. Lock a mid-DEC star, ASC-only trim, DEC trim = 0 — does RA drift die?
3. Enable DEC trim — does the remaining vertical/horizontal drift die?
4. Repeat near the equator (expect larger raw px/step on ASC; same PID)
5. Repeat at high DEC — confirm ASC goes quiet and does not oscillate

---

## 11. What we are explicitly not doing in v1

- Plate-solving / astrometry.net
- Multi-star / PHD2-style calibration dance (the known `θ` + `cos δ` replaces most of that)
- PEC curve recording
- Autofocus / rotator
- Guiding from Bayer science frames (preview RGB is enough; science stays for Siril)
- A second process opening the HQ camera
- Per-DEC PID gain files

---

## 12. Open items to settle on the first implementation PR

1. **Celestial δ source of truth** — typed DEC vs mount-count + park offset. Need one config key for the park.
2. **DEC arcsec/step** — copy ASC’s 0.99″/step or measure with a DEC pulse.
3. **Exact WS path** — piggyback `guideSample` on the existing camera→hub stream vs a dedicated `/guide` client.
4. **Whether DEC gear train matches ASC** — if DEC `steps_per_degree` is wildly different, it only changes `DEC_arcsec_per_step`, not the PID structure.
5. **Sign of `DIR_INVERT_*` vs sky** — already flags in [`pico_motor.py`](../backapp/pico_motor.py); guide rotation must use the *on-sky* result after those flags.

---

## 13. Pointers into the current tree

| Piece | Path | Role in this evolution |
|-------|------|------------------------|
| Sidereal feedforward | [`backapp/asc_rates.py`](../backapp/asc_rates.py) | `ω_ff_asc`; `ASC_STEPS_PER_DEGREE` → arcsec/step |
| Rate → Pico | [`backapp/pico_motor.py`](../backapp/pico_motor.py) | unchanged protocol; mixer sits above it |
| Motor worker | [`backapp/motorControl.py`](../backapp/motorControl.py) | mixer + (layout A) PID |
| Camera worker | [`backapp/cam_picamera2.py`](../backapp/cam_picamera2.py) | ROI centroid + `guideSample` |
| Hub | [`backapp/rootserver.py`](../backapp/rootserver.py) | lock / sample / info fan-out |
| Preview click | [`webapp/wasp/src/components/imgDisplay.vue`](../webapp/wasp/src/components/imgDisplay.vue) | lock UI |
| Manual rates | [`webapp/wasp/src/components/stepperControl.vue`](../webapp/wasp/src/components/stepperControl.vue) | feedforward + guide enable |
| Sensor / exclusive access | [`backapp/docs/pi-hq-camera.md`](../backapp/docs/pi-hq-camera.md) | why centroid lives in the camera worker |
| Pico timing | [`firm/pico2w/README.md`](../firm/pico2w/README.md) | 100 ms rate ramp; sparse setpoints |

---

## 14. One-sentence summary

Keep the empirical sidereal rate as feedforward, measure one lock star on the HQ RGB, rotate that pixel error into mount axes, **divide ASC by `cos δ` so the PID always sees “steps of error”**, and add small ASC/DEC rate trims — DEC included because polar alignment is only close.
