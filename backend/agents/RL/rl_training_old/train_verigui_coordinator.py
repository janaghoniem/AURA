# rl_training/train_verigui_coordinator_full.py
import os
import json
import random
import time
from typing import List, Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# TF-IDF fallback
from sklearn.feature_extraction.text import TfidfVectorizer

# -------------------------
# CONFIG
# -------------------------
DATA_DIR = "./preprocessed_verigui_new"
SPLIT_PATH = os.path.join(DATA_DIR, "trajs_split.pt")
CHECKPOINT_DIR = "rl_training/checkpoints/coordinator_full"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Action mapping
AGENT_TYPES = ["execution_agent", "language_agent", "reasoning_agent"]
ACTION_DIM = len(AGENT_TYPES)

# PPO / training hyperparams (tweak as needed)
LR = 3e-5
WEIGHT_DECAY = 1e-6
CLIP_EPS = 0.2
PPO_EPOCHS = 6
MINIBATCH_SIZE = 64
STEPS_PER_UPDATE = 2048  # how many step transitions to collect before each update
GAMMA = 0.99
GAE_LAMBDA = 0.95
ENTROPY_COEF = 0.01
VALUE_COEF = 0.5
TOTAL_EPOCHS = 200
SEED = 42

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# Reward balancing: will compute from counts (train set) after loading
AGENT_POS_REW = None   # dict: agent->pos reward
AGENT_NEG_PEN = None   # dict: agent->neg penalty

