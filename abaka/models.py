import random
from enum import Enum, auto

class Category(Enum):
    PAIR = auto()
    TWO_PAIRS = auto()
    TRIPS = auto()
    SMALL_STRAIGHT = auto()
    LARGE_STRAIGHT = auto()
    FULL = auto()
    KARE = auto()
    ABAKA = auto()
    SUM = auto()
    SCHOOL_1 = auto()
    SCHOOL_2 = auto()
    SCHOOL_3 = auto()
    SCHOOL_4 = auto()
    SCHOOL_5 = auto()
    SCHOOL_6 = auto()

class Die:
    def __init__(self, value, is_joker=False):
        self.value = value
        self.is_joker = is_joker
    def __repr__(self):
        return f"J({self.value})" if self.is_joker else f"{self.value}"

def roll_dice():
    """Roll 4 normal dice and 1 joker die (random 1-6). Joker is wild only when it shows 1."""
    dice = [Die(random.randint(1, 6)) for _ in range(4)]
    joker_value = random.randint(1, 6)
    dice.append(Die(joker_value, is_joker=True))
    random.shuffle(dice)
    return dice
