"""Llika — graph-structured index service over ArangoDB native edges."""
from yanantin.llika.models import CompositionEdge, Path
from yanantin.llika.service import LlikaService

__all__ = ["CompositionEdge", "Path", "LlikaService"]
