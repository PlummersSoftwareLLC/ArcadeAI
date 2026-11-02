"""Import the prospective runtime in its own namespace for synthetic CPU tests."""
import importlib
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parent/'profile04/Robotron'
PREFIX = '_prospective_tail9000_tests'
if PREFIX not in sys.modules:
    namespace = types.ModuleType(PREFIX)
    namespace.__path__ = [str(ROOT/'tools')]
    sys.modules[PREFIX] = namespace
campaign = importlib.import_module(PREFIX+'.run_quality_campaign')

