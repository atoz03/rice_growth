"""机理模型共享的输入、输出及校验。"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ["lai_m2_m2", "biomass_aboveground_kg_ha", "storage_organ_dry_kg_ha", "dvs"]
WEATHER = ["tmin_c", "tmax_c", "radiation_mj_m2_day", "rain_mm_day", "vapour_pressure_kpa", "wind_m_s"]


@dataclass
class Season:
    season_id: str
    site: dict
    variety: str
    start: date
    max_duration: int
    soil: dict
    weather: pd.DataFrame


class MechanisticAdapter(Protocol):
    def simulate(self, season: Season) -> pd.DataFrame:
        """返回逐日标准轨迹；不支持的变量保持缺失，不构造伪观测。"""
        ...


def validate_weather(frame):
    required = ["date", *WEATHER]
    missing = set(required) - set(frame)
    if missing:
        raise ValueError(f"天气缺少字段：{sorted(missing)}")
    dates = pd.to_datetime(frame.date)
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("天气日期必须递增且不重复")
    if len(dates) < 2 or not dates.diff().iloc[1:].eq(pd.Timedelta(days=1)).all():
        raise ValueError("机理模型天气必须逐日连续；缺测应在输入阶段明确处理")
    if not np.isfinite(frame[WEATHER].to_numpy(dtype=float)).all():
        raise ValueError("天气包含缺失或非有限值")
    if (frame.tmax_c < frame.tmin_c).any():
        raise ValueError("最高温不能低于最低温")
    positive = WEATHER[2:]
    if (frame[positive] < 0).any().any():
        raise ValueError("辐射、降水、水汽压和风速不能为负")


def validate_trajectory(frame):
    required = ["date", "season_id", "source", "engine", "weather_source", *TARGETS]
    if set(required) - set(frame):
        raise ValueError(f"轨迹缺少字段：{sorted(set(required) - set(frame))}")
    if frame.duplicated(["season_id", "date"]).any():
        raise ValueError("同一生育季日期重复")
    values = frame[TARGETS].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < -1e-8).any():
        raise ValueError("核心状态必须非负且有限")
    for _, season in frame.groupby("season_id"):
        dates = pd.to_datetime(season.date)
        if not dates.is_monotonic_increasing or not dates.diff().iloc[1:].eq(pd.Timedelta(days=1)).all():
            raise ValueError("轨迹必须按日连续递增")
        if (season.dvs.diff().dropna() < -1e-8).any():
            raise ValueError("生育进程发生倒退")
