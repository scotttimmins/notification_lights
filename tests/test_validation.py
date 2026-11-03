"""Why: a wrongly picked light (main light, duplicate) or a bad offset breaks placement."""

import importlib.util
import pathlib
import sys
import types

# Load only const + validation; the package __init__ needs Home Assistant.
pkg = pathlib.Path(__file__).parent.parent / "custom_components" / "notification_lights"
sys.modules["notification_lights"] = types.ModuleType("notification_lights")
sys.modules["notification_lights"].__path__ = [str(pkg)]
for name in ("const", "validation"):
    spec = importlib.util.spec_from_file_location(f"notification_lights.{name}", pkg / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"notification_lights.{name}"] = module
    spec.loader.exec_module(module)

from notification_lights.validation import validate_pick, validate_ring  # noqa: E402


def test_ring_light_accepted():
    assert validate_pick("light.bed_rgb", []) == {}


def test_main_light_rejected():
    # The central room light must never be taken over (CONTEXT: Notification light).
    assert validate_pick("light.bed", []) == {"light": "not_rgb"}


def test_duplicate_rejected():
    assert validate_pick("light.bed_rgb", ["light.bed_rgb"]) == {"light": "already_added"}


def test_offset_must_be_inside_ring():
    assert validate_ring({"segments": 26, "offset": 26}) == {"offset": "offset_too_large"}
    assert validate_ring({"segments": 26, "offset": 25}) == {}
