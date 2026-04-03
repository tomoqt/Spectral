# Flywheel Managed Run 2026-04-03

This directory stores the exact output bundle copied back from the Flywheel managed-compute run.

## Provenance

- Flywheel root node: `46607673-7686-50ab-a2da-c66f8cbc4b42` (`dry-hall-6882`)
- empirical run node: `4f7a1266-4718-5c81-8db2-c200ce3eeef8` (`blue-wildflower-3129`)
- execution id: `93b3dc4f-4afb-4cc7-845c-e7c310e81a7a`
- compute lease: `a339bf3a-f905-46cd-8a0c-f069cc7ee77d`
- provider / offer: `modal / modal::modal_a10g`
- run commit: `db5ab17584332164467fb77121c2dbc223fbf468`

## What Ran

Base reproduction:

```bash
python -m tiltrotor_repro.reproduce --output-dir outputs/paper_cases
```

CUDA-X extension:

```bash
pip install -e .[cuda]
pip install nvidia-cuda-nvrtc-cu12
export CUDA_PATH=/root/tiltrotor-open-repro/.venv/lib/python3.11/site-packages/nvidia/cuda_nvrtc
export LD_LIBRARY_PATH=/root/tiltrotor-open-repro/.venv/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib:${LD_LIBRARY_PATH}
python -m tiltrotor_repro.reproduce --output-dir outputs/paper_cases_cuda --enable-cuda-extension
```

## Main Outcome

This run does not exactly reproduce the paper's CFD results. It is an open approximation that reproduces part of the paper's directional structure:

- `C1_twist_improves_hover = true`
- `C5_mp3_is_strongest_compromise = true`

and fails to recover several stronger paper claims under the open model:

- `C2_airplane_gain_exceeds_hover_gain = false`
- `C3_chord_sweep_help_airplane_more_than_hover = false`
- `C4_multi_point_compromise = false`

The CUDA-X extension completed successfully with `cupy_available = true` and produced `multipoint_extension.csv`.
