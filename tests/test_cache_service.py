from spotify_yt_transfer.services import CacheInvalidationResult, CacheService


class DummyRepository:
    def __init__(self):
        self.matched_calls = 0
        self.failed_calls = 0

    def delete_all_matched_tracks(self) -> int:
        self.matched_calls += 1
        return 5

    def delete_all_failed_tracks(self) -> int:
        self.failed_calls += 1
        return 2


class DummyYouTubeClient:
    def __init__(self) -> None:
        self.cleared = False

    def clear_search_cache(self) -> None:
        self.cleared = True


def test_cache_service_invalidate():
    repo = DummyRepository()
    youtube = DummyYouTubeClient()
    service = CacheService(repo, youtube)

    result = service.invalidate(True, True, True)

    assert isinstance(result, CacheInvalidationResult)
    assert result.matched_tracks_removed == 5
    assert result.failed_tracks_removed == 2
    assert result.youtube_cache_cleared is True
    assert repo.matched_calls == 1
    assert repo.failed_calls == 1
    assert youtube.cleared is True


def test_cache_service_partial_invalidation():
    repo = DummyRepository()
    youtube = DummyYouTubeClient()
    service = CacheService(repo, youtube)

    result = service.invalidate(False, False, True)

    assert result.matched_tracks_removed == 0
    assert result.failed_tracks_removed == 2
    assert result.youtube_cache_cleared is False
    assert repo.matched_calls == 0
    assert repo.failed_calls == 1
    assert youtube.cleared is False
