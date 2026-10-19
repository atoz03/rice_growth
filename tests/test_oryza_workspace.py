"""运行目录、输入校验与进程调用测试。"""

import hashlib
import json
import subprocess
import sys

import pytest
import yaml

from rice_growth.adapters.oryza import inspect_inputs, run_oryza
from rice_growth.oryza_workspace import check_workspace, load_config, prepare_workspace


def test_prepare_has_explicit_missing_materials_and_preserves_existing_directory(tmp_path):
    root = prepare_workspace(tmp_path / "workspace")
    status = check_workspace(root / "run.yaml")
    assert not status["ready"]
    assert all(not asset["ready"] for asset in status["assets"].values())
    assert (root / "input/CONTROL.DAT.in").is_file()
    assert not (root / "input/CONTROL.DAT").exists()
    with pytest.raises(FileExistsError):
        prepare_workspace(root)


def test_config_paths_are_relative_to_config_file(tmp_path, monkeypatch):
    root = prepare_workspace(tmp_path / "workspace")
    monkeypatch.chdir(tmp_path)
    config = load_config(root / "run.yaml")
    assert config["executable"] == str(root / "bin/ricesim")
    assert config["asset_manifest"] == str(root / "assets.yaml")


def test_manifest_hash_is_checked(tmp_path):
    root = prepare_workspace(tmp_path / "workspace")
    asset = root / "input/crop.crp"
    asset.write_text("资产校验测试")
    manifest_path = root / "assets.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["assets"]["crop"].update(path="input/crop.crp", source="测试夹具", sha256="0" * 64)
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True))
    assert "SHA-256 不匹配" in check_workspace(root / "run.yaml")["assets"]["crop"]["issues"]
    manifest["assets"]["crop"]["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True))
    assert check_workspace(root / "run.yaml")["assets"]["crop"]["ready"]


def test_partial_control_is_not_a_complete_case(tmp_path):
    (tmp_path / "input").mkdir()
    (tmp_path / "input/crop.crp").write_text("测试夹具")
    (tmp_path / "input/CONTROL.DAT").write_text("FILEI1='input/crop.crp'\n")
    status = inspect_inputs(tmp_path)
    assert not status["ready"]
    assert status["required_fields_missing"] == ["FILEI2", "FILEIT"]


def test_timeout_preserves_partial_logs(tmp_path):
    (tmp_path / "input").mkdir()
    (tmp_path / "input/fixture").write_text("测试夹具")
    (tmp_path / "input/CONTROL.DAT").write_text(
        "FILEI1='input/fixture'\nFILEI2='input/fixture'\nFILEIT='input/fixture'\n"
    )
    executable = tmp_path / "timeout_fixture"
    executable.write_text(
        f"#!{sys.executable}\nimport time\nprint('started', flush=True)\ntime.sleep(10)\n"
    )
    executable.chmod(0o700)
    mapping = dict(
        date="date",
        lai_m2_m2="LAI",
        biomass_aboveground_kg_ha="WAGT",
        storage_organ_dry_kg_ha="WSO",
        dvs="DVS",
    )
    with pytest.raises(RuntimeError, match="已保留日志"):
        run_oryza(
            tmp_path, executable, "daily.dat", mapping, "test", 2024, "test", "test", timeout=0.2
        )
    assert "started" in (tmp_path / "runner.stdout.log").read_text()


def test_registered_workspace_cli_run_and_collision_check(tmp_path):
    root = prepare_workspace(tmp_path / "workspace")
    executable = root / "bin/ricesim"
    executable.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        "Path('output/RES.DAT').write_text('YEAR DOY LAI WAGT WSO DVS\\n"
        "2024 60 1 100 0 0.1\\n2024 61 1.1 110 0 0.2\\n')\n"
    )
    executable.chmod(0o700)
    manifest_path = root / "assets.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    for name, entry in manifest["assets"].items():
        path = executable if name == "executable" else root / "input" / name
        if name != "executable":
            path.write_text("进程测试数据")
        entry.update(
            path=str(path.relative_to(root)),
            source="测试夹具",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True))
    (root / "input/CONTROL.DAT").write_text(
        "FILEI1='input/crop'\nFILEI2='input/soil'\nFILEIT='input/management'\nFILEIR='input/rerun'\n"
    )
    config_path = root / "run.yaml"
    config = yaml.safe_load(config_path.read_text())
    config.update(
        season_id="test", year=2024, site_id="test", variety="test", mapping_verified=True
    )
    config_path.write_text(yaml.safe_dump(config))
    check = subprocess.run(
        [sys.executable, "-m", "rice_growth.cli", "oryza-check", "--config", str(config_path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout)["ready"]
    run = subprocess.run(
        [sys.executable, "-m", "rice_growth.cli", "oryza-run", "--config", str(config_path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert run.returncode == 0, run.stderr
    assert (root / "normalized/trajectory.csv").is_file()
    assert not check_workspace(config_path)["ready"]
