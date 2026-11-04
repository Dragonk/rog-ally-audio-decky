# ROG Ally Audio 0.1.11

This release removes the last manual Desktop Mode workaround. ROG Ally Audio now automatically switches the EasyEffects runtime when SteamOS moves between Gaming Mode and KDE Plasma.

- In Gaming Mode, EasyEffects runs using the proven offscreen/headless service.
- In KDE, the plugin automatically hands EasyEffects over to a real Wayland process and enables its system-tray icon.
- Returning to Gaming Mode automatically restores the headless process.
- The controller survives the handoff and continues applying Balanced/Cinema/Loud/Bypass.
- The Flatpak tray permission is configured automatically; no terminal command or manual launch is required.
- EasyEffects' own autostart is disabled so there is only one owner at a time.

Target hardware remains ASUS ROG Xbox Ally X RC73XA.
