from pathlib import Path

import numpy as np
import torch
import litert_torch


class TinyModel(torch.nn.Module):
    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return torch.relu(inputs * 2.0 + 1.0)


model = TinyModel().eval()
sample = (torch.tensor([[-1.0, 0.0, 1.0, 2.0]]),)
expected = model(*sample).detach().numpy()

converted = litert_torch.convert(model, sample)
actual = converted(*sample)
output_path = Path("/tmp/content-retrieval-smoke.tflite")
converted.export(str(output_path))

print(f"LITERT_IMPORT_OK={litert_torch is not None}")
print(f"LITERT_CONVERT_OK={np.allclose(expected, actual, atol=1e-5, rtol=1e-5)}")
print(f"LITERT_FILE_OK={output_path.is_file() and output_path.stat().st_size > 0}")
