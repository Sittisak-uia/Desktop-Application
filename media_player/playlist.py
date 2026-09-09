"""Playlist model for Media Player PRO.

Pure business logic only - no GUI/PyQt dependency. This keeps the model
unit-testable in isolation.
"""

from __future__ import annotations

from typing import List, Optional


class Playlist:
    """Manages a list of track paths and the current play index.

    Tracks are stored as file path strings. Loop behaviour is handled here
    so Previous/Next/Auto-play wrap around the playlist consistently.
    All operations are safe on an empty playlist (no crash, no side effects).
    """

    def __init__(self) -> None:
        self._tracks: List[str] = []
        self._current_index: int = -1

    # ---- read-only properties -------------------------------------------

    @property
    def tracks(self) -> List[str]:
        """A copy of the current track paths."""
        return list(self._tracks)

    @property
    def is_empty(self) -> bool:
        return len(self._tracks) == 0

    def __len__(self) -> int:
        return len(self._tracks)

    @property
    def current_index(self) -> int:
        return self._current_index

    # ---- mutation --------------------------------------------------------

    def add(self, paths: List[str]) -> None:
        """Append one or more track paths to the playlist.

        If the playlist was empty, the first added track becomes the
        current track.
        """
        if not paths:
            return
        was_empty = self.is_empty
        self._tracks.extend(paths)
        if was_empty:
            self._current_index = 0

    def remove(self, index: int) -> Optional[str]:
        """Remove the track at ``index`` and return it.

        Returns ``None`` if the index is out of range. The current index is
        adjusted so it keeps pointing at a valid track where possible.
        """
        if not self._tracks or index < 0 or index >= len(self._tracks):
            return None

        removed = self._tracks.pop(index)

        if self.is_empty:
            self._current_index = -1
        elif index < self._current_index:
            # Removed a track before the current one -> shift current back.
            self._current_index -= 1
        elif index == self._current_index:
            if self._current_index >= len(self._tracks):
                self._current_index = len(self._tracks) - 1

        return removed

    def clear(self) -> None:
        """Remove all tracks and reset the current index."""
        self._tracks.clear()
        self._current_index = -1

    # ---- navigation / selection -----------------------------------------

    def current(self) -> Optional[str]:
        """Return the current track path, or ``None`` if none selected."""
        if self.is_empty or self._current_index < 0:
            return None
        if self._current_index >= len(self._tracks):
            return None
        return self._tracks[self._current_index]

    def select(self, index: int) -> Optional[str]:
        """Select and return the track at ``index`` (no wrapping).

        Returns ``None`` if the index is out of range. Does nothing when
        the playlist is empty.
        """
        if self.is_empty or index < 0 or index >= len(self._tracks):
            return None
        self._current_index = index
        return self._tracks[index]

    def next(self) -> Optional[str]:
        """Advance to the next track, wrapping to the first at the end.

        Returns ``None`` on an empty playlist.
        """
        if self.is_empty:
            return None
        self._current_index = (self._current_index + 1) % len(self._tracks)
        return self._tracks[self._current_index]

    def previous(self) -> Optional[str]:
        """Move to the previous track, wrapping to the last at the start.

        Returns ``None`` on an empty playlist.
        """
        if self.is_empty:
            return None
        self._current_index = (self._current_index - 1) % len(self._tracks)
        return self._tracks[self._current_index]
