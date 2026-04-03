from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.optimize import minimize

from .cuda_extension import cupy_available, dense_weight_sweep


SEA_LEVEL_SPEED_OF_SOUND = 340.294
SEA_LEVEL_DENSITY = 1.225
FEET_TO_METERS = 0.3048
INCH_TO_METERS = 0.0254


@dataclass(frozen=True)
class FlightCondition:
    name: str
    mode: str
    tip_mach: float
    theta75_deg: float
    axial_ratio: float
    density: float
    speed_of_sound: float
    reference_reynolds: float

    @property
    def tip_speed(self) -> float:
        return self.tip_mach * self.speed_of_sound

    @property
    def omega(self) -> float:
        return self.tip_speed / RotorModel.R

    @property
    def v_inf(self) -> float:
        return self.axial_ratio * self.tip_speed


@dataclass(frozen=True)
class DesignCase:
    name: str
    hover_condition: FlightCondition | None
    airplane_condition: FlightCondition | None
    optimize_chord_and_sweep: bool
    hover_weight: float
    airplane_weight: float


@dataclass(frozen=True)
class CaseResult:
    case: str
    mode: str
    ct: float
    cq: float
    figure_of_merit: float | None
    eta: float | None
    delta_fom_pct: float | None
    delta_eta_pct: float | None
    trim_collective_deg: float
    design_vector: list[float]


