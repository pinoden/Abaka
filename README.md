# Abaka

A modern dice game with a beautiful, modular UI built in Python and Streamlit.

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
│   └── __main__.py          # CLI entry point
├── ui_components/            # Modular UI components
│   ├── __init__.py          # Package initialization
│   ├── main_ui.py           # Main UI orchestrator
│   ├── scoreboard.py        # Scoreboard rendering
│   ├── dice.py              # Dice display and interaction
│   ├── move_selection.py    # Move selection interface
│   ├── sidebar.py           # Sidebar and new game
│   ├── requirements.txt     # UI dependencies
│   └── README.md            # UI component documentation
├── tests/                    # Test suite
│   └── test_abaka_engine.py
├── abaka_ui.py              # Main Streamlit application
├── main.py                  # Alternative entry point
├── requirements.txt          # Core dependencies
└── README.md                # This file
```

## Features

- **Beautiful UI**: Modern, responsive interface built with Streamlit
- **Modular Architecture**: Clean, maintainable code structure
- **Professional Scoreboard**: Clean table layout with visual separators
- **Interactive Dice**: Click to select, visual feedback, joker support
- **Smart Move Selection**: Radio button interface with descriptive labels
- **Real-time Updates**: Live scoreboard and turn management

## Quick Start

### Prerequisites
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
pip install -r ui_components/requirements.txt
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

### Scoreboard (`ui_components/scoreboard.py`)
- Professional table layout with visual separators
- Color-coded scores and bonuses
- Clear player separation and current player highlighting

### Dice Interface (`ui_components/dice.py`)
- Interactive dice selection
- Visual feedback with colored borders
- Joker die support with special styling

### Move Selection (`ui_components/move_selection.py`)
- Radio button interface for actions (Score/Cross)
- Grid layout for move categories
- Descriptive labels instead of abbreviations

### Sidebar (`ui_components/sidebar.py`)
- New game functionality
- Player name configuration
- Clean, organized layout

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
from ui_components.scoreboard import render_scoreboard
from ui_components.dice import render_dice_section
from ui_components.move_selection import render_move_selection
```

## Requirements

### Core Dependencies
- Python 3.9+
- See `requirements.txt` for full list

### UI Dependencies
- Streamlit >= 1.28.0
- Pillow >= 9.0.0
- See `ui_components/requirements.txt` for full list

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).

