import ast
from pathlib import Path

import pytest

INTEGRATION_PATH = Path(__file__).parents[1] / "custom_components" / "sleepytroll"


@pytest.mark.parametrize(
    ("module_name", "class_name", "base_name"),
    [
        ("button", "SleepytrollButtonDescription", "ButtonEntityDescription"),
        ("number", "SleepytrollNumberDescription", "NumberEntityDescription"),
        ("sensor", "SleepytrollSensorDescription", "SensorEntityDescription"),
    ],
)
def test_platform_descriptions_extend_home_assistant_description(
    module_name: str, class_name: str, base_name: str
) -> None:
    tree = ast.parse((INTEGRATION_PATH / f"{module_name}.py").read_text())

    imports_base_description = any(
        isinstance(node, ast.ImportFrom)
        and node.module == f"homeassistant.components.{module_name}"
        and any(alias.name == base_name for alias in node.names)
        for node in tree.body
    )
    assert imports_base_description

    description_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )

    assert any(
        isinstance(base, ast.Name) and base.id == base_name
        for base in description_class.bases
    )


def test_sleepytroll_uses_switch_for_rocking() -> None:
    tree = ast.parse((INTEGRATION_PATH / "const.py").read_text())
    platforms = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "PLATFORMS"
            for target in node.targets
        )
    )

    platform_names = {
        elt.attr
        for elt in platforms.value.elts
        if isinstance(elt, ast.Attribute) and isinstance(elt.value, ast.Name)
    }

    assert "SWITCH" in platform_names
    assert "BUTTON" in platform_names


def test_buttons_expose_sync_and_reset_only() -> None:
    tree = ast.parse((INTEGRATION_PATH / "button.py").read_text())
    keys = {
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "SleepytrollButtonDescription"
        for keyword in node.keywords
        if keyword.arg == "key" and isinstance(keyword.value, ast.Constant)
    }

    assert {"sync_state", "reset"} <= keys
    assert "start_rocking" not in keys
    assert "pause_rocking" not in keys
    assert "acknowledge" not in keys


def test_rocking_switch_keeps_local_state_until_ble_status_arrives() -> None:
    source = (INTEGRATION_PATH / "switch.py").read_text()

    assert "self._is_on = False" in source
    assert "return self._is_on" in source
    assert "status in {1, 2}" in source
    assert "status in {0, 3}" in source
    assert "self._is_on = True" in source
    assert "self._is_on = False" in source
    assert "self.async_write_ha_state()" in source
