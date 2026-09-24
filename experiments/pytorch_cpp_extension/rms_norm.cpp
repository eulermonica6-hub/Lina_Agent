#include <ATen/ATen.h>
#include <ATen/Parallel.h>
#include <torch/library.h>

#include <cmath>

namespace {

at::Tensor rms_norm_cpu(const at::Tensor& input, const at::Tensor& weight, double epsilon) {
    TORCH_CHECK(input.device().is_cpu(), "input must be a CPU tensor");
    TORCH_CHECK(weight.device().is_cpu(), "weight must be a CPU tensor");
    TORCH_CHECK(input.scalar_type() == at::kFloat, "input must use float32");
    TORCH_CHECK(weight.scalar_type() == at::kFloat, "weight must use float32");
    TORCH_CHECK(input.dim() >= 1, "input must have at least one dimension");
    TORCH_CHECK(weight.dim() == 1, "weight must be one-dimensional");
    TORCH_CHECK(
        input.size(-1) == weight.size(0),
        "weight length must match the input hidden dimension"
    );
    TORCH_CHECK(epsilon > 0.0, "epsilon must be positive");

    const auto contiguous_input = input.contiguous();
    const auto contiguous_weight = weight.contiguous();
    auto output = at::empty_like(contiguous_input);
    const auto hidden_size = contiguous_input.size(-1);
    const auto row_count = contiguous_input.numel() / hidden_size;
    const auto* input_data = contiguous_input.data_ptr<float>();
    const auto* weight_data = contiguous_weight.data_ptr<float>();
    auto* output_data = output.data_ptr<float>();

    at::parallel_for(0, row_count, 16, [&](int64_t start, int64_t end) {
        for (int64_t row = start; row < end; ++row) {
            const auto offset = row * hidden_size;
            float square_sum = 0.0F;
            for (int64_t column = 0; column < hidden_size; ++column) {
                const auto value = input_data[offset + column];
                square_sum += value * value;
            }
            const auto inverse_rms = 1.0F / std::sqrt(
                square_sum / static_cast<float>(hidden_size) + static_cast<float>(epsilon)
            );
            for (int64_t column = 0; column < hidden_size; ++column) {
                output_data[offset + column] =
                    input_data[offset + column] * inverse_rms * weight_data[column];
            }
        }
    });
    return output.view(input.sizes());
}

}  // namespace

TORCH_LIBRARY(lina_rms_norm, library) {
    library.def("forward(Tensor input, Tensor weight, float epsilon=1e-6) -> Tensor");
}

TORCH_LIBRARY_IMPL(lina_rms_norm, CPU, library) {
    library.impl("forward", rms_norm_cpu);
}
