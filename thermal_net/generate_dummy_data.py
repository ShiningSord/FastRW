import argparse
from pathlib import Path
import numpy as np


def generate(args):
    Path(args.output).mkdir(parents=True, exist_ok=True)
    for i in range(args.num_samples):
        idx = f"{i:05d}"
        power = np.random.rand(5, 100, 100).astype(np.float32) * 3e11
        temp = np.random.rand(5, 100, 100).astype(np.float32) * 100 + 20  # 20-120
        np.save(Path(args.output) / f"RR_{idx}_power.npy", power)
        np.save(Path(args.output) / f"RR_{idx}_temp.npy", temp)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, required=True)
    parser.add_argument('--num_samples', type=int, default=10)
    generate(parser.parse_args())
