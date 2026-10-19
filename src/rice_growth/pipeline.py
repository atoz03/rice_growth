"""配置驱动的模拟、预测与运行溯源。"""

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
from .weather import attach_weather, synthetic_weather

CONFIG_FIELDS = ["seed", "years", "varieties", "sites", "crop", "soil", "forecast"]
SECTION_FIELDS = {
    "crop": ["start_month", "start_day", "max_duration_days"],
    "forecast": [
        "history_days",
        "horizon_days",
        "stride_days",
        "ridge_alpha",
        "train_years",
        "validation_years",
        "test_years",
    ],
}
SITE_FIELDS = ["id", "latitude", "longitude", "elevation_m", "temperature_offset_c"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_config(config):
    if not isinstance(config, dict):
        raise ValueError("示例配置必须为字段映射")
    missing = [key for key in CONFIG_FIELDS if key not in config]
    for section, keys in SECTION_FIELDS.items():
        if section in config:
            values = config[section] if isinstance(config[section], dict) else {}
            missing += [f"{section}.{key}" for key in keys if key not in values]
    sites = config.get("sites")
    if not isinstance(sites, list) or not sites:
        missing.append("sites[0]")
    else:
        for i, site in enumerate(sites):
            values = site if isinstance(site, dict) else {}
            missing += [f"sites[{i}].{key}" for key in SITE_FIELDS if key not in values]
    if missing:
        raise ValueError(f"示例配置缺少字段：{missing}")


def run_demo(config_path, output):
    config_path, output = Path(config_path), Path(output)
    lock_path = ROOT / "external.lock.json"
    if not lock_path.is_file():
        raise ValueError(f"未找到 {lock_path}；demo 须在仓库目录中以可编辑模式安装后运行")
    config = yaml.safe_load(config_path.read_text())
    check_config(config)
    lock = json.loads(lock_path.read_text())
    upstream = {}
    for name, spec in lock.items():
        path = ROOT / "external" / name
        if not path.is_dir():
            raise ValueError(f"缺少上游 {name}，请先运行 scripts/bootstrap.py")
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
                        season_id,
                        site,
                        variety,
                        start,
                        duration,
                        config["soil"],
                        weather,
                        "synthetic_demo",
                    )
                    track = attach_weather(adapter.simulate(season), weather)
                    tracks.append(track)
                    weather_frames.append(
                        weather.assign(season_id=season_id, weather_source="synthetic_demo")
                    )
                    print(f"模拟完成：{season_id}，{len(track)} 日")
        trajectories = pd.concat(tracks, ignore_index=True)
        trajectories.to_csv(output / "trajectories.csv", index=False)
        pd.concat(weather_frames, ignore_index=True).to_csv(output / "weather.csv", index=False)
        arrays, manifest = build_windows(trajectories, config["forecast"])
        np.savez_compressed(output / "windows.npz", **arrays)
        manifest.to_csv(output / "samples.csv", index=False)
        report = evaluate(arrays, config["forecast"]["ridge_alpha"], output)
        summary = report.groupby(["split", "model", "variable"])["mae"].mean().to_string()
        (output / "summary.txt").write_text(
            "天气来源：synthetic_demo；目标来源：mechanistic_simulation。\n\n" + summary + "\n"
        )
        metadata = {
            "status": "complete",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "weather_source": "synthetic_demo",
            "target_source": "mechanistic_simulation",
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
            "targets": "LAI、地上部干物质、贮藏器官干物质、DVS",
            "files": {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()},
        }
        (output / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        print(f"闭环完成：{output.resolve()}")
        return metadata
    except Exception as exc:
        (output / "failure.json").write_text(
            json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2)
        )
        raise
