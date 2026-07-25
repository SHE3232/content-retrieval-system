from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from verify_parity import compare_outputs


def _as_numpy(value: object) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export both local MobileCLIP-S0 encoders to LiteRT."
    )
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--mobileclip-source", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--sample-text", default="a blue application icon")
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "schema_version": "1",
        "model_id": "mobileclip-s0-v1",
        "license_name": "Apple Machine Learning Research Model License",
        "passed": False,
        "text_input_contract": (
            "tokenizer returns token_ids; host computes the EOT index as "
            "argmax(token_ids) and supplies both tensors"
        ),
        "encoders": {},
    }
    try:
        import litert_torch
        import torch

        source = args.mobileclip_source.resolve(strict=True)
        weights = args.weights.resolve(strict=True)
        sys.path.insert(0, str(source))
        import mobileclip

        model, _, _ = mobileclip.create_model_and_transforms(
            "mobileclip_s0",
            pretrained=str(weights),
            device="cpu",
        )
        model.eval()
        tokenizer = mobileclip.get_tokenizer("mobileclip_s0")

        class ImageEncoder(torch.nn.Module):
            def __init__(self, clip_model: torch.nn.Module) -> None:
                super().__init__()
                self.clip_model = clip_model

            def forward(self, image: torch.Tensor) -> torch.Tensor:
                return self.clip_model.encode_image(image, normalize=True)

        class TextEncoder(torch.nn.Module):
            def __init__(self, clip_model: torch.nn.Module) -> None:
                super().__init__()
                self.clip_model = clip_model

            def forward(
                self,
                tokens: torch.Tensor,
                eot_indices: torch.Tensor,
            ) -> torch.Tensor:
                token_embeddings = self.clip_model.text_encoder.encode_text(
                    text_tokens=tokens,
                    return_all_tokens=True,
                )
                gather_indices = eot_indices.reshape(-1, 1, 1).expand(
                    -1,
                    1,
                    token_embeddings.shape[-1],
                )
                selected = torch.gather(
                    token_embeddings,
                    dim=1,
                    index=gather_indices,
                ).squeeze(1)
                projected = (
                    selected
                    @ self.clip_model.text_encoder.projection_layer
                )
                return torch.nn.functional.normalize(
                    projected,
                    p=2,
                    dim=-1,
                )

        output_directory = args.output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        text_tokens = tokenizer([args.sample_text])
        jobs = [
            (
                "image",
                ImageEncoder(model).eval(),
                (
                    torch.linspace(
                        -1.0,
                        1.0,
                        steps=3 * 256 * 256,
                        dtype=torch.float32,
                    ).reshape(1, 3, 256, 256),
                ),
            ),
            (
                "text",
                TextEncoder(model).eval(),
                (text_tokens, text_tokens.argmax(dim=-1)),
            ),
        ]

        for name, wrapper, sample in jobs:
            try:
                with torch.inference_mode():
                    reference = _as_numpy(wrapper(*sample))
                converted_model = litert_torch.convert(wrapper, sample)
                converted = _as_numpy(converted_model(*sample))
                model_path = output_directory / f"mobileclip_s0_{name}.tflite"
                converted_model.export(str(model_path))
                reference_path = model_path.with_suffix(".reference.npy")
                converted_path = model_path.with_suffix(".litert.npy")
                np.save(reference_path, reference, allow_pickle=False)
                np.save(converted_path, converted, allow_pickle=False)
                metrics = compare_outputs(reference, converted)
                passed = (
                    metrics["cosine_similarity"] >= 0.999
                    and metrics["max_absolute_error"] <= 1e-4
                )
                payload["encoders"][name] = {
                    "passed": passed,
                    "metrics": metrics,
                    "artifacts": {
                        "converted_model": str(model_path),
                        "reference_output": str(reference_path),
                        "converted_output": str(converted_path),
                    },
                }
            except Exception as error:
                payload["encoders"][name] = {
                    "passed": False,
                    "stage": "convert_or_export",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }

        payload["passed"] = (
            set(payload["encoders"]) == {"image", "text"}
            and all(
                result["passed"]
                for result in payload["encoders"].values()
            )
        )
    except Exception as error:
        payload["stage"] = "load"
        payload["error_type"] = type(error).__name__
        payload["error"] = str(error)

    _write_json(args.report, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
