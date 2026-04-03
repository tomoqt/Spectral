# Empirical: Multi-point design family MP1 MP2 MP3

- slug: `bitter-lake-2114`
- kind: `empirical`
- parents: `dry-hall-6882`, `wispy-sea-3682`, `wild-queen-5010`, `red-paper-3383`, `bitter-shadow-9715`

## Summary

Paper multi-point node covering MP1, MP2, and MP3. Reported results: MP1 gives +0.645% FoM and +2.197% eta; MP2 gives +0.645% FoM and +2.686% eta; MP3 gives -0.387% FoM and +4.945% eta. The repo preserves the same weight settings and active-variable sets for open approximation runs.

## Hypothesis

Weighted multi-point optimization should return compromise blades that sacrifice little hover performance while recovering a meaningful portion of the airplane-mode efficiency gain.

## Notes

- This node represents the paper family rather than the open managed run itself.
- The exact executable output bundle for the open approximation is attached on blue-wildflower-3129.
- The CUDA sweep extension hangs off this node as a denser continuation of the same compromise study.
