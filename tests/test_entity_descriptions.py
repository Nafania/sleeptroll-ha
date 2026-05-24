import ast
import json
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


def test_light_value_is_not_exposed_as_duplicate_sensor() -> None:
    sensor_tree = ast.parse((INTEGRATION_PATH / "sensor.py").read_text())
    sensor_keys = {
        keyword.value.value
        for node in ast.walk(sensor_tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "SleepytrollSensorDescription"
        for keyword in node.keywords
        if keyword.arg == "key" and isinstance(keyword.value, ast.Constant)
    }

    number_tree = ast.parse((INTEGRATION_PATH / "number.py").read_text())
    number_keys = {
        keyword.value.value
        for node in ast.walk(number_tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "SleepytrollNumberDescription"
        for keyword in node.keywords
        if keyword.arg == "key" and isinstance(keyword.value, ast.Constant)
    }

    assert "light_value" not in sensor_keys
    assert "light_sensitivity" in number_keys


def test_mode_select_exposes_only_round_trippable_options() -> None:
    tree = ast.parse((INTEGRATION_PATH / "select.py").read_text())
    constants = {
        node.target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }

    options = {
        constants[keyword.value.id]
        if isinstance(keyword.value, ast.Name)
        else keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "SleepytrollSelectOption"
        for keyword in node.keywords
        if keyword.arg == "option"
        and isinstance(keyword.value, ast.Name | ast.Constant)
    }

    assert options == {
        "continuous",
        "sensor",
        "sleep_short",
        "sleep_medium",
        "sleep_long",
    }


def test_registry_cleanup_removes_deprecated_light_value_sensor() -> None:
    source = (INTEGRATION_PATH / "__init__.py").read_text()

    assert '(Platform.SENSOR, "light_value")' in source


def test_numeric_sleepytroll_entity_ids_are_repaired_to_expected_keys() -> None:
    source = (INTEGRATION_PATH / "__init__.py").read_text()

    assert "_legacy_numeric_entity_id" in source
    assert "object_id.rsplit(\"_\", 1)" in source
    assert 'prefix.endswith(f"_{key}")' in source
    assert "new_entity_id=" in source


@pytest.mark.parametrize(
    ("domain", "module_name", "description_class"),
    [
        ("button", "button", "SleepytrollButtonDescription"),
        ("number", "number", "SleepytrollNumberDescription"),
        ("sensor", "sensor", "SleepytrollSensorDescription"),
    ],
)
def test_entity_description_keys_have_translations(
    domain: str, module_name: str, description_class: str
) -> None:
    strings = json.loads((INTEGRATION_PATH / "strings.json").read_text())
    tree = ast.parse((INTEGRATION_PATH / f"{module_name}.py").read_text())
    keys = {
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == description_class
        for keyword in node.keywords
        if keyword.arg == "key" and isinstance(keyword.value, ast.Constant)
    }

    translated_keys = set(strings["entity"][domain])

    assert keys <= translated_keys
