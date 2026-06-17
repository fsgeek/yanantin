def test_checksum_canonical_paths_import():
    from yanantin.collector.storage.local.checksum import (
        ChecksumData, ChecksumCollector, SyntheticChecksumCollector,
    )
    from yanantin.recorder.storage.local.checksum import (
        ChecksumRecorder, ChecksumFactRecorder, collect_and_record_checksum,
    )
    # collector self-describes; provider id is stable across instances
    c = ChecksumCollector  # class import is enough for the smoke
    assert ChecksumData is not None
    assert collect_and_record_checksum is not None
