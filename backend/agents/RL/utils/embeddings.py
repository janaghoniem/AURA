import torch.nn as nn

class TaskEmbedding(nn.Module):
    def __init__(self, num_tasks, dim):
        super().__init__()
        self.embed = nn.Embedding(num_tasks, dim)

    def forward(self, task_ids):
        return self.embed(task_ids)