class RotorModel:
    B = 3
    R = 12.5 * FEET_TO_METERS / 2.0
    A = math.pi * R * R
    CUTOUT = 0.0875
    R75 = 0.75
    C_ROOT = 17.0 * INCH_TO_METERS
    C_TIP = 14.0 * INCH_TO_METERS
    TWIST_ROOT = 38.7
    TWIST_75 = 6.61
    TWIST_TIP = 0.0

    def __init__(self, n_stations: int = 56) -> None:
        self.rhat = np.linspace(max(self.CUTOUT, 0.12), 0.995, n_stations)
        self.dr = np.gradient(self.rhat) * self.R

    def baseline_twist_deg(self, rhat: np.ndarray) -> np.ndarray:
        inboard = np.interp(rhat, [self.CUTOUT, self.R75], [self.TWIST_ROOT, self.TWIST_75])
        outboard = np.interp(rhat, [self.R75, 1.0], [self.TWIST_75, self.TWIST_TIP])
        return np.where(rhat <= self.R75, inboard, outboard)

    def baseline_chord(self, rhat: np.ndarray) -> np.ndarray:
        return np.interp(rhat, [self.CUTOUT, 1.0], [self.C_ROOT, self.C_TIP])

    @staticmethod
    def bernstein_basis(order: int, idx: int, x: np.ndarray) -> np.ndarray:
        coeff = math.comb(order, idx)
        return coeff * np.power(x, idx) * np.power(1.0 - x, order - idx)

    def twist_perturbation_deg(self, alpha: np.ndarray) -> np.ndarray:
        x = self.rhat
        total = np.zeros_like(x)
        for i, val in enumerate(alpha[:7]):
            total += val * self.bernstein_basis(6, i, x)
        return total

    def chord_distribution(self, alpha: np.ndarray) -> np.ndarray:
        base = self.baseline_chord(self.rhat)
        alpha7 = alpha[7]
        alpha8 = alpha[8]

        scale = np.ones_like(self.rhat)
        mask_mid = (self.rhat >= 0.25) & (self.rhat <= 0.8)
        scale[mask_mid] = alpha7

        mask_inboard = (self.rhat >= 0.2) & (self.rhat < 0.25)
        if np.any(mask_inboard):
            scale[mask_inboard] = np.interp(self.rhat[mask_inboard], [0.2, 0.25], [1.0, alpha7])

        mask_tip = self.rhat > 0.8
        if np.any(mask_tip):
            eta = (self.rhat[mask_tip] - 0.8) / 0.2
            scale[mask_tip] = alpha7 + (alpha8 - alpha7) * eta * eta

        return base * scale

    def sweep_offset(self, alpha: np.ndarray) -> np.ndarray:
        sweep = np.zeros_like(self.rhat)
        alpha9 = alpha[9]
        mask_tip = self.rhat > 0.8
        if np.any(mask_tip):
            eta = (self.rhat[mask_tip] - 0.8) / 0.2
            sweep[mask_tip] = alpha9 * eta * eta
        return sweep

    def sweep_angle_rad(self, alpha: np.ndarray) -> np.ndarray:
        offset = self.sweep_offset(alpha)
        x = self.rhat * self.R
        dydx = np.gradient(offset, x)
        return np.arctan(dydx)

    def local_pitch_deg(self, alpha: np.ndarray) -> np.ndarray:
        return self.baseline_twist_deg(self.rhat) + self.twist_perturbation_deg(alpha)

    def evaluate(
        self,
        condition: FlightCondition,
        alpha: np.ndarray,
        collective_offset_deg: float,
    ) -> tuple[float, float, float, float]:
        r = self.rhat * self.R
        chord = self.chord_distribution(alpha)
        sweep = self.sweep_angle_rad(alpha)
        local_pitch = np.deg2rad(self.local_pitch_deg(alpha) + collective_offset_deg)
        tip_speed = condition.tip_speed
        omega = condition.omega
        v_inf = condition.v_inf
        rho = condition.density

        ct_guess = 0.006 if condition.mode == "hover" else 0.003
        lambda_i = self._induced_inflow(condition.axial_ratio, ct_guess)

        for _ in range(25):
            u_t = omega * r
            u_a = v_inf + lambda_i * tip_speed
            phi = np.arctan2(u_a, u_t)
            v_rel = np.sqrt(u_t * u_t + u_a * u_a)
            mach_local = v_rel / condition.speed_of_sound
            alpha_eff = local_pitch - phi

            cl_alpha = (2.0 * math.pi) / np.sqrt(np.maximum(1.0 - np.minimum(mach_local, 0.92) ** 2, 0.15))
            cl = np.clip(cl_alpha * alpha_eff, -1.35, 1.35)

            reynolds_scale = np.clip(condition.reference_reynolds / 3.0e6, 0.6, 2.0)
            cd0 = 0.0095 + 0.0018 * (1.0 / reynolds_scale)
            cd_profile = cd0 + 0.0105 * cl * cl
            mach_normal = mach_local * np.cos(sweep)
            wave_drag = 0.18 * np.maximum(mach_normal - 0.72, 0.0) ** 4
            tip_drag = 0.012 * np.maximum(self.rhat - 0.85, 0.0) * np.maximum(mach_normal - 0.68, 0.0)
            cd = cd_profile + wave_drag + tip_drag

            q = 0.5 * rho * v_rel * v_rel
            d_lift = q * chord * cl * self.dr
            d_drag = q * chord * cd * self.dr

            d_thrust = self.B * (d_lift * np.cos(phi) - d_drag * np.sin(phi))
            d_torque = self.B * r * (d_lift * np.sin(phi) + d_drag * np.cos(phi))

            thrust = float(np.sum(d_thrust))
            torque = float(np.sum(d_torque))
            ct = thrust / (rho * self.A * tip_speed * tip_speed)
            new_lambda_i = self._induced_inflow(condition.axial_ratio, ct)
            if abs(new_lambda_i - lambda_i) < 1.0e-5:
                lambda_i = new_lambda_i
                break
            lambda_i = 0.5 * (lambda_i + new_lambda_i)

        cq = torque / (rho * self.A * tip_speed * tip_speed * self.R)
        fom = ct ** 1.5 / (math.sqrt(2.0) * cq) if condition.mode == "hover" else 0.0
        eta = (ct * condition.v_inf) / (cq * tip_speed) if condition.mode == "airplane" and cq > 0.0 else 0.0
        return ct, cq, fom, eta

    @staticmethod
    def _induced_inflow(axial_ratio: float, ct: float) -> float:
        mu = axial_ratio
        return -0.5 * mu + math.sqrt(max(0.25 * mu * mu + max(ct, 1.0e-6) / 2.0, 1.0e-8))


