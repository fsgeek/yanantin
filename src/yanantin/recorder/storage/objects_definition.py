"""The shape of the shared Objects storage collection — substrate-wide, not
per-platform. Lifted here when the CLOUD storage leaf became the SECOND
contributor into Objects (the linux-local leaf was the first): the
second-instance forces the extraction (premature decomposition wears
good-engineering clothes; one instance is not enough). Both leaves import
these names + the definition so neither owns the shared destination's shape.

The temporal window is the search-space reducer (the episodic pivot): a
persistent sorted index on `modified` turns the temporal-window query from an
O(n) full collection scan into an O(log n) IndexNode. Measured on the live
35,805-doc Objects slice: 38ms full scan -> 3ms index, the gap widening with n
(the full census is ~4.1M files). schema stays None — the open-lane posture
A1/A2 settled; this binds only the index, the invisible tuning the find model
needs. The field name is SEMANTIC ("modified"); watay obfuscates it to the
physical name when the index is created, same as the view-link path (gh #32).
"""

from __future__ import annotations

from yanantin.core.collection_definition import CollectionDefinition

STORAGE_OBJECTS = "Objects"
STORAGE_RELATIONSHIPS = "Relationships"
CONTAINS_RELATION = "contains"  # directory -> child; DISTINCT from "records" provenance

OBJECTS_DEFINITION = CollectionDefinition(
    schema=None,
    indices=(
        {
            "type": "persistent",
            "fields": ["modified"],
            "name": "idx_objects_modified",
            "sparse": False,
        },
    ),
)
