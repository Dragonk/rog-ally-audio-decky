# Changelog

## 0.1.11

- Make KDE Desktop Mode fully automatic: no manual EasyEffects launch is required after switching from Gaming Mode.
- Add a persistent session handoff service that detects `plasmashell` and owns exactly one EasyEffects runtime at a time.
- Gaming Mode keeps the proven offscreen EasyEffects service; KDE runs a real Wayland EasyEffects service with a StatusNotifier tray icon.
- Automatically grant the Flatpak `org.kde.StatusNotifierWatcher` permission and enable the EasyEffects tray icon in KDE.
- Disable EasyEffects' own autostart to prevent duplicate instances.
- Import the live Plasma Wayland environment from `plasmashell` before starting the KDE EasyEffects process.
- Make the audio controller accept either the Gaming/headless or KDE/graphical EasyEffects owner.
- Remove the old manual GUI stop/start bridge and stale `gui-active` sentinel.
- Preserve automatic HDMI/USB/Bluetooth/jack bypass and native microphone routing.

## 0.1.10

- Fix KDE launcher visibility by using a unique `rog-ally-audio-easyeffects.desktop` ID instead of shadowing Flatpak's own desktop entry.
- Remove the obsolete user override created by 0.1.8/0.1.9 when it points at the plugin GUI wrapper.
- Treat `waiting-audio` as healthy while no playback stream exists.
- Add a live DSP watchdog: with built-in speakers and active playback, a missing/partial chain is automatically reloaded and streams are force-routed back through EasyEffects.
- Preserve native HDMI/USB/Bluetooth/headphone routing and native input selection.

## 0.1.9

- Fix KDE launcher visibility by refreshing the desktop database/KService cache after installing the EasyEffects GUI bridge.
- Keep the persistent headless DSP architecture while exposing a normal KDE EasyEffects launcher.
- Treat `waiting-audio` as a healthy final state when no playback streams exist; DSP nodes are stream-dependent.
- Preserve strict 5/5 DSP verification whenever audio is actually active.


## 0.1.8

- Fixed a Decky startup race where automatic bootstrap stopped healthy audio services after plugin_loader came up.
- Automatic bootstrap is now non-disruptive; controlled service restarts happen only during explicit repair/setup.
- Added GUI-session sentinel protection so Decky reloads do not collide with a normal EasyEffects window.
- Strengthened runtime readiness checks with live systemd state and fresh status timestamps.
- Added installer A/B DSP verification and post-Decky survival verification.

## 0.1.7

- Restored the proven SteamOS/Gamescope EasyEffects runtime: offscreen Qt, explicit user-session bus environment and `Restart=always`.
- Fixed the Flatpak wrapper exiting successfully after a few hundred milliseconds and leaving the DSP offline.
- Added a KDE GUI bridge: the headless runtime is paused only while the normal EasyEffects window is open and restored after the GUI exits.
- Preserves a Balanced/Cinema/Loud/Bypass choice made manually in the EasyEffects GUI before restarting the controller.
- Keeps physical output/input selection native and leaves microphone processing disabled.
- Runtime health now requires the persistent EasyEffects server, not merely a remembered preset name.

## 0.1.6

- Restore the proven EasyEffects stream-routing model on built-in speakers.
- Keep `Process all output streams` enabled for built-in speakers, including the empty Bypass preset.
- Disable automatic EasyEffects output routing only for HDMI, USB, Bluetooth and headphone outputs.
- Apply routing preference changes to both persistent dconf and the live EasyEffects instance.
- Keep input stream processing disabled.
- Fix Balanced/Bypass sounding identical after the dock-routing changes.

## 0.1.4 — 2026-09-08

- Disable EasyEffects `Process All Output Streams` and `Process All Input Streams` through the host dconf database instead of sandboxed `gsettings`.
- Verify both routing preferences are actually `false`; report a controller error if they are not.
- Prevent EasyEffects from immediately stealing a stream back after the controller routes Bypass directly to the physical speakers.
- Restore the large audible difference between Balanced/Cinema/Loud and true direct Bypass.

## 0.1.3 — 2026-09-08

- Respect manual Balanced/Cinema/Loud/Bypass changes made in the EasyEffects KDE GUI.
- Synchronize a manually selected EasyEffects factory preset back to the controller mode.
- Switch live playback between Easy Effects Sink and the physical speakers when KDE changes the preset.
- Stop the controller from periodically overwriting a valid manual preset choice.


## 0.1.2 — 2026-09-08

- Make Bypass a true direct routing bypass on built-in speakers.
- Move already-playing streams between the physical speaker sink and Easy Effects Sink when switching Bypass <-> Balanced/Cinema/Loud.
- Apply the same routing semantics to the A/B test.

## 0.1.1 — 2026-09-08

- Stop EasyEffects from hijacking all input/output streams.
- Explicitly route playback through EasyEffects only for the built-in speakers.
- Keep HDMI, USB, Bluetooth and 3.5 mm headphones on native PipeWire routing.
- Add output and input device switching directly to the Decky panel.
- Move already-running playback streams when the default output changes.
- Add a KDE desktop launcher wrapper so the EasyEffects GUI opens normally while the persistent Gaming Mode service is temporarily paused.
- Remove `QT_QPA_PLATFORM=offscreen` from the persistent EasyEffects unit.

## 0.1.0 — 2026-08-27

Initial public release.

### Added

- Decky QAM UI for Auto, Balanced, Cinema, Loud and Bypass.
- Persistent EasyEffects Flatpak service for Gaming Mode.
- User-scoped controller with retry/recovery logic.
- Hardware guard for ASUS ROG Xbox Ally X (RC73XA).
- Tuned Balanced, Cinema and Loud presets plus true empty-chain Bypass.
- Automatic Bypass for external HDMI/Bluetooth/USB output.
- Real-state DSP diagnostics and active-audio detection.
- Two-second A/B Bypass test.
- One-click EasyEffects installation/setup.
- Safe factory-preset ownership hashes and user-edit preservation.
- Explicit factory reset with backups.
- Migration from pre-release local `rog-ally-*` units.
- Unit, preset, controller and runtime resource tests.
- GitHub Actions CI, packaging and automatic version release workflow.
