# Tiltrotor CFD Part II Open Reproduction

Open, low-budget reproduction of:

Jimenez Garcia, A., Biava, M., Barakos, G. N., Baverstock, K. D., Gates, S., and Mullen, P.,
"Tiltrotor CFD Part II: aerodynamic optimisation of tiltrotor blades,"
*The Aeronautical Journal*, 121(1239), 2017.

This repo does two things:

1. It encodes the paper's claims, experiments, and logical dependencies so they can be mirrored into a non-flat Flywheel graph.
2. It implements a transparent open approximation of the paper's optimization study using a blade-element model and an optional CUDA-X extension path with CuPy.

The exact paper workflow is not publicly reproducible from the paper alone because the original work depends on the in-house `HMB3` solver, its discrete adjoint, and a private Chimera mesh. This repo therefore reproduces the public experimental structure and measures where an open model does and does not match the paper's reported conclusions.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m tiltrotor_repro.reproduce --output-dir outputs/paper_cases
```

Optional CUDA-X extension:

```bash
pip install -e .[cuda]
python -m tiltrotor_repro.reproduce --output-dir outputs/paper_cases_cuda --enable-cuda-extension
```

## Managed Run

The exact managed-compute output set captured from Flywheel is checked into:

- `results/flywheel-managed-run-2026-04-03/`

That directory includes:

- paper-case outputs
- claim checks
- the dense CUDA-X multi-point sweep
- a run manifest with the exact Flywheel node, execution, lease, branch, and run commit

See `PROJECT.md` for the paper-to-repo mapping and modeling boundary.
