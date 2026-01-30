from sentence_transformers import SentenceTransformer
import torch
import torch.nn.functional as F
from RL.action_space import ACTION_SPACE

# Load SentenceTransformer once
model = SentenceTransformer("all-MiniLM-L6-v2")

# Create a single source of truth for action embeddings
def build_action_embeddings():
    embeddings = {}
    for k, v in ACTION_SPACE.items():
        emb = torch.tensor(model.encode(
            v, convert_to_numpy=True), dtype=torch.float32
        )
        emb = F.normalize(emb, dim=0)  # ✅ normalize here
        embeddings[k] = emb
    return embeddings

ACTION_EMBEDDINGS = build_action_embeddings()

# Vectorized matrix for faster similarity
ACTION_IDS = sorted(ACTION_EMBEDDINGS.keys())
ACTION_MATRIX = torch.stack([ACTION_EMBEDDINGS[i] for i in ACTION_IDS])
