# Abaka UI Components

This directory contains the modular UI components for the Abaka game interface.

## Structure

```
ui_components/
├── __init__.py              # Package initialization
├── main_ui.py              # Main UI orchestrator
├── scoreboard.py           # Scoreboard rendering component
├── dice.py                 # Dice display and interaction component
├── move_selection.py       # Move selection interface component
├── sidebar.py              # Sidebar and new game component
├── requirements.txt        # UI-specific dependencies
└── README.md              # This file
```

## Components

### `main_ui.py`
- **Purpose**: Main orchestrator that coordinates all UI components
- **Functions**: 
  - `render_main_ui()`: Renders the complete game interface
  - `initialize_session_state()`: Sets up Streamlit session state
  - `render_new_game_setup()`: Shows the new game form

### `scoreboard.py`
- **Purpose**: Renders the game scoreboard with proper styling
- **Functions**:
  - `render_scoreboard()`: Main scoreboard renderer
  - `_build_scoreboard_html()`: Builds the HTML table structure
  - Section builders for school, combo, bonus, and totals

### `dice.py`
- **Purpose**: Handles dice display, selection, and reroll functionality
- **Functions**:
  - `render_dice_section()`: Renders the complete dice section
  - `_make_die_image()`: Creates custom die images
  - `_parse_die()`: Parses die data from the game engine

### `move_selection.py`
- **Purpose**: Manages the move selection interface with radio buttons
- **Functions**:
  - `render_move_selection()`: Renders the move selection interface
  - `_get_descriptive_label()`: Converts category enums to readable labels

### `sidebar.py`
- **Purpose**: Handles the sidebar with new game functionality
- **Functions**:
  - `render_sidebar()`: Renders the sidebar with new game controls

## Usage

### Running the Clean Version
```bash
streamlit run abaka_ui_clean.py
```

### Running the Original Version
```bash
streamlit run abaka_ui.py
```

## Benefits of the New Structure

1. **Modularity**: Each component has a single responsibility
2. **Maintainability**: Easier to find and fix issues
3. **Testability**: Individual components can be tested separately
4. **Reusability**: Components can be reused in other interfaces
5. **Readability**: Much cleaner and easier to understand
6. **Production Ready**: Professional code structure

## File Sizes

- **Original**: `abaka_ui.py` - 540 lines
- **New Structure**: 
  - `abaka_ui_clean.py` - 35 lines (main orchestrator)
  - `ui_components/scoreboard.py` - 180 lines
  - `ui_components/dice.py` - 120 lines
  - `ui_components/move_selection.py` - 80 lines
  - `ui_components/sidebar.py` - 30 lines
  - `ui_components/main_ui.py` - 50 lines

## Migration

The new structure maintains 100% compatibility with the original functionality while providing a much cleaner, more maintainable codebase.
