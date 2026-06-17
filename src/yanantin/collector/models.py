"""Data models for the collector/wrangler/recorder pipeline.

Serializable data is the boundary contract. Everything that moves through
the pipeline is a Pydantic model that can go through any wrangler strategy
unchanged. The wrangler doesn't transform data — it moves it.
"""

from __future__ import annotations

from yanantin.transport.models import ProviderRegistration, WranglerEnvelope  # noqa: F401
