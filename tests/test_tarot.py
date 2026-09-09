import unittest

from media_player.tarot import (
    ReadingPosition,
    TarotCard,
    TarotDeck,
    TarotReading,
)


class TestTarotLogict(unittest.TestCase):
    def setUp(self):
        self.deck = TarotDeck()

    def test_deck_contains_22_major_arcana(self):
        self.assertEqual(len(self.deck.cards), 22)

    def test_draw_returns_exactly_3_cards(self):
        reading = self.deck.draw_reading()
        self.assertEqual(len(reading.cards), 3)

    def test_reading_has_no_duplicates(self):
        reading = self.deck.draw_reading()
        drawn = list(reading.cards.values())
        ids = [card.id for card in drawn]
        self.assertEqual(len(ids), len(set(ids)))

    def test_positions_are_past_present_future(self):
        reading = self.deck.draw_reading()
        self.assertIn(ReadingPosition.PAST, reading.cards)
        self.assertIn(ReadingPosition.PRESENT, reading.cards)
        self.assertIn(ReadingPosition.FUTURE, reading.cards)
        self.assertEqual(
            set(reading.cards.keys()),
            {ReadingPosition.PAST, ReadingPosition.PRESENT, ReadingPosition.FUTURE},
        )

    def test_every_card_has_name_and_meaning(self):
        reading = self.deck.draw_reading()
        for card in reading.cards.values():
            self.assertIsInstance(card, TarotCard)
            self.assertTrue(card.name)
            self.assertTrue(card.meaning)

    def test_all_deck_cards_have_name_and_meaning(self):
        for card in self.deck.cards:
            self.assertTrue(card.name)
            self.assertTrue(card.meaning)

    def test_multiple_readings_can_be_generated(self):
        readings = [self.deck.draw_reading() for _ in range(50)]
        for reading in readings:
            self.assertIsInstance(reading, TarotReading)
            self.assertEqual(len(reading.cards), 3)

    def test_current_reading_is_accessible(self):
        reading = self.deck.draw_reading()
        self.assertIs(self.deck.current_reading, reading)

    def test_card_method_returns_by_position(self):
        reading = self.deck.draw_reading()
        past_card = reading.card(ReadingPosition.PAST)
        self.assertIs(past_card, reading.cards[ReadingPosition.PAST])

    def test_each_reading_position_has_unique_card(self):
        reading = self.deck.draw_reading()
        cards = list(reading.cards.values())
        self.assertEqual(len({id(c) for c in cards}), 3)


if __name__ == "__main__":
    unittest.main()
