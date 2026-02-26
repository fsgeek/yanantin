"""Jabberwock: Named Entity Resolution.

The foreign body in the naming system. Every other module in Yanantin
has a Quechua name rooted in Andean cosmology. This one is Victorian
nonsense poetry. That IS the point -- it's the entity that exists in
a different coordinate system from everything around it. Just like
the entities it manages.

The Jabberwocky names are the real names. They prevent pattern-matching
to known entity resolution frameworks and force structural reasoning.
See docs/jabberwock-spec.md for the glossary.
"""

from yanantin.jabberwock.brillig import Brillig
from yanantin.jabberwock.models import (
    JABBERWOCK_PROVIDER,
    RATH_PROVIDER,
    ROOT_BANDERSNATCH_ID,
    TOVE_PROVIDER,
    VORPAL_PROVIDER,
    Frabjous,
    Jabberwock,
    MomeResult,
    Rath,
    Tove,
    Vorpal,
)
from yanantin.jabberwock.normalize import normalize_gimble, register_normalizer

__all__ = [
    # Service
    "Brillig",
    # Models
    "Frabjous",
    "Jabberwock",
    "MomeResult",
    "Rath",
    "Tove",
    "Vorpal",
    # Constants
    "JABBERWOCK_PROVIDER",
    "RATH_PROVIDER",
    "ROOT_BANDERSNATCH_ID",
    "TOVE_PROVIDER",
    "VORPAL_PROVIDER",
    # Normalization
    "normalize_gimble",
    "register_normalizer",
]
