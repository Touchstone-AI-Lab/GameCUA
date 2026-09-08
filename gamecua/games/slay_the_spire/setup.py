"""Native log projection and installation paths for Slay the Spire."""

import re
from pathlib import Path

ENCOUNTER = re.compile(r"AbstractDungeon> MONSTER: (.+?)\s*$", re.M)
PRIVATE = re.compile(
    rb"steam[./]|Steam API|SteamAPI|Steamworks|SteamInternal|Steam ID|steamclient|DistributorPlatform=steam|"
    rb"ACCOUNT ID|SteamGameId|SteamAppId|userdata|\b(?:token|password)\b|https://s\.team/q/",
    re.I,
)


def public_log(raw):
    """Drop Steam account and authentication lines from a native log."""
    return b"".join(line for line in raw.splitlines(keepends=True) if not PRIVATE.search(line))


def default_game_dir():
    return Path.home() / ".local/share/Steam/steamapps/common/SlayTheSpire"
