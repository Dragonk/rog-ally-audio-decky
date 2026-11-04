import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("controller", ROOT / "runtime/controller.py")
assert SPEC and SPEC.loader
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


def test_desired_for_internal_and_external():
    internal = "alsa_loopback_device.alsa_output.pci-0000_64_00.6.analog-stereo"
    mode, preset, is_internal = controller.desired_for("auto", internal)
    assert (mode, is_internal) == ("balanced", True)
    assert preset == controller.PROFILES["balanced"]

    mode, preset, is_internal = controller.desired_for("cinema", "bluez_output.foo")
    assert (mode, is_internal) == ("bypass", False)
    assert preset == controller.PROFILES["bypass"]


def full_graph():
    return "\n".join(controller.DSP_TOKENS.values())


def test_dsp_chain_present():
    desired = controller.PROFILES["balanced"]
    status, present, expected = controller.dsp_snapshot(
        desired, desired, True, streams=1, graph=full_graph()
    )
    assert (status, present, expected) == ("chain-present", 5, 5)


def test_active_audio_without_nodes_is_not_ok():
    desired = controller.PROFILES["balanced"]
    status, present, expected = controller.dsp_snapshot(
        desired, desired, True, streams=1, graph=""
    )
    assert status == "chain-missing"
    assert (present, expected) == (0, 5)


def test_bypass_requires_actual_bypass_confirmation():
    bypass = controller.PROFILES["bypass"]
    balanced = controller.PROFILES["balanced"]

    status, _, _ = controller.dsp_snapshot(
        bypass, balanced, True, streams=0, graph=""
    )
    assert status == "bypass-mismatch"

    status, present, expected = controller.dsp_snapshot(
        bypass, bypass, True, streams=0, graph=""
    )
    assert (status, present, expected) == ("bypass-confirmed", 0, 0)


def test_headphone_port_on_internal_codec_forces_bypass():
    internal = "alsa_loopback_device.alsa_output.pci-0000_64_00.6.analog-stereo"
    mode, preset, is_internal = controller.desired_for(
        "loud", internal, "analog-output-headphones"
    )
    assert (mode, is_internal) == ("bypass", False)
    assert preset == controller.PROFILES["bypass"]


def test_parse_sink_inputs_and_skip_easyeffects_stream():
    sample = '''Sink Input #10
\tSink: 52
\tProperties:
\t\tapplication.name = "Firefox"
\t\tapplication.id = "org.mozilla.firefox"
Sink Input #11
\tSink: 52
\tProperties:
\t\tapplication.name = "Easy Effects"
\t\tapplication.id = "com.github.wwmm.easyeffects"
'''
    streams = controller.parse_sink_inputs(sample)
    assert len(streams) == 2
    assert streams[0]["index"] == "10"
    assert not controller.is_easyeffects_stream(streams[0])
    assert controller.is_easyeffects_stream(streams[1])


def test_internal_bypass_keeps_known_good_easyeffects_transport():
    balanced = controller.PROFILES["balanced"]
    bypass = controller.PROFILES["bypass"]
    assert controller.should_use_easyeffects(True, balanced) is True
    assert controller.should_use_easyeffects(True, bypass) is True
    assert controller.should_use_easyeffects(False, balanced) is False


def test_route_streams_switches_target_between_easyeffects_and_physical(monkeypatch):
    sinks = [
        {"id": "10", "name": "EasyEffectsSink", "description": "Easy Effects Sink", "state": "RUNNING", "active_port": ""},
        {"id": "20", "name": "physical", "description": "Speakers", "state": "RUNNING", "active_port": "analog-output-speaker"},
    ]
    stream_text = 'Sink Input #7\n\tSink: 10\n\tProperties:\n\t\tapplication.name = "Firefox"\n'
    monkeypatch.setattr(controller, "pactl_value", lambda cmd: stream_text)
    moves = []
    monkeypatch.setattr(controller, "move_sink_input", lambda index, target: moves.append((index, target)) or True)
    controller.route_streams("physical", False, sinks, force_all=True, seen_streams=set())
    assert moves[-1] == ("7", "physical")

    stream_text2 = 'Sink Input #7\n\tSink: 20\n\tProperties:\n\t\tapplication.name = "Firefox"\n'
    monkeypatch.setattr(controller, "pactl_value", lambda cmd: stream_text2)
    controller.route_streams("physical", True, sinks, force_all=True, seen_streams=set())
    assert moves[-1] == ("7", "EasyEffectsSink")


