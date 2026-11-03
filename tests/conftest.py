import pathlib
import sys

# Make `custom_components` importable for the Home Assistant tests.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
