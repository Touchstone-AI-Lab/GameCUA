"""Only complete observer lines from the private native log become evidence rows."""

import json

from gamecua.games.dont_starve.integration import Backend


def stream(tmp_path):
    instance = object.__new__(Backend)
    instance.profile = tmp_path
    instance.offset = 0
    return instance, tmp_path / "stdout.local.log"


def line(row):
    return (
        "[00:00:23]: ../mods/gamecua_observer/modmain.lua(48,1) GAMECUA_OBSERVER "
        + json.dumps(row)
        + "\t\n"
    )


def test_only_complete_observer_lines_enter_evidence(tmp_path):
    reader, path = stream(tmp_path)
    assert reader.read_rows() == []
    path.write_text("Private client output outside evidence\n" + line({"sequence": 1})[:-1])
    assert reader.read_rows() == []
    with path.open("a") as file:
        file.write("\n")
    assert reader.read_rows() == [{"sequence": 1}]
    assert reader.read_rows() == []
    with path.open("a") as file:
        file.write(line({"sequence": 2}) + "Ordinary output\n")
    assert reader.read_rows() == [{"sequence": 2}]
