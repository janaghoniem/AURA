# File: /backend/agents/rl/custom_model.py
import torch  # Move this to the top!

from ray.rllib.models.torch.torch_modelv2 import TorchModelV2
from ray.rllib.utils.annotations import override
from torch import nn

class YUSRMultiAgentModel(TorchModelV2, nn.Module):
    """
    A custom model that handles the Dict observation space for the Nav Agent.
    It combines visual features (e.g., from a CNN) and language features (e.g., goal embedding).
    """
    
    @override(TorchModelV2)
    def __init__(self, obs_space, action_space, num_outputs, model_config, name):
        TorchModelV2.__init__(self, obs_space, action_space, num_outputs, model_config, name)
        nn.Module.__init__(self)

        # Assuming the 'nav_agent' observation space contains 'visual_input' and 'task_goal'
        # The true input size is the sum of all components: 128 + 32 + 5 = 165
        input_size = (
            model_config["custom_model_config"]["vision_input_shape"][0] +
            model_config["custom_model_config"]["language_embedding_size"] +
            5 # for accessibility_features
        )

        # 1. Feature Combination Network (MLP)
        self.combined_network = nn.Sequential(
            nn.Linear(input_size, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU()
        )
        
        # 2. Policy Head (Outputting Action Logits)
        self.policy_head = nn.Linear(128, num_outputs)
        
        # 3. Value Head (Outputting State Value - used for PPO)
        self.value_head = nn.Linear(128, 1)

        self._last_features = None


    @override(TorchModelV2)
    def forward(self, input_dict, state, seq_lens):
        # The complex observation is passed in input_dict["obs"]
        obs = input_dict["obs"]

        # 1. Flatten the inputs from the Dict space
        visual_features = obs["visual_input"]
        language_features = obs["task_goal"]
        accessibility_features = obs["accessibility_features"]
        
        # Concatenate all inputs into one tensor
        combined_input = torch.cat([
            visual_features, 
            language_features, 
            accessibility_features
        ], dim=-1)

        # 2. Pass through the feature network
        self._last_features = self.combined_network(combined_input)
        
        # 3. Calculate Policy (actions)
        logits = self.policy_head(self._last_features)

        # RLlib requires returning logits and the state
        return logits, state

    @override(TorchModelV2)
    def value_function(self):
        # Calculate the Value (how good is the current state)
        assert self._last_features is not None, "must call forward() first"
        return torch.squeeze(self.value_head(self._last_features), -1)

