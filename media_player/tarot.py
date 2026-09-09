import random
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class TarotCard:
    id: str
    name: str
    meaning: str
    image_path: str


class ReadingPosition(Enum):
    PAST = "Past"
    PRESENT = "Present"
    FUTURE = "Future"


@dataclass
class TarotReading:
    cards: dict[ReadingPosition, TarotCard]

    def card(self, position: ReadingPosition) -> TarotCard:
        return self.cards[position]


class TarotDeck:
    def __init__(self):
        self.cards = self._build_major_arcana()
        self._current_reading = None

    @property
    def current_reading(self):
        return self._current_reading

    def draw_reading(self) -> TarotReading:
        drawn = random.sample(self.cards, 3)
        reading = TarotReading(
            cards={
                ReadingPosition.PAST: drawn[0],
                ReadingPosition.PRESENT: drawn[1],
                ReadingPosition.FUTURE: drawn[2],
            }
        )
        self._current_reading = reading
        return reading

    @staticmethod
    def _build_major_arcana() -> list[TarotCard]:
        return [
            TarotCard("0", "The Fool", "New beginnings, optimism, trust in life", "resources/tarot/the_fool.jpg"),
            TarotCard("1", "The Magician", "Manifestation, resourcefulness, power", "resources/tarot/the_magician.jpg"),
            TarotCard("2", "The High Priestess", "Intuition, unconscious knowledge, mystery", "resources/tarot/the_high_priestess.jpg"),
            TarotCard("3", "The Empress", "Abundance, nurturing, fertility", "resources/tarot/the_empress.jpg"),
            TarotCard("4", "The Emperor", "Authority, structure, control", "resources/tarot/the_emperor.jpg"),
            TarotCard("5", "The Hierophant", "Tradition, spiritual guidance, conformity", "resources/tarot/the_hierophant.jpg"),
            TarotCard("6", "The Lovers", "Love, harmony, choices", "resources/tarot/the_lovers.jpg"),
            TarotCard("7", "The Chariot", "Willpower, determination, victory", "resources/tarot/the_chariot.jpg"),
            TarotCard("8", "Strength", "Courage, inner strength, patience", "resources/tarot/strength.jpg"),
            TarotCard("9", "The Hermit", "Introspection, solitude, inner guidance", "resources/tarot/the_hermit.jpg"),
            TarotCard("10", "Wheel of Fortune", "Change, cycles, destiny", "resources/tarot/wheel_of_fortune.jpg"),
            TarotCard("11", "Justice", "Fairness, truth, cause and effect", "resources/tarot/justice.jpg"),
            TarotCard("12", "The Hanged Man", "Letting go, new perspective, surrender", "resources/tarot/the_hanged_man.jpg"),
            TarotCard("13", "Death", "Endings, transformation, transition", "resources/tarot/death.jpg"),
            TarotCard("14", "Temperance", "Balance, moderation, patience", "resources/tarot/temperance.jpg"),
            TarotCard("15", "The Devil", "Attachment, temptation, shadow self", "resources/tarot/the_devil.jpg"),
            TarotCard("16", "The Tower", "Sudden change, upheaval, revelation", "resources/tarot/the_tower.jpg"),
            TarotCard("17", "The Star", "Hope, inspiration, serenity", "resources/tarot/the_star.jpg"),
            TarotCard("18", "The Moon", "Illusion, intuition, subconscious", "resources/tarot/the_moon.jpg"),
            TarotCard("19", "The Sun", "Success, vitality, joy", "resources/tarot/the_sun.jpg"),
            TarotCard("20", "Judgement", "Reflection, reckoning, awakening", "resources/tarot/judgement.jpg"),
            TarotCard("21", "The World", "Completion, wholeness, achievement", "resources/tarot/the_world.jpg"),
        ]