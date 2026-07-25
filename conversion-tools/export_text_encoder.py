from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from verify_parity import write_parity_report


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _as_numpy(value: object) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def _write_failure(
    report_path: Path,
    *,
    model_id: str,
    stage: str,
    error: Exception,
) -> None:
    payload = {
        "schema_version": "1",
        "model_id": model_id,
        "passed": False,
        "stage": stage,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the local multilingual text encoder to LiteRT."
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model-id", default="text-multilingual-v1")
    parser.add_argument("--sample-text", default="离线多模态内容检索")
    parser.add_argument("--max-length", type=int, default=32)
    args = parser.parse_args()

    stage = "load"
    try:
        import litert_torch
        import torch
        from transformers import AutoModel, AutoTokenizer

        model_path = args.model.resolve(strict=True)
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            local_files_only=True,
        )
        encoder = AutoModel.from_pretrained(
            str(model_path),
            local_files_only=True,
        ).eval()

        class TextEncoder(torch.nn.Module):
            def __init__(self, model: torch.nn.Module) -> None:
                super().__init__()
                self.model = model

            def forward(
                self,
                input_ids: torch.Tensor,
                attention_mask: torch.Tensor,
            ) -> torch.Tensor:
                token_embeddings = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    return_dict=False,
                )[0]
                mask = attention_mask.unsqueeze(-1).to(
                    dtype=token_embeddings.dtype
                )
                pooled = (token_embeddings * mask).sum(dim=1) / mask.sum(
                    dim=1
                ).clamp(min=1e-9)
                return torch.nn.functional.normalize(pooled, p=2, dim=1)

        wrapper = TextEncoder(encoder).eval()
        tokens = tokenizer(
            [args.sample_text],
            padding="max_length",
            truncation=True,
            max_length=args.max_length,
            return_tensors="pt",
        )
        sample = (tokens["input_ids"], tokens["attention_mask"])
        with torch.inference_mode():
            reference = _as_numpy(wrapper(*sample))

        stage = "convert"
        converted_model = litert_torch.convert(wrapper, sample)
        converted = _as_numpy(converted_model(*sample))

        stage = "export"
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        converted_model.export(str(output))
        reference_path = output.with_suffix(".reference.npy")
        converted_path = output.with_suffix(".litert.npy")
        np.save(reference_path, reference, allow_pickle=False)
        np.save(converted_path, converted, allow_pickle=False)

        report = write_parity_report(
            output_path=args.report,
            model_id=args.model_id,
            source_runtime="transformers-pytorch",
            converted_runtime="litert",
            reference=reference,
            converted=converted,
            artifacts={
                "converted_model": str(output),
                "reference_output": str(reference_path),
                "converted_output": str(converted_path),
            },
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] else 1
    except Exception as error:
        _write_failure(
            args.report.resolve(),
            model_id=args.model_id,
            stage=stage,
            error=error,
        )
        print(f"text export failed during {stage}: {type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
