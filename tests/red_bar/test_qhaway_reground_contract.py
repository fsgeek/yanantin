"""RED BAR: what qhaway's `[reground]` extra reads from yanantin, pinned.

qhaway never imports yanantin. Its reground.py reads ~/.yanantin/config/db.ini
directly and copies Regrounding.render()'s wording (qhaway
docs/requests/2026-10-14-reply-to-yanantin.md, dated correction). Tony's own
qhaway MCP entry runs it. If any of the three changes here, his qhaway breaks or
diverges silently, so changing one means telling qhaway in the same change.

Known debt: qhaway counts with admin_user/admin_passwd (root). The read-only
account now exists (`python -m yanantin.infra reader --grant llm_memory` writes
~/.yanantin/config/reader.ini; its keys are pinned in
tests/integration/test_reader_account.py). When qhaway switches, drop the admin
keys from the pin below.
"""

from pathlib import Path
from unittest.mock import patch

from yanantin.infra import config
from yanantin.memory.regrounding import Regrounding


def test_config_path_is_where_qhaway_reads_it():
    assert config._DEFAULT_CONFIG_FILE == Path.home() / ".yanantin" / "config" / "db.ini"


def test_config_keys_qhaway_reads(tmp_path):
    config_file = tmp_path / "db.ini"
    config.ApachetaDBConfig._instance = None
    try:
        with patch.object(config.ApachetaDBConfig, "default_config_file", config_file):
            cfg = config.ApachetaDBConfig(config_file=config_file)
        assert {"host", "port", "ssl", "admin_user", "admin_passwd"} <= set(cfg.db.keys())
    finally:
        config.ApachetaDBConfig._instance = None


def test_render_wording_qhaway_copies():
    stale = Regrounding(stored=5, live=7, as_of="2026-10-01", stale=True, collection="c", db="d")
    fresh = Regrounding(stored=7, live=7, as_of="2026-10-01", stale=False, collection="c", db="d")
    assert stale.render() == "7 (live; stored claim 5, as of 2026-10-01)"
    assert fresh.render() == "7 (live; matches stored claim, as of 2026-10-01)"
