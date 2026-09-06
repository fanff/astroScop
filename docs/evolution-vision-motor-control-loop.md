# Evolution: camera ↔ motor autoguide loop

**Status:** plan only (no code in this change). Delivery is **phased A–H** (§11); timing gates are **Pi benches** (§10).  
**Audience:** next implementation pass on the Pi (`piscope`) + wasp UI.  
**Depends on:** current open-loop ASC/DEC path (`motorControl.py` → Pico 2 W) and HQ preview path (`cam_picamera2.py`).

This file is the evolution note for a closed control loop: keep a chosen star still on the IMX477 by trimming ASC and DEC rates. Polar alignment is *close*, not perfect, so DEC must move. ASC sidereal is *close* (−20 … −15 STEP/s; locked today at **−15.15**), not perfect, because of drivetrain / gear error.

The operator surface is a **second locator** (tracking lock), not a reuse of today’s composition mark. Geometry inputs (celestial DEC, focal length, ASC+/DEC+ on the chip) come from the UI and ride with the crop into a **dedicated guide worker**. That worker isolates the star on a small native ROI, converts pixel drift to on-sky angle, and emits rate trims. Camera acquisition, hub fan-out, and motor serial stay out of that hot path.

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
| Camera rotation vs mount axes is known *to the operator* | pixel `(u, v)` can be rotated into mount `(ASC, DEC)` once ASC+ / DEC+ are set on the tracking locator |
| Plant gain vs declination is *not* constant | same PID numbers, if they act on raw pixels, will be wrong as DEC changes |
| Plate scale depends on optics *and* binning | `f_mm` + `sensor_preset` must be in the loop, not a hidden constant only |

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

Operator-visible success:

- A **tracking locator** (separate from the existing preview locator) marks the star being guided.
- The UI can show **which way ASC+ and DEC+ point** on that locator.
- A switch reveals the **small cropped native image** the algorithm actually uses, with the isolated star and a lightweight overlay (centroid, SNR, angular error, trims).

---

## 3. Assumptions we are taking as given

1. **Mount kinematics are equatorial and “close enough.”** Polar error is small compared with the FOV, but not zero. Hour-angle-dependent DEC drift is slow enough for an I-term.
2. **Camera ↔ mount orientation is operator-set in v1.** The tracking locator carries ASC+ and DEC+ directions on the chip (rotation + optional flips). That is a night-ops control, not an online estimator. A later pulse-ASC / pulse-DEC calibration can *fill* those fields; it does not replace them.
3. **Plate scale is computed from UI focal length + known pixel pitch + current binning.** IMX477 pitch is 1.55 µm ([`backapp/docs/pi-hq-camera.md`](../backapp/docs/pi-hq-camera.md)):

   ```text
   s_1x1_arcsec/px = 206.265 × 1.55 / f_mm
   s              = s_1x1 × bin   # bin = 1 for full / full_2160; 2 for bin2x2*
   ```

   `f_mm` is an editable UI field (propagate every lock / settings tick). It can still be refined later by “nudge ASC 1° and count pixels.”
4. **The operator points at the star** with the tracking locator (click and/or sliders). We do not need a catalog in v1.
5. **Celestial DEC of the lock is known to a few degrees** and is typed (or confirmed) in the UI. That is the `cos δ` input. Do **not** treat raw `newdecDeg` as celestial δ unless a park offset is set.
6. **Only the camera worker owns the IMX477.** Guiding must not open a second `Picamera2()`. Exclusive access is already documented in the HQ camera notes. The camera worker *crops*; it does not run PID.
7. **Pico rate changes are already ramped (~100 ms).** The guide loop should issue sparse setpoints, same as today’s UI, not pulse-level commands.
8. **Preview JPEG is display-only.** The loop never centroids the browser image or the hub JPEG.

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

v1 still **requires the operator to enter / confirm `δ` in the UI**. Mount-count mapping is a convenience fill, not the silent source of truth.

### 4.3 Recommended trick: do *not* retune Kp per DEC

Do not keep a table of PID gains vs DEC for v1. Normalize the error into **equivalent motor steps**, then run one PID:

```text
# pixel error in the native guide ROI (capture RGB, after binning)
e_u, e_v          [pixels, lock − current; sign: "where we want the star to go"]

# operator / locator orientation (constant until they change it)
[ e_asc_px ]     [  cosθ  sinθ ] [ e_u ]
[ e_dec_px ]  =  [ −sinθ  cosθ ] [ e_v ]     (+ ASC/DEC axis flips)

# plate scale from f_mm and current preset binning
e_asc_arcsec = e_asc_px · s(f_mm, bin)
e_dec_arcsec = e_dec_px · s(f_mm, bin)

# invert the plant so PID state is "steps of correction still needed"
cos_eff      = max(|cos δ|, cos_floor)          # see pole gate below
e_asc_steps  = e_asc_arcsec / (ASC_arcsec_per_step · cos_eff)
e_dec_steps  = e_dec_arcsec /  DEC_arcsec_per_step
```

Now both plants look like a simple integrator (speed error → position in steps). **One `(Kp, Ki, Kd)` pair per axis**, independent of DEC.

`ASC_arcsec_per_step` is already implied by `ASC_STEPS_PER_DEGREE` (3600 / 3626 ≈ 0.99″/step). DEC can start as the same number and be split later if the two gear trains differ.

The **angular** quantities `e_*_arcsec` (and their per-frame deltas) are what the UI overlay should show as “drift.” The PID still runs on `e_*_steps`.

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
Δω_asc = sat( Kp · e_asc_px + Ki · I_asc )   # STEP/s per axis pixel (not e_*_steps)
Δω_dec = sat( Kp · e_dec_px + Ki · I_dec )

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

Start **PI-only**. Do not ship a D term on night one. See §5.3–5.4.

### 5.2 Suggested starting limits (to be confirmed on sky)

These are *order-of-magnitude* so the first night cannot run away. Not final tunes.

| Parameter | Starting guess | Why |
|-----------|----------------|-----|
| Loop rate | 2–5 Hz | preview emit is already capped at 8 fps; seeing is faster than we can usefully chase. Processing budgets: §10 |
| ASC trim `Δω` | ±2 STEP/s | sidereal is ~15 STEP/s; gears should not need more |
| DEC trim `Δω` | ±1 STEP/s | polar residual should be small if alignment is “close” |
| Deadband | ~0.3–0.8 px (after a 3-frame centroid EMA) | do not chase seeing |
| I clamp | same as trim limits, anti-windup on sat | lost-star / slew must not wind I |
| Min command Δ | ~0.02 STEP/s | Pico `step_us` is integer; skip no-op writes |
| Lost-star | N=8 misses → hold last `Δω`, do not slam to 0 | then after T=5 s revert to feedforward only |

