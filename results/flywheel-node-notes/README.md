# Flywheel Node Notes

This directory mirrors the topology-only nodes in the Flywheel graph for the tiltrotor reproduction.

Each markdown file is a small, UI-friendly note for one node that explains:
- what the node means in the paper
- why it exists in the graph
- how it depends on upstream concepts or experiments
- where the executable evidence lives when the node itself is conceptual

Node mapping:
- `wispy-sea-3682.md`: conflict between hover and airplane twist requirements
- `square-brook-6786.md`: public reproducibility boundary for the original HMB3 workflow
- `wandering-moon-1839.md`: public XV-15 geometry and open approximation space
- `bitter-shadow-9715.md`: optimization formulation and objective structure
- `wild-queen-5010.md`: hover single-point family HM1, HM2, HM3
- `red-paper-3383.md`: airplane single-point family AM1, AM2
- `bitter-lake-2114.md`: multi-point family MP1, MP2, MP3
- `delicate-sun-0460.md`: insight that chord and sweep matter more in airplane mode
- `dry-wildflower-4333.md`: insight that multi-point optimization yields compromise blades

Primary executable evidence is attached to the managed-run node `blue-wildflower-3129` and mirrored in the repository under `results/flywheel-managed-run-2026-04-03/`.
