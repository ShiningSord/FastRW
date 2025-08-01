import torch.nn as nn

class SmallTempNet(nn.Module):
    """A lightweight CNN mapping power to temperature."""

    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(5, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 5, kernel_size=1)
        )

    def forward(self, x):
        return self.net(x)
