"""Run selected source tests with the installed private document Python."""
from pathlib import Path
import sys
import unittest

repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(repo / 'tests'), str(repo / 'src/app'),
                str(repo / 'src/app/gui_v1.8'), str(repo / 'installer'), str(repo / 'src/gui_web')]
modules = sys.argv[1:]
if not modules:
    raise SystemExit('Pass test module names without test_*.py suffix')
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
result = unittest.TextTestRunner(verbosity=0).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
