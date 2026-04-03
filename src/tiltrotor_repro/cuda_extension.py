from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CudaSweepResult:
    weight_hover: float
    weight_airplane: float
    alpha9_sweep: float
    objective: float


def cupy_available() -> bool:
    try:
        import cupy  # noqa: F401
    except Exception:
        return False
    return True


def dense_weight_sweep(
    weight_grid,
    sweep_grid,
    hover_cost_fn,
    airplane_cost_fn,
):
    """
    Vectorized helper for optional CUDA-X exploration.

    The caller provides NumPy-compatible functions that accept batched arrays of
    sweep parameters and return normalized hover and airplane costs. When CuPy is
    available the same code path runs on GPU.
    """
    try:
        import cupy as xp  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only on GPU hosts
        raise RuntimeError("CuPy is not available; install the cuda extra first.") from exc

    w = xp.asarray(weight_grid, dtype=xp.float64)
    s = xp.asarray(sweep_grid, dtype=xp.float64)
    ww, ss = xp.meshgrid(w, s, indexing="ij")
    hover_cost = hover_cost_fn(ss)
    airplane_cost = airplane_cost_fn(ss)
    objective = ww * hover_cost + (1.0 - ww) * airplane_cost
    best_idx = xp.argmin(objective, axis=1)

    results = []
    for row, sweep_idx in enumerate(xp.asnumpy(best_idx)):
        results.append(
            CudaSweepResult(
                weight_hover=float(w[row]),
                weight_airplane=float(1.0 - w[row]),
                alpha9_sweep=float(s[sweep_idx]),
                objective=float(objective[row, sweep_idx]),
            )
        )
    return results
