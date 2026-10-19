"""创建运行目录并校验配置与输入资产。"""

import hashlib
import os
import re
import shutil
from pathlib import Path

import yaml

from .adapters.oryza import inspect_inputs
from .schema import TARGETS

# 模板随包安装，非可编辑安装时同样可用。
TEMPLATE = Path(__file__).resolve().parent / "templates/oryza"


def prepare_workspace(destination):
    destination = Path(destination).resolve()
    shutil.copytree(TEMPLATE, destination)
    for name in ["bin", "weather", "output", "normalized"]:
        (destination / name).mkdir(exist_ok=True)
    return destination


def load_config(path):
    path = Path(path).resolve()
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        raise ValueError("ORYZA 运行配置必须为字段映射")
    for key in ["workdir", "executable", "output", "normalized_output", "asset_manifest"]:
        value = config.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{key} 必须为路径字符串")
    for key in ["workdir", "executable", "normalized_output", "asset_manifest"]:
        value = config.get(key)
        if value:
            value = Path(value)
            config[key] = str(value if value.is_absolute() else path.parent / value)
    return config


def check_workspace(config_path):
    config = load_config(config_path)
    blockers = []
    for key in [
        "workdir",
        "executable",
        "output",
        "normalized_output",
        "season_id",
        "year",
        "site_id",
        "variety",
    ]:
        if config.get(key) is None or config.get(key) == "":
            blockers.append(f"配置未填写：{key}")
    year = config.get("year")
    if year not in (None, "") and (type(year) is not int or not 1 <= year <= 9999):
        blockers.append("year 必须为 1 至 9999 的整数")
    timeout = config.get("timeout", 300)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        blockers.append("timeout 必须为正数")
    mapping = config.get("mapping")
    if (
        not isinstance(mapping, dict)
        or set(TARGETS) - set(mapping)
        or not ("date" in mapping or {"year", "day_of_year"} <= set(mapping))
        or not all(isinstance(value, str) and value.strip() for value in mapping.values())
    ):
        blockers.append("mapping 必须填写真实日表的核心状态列及日期列")
    if config.get("mapping_verified") is not True:
        blockers.append("尚未确认真实日表列名：mapping_verified")
    native = (
        inspect_inputs(config["workdir"])
        if config.get("workdir")
        else {"ready": False, "missing": [], "references": {}}
    )
    if not native["ready"]:
        blockers.append("原生 CONTROL.DAT 或引用的输入文件尚未就绪")
    executable = Path(config.get("executable") or "__missing_executable__")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        blockers.append("当前平台可执行程序缺失或不可执行")
    if config.get("workdir") and config.get("output"):
        if (Path(config["workdir"]) / config["output"]).exists():
            blockers.append("原生结果已存在，需使用新的运行目录")
    if config.get("normalized_output") and Path(config["normalized_output"]).exists():
        blockers.append("标准化结果已存在")

    asset_checks = {}
    manifest_path = Path(
        config.get("asset_manifest") or Path(config_path).resolve().parent / "assets.yaml"
    )
    required = [
        "crop",
        "management",
        "soil",
        "rerun",
        "weather",
        "executable",
    ]
    manifest = yaml.safe_load(manifest_path.read_text()) if manifest_path.is_file() else {}
    entries = manifest.get("assets", {}) if isinstance(manifest, dict) else {}
    if not isinstance(entries, dict):
        entries = {}
    for name in required:
        entry = entries.get(name) or {}
        errors = []
        if not isinstance(entry, dict):
            entry = {}
        for key in ["path", "source", "sha256"]:
            if not entry.get(key):
                errors.append(f"未登记 {key}")
        if entry.get("path"):
            asset = manifest_path.parent / entry["path"]
            if not asset.is_file():
                errors.append("文件不存在")
            elif not re.fullmatch(r"[0-9a-fA-F]{64}", str(entry.get("sha256", ""))):
                errors.append("SHA-256 格式无效")
            elif hashlib.sha256(asset.read_bytes()).hexdigest() != str(entry["sha256"]).lower():
                errors.append("SHA-256 不匹配")
        asset_checks[name] = {"ready": not errors, "issues": errors}
    # 防止登记的是一套资产，而实际 CONTROL 或可执行程序指向另一套文件。
    bindings = {"crop": "FILEI1", "management": "FILEIT", "soil": "FILEI2", "rerun": "FILEIR"}
    for name, native_key in bindings.items():
        entry = entries.get(name)
        reference = native.get("references", {}).get(native_key)
        if isinstance(entry, dict) and entry.get("path") and reference and config.get("workdir"):
            actual = (Path(config["workdir"]) / reference).resolve()
            if actual != (manifest_path.parent / entry["path"]).resolve():
                asset_checks[name]["ready"] = False
                asset_checks[name]["issues"].append(f"登记路径与 {native_key} 不一致")
    entry = entries.get("executable")
    if isinstance(entry, dict) and entry.get("path") and config.get("executable"):
        if executable.resolve() != (manifest_path.parent / entry["path"]).resolve():
            asset_checks["executable"]["ready"] = False
            asset_checks["executable"]["issues"].append("登记路径与实际执行程序不一致")
    for name in required:
        if not asset_checks[name]["ready"]:
            blockers.append(f"资产未就绪：{name}")
    return {
        "ready": not blockers,
        "run_blockers": blockers,
        "native_inputs": native,
        "assets": asset_checks,
    }
