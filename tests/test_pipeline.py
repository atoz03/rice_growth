"""验证量纲、信息边界、分组划分及真实 PCSE 执行链。"""

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

from rice_growth.adapters.oryza import OryzaAdapter, inspect_inputs, run_oryza
from rice_growth.adapters.pcse import PcseAdapter
from rice_growth.baseline import fit_ridge, predict_ridge
from rice_growth.dataset import build_windows
from rice_growth.pipeline import run_demo
from rice_growth.schema import ROOT, TARGETS, WEATHER, Season, validate_weather
from rice_growth.weather import attach_weather, pcse_weather_values, synthetic_weather


def test_weather_units_and_missing_days():
    weather = synthetic_weather(date(2021, 6, 1), 10, 42)
    weather.loc[0, ["radiation_mj_m2_day", "rain_mm_day", "vapour_pressure_kpa"]] = [18, 12, 2.3]
    converted = pcse_weather_values(next(weather.itertuples(index=False)))
    assert converted["IRRAD"] == 18e6
    assert converted["RAIN"] == 1.2
    assert converted["VAP"] == 23
    with pytest.raises(ValueError, match="逐日连续"):
        validate_weather(weather.drop(index=3))


def test_ridge_uses_training_statistics_and_learns_linear_signal():
    x = np.arange(20, dtype=float).reshape(10, 2)
    y = (x[:, :1] * 2 + 3).reshape(10, 1, 1)
    model = fit_ridge(x, y, 1e-6)
    np.testing.assert_array_equal(model["mean"], x.mean(axis=0))
    np.testing.assert_allclose(predict_ridge(model, x), y, atol=1e-4)


def trajectories():
    frames = []
    for year in [2021, 2022, 2023]:
        weather = synthetic_weather(date(year, 6, 1), 30, year)
        for i, name in enumerate(TARGETS):
            weather[name] = np.arange(30, dtype=float) * (i + 1) / 100
        frames.append(
            weather.assign(
                season_id=str(year),
                year=year,
                site_id="test",
                variety="test",
                source="mechanistic_simulation",
                engine="test",
                weather_source="synthetic_demo",
            )
        )
    return pd.concat(frames, ignore_index=True)


def forecast():
    return dict(
        history_days=5,
        horizon_days=3,
        stride_days=3,
        train_years=[2021],
        validation_years=[2022],
        test_years=[2023],
    )


def test_split_by_season_and_future_targets_never_enter_features():
    frame = trajectories()
    original, manifest = build_windows(frame, forecast())
    assert manifest.groupby("season_id").split.nunique().eq(1).all()
    assert set(manifest[manifest.split == "test"].year) == {2023}
    changed = frame.copy()
    changed.loc[(changed.year == 2021) & (changed.index >= 5), "lai_m2_m2"] += 100
    updated, _ = build_windows(changed, forecast())
    np.testing.assert_array_equal(original["train_x"][0], updated["train_x"][0])
    assert not np.array_equal(original["train_y"][0], updated["train_y"][0])


def test_overlapping_years_rejected():
    config = forecast()
    config["test_years"] = [2021]
    with pytest.raises(ValueError, match="年份不能重叠"):
        build_windows(trajectories(), config)


def test_oryza_identifies_missing_real_inputs(tmp_path):
    (tmp_path / "input").mkdir()
    (tmp_path / "input/CONTROL.DAT").write_text("*FILEI2='ignored.dat'\nFILEI1='missing.crp'\n")
    status = inspect_inputs(tmp_path)
    assert not status["ready"]
    assert status["missing"] == ["missing.crp"]


def oryza_fixture(tmp_path):
    """日表解析测试程序及其输出映射。"""
    (tmp_path / "input").mkdir()
    (tmp_path / "input/crop.crp").write_text("测试输入")
    (tmp_path / "input/CONTROL.DAT").write_text(
        "FILEI1='input/crop.crp'\nFILEI2='input/crop.crp'\nFILEIT='input/crop.crp'\n"
    )
    executable = tmp_path / "format_fixture.sh"
    executable.write_text(
        "#!/bin/sh\ncat > daily.dat <<'EOF'\nYEAR DOY LAI WAGT WSO DVS\n2024 60 1 100 0 0.1\n2024 61 1.1 110 0 0.2\nEOF\n"
    )
    executable.chmod(0o700)
    mapping = dict(
        year="YEAR",
        day_of_year="DOY",
        lai_m2_m2="LAI",
        biomass_aboveground_kg_ha="WAGT",
        storage_organ_dry_kg_ha="WSO",
        dvs="DVS",
    )
    return executable, mapping


