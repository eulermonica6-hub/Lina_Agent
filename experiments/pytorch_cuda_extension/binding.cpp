#include <ATen/ATen.h>
#include <torch/library.h>

at::Tensor rms_norm_cuda(const at::Tensor& input, const at::Tensor& weight, double epsilon);

TORCH_LIBRARY(lina_rms_norm_cuda, library) {
    library.def("forward(Tensor input, Tensor weight, float epsilon=1e-6) -> Tensor");
}

TORCH_LIBRARY_IMPL(lina_rms_norm_cuda, CUDA, library) {
    library.impl("forward", rms_norm_cuda);
}