Derivative on a 3-sample EMA of the centroid, never on raw pixels.

### 5.3 Why PI, and why no D

The plant is already an integrator: we command **rate**, the star’s **position** is `∫ rate_error dt`. For that shape:

| Term | Fits this mount? |
|------|------------------|
| **P on position** | Yes. Offset decays. This is the main stabilizer. |
| **I on position** | Yes. Eats the biases we actually have (sidereal a bit wrong, polar-alignment DEC drift, a slow gear mean). |
| **D on position** | Not for v1. At 2–5 Hz, `d(centroid)/dt` is mostly **seeing**. Differentiating that makes the motors chase atmosphere and often tracks *worse* than open-loop sidereal. |

Commanding rate from position already uses the velocity channel. Extra D is “brake when the error is shrinking.” That only helps if the plant is laggy enough to overshoot **and** the velocity is clean. We have some lag (exposure + centroid + Pico’s ~100 ms ramp), but not a heavy current-loop servo.

**Add D later only if** a slow, clean overshoot remains after a 3-frame EMA — and then only on that filtered velocity, never on raw pixels. Prefer the drift-rate estimator in §5.4 before turning on `Kd`.

I is the term that can actually hurt: windup on a lost star or a slew. Clamp I to the trim limits and drop trim when the star disappears. That matters more than D.

CPU on the Pi is not the constraint. Isolation + PI on a 64–128 px tile is cheap next to JPEG encode. The constraints are **who owns the IMX477**, **not guiding from the browser JPEG**, and **not stalling capture / serial / hub** while we do it.

This is the same family as PHD2-style guiders (P / aggression + a slow bias), even when they do not call it PID.

### 5.4 Better methods — what is worth it later

Ranked for *this* mount, not in general:

| Priority | Method | When |
|----------|--------|------|
| v1 | **PI + sidereal feedforward + `cos δ` step-normalization** | First closed loop. Matching physics: integrator + constant bias + seeing. |
| Next, if I is ugly | **Drift-rate estimator, then P only** | Kalman or a slow EMA of centroid velocity. Treat estimated `ω_err` as extra feedforward; P only on leftover position. Same job as I, but the memory is a filtered rate, not an unbounded integral. Do this **before** adding `Kd`. |
| Cheap robustness | **Hysteresis / min-move** | Do nothing inside the deadband (seeing), then a proportional pulse. Can sit in front of the same PI. |
| After a working loop | **PEC** | Learn the worm/belt period on ASC. PID cannot memorize repeating PE; it only chases it. |
| Later SNR | **Multi-star / correlation** | Better measurement, same controller. Not a different philosophy. |

Usually **not** worth it here: MPC, LQR, Smith predictors, adaptive-gain PID tables. The `cos δ` normalization already does the one schedule that is physically real. Plate-solving every frame, or a full PHD2 calibration dance, is also not better for v1 — known camera-vs-axes rotation *is* that calibration.

### 5.5 What the loop is *not*

- Not a position goto. We command **rates**, same as today.
- Not PEC. Periodic gear error will be reduced, not memorized (until §5.4).
- Not field-rotation correction. One star cannot de-rotate the frame; polar error will still rotate the field slowly. That is acceptable for v1 (spectro / single-object work).

---

## 6. Star lock (sensing)

### 6.1 Two locators — do not overload the existing one

Today’s [`locator_*`](../backapp/cam_locator.py) is a **composition / aiming mark**: burned into the **preview JPEG only**, full-sensor normalized `(x, y)`, size scale, circle + cardinal ticks. It is *not* a lock, it does not name axes, and science Bayer is untouched. Keep it.

The autoguide loop needs a **tracking locator**, a different object:

| | Existing `locator_*` | New tracking locator (`track_*` names indicative) |
|--|----------------------|---------------------------------------------------|
| Purpose | “where am I looking / framing” | “this star is the lock” |
| Drawn | burned into preview JPEG in the camera worker | **client overlay** (and optional crop JPEG from the guide worker) |
| Position | full IMX477 fractions `locator_x/y` | same coordinate space: full-sensor fractions `track_x/y` |
| Size | glyph radius | **ROI size** (how much native image to crop), plus a distinct glyph |
| Axes | none | **ASC+ and DEC+ directions** on the chip |
| When disabled | no red mark | no lock, no crop, no PID |

Why a second object:

- Operators still want the composition circle while guiding a different star (or while the lock is off).
- Burning the lock into the preview JPEG fights the “show me the work crop / overlay” requirement and couples display to sensing.
- Axis arrows would make the existing red glyph unreadable if we stuffed them into the same mark.

v1 lock gesture: **stay-where-placed**. Click on [`imgDisplay.vue`](../webapp/wasp/src/components/imgDisplay.vue) (it already computes normalized `(pixx, pixy)` and only `console.log`s them) *or* sliders/nudges, same pattern as the composition locator. Map the click from displayed JPEG pixels → full-sensor fractions using current `scaler_crop` / preview size (same math as `locator_preview_xy`, inverted). Optional later: “brightest blob near FOV center” if no click.

Hold-at-center (slew the star to chip center) is out of scope for the first loop.

### 6.2 Operator geometry fields (must reach the guide worker)

These are first-class UI + wire fields, not comments in a Pi config file:

| Field | Why |
|-------|-----|
| `track_enabled` + `track_x` + `track_y` | lock position in full-sensor fractions |
| `track_roi` | crop half-size in **native capture pixels** after the current preset (start 32–64; UI slider) |
| `track_asc_dir` / `track_dec_dir` | which way is the **positive** ASC / DEC axis on the image (see §6.5) |
| `guide_dec_deg` | celestial `δ` for `cos δ` (editable; few degrees is enough) |
| `guide_focal_mm` | optics; plate scale with 1.55 µm pitch and current binning |

Changing `sensor_preset`, `scaler_crop`, or `preview_div` drops the lock (coordinate spaces moved) and requires a new placement. Changing `guide_dec_deg` / `guide_focal_mm` / axis dirs while locked **updates the geometry on the next sample** without unlocking — the star did not move on the chip.

### 6.3 Native crop (camera worker only copies pixels)

