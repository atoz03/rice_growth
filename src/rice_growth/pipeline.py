"""配置驱动的演示闭环和运行溯源。"""

import hashlib
import importlib.metadata
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .adapters.pcse import PcseAdapter
from .baseline import evaluate
from .dataset import build_windows
from .schema import ROOT, Season
from .weather import synthetic_weather


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_demo(config_path, output):
    config_path, output = Path(config_path), Path(output)
    config = yaml.safe_load(config_path.read_text())
    lock = json.loads((ROOT / "external.lock.json").read_text())
    upstream = {}
    for name, spec in lock.items():
        path = ROOT / "external" / name
        actual = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], text=True
        ).strip()
        if actual != spec["commit"] or dirty:
            raise ValueError(f"上游 {name} 与锁定版本不符或存在源码修改")
        upstream[name] = {**spec, "actual_commit": actual}
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    try:
        tracks, weather_frames = [], []
        adapter = PcseAdapter()
        for year in config["years"]:
            for site_index, site in enumerate(config["sites"]):
                start = date(year, config["crop"]["start_month"], config["crop"]["start_day"])
                duration = config["crop"]["max_duration_days"]
                # 相同地点年份的各品种共用同一天气实现。
                weather = synthetic_weather(
                    start,
                    duration + 1,
                    config["seed"] + year * 100 + site_index,
                    site["temperature_offset_c"],
                )
                for variety in config["varieties"]:
                    season_id = f"{site['id']}_{year}_{variety}"
                    season = Season(
                        season_id, site, variety, start, duration, config["soil"], weather
                    )
                    track = adapter.simulate(season)
                    track = track.merge(weather, on="date", how="left", validate="one_to_one")
                    tracks.append(track)
                    weather_frames.append(
                        weather.assign(season_id=season_id, source="synthetic_demo")
                    )
                    print(f"模拟完成：{season_id}，{len(track)} 日")
        trajectories = pd.concat(tracks, ignore_index=True)
        trajectories.to_csv(output / "trajectories.csv", index=False)
        pd.concat(weather_frames, ignore_index=True).to_csv(output / "weather.csv", index=False)
        arrays, manifest = build_windows(trajectories, config["forecast"])
        np.savez_compressed(output / "windows.npz", **arrays)
        manifest.to_csv(output / "samples.csv", index=False)
        report = evaluate(arrays, config["forecast"]["ridge_alpha"], output)
        metadata = {
            "status": "complete",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "仅验证工程管线；全部标签为机理模拟，天气为人工生成，不是实测精度",
            "source_report": "report.tex（本地研究报告，不随代码发布）",
            "source_report_sha256": sha256(ROOT / "report.tex")
            if (ROOT / "report.tex").is_file()
            else None,
            "config_sha256": sha256(config_path),
            "upstream": upstream,
            "pipeline_source_sha256": {
                str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "src").rglob("*.py"))
            },
            "packages": {
                name: importlib.metadata.version(name)
                for name in ["rice-growth", "pcse", "numpy", "pandas"]
            },
            "seasons": int(trajectories.season_id.nunique()),
            "daily_rows": len(trajectories),
            "windows": manifest.groupby("split").size().to_dict(),
            "targets": "LAI、地上部干物质、贮藏器官干物质和原生 DVS；不等同于实收产量",
            "files": {p.name: sha256(p) for p in output.iterdir() if p.is_file()},
        }
        (output / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        summary = report.groupby(["split", "model", "variable"])["mae"].mean().to_string()
        (output / "summary.txt").write_text(
            "人工天气和机理模拟标签，仅用于工程验证。\n\n" + summary + "\n"
        )
        print(f"闭环完成：{output.resolve()}")
        return metadata
    except Exception as exc:
        (output / "failure.json").write_text(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2)
        )
        raise
