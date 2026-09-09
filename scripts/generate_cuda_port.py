"""Regenerate src/walker_cuda.cu from the Metal reference implementation.

The random-walk algorithm remains single-sourced in walker_metal.mm.  This
script translates the portable kernel portion and combines it with a CUDA
runtime host adapter.  Run it after changing the Metal kernel.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
METAL = ROOT / "src" / "walker_metal.mm"
OUT = ROOT / "src" / "walker_cuda.cu"

source = METAL.read_text(encoding="utf-8")
kernel_start = source.index("constant int REGION_BOTTOM")
kernel_end = source.index(")MSL\";", kernel_start)
kernel = source[kernel_start:kernel_end]

kernel = kernel.replace("MetalGeometry", "CudaGeometry")
kernel = kernel.replace("PassRecord", "CudaPassRecord")
kernel = re.sub(r"\bconstant\s+", "const ", kernel)
kernel = re.sub(r"\bdevice\s+", "", kernel)
kernel = re.sub(r"\bthread\s+", "", kernel)
kernel = re.sub(r"\buint\b", "unsigned int", kernel)
kernel = re.sub(r"(?m)^inline\s+", "__device__ __forceinline__ ", kernel)
kernel = re.sub(
    r"(?m)^(\s*)const (int|float) ([A-Z][A-Z0-9_]+) =",
    r"\1constexpr \2 \3 =",
    kernel,
)

signature_start = kernel.index("kernel void simulate_paths_kernel(")
body_start = kernel.index(") {", signature_start) + 3
cuda_signature = """__global__ void simulate_paths_kernel(
    CudaGeometry g,
    const float* power,
    const float* temp,
    const float* points,
    float* out,
    int* steps,
    float* diagnostics,
    const int* target_indices,
    CudaPassRecord* pass_records,
    int* pass_counts,
    int* pass_overflows
) {
    const unsigned int tid = blockIdx.x * blockDim.x + threadIdx.x;
"""
kernel = kernel[:signature_start] + cuda_signature + kernel[body_start:]

helper_start = source.index("int parse_tail_mode(", kernel_end)
helper_end = source.index("} // namespace", helper_start)
helpers = source[helper_start:helper_end]
helpers = helpers.replace("write_metal_diagnostics_to_json", "write_cuda_diagnostics_to_json")

host = r'''

template <typename T>
class CudaBuffer {
public:
    CudaBuffer() = default;
    explicit CudaBuffer(size_t count) { allocate(count); }
    ~CudaBuffer() { if (ptr_) cudaFree(ptr_); }
    CudaBuffer(const CudaBuffer&) = delete;
    CudaBuffer& operator=(const CudaBuffer&) = delete;

    void allocate(size_t count) {
        if (ptr_) cudaFree(ptr_);
        ptr_ = nullptr;
        count_ = count;
        if (count) check_cuda(cudaMalloc(reinterpret_cast<void**>(&ptr_), count * sizeof(T)), "cudaMalloc");
    }
    void upload(const T* source, size_t count) {
        if (count > count_) throw std::runtime_error("CUDA upload exceeds buffer size");
        check_cuda(cudaMemcpy(ptr_, source, count * sizeof(T), cudaMemcpyHostToDevice), "cudaMemcpy H2D");
    }
    void download(T* destination, size_t count) const {
        if (count > count_) throw std::runtime_error("CUDA download exceeds buffer size");
        check_cuda(cudaMemcpy(destination, ptr_, count * sizeof(T), cudaMemcpyDeviceToHost), "cudaMemcpy D2H");
    }
    T* get() { return ptr_; }
    const T* get() const { return ptr_; }
private:
    T* ptr_ = nullptr;
    size_t count_ = 0;
};

} // namespace

struct RandomWalkerCuda::Impl {
    GeometryConfig& geom;
    double max_steps;
    double cutoff_weight;
    double delta_x;
    bool use_tail_correction;
    std::optional<unsigned int> configured_seed;
    double power_scale;
    std::string tail_mode;
    int tail_mode_code;
    std::string robin_local_time_mode;
    int robin_local_time_mode_code;
    CudaBuffer<float> power_buffer;
    CudaBuffer<float> temp_buffer;
    cudaDeviceProp device_properties{};

    Impl(GeometryConfig& geometry_config, double max_steps_, double cutoff_weight_,
         double delta_x_, bool use_tail_correction_, std::optional<unsigned int> seed_,
         double power_scale_, const std::string& tail_mode_,
         const std::string& robin_local_time_mode_)
        : geom(geometry_config), max_steps(max_steps_), cutoff_weight(cutoff_weight_),
          delta_x(delta_x_), use_tail_correction(use_tail_correction_),
          configured_seed(seed_), power_scale(power_scale_), tail_mode(tail_mode_),
          tail_mode_code(parse_tail_mode(tail_mode_)),
          robin_local_time_mode(robin_local_time_mode_),
          robin_local_time_mode_code(parse_robin_local_time_mode(robin_local_time_mode_)) {
        int device_count = 0;
        check_cuda(cudaGetDeviceCount(&device_count), "cudaGetDeviceCount");
        if (device_count <= 0) throw std::runtime_error("No CUDA-capable GPU was found");
        check_cuda(cudaSetDevice(0), "cudaSetDevice");
        check_cuda(cudaGetDeviceProperties(&device_properties, 0), "cudaGetDeviceProperties");
        upload_geometry_data();
        std::cout << "CUDA device: " << device_properties.name
                  << " (compute capability " << device_properties.major << "."
                  << device_properties.minor << ")" << std::endl;
    }

    void upload_geometry_data() {
        const std::vector<float> power = flatten_power_density(geom, power_scale);
        const std::vector<float> temp = flatten_prior_temperature_field(geom);
        power_buffer.allocate(power.size());
        temp_buffer.allocate(temp.size());
        power_buffer.upload(power.data(), power.size());
        temp_buffer.upload(temp.data(), temp.size());
    }

    CudaGeometry make_geometry(unsigned int seed) const {
        CudaGeometry g{};
        g.nx = geom.nx; g.ny = geom.ny; g.nz_heat = geom.nz_heat; g.nz_total = geom.nz_total;
        g.z_bottom_start = geom.z_bottom.first; g.z_bottom_end = geom.z_bottom.second;
        g.z_virtual1_start = geom.z_virtual1.first; g.z_virtual1_end = geom.z_virtual1.second;
        g.z_heat_start = geom.z_heat.first; g.z_heat_end = geom.z_heat.second;
        g.z_virtual2_start = geom.z_virtual2.first; g.z_virtual2_end = geom.z_virtual2.second;
        g.z_top_start = geom.z_top.first; g.z_top_end = geom.z_top.second;
        g.x_size = static_cast<float>(geom.x_size); g.y_size = static_cast<float>(geom.y_size);
        g.xy_resolution = static_cast<float>(geom.xy_resolution);
        g.z_resolution = static_cast<float>(geom.z_resolution);
        g.T_am = static_cast<float>(geom.T_am); g.k_source = static_cast<float>(geom.k_source);
        g.k_medium = static_cast<float>(geom.k_medium);
        g.top_boundary_type = static_cast<int>(geom.top_boundary_type);
        g.bottom_boundary_type = static_cast<int>(geom.bottom_boundary_type);
        g.lateral_boundary_type = static_cast<int>(geom.lateral_boundary_type);
        g.top_boundary_param = static_cast<float>(geom.top_boundary_param);
        g.bottom_boundary_param = static_cast<float>(geom.bottom_boundary_param);
        g.lateral_boundary_param = static_cast<float>(geom.lateral_boundary_param);
        g.eps_dirichlet = static_cast<float>(geom.boundary_epsilon[0]);
        g.eps_neumann = static_cast<float>(geom.boundary_epsilon[1]);
        g.eps_robin = static_cast<float>(geom.boundary_epsilon[2]);
        g.max_steps = static_cast<int>(std::min<double>(max_steps, std::numeric_limits<int>::max()));
        g.cutoff_weight = static_cast<float>(cutoff_weight);
        g.delta_x = static_cast<float>(delta_x);
        g.power_nx = geom.nx + 1; g.power_ny = geom.ny + 1;
        g.use_tail_correction = use_tail_correction ? 1 : 0;
        g.tail_mode = tail_mode_code;
        g.robin_local_time_mode = robin_local_time_mode_code;
        g.seed = seed;
        return g;
    }

    std::vector<MultiPointStats> simulate_temperature_multi(
        const std::vector<Position>& start_points, int N, int requested_threads_per_block,
        int print_interval, const std::string& constraints_json,
        const std::string& diagnostics_json) {
        const int M = static_cast<int>(start_points.size());
        if (M == 0 || N <= 0) return {};

        std::vector<float> points(static_cast<size_t>(M) * 3);
        std::vector<int> target_indices(static_cast<size_t>(M) * 3);
        for (int i = 0; i < M; ++i) {
            points[static_cast<size_t>(i) * 3 + 0] = static_cast<float>(start_points[i][0]);
            points[static_cast<size_t>(i) * 3 + 1] = static_cast<float>(start_points[i][1]);
            points[static_cast<size_t>(i) * 3 + 2] = static_cast<float>(start_points[i][2]);
            target_indices[static_cast<size_t>(i) * 3 + 0] = static_cast<int>(std::floor(start_points[i][0] / geom.z_resolution));
            target_indices[static_cast<size_t>(i) * 3 + 1] = static_cast<int>(std::floor(start_points[i][1] / geom.xy_resolution));
            target_indices[static_cast<size_t>(i) * 3 + 2] = static_cast<int>(std::floor(start_points[i][2] / geom.xy_resolution));
        }
        CudaBuffer<float> points_buffer(points.size());
        CudaBuffer<int> target_indices_buffer(target_indices.size());
        points_buffer.upload(points.data(), points.size());
        target_indices_buffer.upload(target_indices.data(), target_indices.size());

        int threads_per_block = requested_threads_per_block > 0 ? requested_threads_per_block : 256;
        threads_per_block = std::max(1, std::min(threads_per_block, device_properties.maxThreadsPerBlock));
        constexpr int max_samples_per_dispatch = 100;
        const int dispatch_count = (N + max_samples_per_dispatch - 1) / max_samples_per_dispatch;
        std::vector<std::vector<double>> obs_data(N, std::vector<double>(M));
        std::vector<std::vector<PassSample>> all_pass_samples(M);
        std::vector<double> sums(M, 0.0);
        std::vector<long long> step_sums(M, 0);
        std::vector<double> diagnostic_sums(static_cast<size_t>(M) * kDiagnosticStride, 0.0);
        long long pass_overflow_paths = 0;

        const unsigned int seed = configured_seed.value_or(static_cast<unsigned int>(
            std::chrono::high_resolution_clock::now().time_since_epoch().count()));
        const auto sim_start = std::chrono::high_resolution_clock::now();
        for (int sample_offset = 0; sample_offset < N; sample_offset += max_samples_per_dispatch) {
            const int batch_samples = std::min(max_samples_per_dispatch, N - sample_offset);
            const int batch_total = M * batch_samples;
            CudaGeometry g = make_geometry(seed ^
                (static_cast<unsigned int>(sample_offset) * 747796405u + 2891336453u));
            g.point_count = M;
            g.samples_per_point = batch_samples;

            CudaBuffer<float> out_buffer(batch_total);
            CudaBuffer<int> steps_buffer(batch_total);
            CudaBuffer<float> diagnostics_buffer(static_cast<size_t>(batch_total) * kDiagnosticStride);
            CudaBuffer<CudaPassRecord> pass_records_buffer(
                static_cast<size_t>(batch_total) * kMaxPassesPerPath);
            CudaBuffer<int> pass_counts_buffer(batch_total);
            CudaBuffer<int> pass_overflows_buffer(batch_total);

            const int blocks = (batch_total + threads_per_block - 1) / threads_per_block;
            simulate_paths_kernel<<<blocks, threads_per_block>>>(
                g, power_buffer.get(), temp_buffer.get(), points_buffer.get(),
                out_buffer.get(), steps_buffer.get(), diagnostics_buffer.get(),
                target_indices_buffer.get(), pass_records_buffer.get(),
                pass_counts_buffer.get(), pass_overflows_buffer.get());
            check_cuda(cudaGetLastError(), "simulate_paths_kernel launch");
            check_cuda(cudaDeviceSynchronize(), "simulate_paths_kernel execution");

            std::vector<float> out(batch_total);
            std::vector<int> steps(batch_total);
            std::vector<float> diagnostics(static_cast<size_t>(batch_total) * kDiagnosticStride);
            std::vector<CudaPassRecord> pass_records(
                static_cast<size_t>(batch_total) * kMaxPassesPerPath);
            std::vector<int> pass_counts(batch_total);
            std::vector<int> pass_overflows(batch_total);
            out_buffer.download(out.data(), out.size());
            steps_buffer.download(steps.data(), steps.size());
            diagnostics_buffer.download(diagnostics.data(), diagnostics.size());
            pass_records_buffer.download(pass_records.data(), pass_records.size());
            pass_counts_buffer.download(pass_counts.data(), pass_counts.size());
            pass_overflows_buffer.download(pass_overflows.data(), pass_overflows.size());

            for (int i = 0; i < M; ++i) {
                for (int n = 0; n < batch_samples; ++n) {
                    const int sample_index = sample_offset + n;
                    const int batch_index = i * batch_samples + n;
                    const double value = static_cast<double>(out[batch_index]);
                    obs_data[sample_index][i] = value;
                    sums[i] += value;
                    step_sums[i] += steps[batch_index];
                    const size_t diag_base = static_cast<size_t>(i) * kDiagnosticStride;
                    const size_t batch_diag_base = static_cast<size_t>(batch_index) * kDiagnosticStride;
                    for (int k = 0; k < kDiagnosticStride; ++k)
                        diagnostic_sums[diag_base + k] += diagnostics[batch_diag_base + k];
                    if (pass_overflows[batch_index]) ++pass_overflow_paths;
                    const int pass_count = std::min(pass_counts[batch_index], kMaxPassesPerPath);
                    const size_t pass_base = static_cast<size_t>(batch_index) * kMaxPassesPerPath;
                    for (int p = 0; p < pass_count; ++p) {
                        const CudaPassRecord& record = pass_records[pass_base + p];
                        all_pass_samples[i].push_back({record.target_index, record.t_sum,
                            record.e_hat, sample_index, record.step_count, record.record_index});
                    }
                }
            }
        }
        const auto sim_end = std::chrono::high_resolution_clock::now();
        if (pass_overflow_paths > 0) {
            std::cerr << "Warning: CUDA pass-through constraints exceeded max_passes_per_path="
                      << kMaxPassesPerPath << " on " << pass_overflow_paths
                      << " path(s); extra records were dropped." << std::endl;
        }
        write_constraints_to_json(all_pass_samples, M, N, obs_data, constraints_json,
                                  pass_overflow_paths);

        std::vector<MultiPointStats> stats(M);
        for (int i = 0; i < M; ++i) {
            const double mean = sums[i] / N;
            double variance = 0.0;
            if (N > 1) {
                for (int n = 0; n < N; ++n) {
                    const double diff = obs_data[n][i] - mean;
                    variance += diff * diff;
                }
                variance /= N - 1;
            }
            const double mean_variance = variance / N;
            stats[i] = {N, mean, variance, mean_variance, std::sqrt(mean_variance),
                        static_cast<double>(step_sums[i]) / N};
        }
        write_cuda_diagnostics_to_json(geom, start_points, stats, diagnostic_sums, N,
            seed, cutoff_weight, power_scale, tail_mode, robin_local_time_mode,
            diagnostics_json);
        if (print_interval > 0) {
            std::cout << "CUDA simulation complete in "
                      << std::chrono::duration<double>(sim_end - sim_start).count()
                      << " seconds using " << threads_per_block << " threads/block, seed="
                      << seed << ", dispatches=" << dispatch_count << "." << std::endl;
        }
        return stats;
    }
};

RandomWalkerCuda::RandomWalkerCuda(GeometryConfig& geometry_config, double max_steps,
    double cutoff_weight, double delta_x, bool use_tail_correction,
    std::optional<unsigned int> seed, double power_scale, std::string tail_mode,
    std::string robin_local_time_mode)
    : impl(std::make_unique<Impl>(geometry_config, max_steps, cutoff_weight, delta_x,
          use_tail_correction, seed, power_scale, tail_mode, robin_local_time_mode)) {}

RandomWalkerCuda::~RandomWalkerCuda() = default;

double RandomWalkerCuda::simulate_temperature(const Position& x0_meter, int N,
    int threads_per_block, int print_interval) {
    const std::vector<Position> points = {x0_meter};
    const auto stats = impl->simulate_temperature_multi(points, N, threads_per_block,
        print_interval, "outputs/data_cuda_single.json", "");
    return stats.empty() ? 0.0 : stats[0].normal_mean;
}

std::vector<MultiPointStats> RandomWalkerCuda::simulate_temperature_multi(
    const std::vector<Position>& start_points, int N, int threads_per_block,
    int print_interval, const std::string& constraints_json,
    const std::string& diagnostics_json) {
    return impl->simulate_temperature_multi(start_points, N, threads_per_block,
        print_interval, constraints_json, diagnostics_json);
}
'''

preamble = r'''// Generated by scripts/generate_cuda_port.py. Do not edit manually.
// Relative includes keep CUDA 11.x working when a Windows parent directory
// contains an apostrophe, which its response-file parser mishandles in -I paths.
#include "../include/walker_cuda.h"
#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "../third_party/nlohmann/json.hpp"

using json = nlohmann::json;

namespace {
constexpr int kTailModeGt = 0;
constexpr int kTailModeNone = 1;
constexpr int kRobinModeCurrent = 0;
constexpr int kRobinModeEvent = 1;
constexpr int kRobinModeHit = 2;
constexpr int kDiagnosticStride = 28;
constexpr int kMaxPassesPerPath = 1024;

void check_cuda(cudaError_t status, const char* operation) {
    if (status != cudaSuccess) {
        throw std::runtime_error(std::string(operation) + ": " + cudaGetErrorString(status));
    }
}

'''

OUT.write_text(preamble + kernel + "\n\n" + helpers + host, encoding="utf-8")
print(f"generated {OUT}")
