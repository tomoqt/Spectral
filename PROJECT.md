# Tiltrotor CFD Part II Open Reproduction

This repository reconstructs the public, reproducible part of:

Jimenez Garcia, A., Biava, M., Barakos, G. N., Baverstock, K. D., Gates, S., and Mullen, P.,
"Tiltrotor CFD Part II: aerodynamic optimisation of tiltrotor blades,"
*The Aeronautical Journal*, 121(1239), 2017.

## Scope

The paper's exact solver stack is not publicly reproducible from the paper alone:

- flow solver: `HMB3`
- gradients: discrete adjoint tied to `HMB3`
- mesh deformation: inverse-distance weighting inside the in-house tool chain
- mesh: 6.2 million-cell Chimera XV-15 mesh from Part I

This repo therefore does two separate jobs:

1. It encodes the paper's claims, experiments, variables, and dependencies in a machine-readable form for Flywheel.
2. It implements an open, low-budget reproduction of the design study with a blade-element model that matches the paper's public design variables, trim condition, and single-point / multi-point objective structure.

The result is not a claim of exact HMB3 replication. It is a transparent, reproducible approximation that can be audited, extended, and rerun cheaply.

## Paper Facts Captured Here

- XV-15 rotor radius: `3.81 m`
- blades: `3`
- root cutout: `0.0875 R`
- baseline chord: `0.432 m` at `0.0875 R`, `0.356 m` at tip
- baseline aerodynamic twist: approximated as piecewise-linear, consistent with the public `theta_75 = theta_0 + 6.61 deg` relation and total aerodynamic twist of `38.7 deg`
- twist parameterization: 7 Bernstein coefficients `alpha0..alpha6`, bounded in `[-5 deg, +5 deg]`
- chord parameterization: `alpha7`, `alpha8`
- sweep parameterization: `alpha9`
- hover design cases: `HM1`, `HM2`, `HM3`
- airplane design cases: `AM1`, `AM2`
- multi-point design cases: `MP1`, `MP2`, `MP3`

Reference paper results are included so each open reproduction run can be compared against the reported values.

## Model Boundary

The open model captures the paper's design logic:

- trim every candidate blade to the baseline thrust coefficient at each operating point
- minimize normalized torque coefficient
- compute hover figure of merit and airplane propulsive efficiency
- compare twist-only versus twist+chord+sweep cases
- solve single-point and weighted two-point optimization problems with `SLSQP`

The open model does not resolve:

- viscous/transonic 3D rotor flow at CFD fidelity
- overset-grid wake interaction
- adjoint gradients
- the paper's exact mesh or turbulence closure details

## Reproduction Commands

Create an environment and install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run all paper cases:

```bash
python -m tiltrotor_repro.reproduce --output-dir outputs/paper_cases
```

Run the optional CUDA-X extension:

```bash
python -m tiltrotor_repro.reproduce --output-dir outputs/paper_cases --enable-cuda-extension
```

## Expected Outputs

The runner writes:

- `reference_vs_open.csv`
- `design_case_results.json`
- `design_case_results.csv`
- `paper_claim_checks.json`
- `multipoint_extension.csv` when the CUDA path is enabled and available

## Flywheel Mapping

`paper/claims.yaml` is intended to map one-to-one onto Flywheel nodes:

- conceptual assumptions become `insight` nodes
- each experimental family becomes an `empirical` node
- synthesis claims become `insight` nodes with parent edges pointing to the experiments they depend on

That topology is deliberately non-flat so the graph itself captures the paper's causal and logical structure.
