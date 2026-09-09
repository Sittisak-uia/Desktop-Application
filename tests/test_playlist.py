"""Unit tests for media_player.playlist.Playlist.

Uses the standard library `unittest` only - no pytest dependency.
"""

import unittest

from media_player.playlist import Playlist


class TestPlaylistEmpty(unittest.TestCase):
    def setUp(self) -> None:
        self.playlist = Playlist()

    def test_starts_empty(self) -> None:
        self.assertTrue(self.playlist.is_empty)
        self.assertEqual(len(self.playlist), 0)

    def test_current_is_none_when_empty(self) -> None:
        self.assertIsNone(self.playlist.current())

    def test_next_is_none_when_empty(self) -> None:
        self.assertIsNone(self.playlist.next())

    def test_previous_is_none_when_empty(self) -> None:
        self.assertIsNone(self.playlist.previous())

    def test_select_is_none_when_empty(self) -> None:
        self.assertIsNone(self.playlist.select(0))

    def test_remove_is_none_when_empty(self) -> None:
        self.assertIsNone(self.playlist.remove(0))

    def test_clear_on_empty_is_safe(self) -> None:
        self.playlist.clear()
        self.assertTrue(self.playlist.is_empty)
        self.assertEqual(self.playlist.current_index, -1)

    def test_tracks_is_empty_list(self) -> None:
        self.assertEqual(self.playlist.tracks, [])


class TestPlaylistAdd(unittest.TestCase):
    def setUp(self) -> None:
        self.playlist = Playlist()

    def test_add_single_track(self) -> None:
        self.playlist.add(["song_a.mp3"])
        self.assertEqual(len(self.playlist), 1)
        self.assertEqual(self.playlist.tracks, ["song_a.mp3"])

    def test_add_multiple_tracks(self) -> None:
        self.playlist.add(["a.mp3", "b.mp3", "c.mp3"])
        self.assertEqual(len(self.playlist), 3)

    def test_add_empty_paths_is_noop(self) -> None:
        self.playlist.add([])
        self.assertTrue(self.playlist.is_empty)
        self.assertEqual(self.playlist.current_index, -1)

    def test_first_add_sets_current_index_to_zero(self) -> None:
        self.playlist.add(["a.mp3"])
        self.assertEqual(self.playlist.current_index, 0)
        self.assertEqual(self.playlist.current(), "a.mp3")

    def test_add_more_keeps_current_index(self) -> None:
        self.playlist.add(["a.mp3", "b.mp3"])
        self.assertEqual(self.playlist.current_index, 0)
        self.playlist.add(["c.mp3"])
        self.assertEqual(self.playlist.current_index, 0)


class TestPlaylistSelection(unittest.TestCase):
    def setUp(self) -> None:
        self.playlist = Playlist()
        self.playlist.add(["a.mp3", "b.mp3", "c.mp3"])

    def test_select_valid_index(self) -> None:
        self.assertEqual(self.playlist.select(1), "b.mp3")
        self.assertEqual(self.playlist.current_index, 1)

    def test_select_negative_index_returns_none(self) -> None:
        self.assertIsNone(self.playlist.select(-1))
        self.assertEqual(self.playlist.current_index, 0)

    def test_select_out_of_range_returns_none(self) -> None:
        self.assertIsNone(self.playlist.select(3))
        self.assertEqual(self.playlist.current_index, 0)


class TestPlaylistLoop(unittest.TestCase):
    def setUp(self) -> None:
        self.playlist = Playlist()
        self.playlist.add(["a.mp3", "b.mp3", "c.mp3"])
        self.playlist.select(0)

    def test_next_moves_forward(self) -> None:
        self.assertEqual(self.playlist.next(), "b.mp3")
        self.assertEqual(self.playlist.next(), "c.mp3")

    def test_next_wraps_to_first_at_end(self) -> None:
        self.playlist.select(2)
        self.assertEqual(self.playlist.next(), "a.mp3")
        self.assertEqual(self.playlist.current_index, 0)

    def test_previous_moves_backward(self) -> None:
        self.playlist.select(2)
        self.assertEqual(self.playlist.previous(), "b.mp3")
        self.assertEqual(self.playlist.previous(), "a.mp3")

    def test_previous_wraps_to_last_at_start(self) -> None:
        self.playlist.select(0)
        self.assertEqual(self.playlist.previous(), "c.mp3")
        self.assertEqual(self.playlist.current_index, 2)

    def test_next_on_single_track_loops_to_itself(self) -> None:
        single = Playlist()
        single.add(["only.mp3"])
        self.assertEqual(single.next(), "only.mp3")
        self.assertEqual(single.current_index, 0)


class TestPlaylistRemove(unittest.TestCase):
    def setUp(self) -> None:
        self.playlist = Playlist()
        self.playlist.add(["a.mp3", "b.mp3", "c.mp3"])

    def test_remove_returns_removed_track(self) -> None:
        self.assertEqual(self.playlist.remove(1), "b.mp3")
        self.assertEqual(self.playlist.tracks, ["a.mp3", "c.mp3"])

    def test_remove_out_of_range_returns_none(self) -> None:
        self.assertIsNone(self.playlist.remove(5))
        self.assertIsNone(self.playlist.remove(-1))
        self.assertEqual(len(self.playlist), 3)

    def test_remove_before_current_shifts_index(self) -> None:
        self.playlist.select(2)
        self.playlist.remove(0)
        self.assertEqual(self.playlist.current_index, 1)

    def test_remove_after_current_keeps_index(self) -> None:
        self.playlist.select(1)
        self.playlist.remove(2)
        self.assertEqual(self.playlist.current_index, 1)

    def test_remove_current_moves_to_previous_track(self) -> None:
        self.playlist.select(2)
        self.playlist.remove(2)
        self.assertEqual(self.playlist.tracks, ["a.mp3", "b.mp3"])
        self.assertEqual(self.playlist.current_index, 1)

    def test_remove_only_track_resets_state(self) -> None:
        single = Playlist()
        single.add(["only.mp3"])
        single.remove(0)
        self.assertTrue(single.is_empty)
        self.assertEqual(single.current_index, -1)
        self.assertIsNone(single.current())


class TestPlaylistClear(unittest.TestCase):
    def test_clear_removes_all(self) -> None:
        playlist = Playlist()
        playlist.add(["a.mp3", "b.mp3"])
        playlist.clear()
        self.assertTrue(playlist.is_empty)
        self.assertEqual(len(playlist), 0)
        self.assertEqual(playlist.current_index, -1)
        self.assertIsNone(playlist.current())


if __name__ == "__main__":
    unittest.main()