The loop must run on **capture RGB** (the array already in [`cam_picamera2.py`](../backapp/cam_picamera2.py) *before* `preview_div` JPEG), not on the hub JPEG and not in Vue.

Why:

- JPEG + WS + browser adds 100–300 ms and lossy ringing around stars
- `max_emit_fps` already drops frames when the hub is overwhelmed
- only one process may own the sensor
- binning and resolution are those of the **sensor preset + main RGB**, not of the downsampled preview

Per locked frame (or every Nth capture):

1. Map `track_x/y` from full-sensor fractions → **capture-RGB pixels** (account for `sensor_preset` size, `scaler_crop`, and that ScalerCrop metadata is in full-sensor space even when binned — same rules as the existing locator).
2. Center a square ROI of `track_roi` on the last known centroid (first frame: the lock pixel). Clamp to the RGB bounds; if the lock is outside the current crop, `ok: false`.
3. Copy that small tile (and a compact metadata blob) to the guide worker. Do **not** decode `srcimage` in a new process. Pattern: same idea as [`cam_storage.py`](../backapp/cam_storage.py) but the payload is tiny (e.g. 64×64×3 uint8 ≈ 12 KiB), so a **single shm slot or a multiprocessing queue of numpy copies** is enough. Do not ship the full frame.
4. Camera worker continues spectrum + JPEG + optional science Bayer on the **uncropped** path. Cropping must not add a second capture.

The worked image is always this small native tile. That is what makes isolation cheap and stable.

### 6.4 Star isolation (guide worker, every tile)

The star is **not** one pixel. The tile is noisy. Isolation runs every frame, so it must be a boring, stable estimator — not a clever re-acquisition.

Recommended v1 (all numpy, no OpenCV required):

1. Convert ROI to luminance (`0.3 R + 0.6 G + 0.1 B` or max of channels — pick one and freeze it in tests).
2. Background: local median (or 3σ-clipped mean of a border annulus). Subtract.
3. Gate: pixels above `max(k · σ_bg, floor)`. Reject the frame if too few pixels, too many (saturation / cloud / hot column), or peak in the outermost ring (star leaving).
4. **Intensity centroid** of the gated blob (first moment). Optional: one pass of windowed centroid around that peak so a nearby hot pixel does not steal the lock.
5. EMA (3 frames) of `(u, v)` before geometry. Deadband on the smoothed position.
6. `ok: false` on SNR / saturation / left-ROI. Do **not** jump to the brightest unrelated blob in the tile — that is how the lock walks to a neighbor.

Do **not** for v1: 2D Gaussian MLE, matched filter banks, multi-star, or “recenter on the max pixel.” Max-pixel is unstable on a several-pixel PSF plus read noise.

The lock pixel (where the tracking locator was placed) is the **setpoint**. The centroid is the **measurement**. Drift in the ROI is `centroid − lock` in capture pixels, then §4.3.

Synthetic tests (no camera): Gaussian PSF 2–4 px σ, Poisson + Gaussian noise, slow linear drift, a hot pixel, a second dimmer star at the edge. The estimator must stay on the primary and report `ok: false` when SNR collapses.

### 6.5 ASC+ / DEC+ on the tracking locator

Store as an operator-editable orientation, not a hidden `GUIDE_THETA_RAD` only:

```text
track_theta_deg     # image +u → ASC+  (0 = ASC+ points right on the capture RGB)
track_flip_asc      # 0|1  reverse ASC+ after rotation
track_flip_dec      # 0|1  reverse DEC+ after rotation
```

UI: two colored ticks/arrows on the tracking overlay (ASC+ vs DEC+). Discrete 90° rotate + flip buttons are enough for night ops; a free angle slider is optional. DEC+ should stay ~90° from ASC+; if the operator sets a non-orthogonal pair, v1 still uses one `θ` plus flips (document that). If a later calibration shows the axes are not 90°, replace `θ` with both columns of `R`.

Measure once when convenient: pulse ASC +N steps with DEC held; the star’s pixel track *is* ASC+ on the chip. Pulse DEC the same way. That can *write* `track_theta_deg` / flips; the UI remains the source of truth so a 180° camera rotation is a click, not a Pi redeploy.

Signs must be proven on hardware once and then frozen in tests with synthetic tracks. `DIR_INVERT_*` in [`pico_motor.py`](../backapp/pico_motor.py) is a *motor* flag; guide rotation is the *on-sky after those flags* result.

### 6.6 Samples the rest of the stack consumes

Guide worker emits a small `guideSample` / `guideInfo` (not a full frame) at loop rate:

```json
{
  "msgtype": "guideSample",
  "t": 1710000000.12,
  "ok": true,
  "u": 32.4,
  "v": 31.1,
  "lock_u": 32.0,
  "lock_v": 32.0,
  "roi_origin_u": 980,
  "roi_origin_v": 726,
  "snr": 18.2,
  "e_asc_arcsec": 0.41,
  "e_dec_arcsec": -0.12,
  "e_asc_steps": 0.48,
  "e_dec_steps": -0.12,
  "dAsc": -0.07,
  "dDec": 0.02,
  "dec_deg": 42.0,
  "focal_mm": 400,
  "preset": "bin2x2",
  "bin": 2
}
```

`u,v` here are **ROI-local** (small image coordinates). Full-chip position is `roi_origin + (u, v)` for the preview overlay.

Optional, gated by a UI switch (`guide_show_crop`): a **second, small JPEG** of the worked tile with centroid crosshair (encode in the guide worker, not the camera worker). Broadcast only when the switch is on so the hub is not paying for two JPEGs all night.

---

## 7. Where the loop lives in *this* repo

Do not put the PID in the browser. Do not give the guide process a second camera handle. Do not let UI sliders and the PID fight over the same absolute `ASC`/`DEC` setpoint. Do not run isolation inside the camera capture loop or the motor serial loop.

### 7.1 Preferred layout: dedicated guide worker

v1 **picks the dedicated service** (`guideControl.py` + systemd unit, e.g. `astroscop-guide`).

Earlier drafts preferred PID inside the motor worker. That stays a valid fallback, but it couples three different clocks (centroid, PI, Pico UART) and makes the crop-preview encode a motor-process problem. Isolation + geometry + PI + optional crop JPEG is enough work and enough failure domain to stand alone — same reason science Bayer already left the camera process via [`cam_storage.py`](../backapp/cam_storage.py).

