import torch
from torch import nn

class CNNEmbedding(nn.Module):
    def __init__(self, input_dim:int=6, output_dim:int = 120):
        super().__init__()
        assert output_dim % 3 == 0
        self.Branch1 = nn.Conv1d(in_channels=input_dim, out_channels=output_dim//3, kernel_size=1, padding=0,padding_mode="circular")
        self.Branch2 = nn.Conv1d(in_channels=input_dim, out_channels=output_dim // 3, kernel_size=3, padding=1,padding_mode="circular")
        self.Branch3 = nn.Conv1d(in_channels=input_dim, out_channels=output_dim // 3, kernel_size=5, padding=2,padding_mode="circular")

    def forward(self, x):
        x1 = self.Branch1(x)
        x2 = self.Branch2(x)
        x3 = self.Branch3(x)
        return torch.cat([x1, x2, x3], dim=1)

