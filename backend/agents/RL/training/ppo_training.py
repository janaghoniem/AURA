import torch
from environment.coordinator_env import CoordinatorEnv
from RL.models.ppo_actor import PPOActor
from RL.models.decision_transformer import DecisionTransformer

env = CoordinatorEnv()
ppo_actor = PPOActor(12, 11)

dt = DecisionTransformer(12,11,128,1000)
dt.load_state_dict(torch.load("dt_pretrained.pt"))

# Transfer DT → PPO
ppo_actor.net[-1].weight.data.copy_(dt.action_head.weight.data)
ppo_actor.net[-1].bias.data.copy_(dt.action_head.bias.data)