```text
                    full RGB (camera owns IMX477)
   cam_picamera2 ──► crop native ROI ──► shm / queue ──► guideControl
         │                                              │
         │ JPEG preview                                 │ guideSample + trims
         ▼                                              │ optional crop JPEG
    rootserver hub ◄────────────────────────────────────┘
         │
         ├──► wasp (overlays, crop switch, DEC, f_mm, axis dirs)
         └──► motorControl  (mixer: ω = ω_ff + Δω_guide)
                    │
                    ▼
                  Pico
```

| Process | Owns | Must not own |
|---------|------|--------------|
| `cam_picamera2` | IMX477, full RGB, Bayer shm, preview JPEG, **ROI copy** | PID, star isolation, crop JPEG for UI |
| `guideControl` (new) | isolation, `guide_geom`, PI, `GUIDE_DASC/DDEC`, optional crop JPEG, `guideInfo` | Picamera2, Pico serial, hub listen sockets beyond its client WS |
| `motorControl` | Pico, **rate mixer**, `motorInfo` | pixels |
| `rootserver` | fan-out | computation |

Restart domains: camera hang still systemd-restarts only the camera (today). Guide crash must **drop trims** (motor sees silence / `ok` timeout → feedforward only), not take down capture. Motor crash must not unlock the camera.

Hub changes in [`rootserver.py`](../backapp/rootserver.py):

- fan-out tracking-locator / DEC / `f_mm` / axis dirs to camera (for crop) **and** guide (for geometry)
- camera → guide: not via the browser; either a dedicated WS client from `guideControl` to the hub, or a localhost socket / shm metadata channel. Prefer **hub WS** so there is one debug path, but the **pixel tile must not go through the UI**.
- fan-out `GUIDE_DASC` / `GUIDE_DDEC` to the motor socket
- broadcast `guideInfo` (+ optional crop JPEG) to wasp

Camera worker stays the *only* place that touches the sensor. Guide worker is the *only* place that isolates the star and runs PI.

### 7.2 Rate mixer (motor worker) — required

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
| `GUIDE_DASC` / `GUIDE_DDEC` | **guide worker** | trims (STEP/s). Ignored if not enabled or star lost past timeout |
| tracking locator / `GUIDE_LOCK` / `GUIDE_UNLOCK` | UI | forwarded to camera (crop on/off) and guide (PI reset) |

`motorInfo` grows: `guideEnabled`, `dAsc`, `dDec`, `ffAsc`, `ffDec`, so the sliders can keep showing the *operator* feedforward while the Pico runs the sum.

When the operator disarms motors or hits axis stop/reset: drop trims, freeze I-terms, unlock.

The motor worker does **not** subscribe to pixel tiles. It only applies trims it is given.

### 7.3 UI (wasp)

Night-operable, next to [`stepperControl.vue`](../webapp/wasp/src/components/stepperControl.vue) and [`captureOptions.vue`](../webapp/wasp/src/components/captureOptions.vue). Do **not** hide or reuse the existing locator panel.

**Tracking locator panel (new):**

- enable / unlock
- X/Y (full-sensor fractions) + nudge, same UX family as the composition locator but a different glyph (e.g. box or diamond, not the red circle)
- ROI size
- ASC+ / DEC+ rotate 90° and flip; overlay arrows on the preview
- **DEC (deg)** — this *is* the `cos δ` input; pre-fill from mount+park if we have it, always editable
- **focal length (mm)** — plate scale; persist in the client like other camera fields
- **Guide enable** (requires motor arm + Pico linked + tracking locator on + star `ok`)
- **Show work crop** switch — when on, `imgDisplay` (or a sibling overlay) shows the small native JPEG from the guide worker instead of / on top of the full preview; star mark + SNR / `e_asc_arcsec` / `e_dec_arcsec` / `Δω` as text overlay. Prefer a **dedicated HTML overlay** on the existing preview (`imgDisplay.vue`) rather than burning marks in the camera JPEG, so composition locator and tracking overlay can coexist.

**Readouts:** lock SNR, `e_asc_px` / `e_dec_px`, angular error, `Δω_asc` / `Δω_dec`, `cos δ`, lost-star banner.

Do not hide the ASC/DEC sliders. They remain the feedforward (sidereal + jog). While guiding, moving a slider changes `ω_ff`, not a fight with the PID.

Click-to-place: wire `imgClicked` to the tracking locator when that tool is armed; do not steal clicks from the composition locator when only that one is enabled.

---

## 8. Geometry cheatsheet (implementation)

Signs must be proven on hardware once and then frozen in tests with synthetic tracks.

```text
sky, small FOV, camera aligned after R:

  d(u,v)/dt  ≈ s(f_mm, bin)⁻¹ · R · [  (ω_asc_err · cos δ)  ]
                                    [   ω_dec_err           ]

ω_*_err = commanded_rate − true_sky_rate   [STEP/s]
```

Polar misalignment adds a slowly varying `ω_dec_true ≠ 0` and a tiny extra ASC term. The I-terms eat the mean of that. We do not model the full alignment matrix in v1.

Hour angle does **not** change the `cos δ` factor. It *does* change polar-error DEC drift; that is why DEC has an I-term rather than a one-shot offset.

Binning: `u,v` and ROI size are in **capture RGB pixels**. `s` must use the same bin factor as that array (`1` or `2` for current presets). Mixing preview_div pixels into `s` is a bug.

---

## 9. Safety and night-ops behavior

- Guiding never enables drivers by itself. Motor arm + Pico link stay as they are.
- Lost star / `ok: false`: hold last trim briefly, then feedforward-only. Do not command a search slew in v1.
- Exposure / preset change (`sensor_preset`, `scaler_crop`, `preview_div`): drop lock (coords are in a different space) and require a new placement.
- Science save can keep running; the crop is a copy of RGB the preview already has. Do not add a second capture.
- Clamp every command through the existing `speed_to_dir_step_us` limits (50 µs … 10 s).
- Guide worker silence (crash, blocked): motor times out trims the same as lost-star.
- Log `δ`, `f_mm`, `bin`, `cos_eff`, `e_*_arcsec`, `e_*_steps`, `Δω_*` at ~1 Hz for the first on-sky nights.

---

## 10. Performance budgets

The loop is **2–5 Hz** (§5.2). Seeing is faster than that; we do not chase it. Every added stage must leave the camera JPEG path and the Pico serial path alone.

Budgets are **p95 wall time on the Pi**, measured there. A laptop number is a smoke check only — ARM vs x86, numpy/OpenBLAS, and thermal throttling all lie. If a bench misses the gate, the phase is not done.

