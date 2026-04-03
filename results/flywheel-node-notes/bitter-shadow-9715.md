# Insight: Paper uses ten-variable fixed-thrust optimization formulation

- slug: `bitter-shadow-9715`
- kind: `insight`
- parents: `dry-hall-6882`, `wispy-sea-3682`, `wandering-moon-1839`

## Summary

The paper's optimization formulation is preserved in the repo: minimize normalized torque coefficient at fixed thrust for single-point problems, and minimize a weighted sum of normalized torque coefficients for hover and airplane conditions in the multi-point cases.

## Notes

- Single-point optimization maps to Eq. (3): minimize CQ/CQ_baseline subject to CT = CT_baseline.
- Multi-point optimization maps to Eq. (7): whm * CQ_hm/CQ_hm_baseline + wam * CQ_am/CQ_am_baseline.
- The design families differ only in which variables are active and what hover versus airplane weights are applied.
