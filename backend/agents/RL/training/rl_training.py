import torch
import json
from RL.datasets.dt_dataset import DTDataset
from RL.models.model import DecisionTransformer

# ===============================
# LOAD PREPROCESSED DATA
# ===============================
with open("RL/preprocessed data/verigui_coordinator_rl_train.json", "r", encoding="utf-8") as f:
    data = json.load(f)

dataset = DTDataset(data)

# ===============================
# CUSTOM COLLATE FUNCTION
# ===============================
MAX_LEN = 20  # fixed length for padding/truncation

def collate_fn(batch):
    states, actions, rtg, task_id = zip(*batch)

    # truncate to MAX_LEN and pad if shorter
    padded_states = torch.stack([
        torch.nn.functional.pad(s[-MAX_LEN:], (0,0,0,MAX_LEN - s.shape[0]))
        for s in states
    ])
    padded_actions = torch.stack([
        torch.nn.functional.pad(a[-MAX_LEN:], (0,MAX_LEN - a.shape[0]))
        for a in actions
    ])
    padded_rtg = torch.stack([
        torch.nn.functional.pad(r[-MAX_LEN:], (0,MAX_LEN - r.shape[0]))
        for r in rtg
    ])
    task_ids = torch.stack(task_id)

    return padded_states, padded_actions, padded_rtg, task_ids

# ===============================
# DATALOADER
# ===============================
loader = torch.utils.data.DataLoader(
    dataset,
    batch_size=8,
    shuffle=True,
    collate_fn=collate_fn
)

# ===============================
# MODEL SETUP
# ===============================
model = DecisionTransformer(
    state_dim=12,
    act_dim=13,
    hidden=128,
    num_tasks=1000
)

opt = torch.optim.Adam(model.parameters(), lr=3e-4)
loss_fn = torch.nn.CrossEntropyLoss()

# ===============================
# TRAINING LOOP
# ===============================
for epoch in range(10):
    for states, actions, rtg, task_id in loader:
        logits = model(states, actions, rtg, task_id)
        loss = loss_fn(logits[:, -1], actions[:, -1])

        opt.zero_grad()
        loss.backward()
        opt.step()

    print(f"Epoch {epoch} | Loss {loss.item():.4f}")
