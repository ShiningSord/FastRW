# ResRW

This repository contains a C++ port of the original Python simulation.

## Building the C++ version

The code uses C++11 features such as `std::array` and `std::tuple`. Make sure
that you compile with at least C++11 support and include all source files.

```bash
g++ -std=c++11 main.cpp geometry.cpp walker.cpp -o main
```

Running `./main` will print the temperature estimate for the sample point used
in `main.cpp`.


## Learning power-to-temperature mapping

The `thermal_net` package provides a lightweight PyTorch implementation to
predict temperature distributions from power maps stored as numpy arrays.
The dataset should contain pairs of files named `RR_XXXXX_power.npy` and
`RR_XXXXX_temp.npy` where each array has shape `5x100x100`.
When loading, power values are scaled by `3e11` and temperature values are
normalized from the `20-120` °C range to `[0, 1]`.

Example workflow:

```bash
# generate dummy data
python -m thermal_net.generate_dummy_data --output ./dummy --num_samples 20

# train a network
python -m thermal_net.train --data_dir ./dummy --epochs 1 --batch_size 2 --save_path model.pt

# evaluate on the held-out set
python -m thermal_net.test --data_dir ./dummy --checkpoint model.pt
```

