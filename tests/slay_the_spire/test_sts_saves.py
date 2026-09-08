"""Slay the Spire save codec."""

from pathlib import Path

from gamecua.games.slay_the_spire.saves import decode_autosave, encode_autosave

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "slay-the-spire" / "IRONCLAD.autosave"


def test_round_trip():
    state = {"seed": 123456789, "floor_num": 1, "cards": [{"id": "Strike_R", "upgrades": 0}]}
    assert decode_autosave(encode_autosave(state)) == state


def test_decode_real_fixture():
    save = decode_autosave(FIXTURE.read_bytes())
    assert save["seed"] == -4236424554807579186
    assert save["floor_num"] == 1
    assert save["act_num"] == 1
    assert save["post_combat"] is True
    assert save["current_health"] == 80
