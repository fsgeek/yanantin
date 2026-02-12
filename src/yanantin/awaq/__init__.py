"""Awaq -- the weaver. Extracts composition declarations from tensors.

The name is Quechua for weaver. The Awaq reads tensors, finds where
they declare what they compose with and what they don't, and creates
formal edges from narrative prose.

    uv run python -m yanantin.awaq              # scan cairn, render graph
    uv run python -m yanantin.awaq --tensor T15 # one tensor's declarations
    uv run python -m yanantin.awaq --json       # machine-readable output
"""
