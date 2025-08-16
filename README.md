# Abaka

Python game engine for Abaka (dice/slots logic).

## Project layout
```

.
├─ src/
│  └─ abaka/
│     ├─ **init**.py
│     ├─ engine.py
│     ├─ scoring.py
│     └─ **main**.py   # enables `python -m abaka`
├─ tests/
│  ├─ test\_abaka\_engine.py
│  └─ test\_scoring.py
├─ scripts/
│  └─ abaka\_cli.py     # optional CLI entry
├─ requirements.txt
└─ README.md

````

## Quick start
```bash
<!-- python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -->
````

### Run

```bash
# if src/abaka/__main__.py exists:
streamlit run abaka_ui.py
*OR*
python -m abaka

# or via the helper script:
python scripts/abaka_cli.py
```

### Tests

```bash
python -m unittest
# or:
python -m unittest discover -s tests -p "test_*.py"
```

## Import

```python
from abaka.engine import Engine
from abaka.scoring import score_category, Category
```