| Stage | p95 gate (Pi) | Why that number |
|-------|----------------|-----------------|
| Geometry (`pixels_to_axis_steps` + pole gate) | **< 0.5 ms** | trivial; catch accidental Python loops |
| Star isolation on 64×64 RGB | **< 5 ms** | 5 Hz = 200 ms period; isolation must be noise |
| Star isolation on 128×128 RGB | **< 15 ms** | upper ROI we will allow in v1 |
| ROI extract (copy from capture RGB) | **< 2 ms** (64²), **< 5 ms** (128²) | runs *in* the camera worker; must not delay JPEG/spectrum |
| Handoff camera → guide (queue/shm + metadata) | **< 3 ms** extra in the camera process | decoupling is the point |
| PI both axes, one sample | **< 0.5 ms** | rounding error next to isolation |
| Optional crop JPEG encode (128², quality ~70) | **< 15 ms** | **only when UI switch is on**; never on the capture thread |
| Guide worker: tile in → `guideSample` + trims out (JPEG off) | **< 20 ms p95**, **< 50 ms max** | comfortably inside 5 Hz; 2 Hz still fine if we skip frames |
| Sustained | **≥ 5 Hz** for 30 s on synthetic 64², no growing backlog | drop/skip policy if the camera is faster |
| Mixer apply | no extra pixel work; same Pico write path as today | regression: disarm ≡ old behaviour |

Capture-path regression (live camera, Phase D): with tracking crop **on**, preview emit fps and capture `frame_time_ms` stay within **10%** of the same run with crop **off** (same preset, same shutter). Do not accept a design that steals the 8 fps emit budget.

JPEG crop for the UI is **opt-in** and encoded in the guide worker. Measuring that path with the switch off is a failed bench setup.

### 10.1 Where benches run

| Kind | Host | Role |
|------|------|------|
| Correctness unit tests (`test_guide_*.py`, mixer, hub) | **dev machine** (Windows/laptop) every phase | merge gate |
| Timing / throughput benches (`*_bench.py`) | **Pi only** is authoritative | phase gate for §10 table |
| Live camera crop / emit regression | **Pi**, `astroscop-camera` **stopped** (same rule as [`test_cam_settings_bench.py`](../backapp/test_cam_settings_bench.py)) | Phase D |
| On-sky closed loop | **Pi + mount + sky** | last phase; not a CI bench |

Benches are **pushed to the Pi and executed there**, then results pulled back — same family as [`scripts/run_cam_settings_bench.ps1`](../backapp/scripts/run_cam_settings_bench.ps1) (scp modules → `ssh` python → scp `/tmp/...` → local report). Expected new artifacts when those phases are coded (names indicative):

- `backapp/test_guide_geom_bench.py`
- `backapp/test_guide_isolate_bench.py`
- `backapp/test_guide_crop_bench.py` (live RGB crop + emit regression)
- `backapp/test_guide_worker_bench.py` (process loop, JPEG on/off)
- `backapp/scripts/run_guide_bench.ps1` (sync + run + pull)
- `backapp/docs/guide-bench-report.md` (latest PASS/FAIL vs the table above)

**Pi access** (SSH host alias, remote `backapp` path, which user, how to stop `astroscop-camera` / later `astroscop-guide`) is **not** copied here. It will be written into the bench script comment + that phase’s implementation notes, using the same `ASTROSCOP_PI_HOST` / deploy conventions as the camera benches. Do not invent a second way to reach the Pi.

Each bench must print p50/p95/max, iteration count, tile size, and **PASS/FAIL against the gate**. A report that only dumps milliseconds without a gate is incomplete.

---

## 11. Phased delivery

Docs-only until a phase is scheduled. **One phase per implementation pass.** Each phase is mergeable, has a regression net, and does not require the sky until the last one.

Rules:

- Do not start phase *N+1* until phase *N* tests are green **and** that phase’s Pi bench (if it has one) is PASS.
- Default production path stays **guide off** until the UI arm + mixer enable of the late phases.
- Do not put isolation or PID into `cam_picamera2` or `motorControl` “just for a prototype.”
- Names below are indicative; keep contracts stable once Phase A has shipped.

```text
A mixer/contracts → B geom → C isolate+ROI → D camera crop handoff
                                              ↘
                                               E guide worker + PI (synthetic tiles until D)
                                              ↙
                               G UI overlay ← F hub fan-out
                                              ↓
                               H arm mixer + on-sky
```

| Phase | What ships | Sky? | Camera? | Pi bench? |
|-------|------------|------|---------|-----------|
| **A** | Wire shapes + motor mixer | no | no | no (correctness only) |
| **B** | `guide_geom.py` | no | no | yes — geom µs |
| **C** | ROI map + star isolation (pure) | no | no | yes — isolation ms |
| **D** | Camera copies native ROI off-process | no | **yes** (bench) | yes — crop + emit regression |
| **E** | `guideControl` + PI, synthetic in | no | no | yes — worker loop |
| **F** | Hub fan-out (lock / sample / trim) | no | optional | no (hub tests on laptop; smoke on Pi) |
| **G** | wasp tracking locator + overlay + crop switch | no motors | optional live preview | crop-JPEG encode in worker bench |
| **H** | Arm mixer from UI; on-sky bring-up | **yes** | yes | reuse E/D benches; no new gate |

Phases **D** and **E** can overlap on the branch (different files) but **E must run against a fake tile source until D’s handoff exists**. Do not block PI unit tests on a live IMX477.

---

### Phase A — contracts and mixer

**Goal:** Guiding can be *wired* without changing open-loop night ops.

**Code:**

- `ctlparams` keys + `motorInfo` / `guideInfo` / `guideSample` / `track_*` / `guide_dec_deg` / `guide_focal_mm` in [`ws_messages.py`](../backapp/ws_messages.py) (and wasp `messages.js` / `cameraSettings.js` as needed — wasp can wait until G if the hub still ignores unknown keys; prefer adding fields once).
- Motor mixer: `commanded = ff + trim`. Guide disabled (or no trims) ≡ today’s `ASC`/`DEC`.
- Stop / disarm / axis reset clears trim and ignores further `GUIDE_D*` until re-enabled.
- Missing `guideSample` / trim timeout → feedforward only.

**Tests (laptop):**

