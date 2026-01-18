import ray
import os
import sys
from ray.rllib.algorithms.ppo import PPOConfig

# Use absolute import path for your custom environment
# Note: Ensure 'backend' is recognized by adding the project root to sys.path
try:
    from backend.agents.RL.environment import YUSR_UI_MultiAgentEnv
except ModuleNotFoundError:
    print("Error: Could not import YUSR_UI_MultiAgentEnv.")
    print("Ensure $env:PYTHONPATH is set to your project root (C:\\Users\\hala\\Documents\\GitHub\\YUSR).")
    sys.exit(1)

# --- Configuration ---
# 1. Setup PYTHONPATH for Ray workers
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    # Add project root to sys.path so Ray workers can find 'backend'
    sys.path.append(project_root)

# A sample complex instruction from the VeriGUI dataset
COMPLEX_TASK_INSTRUCTION = (
    "Find the Italian film that won the Grand Prix du Jury at the 1989 Cannes Film Festival, "
    "and was written and directed by Giuseppe Tornatore. For this film, provide the actor who played "
    "the blind projectionist Alfredo, and a famous quote about 'life' spoken by this actor."
)

# 2. Initialization
# Initialize Ray
ray.init(ignore_reinit_error=True, local_mode=False) 

# 3. Configure the PPO Algorithm
config = PPOConfig()

# RLlib new API stack (RLModule + new connectors) requires model/catalog
# encoder configs that are stricter. For quick local development keep the
# old API stack which uses the classic policy/model construction and
# default encoders. Remove or adjust this if you intentionally want the
# new API stack and provide full encoder/model configs.
config = config.api_stack(
    enable_rl_module_and_learner=False,
    enable_env_runner_and_connector_v2=False,
)

# --- Environment Configuration ---
config = config.environment(
    env=YUSR_UI_MultiAgentEnv,
    env_config={
        # This task instruction simulates loading a complex trajectory from the dataset
        "task_description": COMPLEX_TASK_INSTRUCTION,
        "start_url": "https://wikipedia.org",  # Start on a knowledge retrieval page
    }
)

# --- Multi-Agent Configuration ---
# We define three separate policies to allow each agent type to specialize.
config = config.multi_agent(
    policies={
        "nav_policy": (None, 
                       YUSR_UI_MultiAgentEnv.observation_space["nav_agent"],
                       YUSR_UI_MultiAgentEnv.action_space["nav_agent"],
                       {}),
        
        "pers_policy": (None,
                        YUSR_UI_MultiAgentEnv.observation_space["pers_agent"],
                        YUSR_UI_MultiAgentEnv.action_space["pers_agent"],
                        {}),

        "llm_policy": (None,
                       YUSR_UI_MultiAgentEnv.observation_space["llm_agent"],
                       YUSR_UI_MultiAgentEnv.action_space["llm_agent"],
                       {}),
    },
    
    # Map agents in the environment (nav_agent, etc.) to the policies defined above.
    # Accept flexible args because RLlib may call the mapping function with
    # different signatures (worker sometimes omitted in earlier code paths).
    policy_mapping_fn=lambda agent_id, episode, *args, **kwargs: 
        {
            "nav_agent": "nav_policy",
            "pers_agent": "pers_policy",
            "llm_agent": "llm_policy",
        }.get(agent_id),

    policies_to_train=["nav_policy", "pers_policy", "llm_policy"],
)

# --- Resource and Training Configuration ---
config = config.env_runners(
    num_env_runners=0,  # Use 4 workers to collect data in parallel (recommended for multi-agent envs)
    rollout_fragment_length=10,
    sample_timeout_s=60.0,
)
config = config.training(
    gamma=0.99, 
    lr=5e-5,    
    train_batch_size=1000,
)
config = config.debugging(
    log_level="WARN" 
)

# 4. Build and Run the Trainer
try:
    trainer = config.build()
    print("\n\n--- Starting Training Loop (5 Iterations) ---\n")
    num_iterations = 5  # Start with a small number of iterations
    for i in range(num_iterations):
        print(f"Running iteration {i+1}/{num_iterations}...")
        result = trainer.train()
        
        # Print key metrics
        print(f"  Episode Reward Mean: {result['episode_reward_mean']:.4f}")
        print(f"  Training Time: {result['time_this_iter_s']:.2f} seconds")
        print("-" * 30)

except Exception as e:
    print(f"\n--- FATAL TRAINING ERROR --- \nAn error occurred during training: {e}")
    print("Check your Tesseract path and ensure all Python packages are installed.")
finally:
    # 5. Cleanup
    if 'trainer' in locals() and trainer:
        trainer.stop()
    if ray.is_initialized():
        ray.shutdown()
    print("\n--- Ray shutdown complete ---")