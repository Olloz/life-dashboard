import json, pathlib, pytest

@pytest.fixture
def CFG():
    return json.loads((pathlib.Path(__file__).parent.parent / "config.json").read_text())
