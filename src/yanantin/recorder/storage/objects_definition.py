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
from yanantin.core.khipu import Khipu
from yanantin.core.storage_obfuscator import StorageObfuscator

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
        # Find by name ("config", ".bashrc") without scanning every object.
        # Measured 2026-10-15 on 4.4M objects: label lookup by full scan 2,375 ms.
        # inBackground: building it must not lock a populated collection.
        {
            "type": "persistent",
            "fields": ["label"],
            "name": "idx_objects_label",
            "sparse": False,
            "inBackground": True,
        },
    ),
)

# Find by a path segment anywhere ("/.ssh/"), by name and by time, in one SEARCH.
# The segment analyzer splits the URI on "/" and keeps each segment exact, so
# ".ssh" never matches "ssh" or "openssh" (text_en, Indaleko's choice for URI,
# would: it drops the dot). text_en stays on uri and label for word search.
# A view links one named collection, so it is not part of OBJECTS_DEFINITION,
# which registrars bind to collections of other names.
PATH_SEGMENTS_ANALYZER = "objects_path_segments"
OBJECTS_FIND_VIEW = "objects_find"


def objects_find_definition(
    collection: str = STORAGE_OBJECTS, view: str = OBJECTS_FIND_VIEW
) -> CollectionDefinition:
    """The path-segment analyzer and the find view over `collection`."""
    return CollectionDefinition(
        analyzers=(
            {"name": PATH_SEGMENTS_ANALYZER, "type": "delimiter",
             "properties": {"delimiter": "/"}, "features": ["frequency", "norm"]},
        ),
        views=(
            {
                "name": view,
                "links": {
                    collection: {
                        "fields": {
                            "uri": {"analyzers": [PATH_SEGMENTS_ANALYZER, "text_en"]},
                            "label": {"analyzers": ["identity", "text_en"]},
                            "modified": {"analyzers": ["identity"]},
                            "source": {"analyzers": ["identity"]},
                        },
                    },
                },
            },
        ),
    )


def ensure_objects_find_view(
    db, obfuscator: StorageObfuscator | None = None,
    collection: str = STORAGE_OBJECTS, view: str = OBJECTS_FIND_VIEW,
) -> None:
    """Create the analyzer and find view over an existing Objects collection (idempotent)."""
    Khipu(db, obfuscator).watay(collection, objects_find_definition(collection, view))
