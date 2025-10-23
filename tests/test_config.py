from spotify_yt_transfer.core.config import settings


def test_debug_flag_is_bool():
    assert isinstance(settings.debug, bool)


def test_default_threshold():
    assert settings.matching.fuzz_threshold == 70
