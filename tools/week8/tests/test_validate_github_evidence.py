from __future__ import annotations

import copy

import pytest
from validate_github_evidence import validate_github_evidence

COMMIT = "a" * 40
SHA = "b" * 64


def _manifest() -> dict[str, object]:
    return {
        "source_commit": COMMIT,
        "artifacts": [{"path": "02_public/source.zip", "sha256": SHA}],
    }


def _evidence() -> dict[str, object]:
    return {
        "source_commit": COMMIT,
        "repository_url": "https://github.com/example/offline-accessible-multimodal-retrieval",
        "tag": "v1.0.0",
        "tag_commit": COMMIT,
        "ci": {"commit": COMMIT, "jobs": {"ubuntu": "PASS", "windows": "PASS"}},
        "anonymous_access": {
            "readme": True,
            "license": True,
            "tag": True,
            "release": True,
            "assets_downloadable": True,
        },
        "release_assets": [
            {
                "name": "source.zip",
                "sha256": SHA,
                "distribution_class": "public",
                "anonymous_download": True,
            }
        ],
    }


def test_accepts_complete_public_release_evidence() -> None:
    result = validate_github_evidence(_evidence(), _manifest(), source_commit=COMMIT)
    assert result["status"] == "PASS"
    assert result["asset_count"] == 1


def test_rejects_research_asset() -> None:
    evidence = copy.deepcopy(_evidence())
    evidence["release_assets"][0]["distribution_class"] = "research-only"
    with pytest.raises(ValueError, match="research-only"):
        validate_github_evidence(evidence, _manifest(), source_commit=COMMIT)


def test_rejects_asset_hash_mismatch() -> None:
    evidence = copy.deepcopy(_evidence())
    evidence["release_assets"][0]["sha256"] = "c" * 64
    with pytest.raises(ValueError, match="hash differs"):
        validate_github_evidence(evidence, _manifest(), source_commit=COMMIT)


def test_rejects_missing_anonymous_check() -> None:
    evidence = copy.deepcopy(_evidence())
    evidence["anonymous_access"]["assets_downloadable"] = False
    with pytest.raises(ValueError, match="anonymous"):
        validate_github_evidence(evidence, _manifest(), source_commit=COMMIT)
