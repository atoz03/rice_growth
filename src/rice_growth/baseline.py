"""直接多步岭回归与持续性基线；统计量仅由训练集拟合。"""

import numpy as np
import pandas as pd

from .schema import TARGETS


def fit_ridge(x, y, alpha):
    if alpha <= 0:
        raise ValueError("岭回归正则系数必须为正")
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    z = (x - mean) / scale
    flat = y.reshape(len(y), -1)
    target_mean = flat.mean(axis=0)
    centered = flat - target_mean
    # 使用样本维度的对偶形式，适合演示数据中少样本、多特征的情况。
    dual = np.linalg.solve(z @ z.T + alpha * np.eye(len(z)), centered)
    return {
        "mean": mean,
        "scale": scale,
        "weights": z.T @ dual,
        "target_mean": target_mean,
        "shape": np.array(y.shape[1:]),
    }


def predict_ridge(model, x):
    y = (x - model["mean"]) / model["scale"] @ model["weights"] + model["target_mean"]
    return y.reshape(len(x), *model["shape"].astype(int))


def metrics(y, prediction, model_name, split):
    rows = []
    for h in range(y.shape[1]):
        for v, name in enumerate(TARGETS):
            actual = y[:, h, v]
            err = prediction[:, h, v] - actual
            denominator = np.sum((actual - actual.mean()) ** 2)
            rows.append(
                {
                    "model": model_name,
                    "split": split,
                    "horizon_day": h + 1,
                    "variable": name,
                    "n": len(actual),
                    "mae": np.abs(err).mean(),
                    "rmse": np.sqrt(np.mean(err**2)),
                    "r2": 1 - np.sum(err**2) / denominator if denominator > 1e-12 else None,
                }
            )
    return pd.DataFrame(rows)


def evaluate(arrays, alpha, output):
    model = fit_ridge(arrays["train_x"], arrays["train_y"], alpha)
    np.savez_compressed(output / "ridge_model.npz", **model)
    reports = []
    for split in ["validation", "test"]:
        actual = arrays[f"{split}_y"]
        ridge = predict_ridge(model, arrays[f"{split}_x"])
        persistence = np.repeat(arrays[f"{split}_last"][:, None, :], actual.shape[1], axis=1)
        np.savez_compressed(
            output / f"{split}_predictions.npz", actual=actual, ridge=ridge, persistence=persistence
        )
        for name, prediction in [("ridge_direct", ridge), ("persistence", persistence)]:
            reports.append(metrics(actual, prediction, name, split))
    report = pd.concat(reports, ignore_index=True)
    report.to_csv(output / "metrics.csv", index=False)
    return report
