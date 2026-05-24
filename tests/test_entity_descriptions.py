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
