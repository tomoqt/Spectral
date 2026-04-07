# Insight: Public XV-15 geometry and design variables define an open approximation space

- slug: `wandering-moon-1839`
- kind: `insight`
- parents: `dry-hall-6882`

## Summary

Public XV-15 data are sufficient to reconstruct an auditable low-order baseline for an open reproduction: radius 3.81 m, three blades, root cutout 0.0875R, root chord 17 in, tip chord 14 in, total aerodynamic twist 38.7 deg, and the theta75/theta0 relation used in public XV-15 reports.

## Notes

- The repo uses a piecewise-linear baseline twist consistent with the public theta75 = theta0 + 6.61 deg relation.
- The repo uses the paper's public design-variable bounds: seven Bernstein twist variables, two chord variables, and one sweep variable.
- These public quantities define the reproducible approximation space to which the optimization logic is applied.
