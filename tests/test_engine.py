from doomguy_overlay_engine import DoomguyFaceEngine


def test_health_bucket_mapping():
    eng = DoomguyFaceEngine()
    assert eng.health_to_bucket(100) == 0
    assert eng.health_to_bucket(80) == 1
    assert eng.health_to_bucket(79) == 2
    assert eng.health_to_bucket(60) == 2
    assert eng.health_to_bucket(59) == 2
    assert eng.health_to_bucket(40) == 3
    assert eng.health_to_bucket(39) == 3
    assert eng.health_to_bucket(20) == 4
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


def test_pain_frame_uses_health_bucket_not_look_direction():
    eng = DoomguyFaceEngine()

    # First frame is center.
    eng.update(100)
    # Health drops by 25 on second tick; pain should use the current health bucket.
    st = eng.update(75)
    assert st.is_pain is True
    assert st.frame_name == "STFOUCH2"


def test_pain_frame_uses_low_health_bucket():
    eng = DoomguyFaceEngine()

    st = eng.update(10)
    assert st.is_pain is True
    assert st.frame_name == "STFOUCH4"


def test_small_damage_does_not_trigger_ouch():
    eng = DoomguyFaceEngine()

    eng.update(100)
    st = eng.update(90)
    assert st.is_pain is False
    assert st.frame_name == "STFST00"


def test_healing_does_not_trigger_ouch():
    eng = DoomguyFaceEngine()

    eng.update(80)
    st = eng.update(100)
    assert st.is_pain is False
    assert st.frame_name == "STFST00"


def test_dead_frame_at_zero_health():
    eng = DoomguyFaceEngine()
    st = eng.update(0)
    assert st.frame_name == "STFDEAD0"
    assert st.is_pain is False
