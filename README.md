# Abaka

A dice game of combinations for 2 to 5 players, built in Python and Streamlit.
Play on one screen, or online with each player on their own device.
 
## Project Layout

```
Abaka/
├── abaka/                    # Game engine core
│   ├── __init__.py
│   ├── engine.py            # Main game logic
│   ├── models.py            # Game models and enums
│   ├── player.py            # Player state management
│   ├── scoring.py           # Scoring logic
│   ├── school.py            # School category logic
│   ├── bonus.py             # Bonus calculation
│   ├── constants.py         # Game constants
│   ├── render.py            # Text-based scoreboard
│   ├── rooms.py             # Shared rooms for online 2-player games
│   └── __main__.py          # CLI entry point
├── ui_components/            # Streamlit UI
│   ├── main_ui.py           # Game screen: top bar, play panel, scoreboard
│   ├── dice.py              # Tappable dice, reroll
│   ├── move_selection.py    # Score / Cross out picker with previews
│   ├── moves.py             # Which moves are possible and what they score (no Streamlit)
│   ├── scoreboard.py        # Scoreboard table
│   ├── rules.py             # "How to play" text
│   ├── style.py             # CSS, dice artwork
│   └── README.md            # UI component documentation
├── .streamlit/config.toml   # Server settings and colour theme
├── tests/                    # Test suite
│   ├── test_rooms.py        # Online room tests
│   ├── test_moves.py        # Move preview tests
│   └── ...
├── abaka_ui.py              # Main Streamlit application
├── main.py                  # Alternative entry point
├── requirements.txt          # Core dependencies
└── README.md                # This file
```

## Features

- **Two ways to play**: on one screen, or online with an invite link (see `README_MULTIPLAYER.md`),
  for 2 to 5 players
- **Tap-to-pick dice**: tap the dice to reroll, or reroll all five; the joker is marked, and so is a wild joker
- **Moves with previews**: every option shows its score ("Full house · 46"), the target cell
  lights up on the scoreboard, and the button says exactly what happens
- **Clean scoreboard**: full row names, totals and school balance in each player's header;
  the last move is highlighted in orange until the next one
- **Live updates**: in online games both screens update within about a second
- **Works on phones**: the layout stacks on narrow screens
- **How to play**: rules on the home screen and in the in-game menu

## Quick Start

### Prerequisites
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run the Game
```bash
# Main Streamlit interface (recommended)
streamlit run abaka_ui.py

# Alternative entry points
python -m abaka              # CLI version
python main.py               # Alternative main
```

## Game Rules

Abaka is a dice game where players:
1. **Roll Dice**: 4 regular dice + 1 joker die
2. **Score Categories**: Fill slots in various scoring categories
3. **School Categories**: Numbers 1-6 with multiple slots
4. **Combination Categories**: Pair, Two Pairs, Three of a Kind, etc.
5. **Bonus Slots**: Earn bonuses for completing rows/columns

## UI Components

See `ui_components/README.md`.

## Development

### Running Tests
```bash
python -m unittest
# or:
python -m unittest discover -s tests -p "test_*.py"
```

### Code Structure
The new modular structure provides:
- **Maintainability**: Each component has a single responsibility
- **Testability**: Individual components can be tested separately
- **Reusability**: Components can be used in other interfaces
- **Scalability**: Easy to add new features and components

### Adding New Components
1. Create a new file in `ui_components/`
2. Implement the component logic
3. Import and use in `ui_components/main_ui.py`
4. Update this README with documentation

## Import Examples

```python
# Game engine
from abaka.engine import GameEngine
from abaka.models import Category
from abaka.scoring import score_category

# UI components
from ui_components.main_ui import render_game
from ui_components.moves import score_options, cross_options
```

## Requirements

### Core Dependencies
- Python 3.9+
- See `requirements.txt` for full list

### UI Dependencies
- Streamlit >= 1.48

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).

