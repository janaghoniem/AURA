import gym
import numpy as np

class CoordinatorEnv(gym.Env):
    """
    Custom Gym environment for the Coordinator Agent.

    State: 12-dimensional continuous vector
    Actions: 11 discrete actions mapped to coordinator behaviors
    Episode length: 20 steps
    """

    def __init__(self):
        super().__init__()

        # === Observation & Action Spaces ===
        self.observation_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(12,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(11)  # 11 actions: 0..10

        # Initialize state
        self.state = np.zeros(12)
        self.steps = 0
        self.max_steps = 20

        # Action mapping (for documentation / reference)
        self.action_mapping = {
            0: "search_web",
            1: "search_database",
            2: "compute_statistic",
            3: "filter_data",
            4: "aggregate_results",
            5: "compare_values",
            6: "identify_maximum",
            7: "identify_minimum",
            8: "generate_report",
            9: "send_notification",
            10: "terminate"
        }

    def reset(self):
        """Reset environment to initial state."""
        self.state = np.zeros(12)
        self.steps = 0
        return self.state

    def step(self, action):
        """Apply action and return (state, reward, done, info)."""
        assert self.action_space.contains(action), f"Invalid action {action}"

        self.steps += 1

        # Compute reward
        reward = self.compute_reward(action)

        # Update state (placeholder logic; replace with real features if available)
        self.state = self.update_state(action)

        # Episode done condition
        done = self.steps >= self.max_steps or action == 10  # terminate action ends episode

        info = {"action_name": self.action_mapping[action]}

        return self.state, reward, done, info

    def compute_reward(self, action):
        """
        Reward logic for actions.
        - Valid actions give small positive reward
        - Invalid actions penalized
        - Minor step penalty to encourage faster task completion
        """
        reward = -0.01  # small step penalty

        # Example: let's assume search_web (0) is invalid in some scenarios
        if action == 0:
            reward -= 0.3
        else:
            reward += 0.5

        # Terminate action gives a bonus if episode completed correctly
        if action == 10:
            reward += 1.0

        return reward

    def update_state(self, action):
        """
        Update the 12-dim state vector based on action taken.
        Currently placeholder: random small perturbation + action encoding.
        """
        new_state = self.state.copy()

        # Encode action into state[0]..state[10]
        action_vector = np.zeros(11)
        action_vector[action] = 1.0

        # Map action vector to first 11 dimensions of state
        new_state[:11] = action_vector

        # Last dimension: step count normalized
        new_state[11] = self.steps / self.max_steps

        return new_state
