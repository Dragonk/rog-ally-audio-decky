from backend.rog_ally_audio.audio_devices import parse_devices


SINKS = '''Sink #51
\tState: RUNNING
\tName: easyeffects_sink
\tDescription: Easy Effects Sink
\tActive Port: null
Sink #52
\tState: IDLE
\tName: alsa_output.pci-0000_64_00.6.analog-stereo
\tDescription: Ryzen HD Audio Controller Analog Stereo
\tActive Port: analog-output-speaker
Sink #53
\tState: SUSPENDED
\tName: alsa_output.usb-Lenovo_ThinkPad_Dock-00.analog-stereo
\tDescription: ThinkPad USB-C Dock Gen2 USB Audio Analogowe stereo
\tActive Port: analog-output
'''

SOURCES = '''Source #61
\tState: IDLE
\tName: easyeffects_source
\tDescription: Easy Effects Source
Source #62
\tState: IDLE
\tName: alsa_input.pci-0000_64_00.6.analog-stereo
\tDescription: Ryzen HD Audio Controller Analog Stereo
\tActive Port: analog-input-internal-mic
Source #63
\tState: IDLE
\tName: alsa_output.pci-0000_64_00.6.analog-stereo.monitor
\tDescription: Monitor of Ryzen HD Audio
'''


def test_sink_parser_filters_easyeffects_and_marks_default():
    devices = parse_devices(SINKS, "sink", "alsa_output.pci-0000_64_00.6.analog-stereo")
    assert [d.name for d in devices] == [
        "alsa_output.pci-0000_64_00.6.analog-stereo",
        "alsa_output.usb-Lenovo_ThinkPad_Dock-00.analog-stereo",
    ]
    assert devices[0].default
    assert devices[0].active_port == "analog-output-speaker"


def test_source_parser_filters_easyeffects_and_monitors():
    devices = parse_devices(SOURCES, "source", "alsa_input.pci-0000_64_00.6.analog-stereo")
    assert len(devices) == 1
    assert devices[0].description.startswith("Ryzen HD")
    assert devices[0].default
