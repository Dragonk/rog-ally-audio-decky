# ROG Ally Audio for Decky Loader

[![CI](https://github.com/Dragonk/ROGAllyAudio/actions/workflows/ci.yml/badge.svg)](https://github.com/Dragonk/ROGAllyAudio/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Dragonk/ROGAllyAudio)](https://github.com/Dragonk/ROGAllyAudio/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Decky Loader plugin that gives the **ASUS ROG Xbox Ally X (RC73XA)** a persistent EasyEffects speaker-processing chain in SteamOS, with quick profile switching directly from the Quick Access Menu.

> [!IMPORTANT]
> v0.1 is intentionally limited to **ROG Xbox Ally X / RC73XA**. The presets were tuned and real-device tested for this model. They are not ASUS/Dolby OEM profiles and should not be treated as suitable for other handhelds.

## Automatic KDE / Gaming Mode integration

ROG Ally Audio owns the EasyEffects lifecycle. No manual EasyEffects startup is required when switching SteamOS modes.

- **Gaming Mode:** the proven offscreen EasyEffects service stays persistent for DSP.
- **KDE Desktop Mode:** a session manager detects Plasma, starts EasyEffects as a real Wayland application in service mode, and enables its system-tray icon automatically.
- **Back to Gaming Mode:** the KDE instance is stopped and the headless instance is restored automatically.
- EasyEffects' own autostart is kept disabled to avoid two competing Flatpak instances.
- HDMI, USB, Bluetooth and the 3.5 mm jack remain direct/bypassed; microphone routing remains native.

## Why this exists

On the tested RC73XA, EasyEffects can significantly improve the built-in speakers, but a normal desktop-launched instance is not reliable enough across KDE and SteamOS Gaming Mode. This plugin installs a user-scoped persistent EasyEffects service plus a small controller, so the processing remains active after session changes and reboots.

## Features

- **Auto** — built-in speakers use Balanced; HDMI/Bluetooth/USB automatically use Bypass.
- **Balanced** — general-purpose tuned profile.
- **Cinema** — fuller psychoacoustic bass and a wider stage.
- **Loud** — more perceived loudness with extra low-frequency headroom.
- **Bypass** — empty EasyEffects output chain.
- Persistent EasyEffects `--hide-window --service-mode` user service.
- Automatic recovery if EasyEffects is not ready during boot/session startup.
- Quick profile switching from Decky without opening KDE.
- Real-state diagnostics: requested profile, actual EasyEffects profile, DSP node count, output device and active audio streams.
- A/B test: temporarily switches to Bypass for 2 seconds and restores the selected profile.
- Protects user-edited presets during normal upgrades.
- One-click factory preset reset with backup.
- Migration from the earlier local `rog-ally-*` service layout.
- No kernel patches, no TAS2781 firmware changes and no modifications to the SteamOS read-only root.

## Supported hardware

| Device | Support |
| --- | --- |
| ASUS ROG Xbox Ally X (RC73XA) | ✅ v0.1 target / real-device tested |
| ASUS ROG Ally X (RC72LA) | ❌ not supported by these presets |
| ASUS ROG Ally | ❌ not supported by these presets |
| Steam Deck / other handhelds | ❌ not supported by these presets |

The plugin checks DMI model identifiers before enabling the runtime. The detected ALC294 subsystem `1043:1384` is reported diagnostically but does not broaden the supported-device list.

## Installation

### One-command installer (auto KDE tray + Gaming Mode) — recommended

The installer script does everything the plugin needs and then verifies the whole chain end-to-end. It works on SteamOS in both KDE Desktop Mode and Gaming Mode and switches the EasyEffects lifecycle between them automatically afterwards.

Prerequisites:

- ASUS ROG Xbox Ally X (RC73XA) running SteamOS.
- Decky Loader installed (the script stops and restarts its `plugin_loader` service).
- Network access if EasyEffects is not installed yet — the script installs the Flatpak from Flathub automatically.
- EasyEffects Flatpak — installed by the script when missing (no manual setup needed):

  ```bash
  # only if you prefer to pre-install it yourself
  flatpak install -y flathub com.github.wwmm.easyeffects
  ```

Run it from **KDE Desktop Mode** in Konsole (Gaming Mode has no terminal; SSH as `deck` works too). Do **not** run it with `sudo`:

```bash
cd ~
curl -LO https://github.com/Dragonk/ROGAllyAudio/releases/latest/download/install-ROG-Ally-Audio-0.1.11-auto-kde-tray.sh
chmod +x install-ROG-Ally-Audio-0.1.11-auto-kde-tray.sh
./install-ROG-Ally-Audio-0.1.11-auto-kde-tray.sh
```

The script asks for the sudo password once (Decky restart) and performs nine verified steps:

1. **Backup** — existing plugin, runtime data, config and user systemd units are copied to a timestamped backup directory.
2. **Verify plugin** — the embedded plugin ZIP is checked against a hard-coded SHA-256, the Python runtime is compiled and the shell script syntax-checked before anything is installed.
3. **Install the plugin** — the plugin is placed in `/home/deck/homebrew/plugins/ROGAllyAudio` (Decky is stopped first and is always restarted again, even if the script aborts).
4. **Bootstrap the runtime** — if EasyEffects is missing it is installed from Flathub first; then presets, configuration and all four `decky-rog-ally-audio-*` user systemd units are set up through the plugin's own `RuntimeManager`.
5. **Restart Decky.**
6. **Session handoff** — the script detects the current session (Plasma vs Gaming Mode) and waits up to 60 s until the session manager reports `phase=ready` with the correct EasyEffects instance (KDE Wayland app in Desktop Mode, headless service in Gaming Mode).
7. **DSP verification** — controller state, EasyEffects server, active streams and the expected DSP chain (or confirmed Bypass) are checked against `status.json`.
8. **KDE tray verification** — in Desktop Mode it confirms the Flatpak override for `org.kde.StatusNotifierWatcher` and that EasyEffects actually registered a tray item with Plasma (queried per item, not by counting icons).
9. **Survival test** — all services are re-checked after Decky has fully started.

On any failure the script prints a complete diagnostic dump: systemd status of every unit, `session.json`/`status.json`, EasyEffects dconf settings, Flatpak overrides and the tray watcher state. After it finishes with `GOTOWE`, switching between Desktop Mode and Gaming Mode (and rebooting) requires no manual action — never start EasyEffects yourself.

Upgrading to a newer version: re-run the matching installer script; it refreshes the plugin and runtime in the same way and keeps a new backup.

### Manual install from the GitHub release

If you prefer to install only the plugin and let its own **Install EasyEffects and configure** button do the runtime setup:

1. Install Decky Loader.
2. In Decky settings, enable **Developer Mode**.
3. Open **Developer → Install Plugin from URL** and use the latest-release asset:
   `https://github.com/Dragonk/ROGAllyAudio/releases/latest/download/ROGAllyAudio.zip`
   (or download the versioned ZIP and use **Install Plugin from ZIP**).
4. Open **ROG Ally Audio** in Quick Access.
5. If EasyEffects is missing, choose **Install EasyEffects and configure**.

If EasyEffects is already installed, setup is automatic. The manual path installs the same systemd units; the KDE tray/Gaming Mode handoff works identically after the in-plugin setup.

### What setup changes

The plugin creates only user-owned files:

- `~/.config/rog-ally-audio/`
- `~/.local/share/decky-rog-ally-audio/`
- `~/.config/systemd/user/decky-rog-ally-audio-easyeffects.service`
- `~/.config/systemd/user/decky-rog-ally-audio-easyeffects-kde.service`
- `~/.config/systemd/user/decky-rog-ally-audio-session.service`
- `~/.config/systemd/user/decky-rog-ally-audio-controller.service`
- EasyEffects output presets under its Flatpak user data directory.

It does **not** change the kernel, ALSA configuration, TAS2781 firmware/calibration, PipeWire system files, or SteamOS root filesystem.

## Presets

### Balanced

The baseline profile used by Auto on built-in speakers:

- high-pass filter: **85 Hz**
- Bass Enhancer: **8 dB**, harmonics **10**, scope **190 Hz**
- 4-band multiband compressor, input **-3 dB**
- Stereo Base: **0.40**
- limiter: threshold **0 dB**, lookahead **4 ms**, attack **2 ms**, release **8 ms**, Half x4/24-bit oversampling

### Cinema

Derived from Balanced with targeted changes only:

- Bass Enhancer amount **10 dB**, scope **200 Hz**
- multiband input **-2.5 dB**
- make-up: **4.5 / 4.0 / 5.0 / 4.5 dB**
- Stereo Base **0.45**

### Loud

Designed for higher perceived loudness without simply adding unrestricted output gain:

- high-pass filter **95 Hz**
- Bass Enhancer **8 dB**, scope **180 Hz**
- multiband input **-1.5 dB**
- make-up: **4.5 / 4.5 / 5.5 / 5.0 dB**
- Stereo Base **0.30**

### Bypass

An empty EasyEffects output chain. The controller requires EasyEffects itself to confirm that the Bypass preset is loaded; absence of DSP nodes alone is **not** treated as proof of Bypass.

## Preset upgrade safety

The plugin stores SHA-256 hashes of factory-managed presets.

- Missing factory presets are installed.
- An unchanged factory preset may be upgraded by a future plugin release.
- An unrecognized or user-modified preset is preserved.
- **Restore factory presets** is explicit and creates a backup before overwriting.

## Architecture

```text
Decky QAM
   │
   │ request.json + mode
   ▼
systemd --user controller
   │
   │ clean environment
   ▼
flatpak enter com.github.wwmm.easyeffects
   │
   ▼
/tmp/EasyEffectsServer
   │
   ├─ load_preset
   └─ get_last_loaded_preset

Persistent EasyEffects service
   └─ flatpak run ... --hide-window --service-mode
```

Decky's Python process never enters the EasyEffects sandbox directly. That separation is deliberate: it avoids Decky/PyInstaller library-environment conflicts and keeps audio ownership in the normal user systemd context.

## Diagnostics

The normal panel shows the useful state only. Advanced diagnostics include:

- persistent EasyEffects service state
- controller service state
- actual EasyEffects preset
- requested/applied request IDs
- default PipeWire sink
- active sink-input count
- expected/present DSP nodes
- last controller error

A non-Bypass profile with active audio and `0/5` DSP nodes is reported as a warning instead of being mistaken for a successful Bypass.

## Uninstall behavior

Uninstalling the plugin disables and removes its two namespaced systemd units and runtime controller. It deliberately leaves these user data items in place:

- EasyEffects itself
- audio presets
- selected mode/configuration
- backups

This avoids destructive uninstall surprises.

## Development

Requirements:

- Node.js 22
- pnpm 9
- Python 3.11+

```bash
pnpm install
pnpm typecheck
pnpm build
python -m pip install pytest
pytest -q
python scripts/package.py
```

The release ZIP is written to `build/`.

## CI and releases

- `CI` runs Python lint/compile/tests, TypeScript type checking, frontend build and release packaging.
- `Release` reruns the checks on `main`, creates `v<package.json version>` if it does not already exist, and publishes the Decky ZIP as a GitHub Release asset.
- Release creation is idempotent: pushing more commits with the same package version does not replace an existing release.

## Tested environment

Initial v0.1 development was real-device tested on:

- ASUS ROG Xbox Ally X (RC73XA)
- SteamOS 3.8.x
- ALC294 / ASUS subsystem 1043:1384
- TAS2781 smart amplifiers bound by the kernel driver
- PipeWire 1.6.x
- EasyEffects 8.2.x Flatpak

## Disclaimer

This is an independent community project. It is not affiliated with, endorsed by, or supported by ASUS, Republic of Gamers, Dolby, Valve, or the EasyEffects project. Product and company names are used only to identify compatible hardware/software.

## License

MIT — see [LICENSE](LICENSE).
