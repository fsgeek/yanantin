def test_openrouter_canonical_paths_import():
    from yanantin.collector.semantic.openrouter.collector import (
        OpenRouterActivityCollector,
    )
    from yanantin.collector.semantic.openrouter.models import OpenRouterActivity
    from yanantin.recorder.semantic.openrouter.fact_recorder import (
        OpenRouterFactRecorder,
    )
    assert OpenRouterActivityCollector is not None
    assert OpenRouterActivity is not None
    assert OpenRouterFactRecorder is not None
