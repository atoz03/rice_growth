"""通过独立进程调用 RICESIM；输入和可执行程序必须由真实资产提供。"""

import re
import subprocess
from pathlib import Path

import pandas as pd

from ..schema import TARGETS, validate_trajectory


def inspect_inputs(workdir):
    control = Path(workdir) / "input/CONTROL.DAT"
    if not control.is_file():
        return {"ready": False, "missing": [str(control)], "references": {}}
    # 星号行是上游输入格式中的注释；只检查实际启用的 FILEI*。
    active = "\n".join(line for line in control.read_text(errors="replace").splitlines()
                       if not line.lstrip().startswith("*"))
    references = dict(re.findall(r"\b(FILEI\w*)\s*=\s*'([^']+)'", active, re.I))
    missing = []
    for value in references.values():
        path = Path(value)
        if re.match(r"^[A-Za-z]:[/\\]", value) or not (path if path.is_absolute() else Path(workdir) / path).is_file():
            missing.append(value)
    return {"ready": bool(references) and not missing, "missing": missing, "references": references}


def run_oryza(workdir, executable, output, mapping, season_id, year, site_id, variety, timeout=300):
    """执行已有引擎并转换逐日结果；单行季末 op.dat 不能替代日轨迹。"""
    workdir = Path(workdir).resolve()
    executable = Path(executable).resolve()
    output = Path(output)
    if not output.is_absolute():
        output = workdir / output
    status = inspect_inputs(workdir)
    if not status["ready"]:
        raise ValueError(f"ORYZA 输入不完整：{status['missing']}")
    if not executable.is_file():
        raise ValueError(f"缺少 ORYZA 可执行文件：{executable}")
    if output.exists():
        raise ValueError("输出已存在，请使用独立的新运行目录，避免误读旧结果")
    if set(TARGETS) - set(mapping) or not ("date" in mapping or {"year", "day_of_year"} <= set(mapping)):
        raise ValueError("输出映射须包含全部核心状态，以及 date 或 year/day_of_year")
    result = subprocess.run([str(executable)], cwd=workdir, capture_output=True, text=True,
                            timeout=timeout, check=False)
    (workdir / "runner.stdout.log").write_text(result.stdout)
    (workdir / "runner.stderr.log").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"ORYZA 退出码 {result.returncode}；请检查 runner 日志")
    if not output.is_file():
        raise RuntimeError(f"ORYZA 未生成指定逐日结果：{output}")
    raw = pd.read_csv(output, sep=r"\s+", comment="*")
    frame = pd.DataFrame({k: raw[mapping[k]] for k in TARGETS})
    if "date" in mapping:
        frame["date"] = pd.to_datetime(raw[mapping["date"]], format="%Y-%m-%d", errors="raise").dt.date
    else:
        years = pd.to_numeric(raw[mapping["year"]], errors="raise")
        doy = pd.to_numeric(raw[mapping["day_of_year"]], errors="raise")
        if (years % 1 != 0).any() or (doy % 1 != 0).any() or not doy.between(1, 366).all():
            raise ValueError("年份和年积日必须为合法整数")
        dates = pd.to_datetime(years.astype(int).astype(str), format="%Y") + pd.to_timedelta(doy - 1, unit="D")
        if not dates.dt.year.eq(years).all():
            raise ValueError("年积日超过该年份的天数")
        frame["date"] = dates.dt.date
    if len(frame) < 2:
        raise ValueError("ORYZA 日轨迹不足两日，不能使用季末汇总作为轨迹")
    frame = frame.assign(season_id=season_id, year=year, site_id=site_id, variety=variety,
                         source="mechanistic_simulation", engine="ricesim_oryza",
                         weather_source="user_supplied")
    validate_trajectory(frame)
    return frame


class OryzaAdapter:
    """使用已准备好的原生运行目录；天气、土壤和管理原生文件由调用方提供。"""

    def __init__(self, workdir, executable, output, mapping, timeout=300):
        self.options = dict(workdir=workdir, executable=executable, output=output,
                            mapping=mapping, timeout=timeout)

    def simulate(self, season):
        frame = run_oryza(**self.options, season_id=season.season_id, year=season.start.year,
                          site_id=season.site["id"], variety=season.variety)
        weather = season.weather.copy()
        weather["date"] = pd.to_datetime(weather.date).dt.date
        # 共同数据结构用于下游；此处不会把通用天气自动写成未经验证的原生格式。
        return frame.merge(weather, on="date", how="left", validate="one_to_one")
