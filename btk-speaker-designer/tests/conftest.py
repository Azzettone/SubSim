import sys
import os

# Add parent directories to path
here = os.path.dirname(__file__)
btk_dir = os.path.dirname(here)
root_dir = os.path.dirname(btk_dir)

sys.path.insert(0, root_dir)  # for 'shared'
sys.path.insert(0, btk_dir)   # for 'core', 'database', etc.

# Create alias for the hyphen package name
import importlib
import types

# Make 'btk_speaker_designer' importable as an alias
btk_pkg = types.ModuleType('btk_speaker_designer')
btk_pkg.__path__ = [btk_dir]
btk_pkg.__package__ = 'btk_speaker_designer'
sys.modules['btk_speaker_designer'] = btk_pkg
