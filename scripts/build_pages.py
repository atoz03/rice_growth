"""从一次运行目录导出 GitHub Pages 展示数据（docs/data.js）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

TARGETS = ["lai_m2_m2", "biomass_aboveground_kg_ha", "storage_organ_dry_kg_ha", "dvs"]
WEATHER = ["tmin_c", "tmax_c", "radiation_mj_m2_day", "rain_mm_day"]


def _round(values, digits: int = 4) -> list[float]:
    return [float(f"{v:.{digits}g}") for v in np.asarray(values, dtype=float)]


def build(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    traj = pd.read_csv(run_dir / "trajectories.csv", parse_dates=["date"])
    metrics = pd.read_csv(run_dir / "metrics.csv")
    samples = pd.read_csv(run_dir / "samples.csv", parse_dates=["cutoff"])
    preds = np.load(run_dir / "test_predictions.npz")

    seasons = []
    for season_id, g in traj.groupby("season_id", sort=True):
        g = g.sort_values("date")
        seasons.append(
            {
                "id": season_id,
                "site": g["site_id"].iloc[0],
                "year": int(g["year"].iloc[0]),
                "variety": g["variety"].iloc[0],
                "start": g["date"].iloc[0].strftime("%Y-%m-%d"),
                "series": {t: _round(g[t].fillna(0.0)) for t in TARGETS},
                "weather": {w: _round(g[w], 3) for w in WEATHER},
            }
        )

    by_season = {s["id"]: s for s in seasons}
    test = samples[samples["split"] == "test"].sort_values("index")
    windows = []
    for row in test.itertuples():
        season = by_season[row.season_id]
        start = pd.Timestamp(season["start"])
        cutoff_day = int((row.cutoff - start).days)
        windows.append(
            {
                "season": row.season_id,
                "cutoff": row.cutoff.strftime("%Y-%m-%d"),
                "cutoff_day": cutoff_day,
                "actual": [_round(preds["actual"][row.index, :, k]) for k in range(len(TARGETS))],
                "ridge": [_round(preds["ridge"][row.index, :, k]) for k in range(len(TARGETS))],
                "persistence": [
                    _round(preds["persistence"][row.index, :, k]) for k in range(len(TARGETS))
                ],
            }
        )

    return {
        "run": {
            "created_utc": run["created_utc"],
            "weather_source": run["weather_source"],
            "target_source": run["target_source"],
            "seasons": run["seasons"],
            "daily_rows": run["daily_rows"],
            "windows": run["windows"],
            "packages": run["packages"],
            "upstream": {k: v["commit"][:7] for k, v in run["upstream"].items()},
        },
        "targets": TARGETS,
        "seasons": seasons,
        "metrics": [
            {
                "model": r.model,
                "split": r.split,
                "h": int(r.horizon_day),
                "variable": r.variable,
                "mae": float(f"{r.mae:.4g}"),
                "rmse": float(f"{r.rmse:.4g}"),
                "r2": float(f"{r.r2:.4g}"),
            }
            for r in metrics.itertuples()
        ],
        "test_windows": windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=Path("artifacts/release_copy_check"))
    parser.add_argument("--output", type=Path, default=Path("docs/data.js"))
    args = parser.parse_args()
    payload = json.dumps(build(args.run), ensure_ascii=False, separators=(",", ":"))
    args.output.write_text(f"window.RICE_DATA = {payload};\n", encoding="utf-8")
    print(f"wrote {args.output} ({args.output.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
