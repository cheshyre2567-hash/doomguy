from doomguy_overlay_engine import DoomguyFaceEngine


def test_health_bucket_mapping():
    eng = DoomguyFaceEngine()
    assert eng.health_to_bucket(100) == 0
    assert eng.health_to_bucket(80) == 0
    assert eng.health_to_bucket(79) == 1
    assert eng.health_to_bucket(60) == 1
    assert eng.health_to_bucket(59) == 2
    assert eng.health_to_bucket(40) == 2
    assert eng.health_to_bucket(39) == 3
    assert eng.health_to_bucket(20) == 3
    assert eng.health_to_bucket(19) == 4
    assert eng.health_to_bucket(1) == 4


def test_look_sequence_center_left_center_right():
    eng = DoomguyFaceEngine()
    looks = [eng.update(100).look for _ in range(8)]
    assert looks == [
        "center",
        "left",
        "center",
        "right",
        "center",
        "left",
        "center",
        "right",
    ]


def test_pain_frame_uses_current_look_direction():
    eng = DoomguyFaceEngine()

    # First frame is center.
    eng.update(100)
    # Health drops on second tick (left look), so pain should be left.
    st = eng.update(95)
    assert st.is_pain is True
    assert st.frame_name == "STFPAIN0"


def test_dead_frame_at_zero_health():
    eng = DoomguyFaceEngine()
    st = eng.update(0)
    assert st.frame_name == "STFDEAD0"
    assert st.is_pain is False
