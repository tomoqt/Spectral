# Insight: Exact HMB3 plus adjoint workflow is not publicly reproducible

- slug: `square-brook-6786`
- kind: `insight`
- parents: `dry-hall-6882`

## Summary

The exact HMB3 CFD plus discrete-adjoint workflow in the paper is not reproducible from the public paper alone, so the repo implements an open approximation that preserves the paper's variables, objectives, and design cases without pretending to recreate the non-public solver stack.

## Notes

- The paper's mesh, flow solver, adjoint implementation, and internal mesh deformation chain are not fully public.
- The open repo therefore reproduces the design-space structure and cost-function logic rather than the exact high-fidelity numerics.
- This node is the boundary condition for interpreting all downstream empirical nodes: paper-reported outcomes are recorded faithfully, while open execution remains an approximation.
