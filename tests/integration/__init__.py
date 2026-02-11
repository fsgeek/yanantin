"""Integration tests for Apacheta backends.

Integration tests verify backends against real external services:
- ArangoDB at 192.168.111.125:8529 (test database)
- Future: Network-based tensor exchange
- Future: Multi-instance coordination

Tests in this directory require external dependencies to be running.
If dependencies are unavailable, tests skip gracefully via pytest.skip().
"""
