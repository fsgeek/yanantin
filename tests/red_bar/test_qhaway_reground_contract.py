"""RED BAR: what qhaway's `[reground]` extra reads from yanantin, pinned.

qhaway never imports yanantin. Since qhaway 0.7.5 (99e133b) its reground.py
activates when ~/.yanantin/config is a directory, reads only
~/.yanantin/config/reader.ini ([database] host, port, ssl, user, password,
written by `python -m yanantin.infra reader`), and copies
Regrounding.render()'s wording. It never opens db.ini. Tony's qhaway MCP runs
it. If any of these changes here, his qhaway goes quiet or diverges silently,
so changing one means telling qhaway in the same change.

The reader.ini key set and its read-only grants are pinned live in
tests/integration/test_reader_account.py.
"""

import inspect
from pathlib import Path

from yanantin.infra import config
from yanantin.infra.orchestrator import ApachetaDBSetup
from yanantin.memory.regrounding import Regrounding


def test_config_directory_is_where_qhaway_looks():
    assert config._DEFAULT_CONFIG_FILE.parent == Path.home() / ".yanantin" / "config"


def test_reader_file_defaults_beside_db_ini():
    source = inspect.getsource(ApachetaDBSetup.ensure_reader)
    assert 'cfg._config_file.parent / "reader.ini"' in source


def test_render_wording_qhaway_copies():
    stale = Regrounding(stored=5, live=7, as_of="2026-10-01", stale=True, collection="c", db="d")
    fresh = Regrounding(stored=7, live=7, as_of="2026-10-01", stale=False, collection="c", db="d")
    assert stale.render() == "7 (live; stored claim 5, as of 2026-10-01)"
    assert fresh.render() == "7 (live; matches stored claim, as of 2026-10-01)"
