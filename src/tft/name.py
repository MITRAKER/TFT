"""The game's display name, kept in one place.

Every banner, page title and file header reads it from here, so renaming the
game is a change to this one line (and to ``src/tft/web/index.html``, which a
test keeps in step).
"""

from __future__ import annotations

GAME_NAME = "Team Fight Tackticktics"
"""The name shown to players."""
