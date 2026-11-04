from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def test_backend_exposes_audio_device_api():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "async def list_audio_devices" in source
    assert "async def set_output_device" in source
    assert "async def set_input_device" in source


def test_frontend_exposes_audio_device_controls():
    source = (ROOT / "src/index.tsx").read_text(encoding="utf-8")
    assert 'callable<[], AudioDevices>("list_audio_devices")' in source
    assert 'callable<[name: string], PluginState>("set_output_device")' in source
    assert 'callable<[name: string], PluginState>("set_input_device")' in source


def _plugin_class():
    sys.modules.setdefault("decky", types.SimpleNamespace(logger=types.SimpleNamespace()))
    from main import Plugin
    return Plugin


def test_request_requires_live_dsp_not_only_preset_name():
    Plugin = _plugin_class()

    base = {
        "controller_ok": True,
        "easyeffects_ok": True,
        "easyeffects_server_ok": True,
        "easyeffects_service_active": True,
        "audio_streams": 1,
        "dsp_effects_expected": 5,
        "dsp_effects_present": 5,
        "dsp_status": "chain-present",
    }
    assert Plugin._request_is_audibly_ready(base)

    offline = dict(base, easyeffects_server_ok=False, dsp_status="ee-offline")
    assert not Plugin._request_is_audibly_ready(offline)

    missing = dict(base, dsp_effects_present=0, dsp_status="chain-missing")
    assert not Plugin._request_is_audibly_ready(missing)


def test_request_accepts_confirmed_bypass_and_idle_waiting_audio():
    Plugin = _plugin_class()

    bypass = {
        "controller_ok": True,
        "easyeffects_ok": True,
        "easyeffects_server_ok": True,
        "easyeffects_service_active": True,
        "audio_streams": 1,
        "dsp_effects_expected": 0,
        "dsp_effects_present": 0,
        "dsp_status": "bypass-confirmed",
    }
    assert Plugin._request_is_audibly_ready(bypass)

    idle = dict(
        bypass,
        audio_streams=0,
        dsp_effects_expected=5,
        dsp_effects_present=0,
        dsp_status="waiting-audio",
    )
    assert Plugin._request_is_audibly_ready(idle)
