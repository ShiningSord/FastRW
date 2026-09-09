#ifndef RANDOM_WALKER_CUDA_H
#define RANDOM_WALKER_CUDA_H

#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "walker.h"

class RandomWalkerCuda {
public:
    RandomWalkerCuda(GeometryConfig& geometry_config, double max_steps = 5e7,
                     double cutoff_weight = 0.01, double delta_x = 5e-7,
                     bool use_tail_correction = true,
                     std::optional<unsigned int> seed = std::nullopt,
                     double power_scale = 1.0,
                     std::string tail_mode = "gt",
                     std::string robin_local_time_mode = "current");
    ~RandomWalkerCuda();

    RandomWalkerCuda(const RandomWalkerCuda&) = delete;
    RandomWalkerCuda& operator=(const RandomWalkerCuda&) = delete;

    double simulate_temperature(const Position& x0_meter, int N = 5000,
                                int threads_per_block = -1,
                                int print_interval = 100);

    std::vector<MultiPointStats> simulate_temperature_multi(
        const std::vector<Position>& start_points, int N = 5000,
        int threads_per_block = -1, int print_interval = 100,
        const std::string& constraints_json = "outputs/constraints.json",
        const std::string& diagnostics_json = "");

private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};

#endif // RANDOM_WALKER_CUDA_H