class PaperReproduction:
    def __init__(self) -> None:
        self.model = RotorModel()
        self.hover_medium = FlightCondition(
            name="hover_medium",
            mode="hover",
            tip_mach=0.69,
            theta75_deg=7.0,
            axial_ratio=0.0,
            density=SEA_LEVEL_DENSITY,
            speed_of_sound=SEA_LEVEL_SPEED_OF_SOUND,
            reference_reynolds=4.95e6,
        )
        self.hover_high = FlightCondition(
            name="hover_high",
            mode="hover",
            tip_mach=0.69,
            theta75_deg=10.0,
            axial_ratio=0.0,
            density=SEA_LEVEL_DENSITY,
            speed_of_sound=SEA_LEVEL_SPEED_OF_SOUND,
            reference_reynolds=4.95e6,
        )
        self.airplane = FlightCondition(
            name="airplane_cruise",
            mode="airplane",
            tip_mach=0.60,
            theta75_deg=47.0,
            axial_ratio=0.759,
            density=0.6527,
            speed_of_sound=316.0,
            reference_reynolds=2.2e6,
        )
        self.baseline_alpha = np.array([0.0] * 7 + [1.0, 1.0, 0.0], dtype=float)
        self.reference_table = {
            "HM1": {"delta_fom_pct": 3.081, "delta_eta_pct": None},
            "HM2": {"delta_fom_pct": 1.988, "delta_eta_pct": None},
            "HM3": {"delta_fom_pct": 2.046, "delta_eta_pct": None},
            "AM1": {"delta_fom_pct": None, "delta_eta_pct": 6.593},
            "AM2": {"delta_fom_pct": None, "delta_eta_pct": 8.180},
            "MP1": {"delta_fom_pct": 0.645, "delta_eta_pct": 2.197},
            "MP2": {"delta_fom_pct": 0.645, "delta_eta_pct": 2.686},
            "MP3": {"delta_fom_pct": -0.387, "delta_eta_pct": 4.945},
        }

    def baseline_trimmed_metrics(self, condition: FlightCondition) -> tuple[float, float, float, float, float]:
        trim_deg = condition.theta75_deg - self.model.TWIST_75
        ct, cq, fom, eta = self.model.evaluate(condition, self.baseline_alpha, trim_deg)
        return trim_deg, ct, cq, fom, eta

    def trim_collective(
        self,
        condition: FlightCondition,
        alpha: np.ndarray,
        target_ct: float,
    ) -> tuple[float, float, float, float, float]:
        lower = condition.theta75_deg - self.model.TWIST_75 - 20.0
        upper = condition.theta75_deg - self.model.TWIST_75 + 20.0

        for _ in range(60):
            mid = 0.5 * (lower + upper)
            ct, cq, fom, eta = self.model.evaluate(condition, alpha, mid)
            if ct < target_ct:
                lower = mid
            else:
                upper = mid
        trim_deg = 0.5 * (lower + upper)
        ct, cq, fom, eta = self.model.evaluate(condition, alpha, trim_deg)
        return trim_deg, ct, cq, fom, eta

    def case_definitions(self) -> list[DesignCase]:
        return [
            DesignCase("HM1", self.hover_medium, None, False, 1.0, 0.0),
            DesignCase("HM2", self.hover_high, None, False, 1.0, 0.0),
            DesignCase("HM3", self.hover_high, None, True, 1.0, 0.0),
            DesignCase("AM1", None, self.airplane, False, 0.0, 1.0),
            DesignCase("AM2", None, self.airplane, True, 0.0, 1.0),
            DesignCase("MP1", self.hover_high, self.airplane, False, 0.5, 0.5),
            DesignCase("MP2", self.hover_high, self.airplane, False, 1.0 / 3.0, 2.0 / 3.0),
            DesignCase("MP3", self.hover_high, self.airplane, True, 1.0 / 3.0, 2.0 / 3.0),
        ]

    def optimize_case(self, case: DesignCase) -> list[CaseResult]:
        alpha0 = self.baseline_alpha.copy()
        bounds: list[tuple[float, float]] = [(-5.0, 5.0)] * 7 + [(1.0, 1.0), (1.0, 1.0), (0.0, 0.0)]
        if case.optimize_chord_and_sweep:
            bounds[7] = (0.85, 1.15)
            bounds[8] = (0.50, 1.50)
            bounds[9] = (-0.5 * self.model.C_TIP, 0.15 * self.model.C_TIP)

        hover_targets = {}
        airplane_targets = {}
        if case.hover_condition is not None:
            _, ct0, cq0, fom0, _ = self.baseline_trimmed_metrics(case.hover_condition)
            hover_targets = {"ct": ct0, "cq": cq0, "fom": fom0}
        if case.airplane_condition is not None:
            _, ct0, cq0, _, eta0 = self.baseline_trimmed_metrics(case.airplane_condition)
            airplane_targets = {"ct": ct0, "cq": cq0, "eta": eta0}

        def objective(x: np.ndarray) -> float:
            total = 0.0
            if case.hover_condition is not None:
                _, _, cq, _, _ = self.trim_collective(case.hover_condition, x, hover_targets["ct"])
                total += case.hover_weight * (cq / hover_targets["cq"])
            if case.airplane_condition is not None:
                _, _, cq, _, _ = self.trim_collective(case.airplane_condition, x, airplane_targets["ct"])
                total += case.airplane_weight * (cq / airplane_targets["cq"])
            return total

        result = minimize(
            objective,
            alpha0,
            method="SLSQP",
            bounds=bounds,
            options={"maxiter": 60, "disp": False, "ftol": 1.0e-6},
        )
        alpha_star = result.x
        outputs: list[CaseResult] = []

        if case.hover_condition is not None:
            trim_deg, ct, cq, fom, _ = self.trim_collective(case.hover_condition, alpha_star, hover_targets["ct"])
            delta_fom_pct = 100.0 * (fom / hover_targets["fom"] - 1.0)
            outputs.append(
                CaseResult(
                    case=case.name,
                    mode="hover",
                    ct=ct,
                    cq=cq,
                    figure_of_merit=fom,
                    eta=None,
                    delta_fom_pct=delta_fom_pct,
                    delta_eta_pct=None,
                    trim_collective_deg=trim_deg,
                    design_vector=[float(v) for v in alpha_star],
                )
            )
        if case.airplane_condition is not None:
            trim_deg, ct, cq, _, eta = self.trim_collective(case.airplane_condition, alpha_star, airplane_targets["ct"])
            delta_eta_pct = 100.0 * (eta / airplane_targets["eta"] - 1.0)
            outputs.append(
                CaseResult(
                    case=case.name,
                    mode="airplane",
                    ct=ct,
                    cq=cq,
                    figure_of_merit=None,
                    eta=eta,
                    delta_fom_pct=None,
                    delta_eta_pct=delta_eta_pct,
                    trim_collective_deg=trim_deg,
                    design_vector=[float(v) for v in alpha_star],
                )
            )
        return outputs

    def run_all(self) -> list[CaseResult]:
        all_results: list[CaseResult] = []
        for case in self.case_definitions():
            all_results.extend(self.optimize_case(case))
        return all_results

    def claim_checks(self, results: Iterable[CaseResult]) -> dict[str, object]:
        by_case_mode = {(r.case, r.mode): r for r in results}
        return {
            "C1_twist_improves_hover": by_case_mode[("HM1", "hover")].delta_fom_pct > 0.0
            and by_case_mode[("HM2", "hover")].delta_fom_pct > 0.0,
            "C2_airplane_gain_exceeds_hover_gain": by_case_mode[("AM1", "airplane")].delta_eta_pct
            > by_case_mode[("HM2", "hover")].delta_fom_pct,
            "C3_chord_sweep_help_airplane_more_than_hover": (
                by_case_mode[("AM2", "airplane")].delta_eta_pct - by_case_mode[("AM1", "airplane")].delta_eta_pct
            )
            > (
                by_case_mode[("HM3", "hover")].delta_fom_pct - by_case_mode[("HM2", "hover")].delta_fom_pct
            ),
            "C4_multi_point_compromise": by_case_mode[("MP1", "hover")].delta_fom_pct > -1.0
            and by_case_mode[("MP1", "airplane")].delta_eta_pct > 0.0,
            "C5_mp3_is_strongest_compromise": by_case_mode[("MP3", "airplane")].delta_eta_pct
            > by_case_mode[("MP1", "airplane")].delta_eta_pct
            and by_case_mode[("MP3", "airplane")].delta_eta_pct > by_case_mode[("MP2", "airplane")].delta_eta_pct,
            "C6_adjoint_efficiency": "recorded_from_paper_only",
        }

    def reference_vs_open_rows(self, results: Iterable[CaseResult]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        by_case_mode = {(r.case, r.mode): r for r in results}
        for case, ref in self.reference_table.items():
            hover = by_case_mode.get((case, "hover"))
            airplane = by_case_mode.get((case, "airplane"))
            rows.append(
                {
                    "case": case,
                    "paper_delta_fom_pct": ref["delta_fom_pct"],
                    "open_delta_fom_pct": None if hover is None else hover.delta_fom_pct,
                    "paper_delta_eta_pct": ref["delta_eta_pct"],
                    "open_delta_eta_pct": None if airplane is None else airplane.delta_eta_pct,
                }
            )
        return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot_comparison(path: Path, rows: list[dict[str, object]]) -> None:
    labels = [row["case"] for row in rows]
    eta_open = [0.0 if row["open_delta_eta_pct"] is None else row["open_delta_eta_pct"] for row in rows]
    fom_open = [0.0 if row["open_delta_fom_pct"] is None else row["open_delta_fom_pct"] for row in rows]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(eta_open, fom_open, c="black")
    for label, x, y in zip(labels, eta_open, fom_open):
        ax.annotate(label, (x, y))
    ax.set_xlabel("Open reproduction delta eta [%]")
    ax.set_ylabel("Open reproduction delta FoM [%]")
    ax.set_title("Open reproduction trade-off map for paper design cases")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def case_color(case: str) -> str:
    if case.startswith("HM"):
        return "#1f77b4"
    if case.startswith("AM"):
        return "#d62728"
    if case.startswith("MP"):
        return "#2ca02c"
    return "#4c4c4c"


def plot_case_metric_summary(path: Path, results: list[CaseResult]) -> None:
    hover_rows = [row for row in results if row.mode == "hover"]
    airplane_rows = [row for row in results if row.mode == "airplane"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    hover_cases = [row.case for row in hover_rows]
    hover_values = [0.0 if row.delta_fom_pct is None else row.delta_fom_pct for row in hover_rows]
    hover_colors = [case_color(row.case) for row in hover_rows]
    axes[0].bar(hover_cases, hover_values, color=hover_colors)
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_ylabel("Delta FoM [%]")
    axes[0].set_title("Hover outcomes")
    for label, value in zip(hover_cases, hover_values):
        axes[0].annotate(f"{value:.2f}", (label, value), xytext=(0, 3), textcoords="offset points", ha="center")

    airplane_cases = [row.case for row in airplane_rows]
    airplane_values = [0.0 if row.delta_eta_pct is None else row.delta_eta_pct for row in airplane_rows]
    airplane_colors = [case_color(row.case) for row in airplane_rows]
    axes[1].bar(airplane_cases, airplane_values, color=airplane_colors)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_ylabel("Delta eta [%]")
    axes[1].set_title("Airplane outcomes")
    for label, value in zip(airplane_cases, airplane_values):
        axes[1].annotate(f"{value:.2f}", (label, value), xytext=(0, 3), textcoords="offset points", ha="center")

    fig.suptitle("Open reproduction metrics by design case")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_paper_vs_open_deltas(path: Path, rows: list[dict[str, object]]) -> None:
    hover_rows = [row for row in rows if row["paper_delta_fom_pct"] is not None]
    airplane_rows = [row for row in rows if row["paper_delta_eta_pct"] is not None]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    width = 0.36

    hover_labels = [str(row["case"]) for row in hover_rows]
    hover_x = np.arange(len(hover_labels))
    hover_paper = [float(row["paper_delta_fom_pct"]) for row in hover_rows]
    hover_open = [float(row["open_delta_fom_pct"]) for row in hover_rows]
    axes[0].bar(hover_x - width / 2.0, hover_paper, width=width, label="Paper", color="#7f7f7f")
    axes[0].bar(hover_x + width / 2.0, hover_open, width=width, label="Open", color="#1f77b4")
    axes[0].set_xticks(hover_x, hover_labels)
    axes[0].set_ylabel("Delta FoM [%]")
    axes[0].set_title("Hover-family and compromise hover deltas")
    axes[0].legend(frameon=False)

    airplane_labels = [str(row["case"]) for row in airplane_rows]
    airplane_x = np.arange(len(airplane_labels))
    airplane_paper = [float(row["paper_delta_eta_pct"]) for row in airplane_rows]
    airplane_open = [float(row["open_delta_eta_pct"]) for row in airplane_rows]
    axes[1].bar(airplane_x - width / 2.0, airplane_paper, width=width, label="Paper", color="#7f7f7f")
    axes[1].bar(airplane_x + width / 2.0, airplane_open, width=width, label="Open", color="#d62728")
    axes[1].set_xticks(airplane_x, airplane_labels)
    axes[1].set_ylabel("Delta eta [%]")
    axes[1].set_title("Airplane-family and compromise cruise deltas")

    fig.suptitle("Paper-reported deltas versus open reproduction deltas")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_geometry_distributions(path: Path, repro: PaperReproduction, results: list[CaseResult]) -> None:
    selected = ["Baseline", "HM2", "HM3", "AM2", "MP3"]
    vectors: dict[str, np.ndarray] = {"Baseline": repro.baseline_alpha.copy()}
    for row in results:
        if row.case not in vectors:
            vectors[row.case] = np.asarray(row.design_vector, dtype=float)

    radius = repro.model.rhat
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True, constrained_layout=True)

    for label in selected:
        alpha = vectors.get(label)
        if alpha is None:
            continue
        axes[0].plot(radius, repro.model.local_pitch_deg(alpha), label=label, linewidth=2.0)
        axes[1].plot(radius, repro.model.chord_distribution(alpha), label=label, linewidth=2.0)
        axes[2].plot(radius, repro.model.sweep_offset(alpha) / repro.model.C_TIP, label=label, linewidth=2.0)

    axes[0].set_ylabel("Pitch distribution [deg]")
    axes[0].set_title("Twist-driven design changes")
    axes[1].set_ylabel("Chord [m]")
    axes[1].set_title("Chord schedule changes")
    axes[2].set_ylabel("Sweep offset / c_tip [-]")
    axes[2].set_xlabel("Radius fraction r/R")
    axes[2].set_title("Tip sweep offset changes")
    axes[0].legend(frameon=False, ncol=3)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_cuda_weight_sweep(path: Path, rows: list[dict[str, object]], tip_chord: float) -> None:
    if not rows:
        return

    sorted_rows = sorted(rows, key=lambda row: float(row["weight_hover"]))
    weight_hover = np.asarray([float(row["weight_hover"]) for row in sorted_rows], dtype=float)
    objective = np.asarray([float(row["objective"]) for row in sorted_rows], dtype=float)
    alpha9 = np.asarray([float(row["alpha9_sweep"]) for row in sorted_rows], dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    axes[0].plot(weight_hover, objective, color="#2ca02c", marker="o")
    axes[0].set_xlabel("Hover weight")
    axes[0].set_ylabel("Weighted normalized objective")
    axes[0].set_title("CUDA dense sweep objective by weighting")

    axes[1].plot(weight_hover, alpha9 / tip_chord, color="#9467bd", marker="o")
    axes[1].set_xlabel("Hover weight")
    axes[1].set_ylabel("Selected sweep / c_tip [-]")
    axes[1].set_title("CUDA dense sweep optimum sweep setting")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_cuda_extension(repro: PaperReproduction, output_dir: Path) -> list[dict[str, object]]:
    if not cupy_available():
        return []

    hover_target = repro.baseline_trimmed_metrics(repro.hover_high)
    airplane_target = repro.baseline_trimmed_metrics(repro.airplane)

    def hover_cost_fn(alpha9_values):
        is_cupy = hasattr(alpha9_values, "get")
        flat_alpha9 = alpha9_values.get().reshape(-1) if is_cupy else np.asarray(alpha9_values).reshape(-1)
        values = []
        for alpha9 in flat_alpha9:
            alpha = repro.baseline_alpha.copy()
            alpha[9] = float(alpha9)
            _, _, cq, _, _ = repro.trim_collective(repro.hover_high, alpha, hover_target[1])
            values.append(cq / hover_target[2])
        out = np.asarray(values).reshape(alpha9_values.shape)
        if is_cupy:
            import cupy as cp  # type: ignore

            return cp.asarray(out)
        return out

    def airplane_cost_fn(alpha9_values):
        is_cupy = hasattr(alpha9_values, "get")
        flat_alpha9 = alpha9_values.get().reshape(-1) if is_cupy else np.asarray(alpha9_values).reshape(-1)
        values = []
        for alpha9 in flat_alpha9:
            alpha = repro.baseline_alpha.copy()
            alpha[7] = 0.92
            alpha[8] = 0.72
            alpha[9] = float(alpha9)
            _, _, cq, _, _ = repro.trim_collective(repro.airplane, alpha, airplane_target[1])
            values.append(cq / airplane_target[2])
        out = np.asarray(values).reshape(alpha9_values.shape)
        if is_cupy:
            import cupy as cp  # type: ignore

            return cp.asarray(out)
        return out

    weights = np.linspace(0.05, 0.95, 19)
    sweeps = np.linspace(-0.5 * repro.model.C_TIP, 0.15 * repro.model.C_TIP, 29)
    rows = [asdict(item) for item in dense_weight_sweep(weights, sweeps, hover_cost_fn, airplane_cost_fn)]
    write_csv(output_dir / "multipoint_extension.csv", rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the open tiltrotor reproduction.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/paper_cases"))
    parser.add_argument("--enable-cuda-extension", action="store_true")
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    repro = PaperReproduction()
    results = repro.run_all()
    result_rows = [asdict(result) for result in results]
    ref_rows = repro.reference_vs_open_rows(results)
    claim_checks = repro.claim_checks(results)

    write_csv(output_dir / "design_case_results.csv", result_rows)
    write_json(output_dir / "design_case_results.json", result_rows)
    write_csv(output_dir / "reference_vs_open.csv", ref_rows)
    write_json(output_dir / "paper_claim_checks.json", claim_checks)
    plot_comparison(output_dir / "tradeoff_map.png", ref_rows)
    plot_case_metric_summary(output_dir / "case_metric_summary.png", results)
    plot_paper_vs_open_deltas(output_dir / "paper_vs_open_deltas.png", ref_rows)
    plot_geometry_distributions(output_dir / "geometry_distributions.png", repro, results)

    claim_graph_path = Path("paper/claims.yaml")
    if claim_graph_path.exists():
        with claim_graph_path.open("r", encoding="utf-8") as handle:
            claims = yaml.safe_load(handle)
        write_json(output_dir / "claims_graph_snapshot.json", claims)

    cuda_rows: list[dict[str, object]] = []
    if args.enable_cuda_extension:
        write_json(output_dir / "cuda_extension_status.json", {"cupy_available": cupy_available()})
        cuda_rows = run_cuda_extension(repro, output_dir)
    elif (output_dir / "multipoint_extension.csv").exists():
        cuda_rows = read_csv(output_dir / "multipoint_extension.csv")

    if cuda_rows:
        plot_cuda_weight_sweep(output_dir / "cuda_weight_sweep.png", cuda_rows, repro.model.C_TIP)


if __name__ == "__main__":
    main()
