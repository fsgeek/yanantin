"""A find-by-name over Objects uses the label index, not a scan of every object."""

from uuid import uuid4

import pytest

from yanantin.core.khipu import Khipu
from yanantin.core.storage_obfuscator import TransparentObfuscator
from yanantin.infra.config import ApachetaDBConfig
from yanantin.recorder.storage.objects_definition import OBJECTS_DEFINITION

pytestmark = pytest.mark.integration


@pytest.fixture
def objects():
    try:
        db = ApachetaDBConfig().connect("test")
        db.properties()
    except Exception as exc:  # no live server here
        pytest.skip(f"no live ArangoDB: {exc}")
    name = f"Obj_label_{uuid4().hex[:8]}"
    collection = Khipu(db=db, obfuscator=TransparentObfuscator()).watay(name, OBJECTS_DEFINITION)
    collection.insert_many([
        {"label": "config", "uri": "file:///home/t/.ssh/config"},
        {"label": "settings.json", "uri": "file:///home/t/.claude/settings.json"},
    ])
    yield db, name
    db.delete_collection(name, ignore_missing=True)


def test_label_lookup_uses_the_index(objects):
    db, name = objects
    query = f'FOR o IN {name} FILTER o.label == "config" RETURN o.uri'
    nodes = db.aql.explain(query)["nodes"]
    used = [i["name"] for n in nodes if n["type"] == "IndexNode" for i in n["indexes"]]
    assert "idx_objects_label" in used
    assert list(db.aql.execute(query)) == ["file:///home/t/.ssh/config"]
