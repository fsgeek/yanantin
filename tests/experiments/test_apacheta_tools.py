from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ConfigDict

from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.experiments.tools.apacheta_tools import (
    QueryBudget,
    QueryBudgetExceeded,
    find_objects_impl,
)


class FakeRecord(ApachetaBaseModel):
    model_config = ConfigDict(extra="allow")


class FakeApacheta:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, int | None]] = []
        self.author_records = [
            (
                uuid4(),
                FakeRecord(
                    provenance={"author_instance_id": "author-A"},
                    lineage_tags=["tag-A"],
                    custom_field="v-author",
                ),
            )
        ]
        self.lineage_records = [
            (
                uuid4(),
                FakeRecord(
                    provenance={"author_instance_id": "author-L"},
                    lineage_tags=["tag-L"],
                    custom_field="v-lineage",
                ),
            )
        ]
        self.has_field_records = [
            (
                uuid4(),
                FakeRecord(
                    provenance={"author_instance_id": "author-H"},
                    lineage_tags=["tag-H"],
                    custom_field="v-has-field",
                ),
            )
        ]
        self.list_records = [
            (
                uuid4(),
                FakeRecord(
                    provenance={"author_instance_id": "author-LIST"},
                    lineage_tags=["tag-LIST"],
                    custom_field="v-list",
                ),
            )
        ]

    def query_open_by_author_instance(
        self, author_instance_id: str, limit: int | None = None
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        self.calls.append(("query_open_by_author_instance", author_instance_id, limit))
        return self.author_records

    def query_open_by_lineage_tag(
        self, tag: str, limit: int | None = None
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        self.calls.append(("query_open_by_lineage_tag", tag, limit))
        return self.lineage_records

    def query_open_has_field(
        self, field_name: str, limit: int | None = None
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        self.calls.append(("query_open_has_field", field_name, limit))
        return self.has_field_records

    def list_open_records(
        self, limit: int | None = None
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        self.calls.append(("list_open_records", None, limit))
        return self.list_records

    # Read-only invariant sentinel methods. Any call to these means the tool
    # violated the contract.
    def store_record(self, *_args, **_kwargs) -> None:
        raise AssertionError("find_objects_impl must not call store_* methods")

    def store_tensor(self, *_args, **_kwargs) -> None:
        raise AssertionError("find_objects_impl must not call store_* methods")


@pytest.mark.parametrize(
    ("args", "expected_call", "expected_value"),
    [
        (
            {"matching": {"author_instance_id": "author-A"}, "limit": 3},
            "query_open_by_author_instance",
            "author-A",
        ),
        (
            {"matching": {"lineage_tag": "tag-L"}, "limit": 4},
            "query_open_by_lineage_tag",
            "tag-L",
        ),
        (
            {"matching": {"has_field": "custom_field"}, "limit": 5},
            "query_open_has_field",
            "custom_field",
        ),
        ({"matching": {}, "limit": 6}, "list_open_records", None),
    ],
)
def test_find_objects_impl_routes_to_expected_read_query(
    args: dict, expected_call: str, expected_value: str | None
) -> None:
    apacheta = FakeApacheta()
    budget = QueryBudget(2)

    envelope = find_objects_impl(apacheta, args, budget)

    assert apacheta.calls == [(expected_call, expected_value, args["limit"])]
    assert set(envelope) == {
        "results",
        "total_matched",
        "next_cursor",
        "diversity",
        "cost_hint",
        "ignored_filters",
        "received_cursor",
    }
    assert envelope["total_matched"] == len(envelope["results"])
    assert envelope["next_cursor"] is None
    assert envelope["diversity"] is None
    assert envelope["cost_hint"] == {"queries_remaining": 1}
    assert envelope["ignored_filters"] == []
    assert envelope["received_cursor"] is None


def test_find_objects_impl_maps_result_shape_from_record_envelope() -> None:
    apacheta = FakeApacheta()
    budget = QueryBudget(1)

    envelope = find_objects_impl(
        apacheta,
        {"matching": {"author_instance_id": "author-A"}, "limit": 1},
        budget,
    )

    assert len(envelope["results"]) == 1
    row = envelope["results"][0]
    assert row["id"] == str(apacheta.author_records[0][0])
    assert row["author_instance_id"] == "author-A"
    assert row["lineage_tags"] == ["tag-A"]
    assert row["fields"]["custom_field"] == "v-author"


def test_find_objects_impl_prefers_first_filter_and_reports_ignored_filters() -> None:
    """Prefer priority routing over errors so malformed multi-filter calls remain analyzable experimental data."""
    apacheta = FakeApacheta()
    budget = QueryBudget(1)

    envelope = find_objects_impl(
        apacheta,
        {
            "matching": {
                "author_instance_id": "author-A",
                "lineage_tag": "tag-L",
                "has_field": "custom_field",
            },
            "limit": 10,
        },
        budget,
    )

    assert apacheta.calls == [("query_open_by_author_instance", "author-A", 10)]
    assert envelope["ignored_filters"] == ["lineage_tag", "has_field"]


def test_find_objects_impl_echoes_received_cursor() -> None:
    apacheta = FakeApacheta()
    budget = QueryBudget(1)

    envelope = find_objects_impl(apacheta, {"cursor": "cursor-123"}, budget)

    assert envelope["received_cursor"] == "cursor-123"


def test_query_budget_contract() -> None:
    budget = QueryBudget(2)

    budget.charge()
    budget.charge()

    assert budget.remaining == 0
    with pytest.raises(QueryBudgetExceeded):
        budget.charge()
    assert budget.remaining == 0


def test_query_budget_rejects_negative_initial_value() -> None:
    with pytest.raises(ValueError):
        QueryBudget(-1)
