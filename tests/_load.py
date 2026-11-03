"""Load the HA-free modules without importing the package __init__ (needs Home Assistant)."""

import importlib.util
import pathlib
import sys
import types

pkg = pathlib.Path(__file__).parent.parent / "custom_components" / "notification_lights"
sys.modules.setdefault("notification_lights", types.ModuleType("notification_lights"))
sys.modules["notification_lights"].__path__ = [str(pkg)]
for name in ("const", "footprint", "paint", "scope", "validation"):
    spec = importlib.util.spec_from_file_location(f"notification_lights.{name}", pkg / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"notification_lights.{name}"] = module
    spec.loader.exec_module(module)
