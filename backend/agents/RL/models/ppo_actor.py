import torch.nn as nn

class PPOActor(nn.Module):
    def __init__(self, state_dim, act_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, act_dim)
        )

    def forward(self, state):
        return self.net(state)
