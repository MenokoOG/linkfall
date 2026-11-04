import re

import linkfall


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", linkfall.__version__)
