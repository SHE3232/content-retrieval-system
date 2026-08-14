from __future__ import annotations

import pytest

from tools.week6.test_taxonomy import classify_nodeid


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        for marker_name in sorted(classify_nodeid(item.nodeid)):
            item.add_marker(getattr(pytest.mark, marker_name))
