#include <ATen/ATen.h>
#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAGuard.h>
#include <c10/cuda/CUDAException.h>

#include <cuda.h>
#include <cuda_runtime.h>

namespace {

constexpr int kThreads = 256;

__global__ void rms_norm_kernel(
    const float* input,
    const float* weight,
    float* output,
    int64_t row_count,
    int64_t hidden_size,
    float epsilon
) {
    const auto row = static_cast<int64_t>(blockIdx.x);
    if (row >= row_count) {
        return;
    }
    extern __shared__ float square_sums[];
    const auto offset = row * hidden_size;
    float thread_sum = 0.0F;
    for (int64_t column = threadIdx.x; column < hidden_size; column += blockDim.x) {
        const auto value = input[offset + column];
        thread_sum += value * value;
    }
    square_sums[threadIdx.x] = thread_sum;
    __syncthreads();

    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (threadIdx.x < stride) {
            square_sums[threadIdx.x] += square_sums[threadIdx.x + stride];
        }
        __syncthreads();
    }

    const auto inverse_rms = rsqrtf(square_sums[0] / static_cast<float>(hidden_size) + epsilon);
    for (int64_t column = threadIdx.x; column < hidden_size; column += blockDim.x) {
        output[offset + column] = input[offset + column] * inverse_rms * weight[column];
    }
}

}  // namespace

at::Tensor rms_norm_cuda(const at::Tensor& input, const at::Tensor& weight, double epsilon) {
    TORCH_CHECK(input.is_cuda(), "input must be a CUDA tensor");
    TORCH_CHECK(weight.is_cuda(), "weight must be a CUDA tensor");
    TORCH_CHECK(input.scalar_type() == at::kFloat, "input must use float32");
    TORCH_CHECK(weight.scalar_type() == at::kFloat, "weight must use float32");
    TORCH_CHECK(input.dim() >= 1, "input must have at least one dimension");
    TORCH_CHECK(weight.dim() == 1, "weight must be one-dimensional");
    TORCH_CHECK(
        input.size(-1) == weight.size(0),
        "weight length must match the input hidden dimension"
    );
    TORCH_CHECK(epsilon > 0.0, "epsilon must be positive");

    const c10::cuda::CUDAGuard device_guard(input.device());
    const auto contiguous_input = input.contiguous();
    const auto contiguous_weight = weight.contiguous();
    auto output = at::empty_like(contiguous_input);
    const auto hidden_size = contiguous_input.size(-1);
    const auto row_count = contiguous_input.numel() / hidden_size;
    const auto stream = at::cuda::getCurrentCUDAStream();

    rms_norm_kernel<<<row_count, kThreads, kThreads * sizeof(float), stream>>>(
        contiguous_input.data_ptr<float>(),
        contiguous_weight.data_ptr<float>(),
        output.data_ptr<float>(),
        row_count,
        hidden_size,
        static_cast<float>(epsilon)
    );
    C10_CUDA_KERNEL_LAUNCH_CHECK();
    return output.view(input.sizes());
}
