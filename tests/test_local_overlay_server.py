from examples.local_overlay_server import extract_health_percent, extract_hud_anchor_visible


def test_extract_health_percent_prefers_explicit_health_percent():
    assert extract_health_percent({"health_percent": 73}) == 73


def test_extract_health_percent_supports_health_alias():
    assert extract_health_percent({"health": 42}) == 42


def test_extract_health_percent_supports_nested_state_sample_and_clamps():
    assert extract_health_percent({"state": {"health_percent": "12"}}) == 12
    assert extract_health_percent({"sample": {"health_percent": 150}}) == 100


def test_extract_health_percent_defaults_to_100_for_invalid_payload():
    assert extract_health_percent({"health_percent": "bad"}) == 100
    assert extract_health_percent({}) == 100


def test_extract_hud_anchor_visible_prefers_top_level_bool():
    assert extract_hud_anchor_visible({"hud_anchor_visible": False}) is False
    assert extract_hud_anchor_visible({"hud_anchor_visible": True}) is True


def test_extract_hud_anchor_visible_supports_nested_and_string_values():
    assert extract_hud_anchor_visible({"state": {"hud_anchor_visible": "false"}}) is False
    assert extract_hud_anchor_visible({"sample": {"hud_anchor_visible": "yes"}}) is True


def test_extract_hud_anchor_visible_defaults_true_for_missing_or_invalid():
    assert extract_hud_anchor_visible({}) is True
    assert extract_hud_anchor_visible({"hud_anchor_visible": "maybe"}) is True
