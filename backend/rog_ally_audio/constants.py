from __future__ import annotations

PLUGIN_VERSION = "0.1.11"
APP_ID = "com.github.wwmm.easyeffects"

MODES = ("auto", "balanced", "cinema", "loud", "bypass")

PROFILE_NAMES = {
    "balanced": "ROG Xbox Ally X - Experimental Balanced",
    "cinema": "ROG Xbox Ally X - Experimental Cinema",
    "loud": "ROG Xbox Ally X - Experimental Loud",
    "bypass": "ROG Xbox Ally X - Bypass",
}

PROFILE_FILENAMES = {
    key: f"{value}.json" for key, value in PROFILE_NAMES.items()
}

CONFIG_DIRNAME = "rog-ally-audio"
DATA_DIRNAME = "decky-rog-ally-audio"

EE_SERVICE = "decky-rog-ally-audio-easyeffects.service"
KDE_EE_SERVICE = "decky-rog-ally-audio-easyeffects-kde.service"
SESSION_SERVICE = "decky-rog-ally-audio-session.service"
CONTROLLER_SERVICE = "decky-rog-ally-audio-controller.service"

LEGACY_EE_SERVICE = "rog-ally-easyeffects.service"
LEGACY_CONTROLLER_SERVICE = "rog-ally-audio-controller.service"
LEGACY_CONFIG_DIRNAME = "rog-ally-audio-controller"

# This is stable on the tested RC73XA SteamOS audio topology. SteamOS may
# wrap the physical sink in an alsa_loopback_device prefix; substring matching
# intentionally handles both forms.
INTERNAL_SINK_TOKEN = "pci-0000_64_00.6.analog-stereo"

SUPPORTED_MODEL_PATTERNS = (
    "RC73XA",
    "ROG XBOX ALLY X",
)

EXPECTED_AUDIO_SUBSYSTEM = "0x10431384"
