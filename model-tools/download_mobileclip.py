from __future__ import annotations

import argparse
import json
from pathlib import Path

from download_models import REPOSITORY_ROOT, download_mobileclip_model


MOBILECLIP_REPOSITORY = "apple/MobileCLIP-S0"
MOBILECLIP_REVISION = "71aa3e13dda93115871afbd017336535ba29886c"
MOBILECLIP_S0_SHA256 = (
    "809b408eff74f8058843e86a1f92967097d42ba782450e85b8f4867b7f0ca0b7"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download the pinned MobileCLIP-S0 research weights and verify "
            "their published LFS SHA-256."
        )
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=REPOSITORY_ROOT / "models",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "models" / "model-manifest.json",
    )
    args = parser.parse_args()

    entry = download_mobileclip_model(
        repo_id=MOBILECLIP_REPOSITORY,
        revision=MOBILECLIP_REVISION,
        expected_sha256=MOBILECLIP_S0_SHA256,
        model_root=args.model_root,
        manifest_path=args.manifest,
    )
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