- Mixer: `ff + trim`, sat, enable off ignores trim, timeout, disarm.
- Regression: [`test_pico_motor.py`](../backapp/test_pico_motor.py) + [`test_rootserver_hub.py`](../backapp/test_rootserver_hub.py) still pass with new keys ignored or round-tripped.
- Composition `locator_*` settings tests unchanged ([`test_cam_locator.py`](../backapp/test_cam_locator.py)).

**Pi bench:** none. Mixer is not the timing risk.

**Done when:** with `GUIDE_ENABLE` unset, a Pi motor session behaves as today. Unit tests green on the laptop.

**Not in this phase:** pixels, UI lock, systemd unit.

---

### Phase B — geometry module

**Goal:** One function the rest of the stack can trust for `cos δ` and plate scale.

**Code:** [`backapp/guide_geom.py`](../backapp/guide_geom.py)

Frozen API:

- `plate_scale_arcsec_per_px(f_mm, bin)` (alias `plate_scale`) — `206.265 × 1.55 / f_mm × bin`
- `bin_factor_for_preset(preset)` — `full` / `full_2160` → 1; `bin2x2*` → 2
- `pixels_to_axis_steps(e_u, e_v, *, f_mm, bin, dec_deg, theta_deg=0, flip_asc=False, flip_dec=False)` → `AxisError` (`e_*_px`, `e_*_arcsec`, `e_*_steps`, `cos_eff`, `pole_gate`)
- `axis_steps_to_pixels(...)` — inverse, same kwargs
- θ = 0: ASC+ = `+u`, DEC+ = `+v` on capture RGB; then flips
- `DEC_ARCSEC_PER_STEP = ASC_ARCSEC_PER_STEP` (`3600 / ASC_STEPS_PER_DEGREE`) until a DEC pulse splits them
- `f_mm <= 0` or `bin` not in `{1, 2}` → `ValueError`
- Pole gate is a **flag**, not a trim: `|δ| > 80°` → `pole_gate=True`, still finite `e_asc_steps` via `cos_eff = max(|cos δ|, cos 80°)`; Phase E freezes ASC I / zeros `Δω_asc`

**Tests (laptop):** [`backapp/test_guide_geom.py`](../backapp/test_guide_geom.py)

- δ = 0°, 45°, 80°, 89°: same on-sky error → ASC step-error grows as `1/cos_eff`; DEC step-error stays flat; 89° `pole_gate` and finite ASC steps
- `bin=1` vs `bin=2`; two `f_mm`; flips reverse the matching axis only; roundtrip
- `f_mm <= 0` / bad bin raise

**Pi bench:** [`backapp/test_guide_geom_bench.py`](../backapp/test_guide_geom_bench.py) — 10k calls, p95 **< 0.5 ms**. Runner: [`backapp/scripts/run_guide_bench.ps1`](../backapp/scripts/run_guide_bench.ps1) (`ssh piscope`, remote `/home/fanf/astroScop/backapp`; geom stage does **not** stop `astroscop-camera`). Report: [`backapp/docs/guide-bench-report.md`](../backapp/docs/guide-bench-report.md).

**Done when:** tests green locally; Pi bench PASS in the report.

**Not in this phase:** isolation, camera, PID.

---

### Phase C — native ROI mapping + star isolation (no camera process)

**Goal:** Stable centroid on a noisy, multi-pixel star, and correct crop coordinates.

**Code:**

- [`backapp/guide_roi.py`](../backapp/guide_roi.py) — `lock_to_roi` / `lock_to_rgb_uv`. Full-sensor fractions + `scaler_crop` + RGB size → square tile. Reuses [`parse_scaler_crop`](../backapp/cam_locator.py) / `FULL_SENSOR_WH`. **Does not** clamp out-of-crop locks (that is the composition glyph). `track_roi` is half-size; tile is `2 * roi_half`, shifted to stay in-bounds.
- [`backapp/guide_isolate.py`](../backapp/guide_isolate.py) — `isolate_star`, `CentroidEma(n=3)`, `TileStack` (5-frame median of the native RGB tile before isolate):
  - luminance `0.3 R + 0.6 G + 0.1 B`
  - 3-px border-annulus median / σ
  - gate `max(3σ, 1)`
  - intensity first-moment **in a window around the lock** (not global max); if the lock window is empty, a short search around the lock recenters
  - `ok: false` on too few gated px, **sky** annulus too full, low SNR, peak in the outer ring — clipped star cores are kept
- Deadband stays Phase E. No geom/PID here.

**Tests (laptop, synthetic tiles):** [`test_guide_roi.py`](../backapp/test_guide_roi.py), [`test_guide_isolate.py`](../backapp/test_guide_isolate.py)

- Gaussian PSF 2–4 px σ + Poisson/read noise; slow drift; lock holds.
- Hot pixel and a dimmer neighbor at the tile edge must **not** steal the lock.
- Lost-star when SNR collapses or the blob hits the outer ring.
- ROI clamp when the lock is near the RGB border; lock outside crop → `ok: false`.

**Pi bench:** [`test_guide_isolate_bench.py`](../backapp/test_guide_isolate_bench.py) — 64² (p95 **< 5 ms**) and 128² (p95 **< 15 ms**), several SNR levels. No Picamera2; do not stop `astroscop-camera`. `run_guide_bench.ps1 -Stage isolate`. Report merges into [`guide-bench-latest`](../backapp/docs/guide-bench-latest/) so geom PASS is kept.

**Done when:** tests green locally; isolate section in [`guide-bench-report.md`](../backapp/docs/guide-bench-report.md) is PASS from `piscope` / `aarch64`.

**Not in this phase:** copying live frames, JPEG, PI, UI.

---

### Phase D — camera worker ROI handoff

**Goal:** The IMX477 owner extracts a small native RGB tile without running isolation, and without regressing preview timing.

**Code:**

- [`backapp/guide_handoff.py`](../backapp/guide_handoff.py) — `extract_guide_tile` (lock-centered `np.copy`) + `GuideTileSlot` **latest-wins shm** (max 128²). Not a `multiprocessing.Queue` (guide is a sibling systemd unit).
- [`CameraSettings`](../backapp/cam_settings.py) **output** fields: `track_enabled` (default false), `track_x/y`, `track_roi` half-size 8–64. No θ / DEC / `f_mm` on the camera.
- [`cam_picamera2.emit_frame`](../backapp/cam_picamera2.py): if tracking on, extract + slot write on the **capture** path. Off path: boolean check + close slot if it was open. No isolate, PID, or crop JPEG.

