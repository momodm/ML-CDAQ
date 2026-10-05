"""M4 local historical query and frozen-model backend."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.runtime/m4_backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
