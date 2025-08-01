import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torch.optim import Adam
from torch.nn import MSELoss

from .dataset import PowerTempDataset
from .model import SmallTempNet


def train(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    train_ds = PowerTempDataset(args.data_dir, split='train', train_ratio=args.train_ratio)
    val_ds = PowerTempDataset(args.data_dir, split='val', train_ratio=args.train_ratio)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)

    model = SmallTempNet().to(device)
    optim = Adam(model.parameters(), lr=args.lr)
    criterion = MSELoss()

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optim.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()
            optim.step()
            total_loss += loss.item() * x.size(0)
        avg_train = total_loss / len(train_loader.dataset)

        model.eval()
        total_loss = 0.0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                out = model(x)
                loss = criterion(out, y)
                total_loss += loss.item() * x.size(0)
        avg_val = total_loss / len(val_loader.dataset)
        print(f"Epoch {epoch}/{args.epochs} - train loss: {avg_train:.6f} - val loss: {avg_val:.6f}")

    if args.save_path:
        Path(args.save_path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), args.save_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train temperature predictor')
    parser.add_argument('--data_dir', type=str, required=True)
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch_size', type=int, default=4)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--train_ratio', type=float, default=0.8)
    parser.add_argument('--save_path', type=str, default='model.pt')

    train(parser.parse_args())
