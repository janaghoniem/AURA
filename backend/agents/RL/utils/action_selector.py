import torch
import torch.nn.functional as F
from RL.utils.action_embedding import ACTION_MATRIX, ACTION_IDS, model

def infer_action_from_text(subtask_text: str) -> int:
    # Encode the subtask text
    emb = torch.tensor(model.encode(subtask_text, convert_to_numpy=True), dtype=torch.float32)
    emb = F.normalize(emb, dim=0)  # ✅ normalize

    # Compute cosine similarity with all action embeddings (vectorized)
    sims = torch.matmul(ACTION_MATRIX, emb)
    best_idx = torch.argmax(sims).item()

    return ACTION_IDS[best_idx]
