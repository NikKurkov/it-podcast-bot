import pytest

from app.utils.locking import exclusive_lock


def test_exclusive_lock_rejects_overlap_and_releases_after_failure(tmp_path):
    lock_path = tmp_path / "pipeline.lock"
    with pytest.raises(ValueError):
        with exclusive_lock(lock_path, "already running"):
            with pytest.raises(RuntimeError, match="already running"):
                with exclusive_lock(lock_path, "already running"):
                    pytest.fail("Overlapping lock must not be acquired")
            raise ValueError("generation failed")
    with exclusive_lock(lock_path, "already running"):
        pass