**Tests (laptop):** [`test_guide_handoff.py`](../backapp/test_guide_handoff.py) — origin vs `lock_to_roi`, outside crop → no tile, shm roundtrip + overwrite, disabled does not allocate, settings ingest.

**Pi bench (live camera, service stopped):** [`test_guide_crop_bench.py`](../backapp/test_guide_crop_bench.py) via `run_guide_bench.ps1 -Stage crop`.

- extract p95 **< 2 ms** (64²), **< 5 ms** (128²); handoff extra **< 3 ms**
- crop-on `frame_time_ms` / emit fps within **10%** of crop-off

**Done when:** laptop tests green; crop section in [`guide-bench-report.md`](../backapp/docs/guide-bench-report.md) PASS from `piscope`.

**Not in this phase:** systemd guide unit, UI, motors, isolate-in-camera.

---

### Phase E — guide worker + PI

**Goal:** A process that turns tiles into trims, fast enough, crash-isolated.

**Code:**

- [`backapp/guide_pid.py`](../backapp/guide_pid.py) — PI-only (`Kd=0`), `Kp=0.4`, `Ki=0.05`, sat ±2/±1, 0.5 px deadband, I anti-windup, pole-gate zeros ASC, lost-star hold 8 samples then drop after 5 s
- [`backapp/guide_process.py`](../backapp/guide_process.py) — `GuideEngine.process_tile`: isolate → EMA → geom → PI → `GuideSample`. Skip unchanged `seq`. `f_mm<=0` refuses
- [`backapp/guideControl.py`](../backapp/guideControl.py) — shm attach or `--feed synthetic`, ~5 Hz. **`--emit-trims` default off** (no Pico). JPEG off unless `--jpeg`
- [`backapp/deploy/astroscop-guide.service`](../backapp/deploy/astroscop-guide.service) — copied by install, **not enabled**

**Tests (laptop):** [`test_guide_pid.py`](../backapp/test_guide_pid.py), [`test_guide_process.py`](../backapp/test_guide_process.py)

**Pi bench:** [`test_guide_worker_bench.py`](../backapp/test_guide_worker_bench.py) — synthetic 64², **do not** stop the camera. `run_guide_bench.ps1 -Stage worker`. Gates: tile→sample p95 **< 20 ms**; JPEG-on p95 **< 15 ms**; 5 Hz 30 s and 10 Hz with **no backlog**.

**Done when:** tests green; worker section PASS on `piscope`.

**Not in this phase:** wasp overlay, hub `/guide` path, `GUIDE_ENABLE` from UI.

---

### Phase F — hub fan-out

**Status:** implemented. Tiles stay on shm. Control/status on WebSocket. `astroscop-guide` stays **disabled**; `--emit-trims` default off.

**Code:** [`rootserver.py`](../backapp/rootserver.py), [`guideControl.py`](../backapp/guideControl.py), [`cam_settings.py`](../backapp/cam_settings.py)

- Same validated `params` → camera (crop) **and** `/guide` (geometry)
- `GUIDE_D*` `ctlparams` from the guide socket → motor (mixer still needs `GUIDE_ENABLE`)
- `guideInfo` / `guideSample` → UI after stripping `jpeg` / `imageData` / `tile`
- Guide worker is a hub client at `ws://127.0.0.1:8765/guide`

**Tests (laptop):** [`test_rootserver_hub.py`](../backapp/test_rootserver_hub.py) `test_guide_hub_fanout`

**Pi bench:** none.

**Done when:** hub tests green.

**Not in this phase:** night-operable Vue; enabling the guide unit.

---

### Phase G — UI (tracking locator, overlay, work-crop switch)

**Status:** implemented. Mixer stays off (no `GUIDE_ENABLE` control). `astroscop-guide` stays disabled.

**Code:**

- [`guidePanel.vue`](../webapp/wasp/src/components/guidePanel.vue) — lock, ROI, 90°+flips, DEC, `f_mm`, show-crop; composition locator unchanged
- [`imgDisplay.vue`](../webapp/wasp/src/components/imgDisplay.vue) — HTML overlay (box + ASC+/DEC+ arrows); click-to-place when armed; crop inset
- [`trackOverlay.js`](../webapp/wasp/src/ws/trackOverlay.js) — invert `locator_preview_xy` + `object-fit: contain` click map
- Hub: `guideInfo.data.jpeg` (string) is forwarded; `tile` still stripped
- [`guideControl.py`](../backapp/guideControl.py) attaches base64 JPEG when encoding

**Tests:** `python test_cam_locator.py` invert; `test_rootserver_hub.py` jpeg-keep/tile-strip; `npm run test:overlay` in wasp.

**Pi bench:** none required.

**Done when:** overlay + composition locator are independent; crop inset works when the guide worker is running.

**Not in this phase:** claiming on-sky tracking success; mixer arm.

---

### Phase H — arm mixer and on-sky bring-up

**Status:** wiring implemented. Mixer defaults off. No sky simulator; on-sky steps are night notes (`ssh piscope`).

**Code:**

- [`astroscop-guide.service`](../backapp/deploy/astroscop-guide.service) — enabled on install; `--emit-trims` (mixer still ignores until `GUIDE_ENABLE`)
- [`motorControl.py`](../backapp/motorControl.py) — `GUIDE_ENABLE` only if UI armed **and** Pico linked
- Hub forwards `GUIDE_ENABLE`/`DISABLE` to `/guide` as well as motor; [`GuideEngine.reset()`](../backapp/guide_process.py) on those keys and on `track_enabled` falling
- wasp **Guide enable** gated by arm + Pico + lock + `ok` + `f_mm>0`; auto-disable if a gate drops
- ~1 Hz journal log: δ, f_mm, bin, cos_eff, e_arcsec, e_steps, Δω, ok

**Tests (laptop):** hub fan-out of `GUIDE_ENABLE` to motor+guide; `guideEnable.test.js` gate matrix.

**Pi indoor smoke (not a tracking PASS):** lock a lamp/LED; crop + `ok` without enable. If Pico linked: arm, enable, `systemctl kill astroscop-guide` → trims expire ~5 s.

**Night notes (deferred):** pulse ASC for arrows; mid-DEC / equator / high-DEC; crop vs full frame. Log δ, e_arcsec, Δω — do not file as a fake bench PASS.

**Not in this phase:** claiming on-sky success; sky simulator.

---

### Suggested implementation order (when we start)

Work **A → B → C** entirely on the laptop (plus B/C Pi benches once Pi access is written down). Then **D** (needs the camera) and **E** (needs the Pi for the worker bench, not the sky). **F** and **G** can proceed against a fake `guideInfo` if the hub contract from A/F is stable. **H** last.

