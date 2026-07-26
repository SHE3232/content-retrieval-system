import mobileclip
import torch
from transformers import BertConfig, BertModel


bert = BertModel(
    BertConfig(
        vocab_size=100,
        hidden_size=32,
        num_hidden_layers=1,
        num_attention_heads=4,
        intermediate_size=64,
    )
).eval()
bert_output = bert(
    input_ids=torch.tensor([[1, 2, 3]]),
    attention_mask=torch.tensor([[1, 1, 1]]),
)

mobileclip_model, _, _ = mobileclip.create_model_and_transforms("mobileclip_s0")
mobileclip_model.eval()

print(f"TORCH_VERSION={torch.__version__}")
print(f"BERT_FORWARD_OK={tuple(bert_output.last_hidden_state.shape) == (1, 3, 32)}")
print(f"MOBILECLIP_INIT_OK={mobileclip_model is not None}")
print(f"CUDA_AVAILABLE={torch.cuda.is_available()}")
