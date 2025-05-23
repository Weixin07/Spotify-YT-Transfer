import os
import importlib
from config import DEBUG, MATCH_FUZZ_THRESHOLD

def test_debug_flag_is_bool():
    assert isinstance(DEBUG, bool)

def test_default_threshold():
    assert MATCH_FUZZ_THRESHOLD == 70
