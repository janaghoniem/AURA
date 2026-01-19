import torch
from collections import defaultdict

class DTDataset(torch.utils.data.Dataset):
    def __init__(self, transitions, max_len=20):
        self.max_len = max_len
        self.episodes = defaultdict(list)

        for t in transitions:
            self.episodes[t["episode_id"]].append(t)

        self.episodes = list(self.episodes.values())

    def __len__(self):
        return len(self.episodes)

    def __getitem__(self, idx):
        ep = self.episodes[idx][-self.max_len:]

        states = torch.tensor([t["state"] for t in ep])
        actions = torch.tensor([t["action"] for t in ep])
        rtg = torch.tensor([t["return_to_go"] for t in ep])
        task_id = torch.tensor(ep[0]["task_id"])

        return states, actions, rtg, task_id
