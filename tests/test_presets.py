import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "presets"


def load(name: str):
    return json.loads((PRESETS / name).read_text(encoding="utf-8"))


def test_balanced_tuned_values_are_locked_in():
    data = load("ROG Xbox Ally X - Experimental Balanced.json")["output"]
    assert data["plugins_order"] == [
        "filter#0",
        "bass_enhancer#0",
        "multiband_compressor#0",
        "stereo_tools#0",
        "limiter#0",
    ]
    assert data["filter#0"]["frequency"] == 85.0
    assert data["bass_enhancer#0"]["amount"] == 8.0
    assert data["bass_enhancer#0"]["harmonics"] == 10.0
    assert data["bass_enhancer#0"]["scope"] == 190.0
    assert data["multiband_compressor#0"]["input-gain"] == -3.0
    assert data["stereo_tools#0"]["stereo-base"] == 0.4
    assert data["limiter#0"]["threshold"] == 0.0


def test_cinema_and_loud_keep_complete_chain():
    for filename in (
        "ROG Xbox Ally X - Experimental Cinema.json",
        "ROG Xbox Ally X - Experimental Loud.json",
    ):
        data = load(filename)["output"]
        assert data["plugins_order"] == [
            "filter#0",
            "bass_enhancer#0",
            "multiband_compressor#0",
            "stereo_tools#0",
            "limiter#0",
        ]


def test_profile_variants_have_expected_character():
    balanced = load("ROG Xbox Ally X - Experimental Balanced.json")["output"]
    cinema = load("ROG Xbox Ally X - Experimental Cinema.json")["output"]
    loud = load("ROG Xbox Ally X - Experimental Loud.json")["output"]

    assert cinema["bass_enhancer#0"]["amount"] > balanced["bass_enhancer#0"]["amount"]
    assert cinema["stereo_tools#0"]["stereo-base"] > balanced["stereo_tools#0"]["stereo-base"]
    assert loud["filter#0"]["frequency"] > balanced["filter#0"]["frequency"]
    assert loud["multiband_compressor#0"]["input-gain"] > balanced["multiband_compressor#0"]["input-gain"]


def test_bypass_is_really_empty():
    data = load("ROG Xbox Ally X - Bypass.json")["output"]
    assert data["plugins_order"] == []
    assert data["blocklist"] == []