def test_oryza_process_and_native_date_conversion(tmp_path):
    executable, mapping = oryza_fixture(tmp_path)
    frame = run_oryza(tmp_path, executable, "daily.dat", mapping, "test", 2024, "test", "test")
    assert frame.date.tolist() == [date(2024, 2, 29), date(2024, 3, 1)]
    assert (tmp_path / "runner.stdout.log").is_file()
    with pytest.raises(ValueError, match="输出已存在"):
        run_oryza(tmp_path, executable, "daily.dat", mapping, "test", 2024, "test", "test")


def test_oryza_adapter_returns_states_and_weather_must_cover_dates(tmp_path):
    executable, mapping = oryza_fixture(tmp_path)
    start = date(2024, 2, 29)
    weather = synthetic_weather(start, 2, 1)
    season = Season("test", {"id": "test"}, "test", start, 1, {}, weather, "user_supplied")
    adapter = OryzaAdapter(tmp_path, executable, "daily.dat", mapping)
    frame = adapter.simulate(season)
    assert not set(WEATHER) & set(frame)
    merged = attach_weather(frame, weather)
    assert np.isfinite(merged[WEATHER].to_numpy(float)).all()
    with pytest.raises(ValueError, match="输出已存在"):
        adapter.simulate(season)
    with pytest.raises(ValueError, match="未覆盖"):
        attach_weather(frame, synthetic_weather(date(2024, 3, 1), 2, 1))


def test_pcse_adapter_labels_weather_source_and_requires_full_weather():
    start = date(2021, 6, 1)
    weather = synthetic_weather(start, 181, 1)
    site = dict(id="test", latitude=18.0, longitude=100.0, elevation_m=50.0)
    soil = yaml.safe_load((ROOT / "configs/demo.yaml").read_text())["soil"]
    season = Season("test", site, "Rice_IR64", start, 180, soil, weather, "station_observed")
    assert set(PcseAdapter().simulate(season).weather_source) == {"station_observed"}
    with pytest.raises(ValueError, match="天气须覆盖"):
        PcseAdapter().simulate(replace(season, weather=weather.iloc[:100]))


def test_real_pcse_demo_end_to_end(tmp_path):
    config = yaml.safe_load((ROOT / "configs/demo.yaml").read_text())
    config["sites"] = config["sites"][:1]
    config["varieties"] = config["varieties"][:1]
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    output = tmp_path / "run"
    metadata = run_demo(config_path, output)
    assert metadata["status"] == "complete"
    assert metadata["seasons"] == 3
    assert metadata["daily_rows"] > 200
    frame = pd.read_csv(output / "trajectories.csv")
    assert frame.lai_m2_m2.max() > 1
    assert frame.biomass_aboveground_kg_ha.max() > 1000
    assert set(frame.weather_source) == {"synthetic_demo"}
    report = pd.read_csv(output / "metrics.csv")
    assert np.isfinite(report[["mae", "rmse"]]).all().all()
    assert set(report.model) == {"ridge_direct", "persistence"}
    assert set(pd.read_csv(output / "weather.csv").weather_source) == {"synthetic_demo"}
    assert "summary.txt" in metadata["files"]
    samples = pd.read_csv(output / "samples.csv")
    assert set(samples.weather_source) == {"synthetic_demo"}
    assert set(samples.weather_mode) == {"known_future_weather"}
    with pytest.raises(FileExistsError):
        run_demo(config_path, output)


def test_missing_upstream_is_reported_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr("rice_growth.pipeline.ROOT", tmp_path)
    with pytest.raises(ValueError, match="可编辑模式"):
        run_demo(ROOT / "configs/demo.yaml", tmp_path / "run")
    (tmp_path / "external.lock.json").write_text((ROOT / "external.lock.json").read_text())
    with pytest.raises(ValueError, match="bootstrap"):
        run_demo(ROOT / "configs/demo.yaml", tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_incomplete_config_is_rejected_before_output(tmp_path):
    config = yaml.safe_load((ROOT / "configs/demo.yaml").read_text())
    del config["forecast"]["ridge_alpha"]
    del config["sites"][0]["latitude"]
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match=r"forecast\.ridge_alpha.*sites\[0\]\.latitude"):
        run_demo(config_path, tmp_path / "run")
    assert not (tmp_path / "run").exists()
