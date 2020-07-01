r"""This file is allowed to initialize CUDA context when imported."""

import functools
import contextlib
import torch
import torch.cuda
from torch.testing._internal.common_utils import TEST_NUMBA
from torch.testing._internal.common_device_type import tfloat32, tcomplex64, tf32_to_fp32


TEST_CUDA = torch.cuda.is_available()
TEST_MULTIGPU = TEST_CUDA and torch.cuda.device_count() >= 2
CUDA_DEVICE = TEST_CUDA and torch.device("cuda:0")
# note: if ROCm is targeted, TEST_CUDNN is code for TEST_MIOPEN
TEST_CUDNN = TEST_CUDA and torch.backends.cudnn.is_acceptable(torch.tensor(1., device=CUDA_DEVICE))
TEST_CUDNN_VERSION = torch.backends.cudnn.version() if TEST_CUDNN else 0

if TEST_NUMBA:
    import numba.cuda
    TEST_NUMBA_CUDA = numba.cuda.is_available()
else:
    TEST_NUMBA_CUDA = False

# Used below in `initialize_cuda_context_rng` to ensure that CUDA context and
# RNG have been initialized.
__cuda_ctx_rng_initialized = False


# after this call, CUDA context and RNG must have been initialized on each GPU
def initialize_cuda_context_rng():
    global __cuda_ctx_rng_initialized
    assert TEST_CUDA, 'CUDA must be available when calling initialize_cuda_context_rng'
    if not __cuda_ctx_rng_initialized:
        # initialize cuda context and rng for memory tests
        for i in range(torch.cuda.device_count()):
            torch.randn(1, device="cuda:{}".format(i))
        __cuda_ctx_rng_initialized = True


def tf32_is_not_fp32():
    if not torch.cuda.is_available():
        return False
    if torch.cuda.get_device_properties(torch.cuda.current_device()).major < 8:
        return False
    return True


@contextlib.contextmanager
def setup_tf32(dtype, rtol=0.001, atol=1e-5):
    if dtype in {tfloat32, tcomplex64}:
        torch.backends.cuda.matmul.allow_tf32 = True
        if tf32_is_not_fp32():
            yield tf32_to_fp32(dtype), rtol, atol
        else:
            yield tf32_to_fp32(dtype), None, None
    else:
        if dtype in {torch.float32, torch.complex64}:
            torch.backends.cuda.matmul.allow_tf32 = False
        yield dtype, None, None
    torch.backends.cuda.matmul.allow_tf32 = True


def tf32_on_and_off(rtol_=0.001, atol_=1e-5):
    def wrapper(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            rtol, atol = (rtol_, atol_) if tf32_is_not_fp32() else (None, None)
            torch.backends.cuda.matmul.allow_tf32 = True
            f(*args, **kwargs, rtol=rtol, atol=atol)
            torch.backends.cuda.matmul.allow_tf32 = False
            f(*args, **kwargs, rtol=None, atol=None)
            torch.backends.cuda.matmul.allow_tf32 = True

        return wrapped
    return wrapper
