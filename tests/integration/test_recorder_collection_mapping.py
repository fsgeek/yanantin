from uuid import uuid4

import pytest
from pydantic import ValidationError

from yanantin.core.contribution import ContributionTarget, ContributedRecord


def test_collector_mapping_is_empty():
    target = ContributionTarget(name="X", kind="doc", naming="well_known")
    assert target.model_dump(mode="json") == {
        "name": "X",
        "kind": "doc",
        "naming": "well_known",
    }

    with pytest.raises(ValidationError):
        ContributionTarget(name="X", kind="banana", naming="well_known")

    source = uuid4()
    record = ContributedRecord(source=source, raw={"a": 1})
    assert record.timestamp is not None

    fields = record.to_contribution_fields()
    assert fields["source"] == str(source)
    assert fields["raw"] == {"a": 1}

    extra_record = ContributedRecord(source=uuid4(), raw={"a": 1}, path="/data/x")
    assert extra_record.path == "/data/x"
    assert extra_record.to_contribution_fields()["path"] == "/data/x"
