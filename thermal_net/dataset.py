import os
import numpy as np
import torch
from torch.utils.data import Dataset

class PowerTempDataset(Dataset):
    """Dataset for power-temperature pairs stored as numpy arrays.

    Power values are divided by ``power_scale`` (default ``3e11``) while
    temperatures are rescaled from the ``20-120``\u00b0C range to ``[0, 1]``.
    """

    def __init__(self, root_dir, split="train", train_ratio=0.8, power_scale=3e11):
        self.root_dir = root_dir
        self.power_scale = power_scale
        # gather ids from filenames
        ids = []
        for fname in os.listdir(root_dir):
            if fname.startswith("RR_") and fname.endswith("_power.npy"):
                ids.append(fname[len("RR_"):-len("_power.npy")])
        ids = sorted(ids)
        if not ids:
            raise RuntimeError(f"No power/temperature files found in {root_dir}")

        split_idx = int(len(ids) * train_ratio)
        if split == "train":
            self.ids = ids[:split_idx]
        else:
            self.ids = ids[split_idx:]
        if not self.ids:
            raise RuntimeError(f"Split '{split}' has no samples")

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, idx):
        id_str = self.ids[idx]
        p_path = os.path.join(self.root_dir, f"RR_{id_str}_power.npy")
        t_path = os.path.join(self.root_dir, f"RR_{id_str}_temp.npy")
        power = np.load(p_path).astype(np.float32)
        temp = np.load(t_path).astype(np.float32)
        if temp.min() < 20 or temp.max() > 120:
            raise ValueError(f"Temperature range out of bounds in sample {id_str}")
        power = power / self.power_scale
        temp = (temp - 20.0) / 100.0
        return torch.from_numpy(power), torch.from_numpy(temp)
