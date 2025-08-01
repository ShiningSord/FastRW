import argparse
import torch
from torch.utils.data import DataLoader
from torch.nn import MSELoss

from .dataset import PowerTempDataset
from .model import SmallTempNet


def evaluate(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    test_ds = PowerTempDataset(args.data_dir, split='val', train_ratio=args.train_ratio)
    loader = DataLoader(test_ds, batch_size=args.batch_size)
    model = SmallTempNet().to(device)
    model.load_state_dict(torch.load(args.checkpoint, map_location=device))
    model.eval()
    criterion = MSELoss()
    total_loss = 0.0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            loss = criterion(out, y)
            total_loss += loss.item() * x.size(0)
    print(f"Test MSE: {total_loss / len(loader.dataset):.6f}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate temperature predictor')
    parser.add_argument('--data_dir', type=str, required=True)
    parser.add_argument('--checkpoint', type=str, required=True)
    parser.add_argument('--batch_size', type=int, default=4)
    parser.add_argument('--train_ratio', type=float, default=0.8)

    evaluate(parser.parse_args())