# -------------------------
# Utilities: load splits
# -------------------------
def load_splits(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Split file not found: {path}")
    data = torch.load(path)
    # expected keys: "train","val","test"
    return data["train"], data["val"], data["test"]

# -------------------------
# Build embedder (TF-IDF) from train set
# -------------------------
def build_tfidf(train_trajs: List[Dict], max_features=5000):
    corpus = []
    for t in train_trajs:
        main = t.get("instruct", "")
        if main:
            corpus.append(main)
        for st in t.get("sub_tasks", []):
            corpus.append(st.get("instruct", ""))
    tfidf = TfidfVectorizer(max_features=max_features, ngram_range=(1,2))
    tfidf.fit(corpus)
    return tfidf

def embed_texts(tfidf, texts: List[str]) -> np.ndarray:
    X = tfidf.transform(texts)
    # normalize rows to unit norm to keep scale stable
    X = X.toarray()
    norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
    X = X / norms
    return X.astype(np.float32)

# -------------------------
# Environment: wraps one trajectory as an episode
# -------------------------
class CoordinatorEnv:
    """
    Simulated environment that uses a ground-truth trajectory.
    At each step agent picks which specialist to route the subtask to.
    Rewards are based on match with ground-truth _agent_label and dependency checks.
    """
    def __init__(self, traj: Dict, tfidf, embed_dim: int, agent_pos_reward: Dict[str,float], agent_neg_pen: Dict[str,float]):
        self.traj = traj
        self.subtasks = traj.get("sub_tasks", [])
        self.n = len(self.subtasks)
        self._deps = traj.get("_deps", [[] for _ in range(self.n)])
        self.current = 0
        self.executed = set()
        self.failed = False
        self.tfidf = tfidf
        self.embed_dim = embed_dim
        self.agent_pos_reward = agent_pos_reward
        self.agent_neg_pen = agent_neg_pen

        # Precompute embeddings for subtask instructions (so state is quick)
        texts = [s.get("instruct","") for s in self.subtasks]
        if texts:
            self.embeds = embed_texts(self.tfidf, texts)  # shape (n, embed_dim)
        else:
            self.embeds = np.zeros((self.n, embed_dim), dtype=np.float32)

        # agent history (counts) for state
        self.agent_history = np.zeros(len(AGENT_TYPES), dtype=np.float32)
        # last actions window
        self.last_actions = []

    def reset(self):
        self.current = 0
        self.executed = set()
        self.failed = False
        self.agent_history[:] = 0.0
        self.last_actions = []
        # return initial state for step 0 (if exists)
        return self._get_state(self.current)

    def _deps_satisfied(self, step_idx: int) -> bool:
        deps = self._deps[step_idx] if step_idx < len(self._deps) else []
        return all(d in self.executed for d in deps)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        """
        action: index in AGENT_TYPES
        returns: (next_state, reward, done, info)
        """
        info = {}
        if self.current >= self.n:
            # already finished
            return self._get_state(self.n-1 if self.n>0 else 0), 0.0, True, {"success": True}

        step_meta = self.subtasks[self.current]
        true_agent_label = step_meta.get("_agent_label", AGENT_TYPES[1])  # default language_agent if missing
        true_agent_idx = AGENT_TYPES.index(true_agent_label) if true_agent_label in AGENT_TYPES else 1

        reward = 0.0
        # agent match reward / penalty
        if action == true_agent_idx:
            reward += self.agent_pos_reward[true_agent_label]
        else:
            # apply penalty proportional to the true agent (we penalize choosing wrong)
            # Negative penalty scaled by chosen agent? use penalty for chosen agent to avoid discouraging rare true agent
            chosen_label = AGENT_TYPES[action]
            # Use the penalty of the *chosen* agent (less punishment for common agent choosing wrong)
            reward += self.agent_neg_pen[chosen_label]

        # dependency check: if deps not satisfied and we try to "execute" this step (any agent means executing)
        if not self._deps_satisfied(self.current):
            # heavy penalty for attempting to run before deps
            reward -= 1.5
            info["dep_violation"] = True
        else:
            info["dep_violation"] = False

        # mark step executed (in this offline simulation we assume action always produces the result)
        self.executed.add(self.current)
        self.agent_history[action] += 1
        self.last_actions.append(action)
        if len(self.last_actions) > 5:
            self.last_actions.pop(0)

        # advance
        self.current += 1
        done = self.current >= self.n

        # terminal reward if finished and no fatal dependency violation (we consider success when all steps done)
        if done and not self.failed:
            # small terminal bonus scaled by fraction of matched agents
            # compute match ratio over episode: we can't reconstruct that here easily; skip huge terminal reward
            reward += 2.0

        info["step_idx"] = self.current - 1
        info["success"] = (done and not self.failed)
        return (self._get_state(self.current if self.current < self.n else self.n-1),
                float(reward), done, info)

    def _get_state(self, step_idx: int) -> np.ndarray:
        """
        Compose state vector:
         - embedding of current subtask (embed_dim)
         - simple counts: current_step, remaining_steps, executed_count (3 scalars)
         - agent_history normalized (len AGENT_TYPES)
         - last_actions window (len AGENT_TYPES)
        """
        if self.n == 0:
            emb = np.zeros(self.embed_dim, dtype=np.float32)
        else:
            emb = self.embeds[step_idx] if step_idx < self.n else self.embeds[-1]
        current_frac = float(step_idx / max(1, self.n))
        remaining_frac = float((self.n - step_idx) / max(1, self.n))
        executed_count = float(len(self.executed) / max(1, self.n))
        # normalize agent_history
        total_hist = self.agent_history.sum() + 1e-12
        hist = (self.agent_history / total_hist).astype(np.float32)
        # last actions frequency vector
        last_vec = np.zeros(len(AGENT_TYPES), dtype=np.float32)
        for a in self.last_actions:
            last_vec[a] += 1.0
        if len(self.last_actions) > 0:
            last_vec = last_vec / float(len(self.last_actions))
        # stack everything
        state = np.concatenate([
            emb,
            np.array([current_frac, remaining_frac, executed_count], dtype=np.float32),
            hist,
            last_vec
        ])
        return state

# -------------------------
# Simple PPO network
# -------------------------
class PPOCoordinator(nn.Module):
    def __init__(self, state_dim:int, hidden:int=512, action_dim:int=ACTION_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU()
        )
        self.actor = nn.Linear(hidden, action_dim)
        self.critic = nn.Linear(hidden, 1)

    def forward(self, x):
        h = self.net(x)
        return self.actor(h), self.critic(h).squeeze(-1)

# -------------------------
# Rollout collector & PPO update helpers
# -------------------------
def compute_gae_from_episode(rewards: List[float], values: List[float], dones: List[bool], gamma=GAMMA, lam=GAE_LAMBDA):
    # returns advantages, returns
    advs = []
    gae = 0.0
    next_value = 0.0
    for t in reversed(range(len(rewards))):
        mask = 0.0 if dones[t] else 1.0
        next_v = next_value
        delta = rewards[t] + gamma * next_v * mask - values[t]
        gae = delta + gamma * lam * mask * gae
        advs.insert(0, gae)
        next_value = values[t]
    returns = [a + v for a, v in zip(advs, values)]
    return advs, returns

def ppo_update(model: nn.Module, optimizer: optim.Optimizer,
               batch_states: torch.Tensor, batch_actions: torch.Tensor,
               batch_old_logp: torch.Tensor, batch_returns: torch.Tensor, batch_advs: torch.Tensor,
               clip_eps=CLIP_EPS, ppo_epochs=PPO_EPOCHS, minibatch_size=MINIBATCH_SIZE):
    dataset_size = batch_states.size(0)
    inds = np.arange(dataset_size)
    for _ in range(ppo_epochs):
        np.random.shuffle(inds)
        for start in range(0, dataset_size, minibatch_size):
            bi = inds[start:start+minibatch_size]
            s = batch_states[bi].to(DEVICE)
            a = batch_actions[bi].to(DEVICE)
            old_logp = batch_old_logp[bi].to(DEVICE)
            ret = batch_returns[bi].to(DEVICE)
            adv = batch_advs[bi].to(DEVICE)

            logits, vals = model(s)
            probs = torch.softmax(logits, dim=-1)
            dist = torch.distributions.Categorical(probs)
            new_logp = dist.log_prob(a)

            ratio = torch.exp(new_logp - old_logp)
            surr1 = ratio * adv
            surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * adv
            policy_loss = -torch.min(surr1, surr2).mean()
            value_loss = VALUE_COEF * (ret - vals).pow(2).mean()
            entropy_loss = -ENTROPY_COEF * dist.entropy().mean()
            loss = policy_loss + value_loss + entropy_loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

# -------------------------
# Top-level training loop
# -------------------------
def main():
    global AGENT_POS_REW, AGENT_NEG_PEN

    print("Loading splits...")
    train_trajs, val_trajs, test_trajs = load_splits(SPLIT_PATH)
    print(f"Loaded splits -> train: {len(train_trajs)} val: {len(val_trajs)} test: {len(test_trajs)}")

    # compute agent counts to set balanced rewards/penalties
    counts = {a: 0 for a in AGENT_TYPES}
    for t in train_trajs:
        for s in t.get("sub_tasks", []):
            lab = s.get("_agent_label", "language_agent")
            if lab in counts:
                counts[lab] += 1
    print("Train agent counts:", counts)
    # derive rewards: inverse frequency scaling (simple)
    total = sum(counts.values()) + 1e-12
    pos_base = 2.0  # baseline positive reward
    AGENT_POS_REW = {}
    AGENT_NEG_PEN = {}
    for a in AGENT_TYPES:
        freq = counts[a] / total
        # positive reward = pos_base * (1/freq) normalized
        AGENT_POS_REW[a] = float(pos_base * (1.0 / (freq + 1e-12)) * (1.0 / len(AGENT_TYPES)))
        # penalty: smaller magnitude than positive reward, scaled inversely (but not too big)
        AGENT_NEG_PEN[a] = float(-0.3 * (1.0 / (freq + 1e-12)) * (1.0 / len(AGENT_TYPES)))

    print("Agent step rewards:", AGENT_POS_REW)
    print("Agent incorrect penalties:", AGENT_NEG_PEN)

    # build TF-IDF embedder (train set)
    tfidf = build_tfidf(train_trajs, max_features=5000)
    embed_dim = len(tfidf.get_feature_names_out())
    print(f"[Embedder] Using TF-IDF, dim={embed_dim}")

    # build a single state_dim: embed_dim + (3 scalars) + 2*len(AGENT_TYPES) (history + last_action)
    state_dim = embed_dim + 3 + 2 * len(AGENT_TYPES)
    print(f"STATE_DIM set to {state_dim} (embed_dim {embed_dim} + extras)")

    # model and optimizer
    model = PPOCoordinator(state_dim=state_dim, hidden=512).to(DEVICE)
    optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)

    # training loop variables
    best_val = -1e9

    for epoch in range(1, TOTAL_EPOCHS + 1):
        t0 = time.time()
        # collect rollouts (on-policy) by sampling episodes from train_trajs
        transitions = []  # each element: dict with state, action, logp, reward, value, done
        episodes = 0
        total_reward_accum = 0.0
        correct_actions = 0
        total_actions = 0
        successes = 0

        while len(transitions) < STEPS_PER_UPDATE and episodes < len(train_trajs):
            traj = random.choice(train_trajs)
            env = CoordinatorEnv(traj, tfidf, embed_dim, AGENT_POS_REW, AGENT_NEG_PEN)
            state = env.reset()
            done = False
            ep_rewards = []
            ep_values = []
            ep_logps = []
            ep_states = []
            ep_actions = []
            ep_dones = []
            ep_true_matches = 0
            ep_len = 0

            while not done:
                s_tensor = torch.tensor(state, dtype=torch.float32, device=DEVICE).unsqueeze(0)
                with torch.no_grad():
                    logits, value = model(s_tensor)
                    probs = torch.softmax(logits, dim=-1).squeeze(0)
                dist = torch.distributions.Categorical(probs)
                action = int(dist.sample().item())
                logp = dist.log_prob(torch.tensor(action)).item()
                value_item = float(value.item())

                next_state, reward, done, info = env.step(action)

                # bookkeeping
                transitions.append({
                    "state": state,
                    "action": action,
                    "logp": logp,
                    "reward": reward,
                    "value": value_item,
                    "done": done
                })
                total_reward_accum += reward
                ep_rewards.append(reward)
                ep_values.append(value_item)
                ep_logps.append(logp)
                ep_states.append(state)
                ep_actions.append(action)
                ep_dones.append(done)

                # accuracy: compare to ground-truth for this step
                step_idx = info.get("step_idx", 0)
                true_label = traj.get("sub_tasks", [])[step_idx].get("_agent_label", AGENT_TYPES[1]) if traj.get("sub_tasks") else AGENT_TYPES[1]
                if AGENT_TYPES[action] == true_label:
                    correct_actions += 1
                    ep_true_matches += 1
                total_actions += 1

                ep_len += 1
                state = next_state

                # safety cap: ensure we don't loop forever
                if ep_len > max(1, len(traj.get("sub_tasks", [])) * 3):
                    break

            # episode done
            episodes += 1
            # success determination: finished all steps
            if len(env.executed) >= env.n:
                successes += 1

        # prepare tensors for PPO update
        # collect arrays from transitions
        states = torch.tensor([t["state"] for t in transitions], dtype=torch.float32)
        actions = torch.tensor([t["action"] for t in transitions], dtype=torch.long)
        old_logps = torch.tensor([t["logp"] for t in transitions], dtype=torch.float32)
        rewards = [t["reward"] for t in transitions]
        values = [t["value"] for t in transitions]
        dones = [t["done"] for t in transitions]

        # compute advantages/returns using GAE - do it in one pass (treating transitions as single sequence)
        # For simplicity we compute GAE treating sequence boundaries by 'done' flags
        advantages = []
        returns = []
        gae = 0.0
        next_value = 0.0
        for t in reversed(range(len(rewards))):
            mask = 0.0 if dones[t] else 1.0
            delta = rewards[t] + GAMMA * next_value * mask - values[t]
            gae = delta + GAMMA * GAE_LAMBDA * mask * gae
            advantages.insert(0, gae)
            next_value = values[t]
        returns = [adv + v for adv, v in zip(advantages, values)]

        # normalize advantages
        adv_arr = np.array(advantages, dtype=np.float32)
        if adv_arr.std() > 0:
            adv_arr = (adv_arr - adv_arr.mean()) / (adv_arr.std() + 1e-8)
        else:
            adv_arr = adv_arr - adv_arr.mean()

        # convert batches to tensors
        batch_states = states
        batch_actions = actions
        batch_old_logp = old_logps
        batch_returns = torch.tensor(returns, dtype=torch.float32)
        batch_advs = torch.tensor(advantages, dtype=torch.float32)

        # ppo update
        ppo_update(model, optimizer, batch_states, batch_actions, batch_old_logp, batch_returns, batch_advs)

        # metrics
        avg_reward = total_reward_accum / max(1, len(transitions))
        acc = (correct_actions / max(1, total_actions)) * 100.0
        success_rate = (successes / max(1, episodes)) * 100.0

        t1 = time.time()
        print(f"\n--- Epoch {epoch} --- time {t1-t0:.1f}s")
        print(f"Epoch {epoch} metrics -> Total Steps Collected: {len(transitions)}, Episodes: {episodes}")
        print(f"  Total Reward (sum): {total_reward_accum:.3f}, Avg Reward/step: {avg_reward:.4f}")
        print(f"  Agent selection accuracy: {acc:.2f}%  |  Success Rate (episodes finished): {success_rate:.2f}%")

        # save checkpoint
        torch.save({
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict()
        }, os.path.join(CHECKPOINT_DIR, f"epoch_{epoch}.pth"))

    print("Training finished.")

if __name__ == "__main__":
    main()
