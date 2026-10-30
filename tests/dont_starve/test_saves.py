"""Native KLEI saves decode as literal data without executing Lua."""

import base64
import struct
import zlib

from gamecua.games.dont_starve.saves import decode
from gamecua.games.dont_starve.setup import OBSERVER_MOD, observer_mod


def packed(text):
    raw = text.encode()
    data = zlib.compress(raw)
    return b"KLEI     1D" + base64.b64encode(struct.pack("<4I", 1, 16, len(raw), len(data)) + data)


def test_decodes_native_literal_format_without_executing_lua():
    assert decode(
        packed(
            'return {name="Wilson", [2]={true, false, nil}, number=-1.25e2, '
            'escaped="a\\010b\\"", quoted=\'it\\\'s\'; ["k"]=3}'
        )
    ) == {
        "name": "Wilson",
        2: {1: True, 2: False, 3: None},
        "number": -125.0,
        "escaped": 'a\nb"',
        "quoted": "it's",
        "k": 3,
    }


def test_observer_mod_name_comes_from_the_prepared_save(tmp_path):
    assert observer_mod(tmp_path) == OBSERVER_MOD
    (tmp_path / "save").mkdir()
    (tmp_path / "save/saveindex").write_bytes(
        packed('return {slots={{mods={"gamescientist_observer"}}}}')
    )
    assert observer_mod(tmp_path) == "gamescientist_observer"
