"""Import the repository's canonical schedule parser without duplicating it."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "cron-regex-scheduler" / "cron_parse.py"
_spec = importlib.util.spec_from_file_location("canonical_cron_parse", _path)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)
parse = _module.parse
