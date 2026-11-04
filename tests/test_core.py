from backend.rog_ally_audio.constants import PROFILE_NAMES
from backend.rog_ally_audio.core import (
    classify_sink,
    desired_profile_for,
    effective_mode_for,
    evaluate_device,
    is_internal_sink,
    normalize_mode,
    short_profile_name,
)


def test_normalize_mode():
    assert normalize_mode("LOUD") == "loud"
    assert normalize_mode(" nonsense ") == "auto"
    assert normalize_mode(None) == "auto"


def test_internal_sink_with_steamos_loopback_prefix():
    sink = "alsa_loopback_device.alsa_output.pci-0000_64_00.6.analog-stereo"
    assert is_internal_sink(sink)
    assert classify_sink(sink) == "internal"


def test_external_outputs_force_bypass():
    assert effective_mode_for("loud", "alsa_output.pci.hdmi-stereo") == "bypass"
    assert effective_mode_for("cinema", "bluez_output.foo") == "bypass"
    assert desired_profile_for("loud", "alsa_output.pci.hdmi-stereo") == PROFILE_NAMES["bypass"]


def test_auto_internal_is_balanced():
    sink = "alsa_output.pci-0000_64_00.6.analog-stereo"
    assert effective_mode_for("auto", sink) == "balanced"
    assert desired_profile_for("auto", sink) == PROFILE_NAMES["balanced"]


def test_profile_short_names():
    for mode, name in PROFILE_NAMES.items():
        assert short_profile_name(name).lower() == mode


def test_rc73xa_is_supported():
    info = evaluate_device("ROG Xbox Ally X RC73XA", audio_subsystem="0x10431384")
    assert info.supported
    assert "RC73XA" in info.support_reason


def test_other_ally_is_not_supported():
    info = evaluate_device("ROG Ally X RC72LA", audio_subsystem="0x10431384")
    assert not info.supported