def test_manual_kde_preset_override_maps_known_profiles_only():
    balanced = controller.PROFILES["balanced"]
    bypass = controller.PROFILES["bypass"]
    assert controller.manual_mode_override(
        bypass, balanced, internal=True
    ) == "bypass"
    assert controller.manual_mode_override(
        balanced, bypass, internal=True
    ) == "balanced"
    assert controller.manual_mode_override(
        bypass, balanced, internal=False
    ) == ""
    assert controller.manual_mode_override(
        "Some custom preset", balanced, internal=True
    ) == ""


def test_manual_same_profile_does_not_override_mode():
    balanced = controller.PROFILES["balanced"]
    assert controller.manual_mode_override(
        balanced, balanced, internal=True
    ) == ""


def test_configure_preferences_uses_host_dconf_and_verifies_false(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, timeout=4):
        calls.append(cmd)
        if cmd[1] == "read":
            return Result(stdout="false\n")
        return Result()

    monkeypatch.setattr(controller, "run", fake_run)
    monkeypatch.setattr(controller, "ensure_service", lambda: False)
    assert controller.configure_easyeffects_preferences(False) == ""
    assert [cmd[:3] for cmd in calls] == [
        ["/usr/bin/dconf", "write", "/com/github/wwmm/easyeffects/process-all-outputs"],
        ["/usr/bin/dconf", "read", "/com/github/wwmm/easyeffects/process-all-outputs"],
        ["/usr/bin/dconf", "write", "/com/github/wwmm/easyeffects/process-all-inputs"],
        ["/usr/bin/dconf", "read", "/com/github/wwmm/easyeffects/process-all-inputs"],
    ]
    assert calls[0][-1] == "false"
    assert calls[2][-1] == "false"


def test_configure_preferences_reports_when_dconf_did_not_change_value(monkeypatch):
    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, timeout=4):
        if cmd[1] == "read":
            return Result(stdout="true\n")
        return Result()

    monkeypatch.setattr(controller, "run", fake_run)
    monkeypatch.setattr(controller, "ensure_service", lambda: False)
    error = controller.configure_easyeffects_preferences(False)
    assert "process-all-outputs" in error
    assert "process-all-inputs" in error


def test_configure_preferences_can_enable_output_processing(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, timeout=4):
        calls.append(cmd)
        if cmd[:3] == ["/usr/bin/dconf", "read", "/com/github/wwmm/easyeffects/process-all-outputs"]:
            return Result(stdout="true\n")
        if cmd[:3] == ["/usr/bin/dconf", "read", "/com/github/wwmm/easyeffects/process-all-inputs"]:
            return Result(stdout="false\n")
        return Result()

    monkeypatch.setattr(controller, "run", fake_run)
    monkeypatch.setattr(controller, "ensure_service", lambda: False)
    assert controller.configure_easyeffects_preferences(True) == ""
    writes = [cmd for cmd in calls if cmd[:2] == ["/usr/bin/dconf", "write"]]
    assert writes[0][-1] == "true"
    assert writes[1][-1] == "false"

def test_builtin_profiles_use_easyeffects_transport():
    assert controller.should_use_easyeffects(True, controller.PROFILES["balanced"]) is True
    assert controller.should_use_easyeffects(True, controller.PROFILES["bypass"]) is True


def test_external_output_bypasses_easyeffects_transport():
    assert controller.should_use_easyeffects(False, controller.PROFILES["bypass"]) is False


def test_live_chain_missing_requires_self_heal_but_idle_does_not():
    balanced = controller.PROFILES["balanced"]
    assert controller.dsp_requires_self_heal(True, balanced, 1, "chain-missing") is True
    assert controller.dsp_requires_self_heal(True, balanced, 0, "waiting-audio") is False
    assert controller.dsp_requires_self_heal(False, balanced, 1, "chain-missing") is False


def test_live_bypass_mismatch_requires_self_heal():
    bypass = controller.PROFILES["bypass"]
    assert controller.dsp_requires_self_heal(True, bypass, 1, "bypass-mismatch") is True
    assert controller.dsp_requires_self_heal(True, bypass, 1, "bypass-confirmed") is False