If a phase is too large for one PR, split **inside** the phase (e.g. E: PID module + tests, then process + bench) but do not skip that phase’s Pi gate.

---

## 12. What we are explicitly not doing in v1

- Plate-solving / astrometry.net
- Multi-star / PHD2-style calibration dance (the locator `θ` + `cos δ` replaces most of that)
- PEC curve recording
- Autofocus / rotator
- Guiding from Bayer science frames (native **RGB** ROI is enough; science stays for Siril)
- A second process opening the HQ camera
- Per-DEC PID gain files
- Reusing or extending the existing burned-in `locator_*` glyph as the lock
- Running isolation or PID inside `cam_picamera2` or `motorControl`
- Centroiding the browser JPEG

---

## 13. Open items to settle on the first implementation PR

1. **Celestial δ source of truth** — typed DEC vs mount-count + park offset. Need one config key for the park; UI still confirms.
2. **DEC arcsec/step** — copy ASC’s 0.99″/step or measure with a DEC pulse.
3. **Pixel path camera → guide** — **decided (Phase D):** latest-wins `shared_memory` slot (`astroscop-guide-tile`), not a Queue. Queue cannot cross sibling systemd units.
4. **Hub vs localhost** — **decided (Phase F):** guide worker is a hub WS client on `/guide`. Control messages and sanitized `guideInfo` go through the hub; **tiles must not be base64 through wasp** (stripped + shm).
5. **Whether DEC gear train matches ASC** — if DEC `steps_per_degree` is wildly different, it only changes `DEC_arcsec_per_step`, not the PID structure.
6. **Sign of `DIR_INVERT_*` vs sky** — already flags in [`pico_motor.py`](../backapp/pico_motor.py); guide rotation must use the *on-sky* result after those flags.
7. **Default `guide_focal_mm`** — **18 mm** (this OTA); empty/zero still refuses to arm (plate scale undefined).
8. **Axis UI granularity** — 90° steps + flips vs continuous `θ`. Start with 90° + flips if the camera is square-on to the mount; add free `θ` if the first pulse test is clearly diagonal.
9. **Bench script host details** — filled: `ssh piscope`, remote `/home/fanf/astroScop/backapp`, user `fanf` (same as [`run_cam_settings_bench.ps1`](../backapp/scripts/run_cam_settings_bench.ps1)). Geom/isolate benches do not stop the camera; crop bench (Phase D) still must.

---

## 14. Pointers into the current tree

| Piece | Path | Role in this evolution |
|-------|------|------------------------|
| Sidereal feedforward | [`backapp/asc_rates.py`](../backapp/asc_rates.py) | `ω_ff_asc`; `ASC_STEPS_PER_DEGREE` → arcsec/step |
| Guide geometry | [`backapp/guide_geom.py`](../backapp/guide_geom.py) | plate scale, `cos δ`, pole gate, pixel ↔ step error |
| Guide ROI map | [`backapp/guide_roi.py`](../backapp/guide_roi.py) | full-sensor lock → capture-RGB tile (no out-of-crop clamp) |
| Guide isolation | [`backapp/guide_isolate.py`](../backapp/guide_isolate.py) | lock-window centroid + 3-frame EMA |
| Guide handoff | [`backapp/guide_handoff.py`](../backapp/guide_handoff.py) | lock-centered RGB copy + shm latest-wins |
| Guide PI | [`backapp/guide_pid.py`](../backapp/guide_pid.py) | PI trims on step-error (`Kd=0`) |
| Guide worker | [`backapp/guideControl.py`](../backapp/guideControl.py) | isolate + geom + PI; trims default off |
| Rate → Pico | [`backapp/pico_motor.py`](../backapp/pico_motor.py) | unchanged protocol; mixer sits above it |
| Motor worker | [`backapp/motorControl.py`](../backapp/motorControl.py) | mixer **only** (not PID) |
| Camera worker | [`backapp/cam_picamera2.py`](../backapp/cam_picamera2.py) | native RGB ROI copy; no isolation |
| Composition locator | [`backapp/cam_locator.py`](../backapp/cam_locator.py) | **unchanged**; preview JPEG mark only |
| Bayer offload pattern | [`backapp/cam_storage.py`](../backapp/cam_storage.py) | model for camera→other-process pixel handoff |
| Guide worker (new) | `backapp/guideControl.py` | isolation + geom + PI + crop JPEG + trims |
| Hub | [`backapp/rootserver.py`](../backapp/rootserver.py) | lock / sample / info / trim fan-out |
| Preview click | [`webapp/wasp/src/components/imgDisplay.vue`](../webapp/wasp/src/components/imgDisplay.vue) | tracking overlay + optional work-crop |
| Capture UI | [`webapp/wasp/src/components/captureOptions.vue`](../webapp/wasp/src/components/captureOptions.vue) | keep existing locator; add tracking panel *or* sibling |
| Manual rates | [`webapp/wasp/src/components/stepperControl.vue`](../webapp/wasp/src/components/stepperControl.vue) | feedforward + guide enable |
| Settings contract | [`backapp/docs/camera-settings-contract.md`](../backapp/docs/camera-settings-contract.md) | `track_*` + `guide_*` output fields |
| Sensor / exclusive access | [`backapp/docs/pi-hq-camera.md`](../backapp/docs/pi-hq-camera.md) | why the camera worker only *copies* the ROI |
| Camera bench pattern | [`backapp/scripts/run_cam_settings_bench.ps1`](../backapp/scripts/run_cam_settings_bench.ps1) | model for push-to-Pi guide benches |
| Guide benches (new, from phase B) | `test_guide_*_bench.py`, `scripts/run_guide_bench.ps1`, `docs/guide-bench-report.md` | Pi is the timing authority |
| Pico timing | [`firm/pico2w/README.md`](../firm/pico2w/README.md) | 100 ms rate ramp; sparse setpoints |
| Pi units | [`README.md`](../README.md) | add `astroscop-guide` when implemented |

---

## 15. One-sentence summary

Keep the empirical sidereal rate as feedforward; lock with a **new tracking locator** (ASC+/DEC+, DEC, focal length); crop a **small native RGB** around that lock; isolate the star in a **dedicated guide worker**; convert pixel drift to **arcseconds then motor steps** with `cos δ`; add small ASC/DEC rate trims — DEC included because polar alignment is only close.
