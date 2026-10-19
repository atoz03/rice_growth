"""先划分完整生育季，再生成不跨季节的条件预测窗口。"""

import numpy as np
import pandas as pd

from .schema import TARGETS, WEATHER, validate_trajectory


def build_windows(trajectories, forecast):
    validate_trajectory(trajectories)
    history, horizon, stride = (
        forecast[k] for k in ["history_days", "horizon_days", "stride_days"]
    )
    if min(history, horizon, stride) < 1:
        raise ValueError("历史长度、预测长度和步长必须为正")
    partitions = {name: set(forecast[f"{name}_years"]) for name in ["train", "validation", "test"]}
    names = list(partitions)
    if any(partitions[a] & partitions[b] for i, a in enumerate(names) for b in names[i + 1 :]):
        raise ValueError("训练、验证和测试年份不能重叠")
    payload = {name: {"x": [], "y": [], "last": []} for name in partitions}
    manifest = []
    for season_id, season in trajectories.groupby("season_id", sort=True):
        season = season.sort_values("date").reset_index(drop=True)
        if season.year.nunique() != 1:
            raise ValueError("year 应记录生育季年份，而非逐日的日历年份")
        split = next(
            (name for name, years in partitions.items() if int(season.year.iloc[0]) in years), None
        )
        if split is None:
            raise ValueError(f"生育季 {season_id} 未配置所属数据集")
        for end in range(history, len(season) - horizon + 1, stride):
            past = season.iloc[end - history : end]
            future = season.iloc[end : end + horizon]
            # 未来只读取天气情景，预测目标仅用于 y。
            x = np.concatenate(
                [
                    past[TARGETS + WEATHER].to_numpy(float).ravel(),
                    future[WEATHER].to_numpy(float).ravel(),
                ]
            )
            y = future[TARGETS].to_numpy(float)
            if not np.isfinite(x).all() or not np.isfinite(y).all():
                raise ValueError("窗口包含缺失值")
            index = len(payload[split]["x"])
            payload[split]["x"].append(x)
            payload[split]["y"].append(y)
            payload[split]["last"].append(past[TARGETS].iloc[-1].to_numpy(float))
            manifest.append(
                {
                    "split": split,
                    "index": index,
                    "season_id": season_id,
                    "site_id": season.site_id.iloc[0],
                    "year": int(season.year.iloc[0]),
                    "variety": season.variety.iloc[0],
                    "cutoff": str(past.date.iloc[-1]),
                    "target_end": str(future.date.iloc[-1]),
                    "source": season.source.iloc[0],
                    "weather_source": season.weather_source.iloc[0],
                    # 特征中的未来天气取自该生育季的实际天气序列。
                    "weather_mode": "known_future_weather",
                }
            )
    arrays = {}
    for split, values in payload.items():
        if not values["x"]:
            raise ValueError(f"{split} 没有可用预测窗口")
        for key, value in values.items():
            arrays[f"{split}_{key}"] = np.stack(value)
    return arrays, pd.DataFrame(manifest)
