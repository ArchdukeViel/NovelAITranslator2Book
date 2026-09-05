from novelai.db.advisory_lock import string_to_advisory_lock_id


def test_string_to_advisory_lock_id_deterministic() -> None:
    id1 = string_to_advisory_lock_id("novel:backup:123")
    id2 = string_to_advisory_lock_id("novel:backup:123")
    assert id1 == id2
    assert isinstance(id1, int)
    # Check fits in signed 64-bit int
    assert -(2**63) <= id1 < 2**63
