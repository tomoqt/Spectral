# CUDA Extension Summary

This node records the successful CUDA-X extension run on Flywheel managed compute.

## Outcome

- CuPy executed successfully on a Modal A10G lease
- `nvidia-cuda-nvrtc-cu12` was required for NVRTC discovery
- `CUDA_PATH` and `LD_LIBRARY_PATH` were set to the installed NVRTC runtime
- the dense sweep output was written to `multipoint_extension.csv`

## Provenance

- lease id: `a339bf3a-f905-46cd-8a0c-f069cc7ee77d`
- run node: `blue-wildflower-3129`
- execution commit: `db5ab17584332164467fb77121c2dbc223fbf468`

The full shared output bundle is attached on `blue-wildflower-3129`; this node now carries the CUDA-specific subset directly.
