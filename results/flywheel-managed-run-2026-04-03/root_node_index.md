# Root Node Artifact Index

This root node is the entry point for the full Flywheel graph.

## Where The Exact Run Evidence Lives

- managed execution node: `blue-wildflower-3129`
- node id: `4f7a1266-4718-5c81-8db2-c200ce3eeef8`
- execution id: `93b3dc4f-4afb-4cc7-845c-e7c310e81a7a`

That node contains the complete output bundle:

- managed-run README
- run manifest
- design-case results
- paper-claim checks
- reference-vs-open comparison
- CUDA-X sweep output
- tradeoff plot

## Repo Mirror

- repository: `https://github.com/tomoqt/Spectral`
- branch: `codex/tiltrotor-cfd-reproduction`
- documentation commit: `5ecce39d7797e23488ba40a73caee9c3dcf7054f`

## Graph Intent

The graph is not flat. Parent edges encode logical dependence:

- conceptual conflict and public-boundary assumptions feed the formulation node
- hover and airplane empirical families feed the multi-point family
- synthesis claims depend on the specific experiment families that support them
- the CUDA-X extension depends on the multi-point family
