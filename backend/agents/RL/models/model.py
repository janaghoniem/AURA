import torch
import torch.nn as nn

class DecisionTransformer(nn.Module):
    def __init__(self, state_dim, act_dim, hidden, num_tasks):
        super().__init__()
        self.state = nn.Linear(state_dim, hidden)
        self.action = nn.Embedding(act_dim, hidden)
        self.rtg = nn.Linear(1, hidden)
        self.task = nn.Embedding(num_tasks, hidden)

        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(hidden, 4), 3
        )

        self.head = nn.Linear(hidden, act_dim)

    def forward(self, states, actions, rtg, task_ids):
        s = self.state(states)
        a = self.action(actions)
        r = self.rtg(rtg.unsqueeze(-1))
        t = self.task(task_ids).unsqueeze(1)

        x = s + a + r + t
        x = self.transformer(x)
        return self.head(x)
