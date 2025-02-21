import sys
from pathlib import Path


# Commands are not a Python package, just files in container.
# Add src/ to Python path.
src_path = Path(__file__).resolve().parent.parent.parent / "src"

sys.path.insert(0, str(src_path))
