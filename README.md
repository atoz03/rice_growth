# Rice Growth

水稻机理模拟与生长轨迹预测工具。支持 PCSE/WOFOST 水稻模拟、生育季分组、多步预测和逐变量评测，并提供 RICESIM-ORYZA 外部程序接口。

## 安装

Python 3.11，在仓库根目录执行：

```bash
python3 scripts/bootstrap.py
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps ./external/pcse
.venv/bin/python -m pip install --no-deps -e .
```

上游版本固定在 `external.lock.json`。首次安装需要联网，模拟使用本地参数。PCSE 首次导入会创建 `~/.pcse`。

## 运行

```bash
.venv/bin/rice-growth doctor
.venv/bin/rice-growth demo --config configs/demo.yaml --output artifacts/run_001
```

示例使用人工天气、2 个地点、3 个年份及 Rice_IR64、Rice_IR72 参数，读取 14 天历史，直接预测未来 7 天的 LAI、地上部干物质、贮藏器官干物质和 DVS。训练、验证和测试按年份隔离，基线包括持续性预测与岭回归。

| 引擎 | 支持范围 |
| --- | --- |
| PCSE / WOFOST 7.2 PP | 水稻潜在生产模拟；水氮供应不受限 |
| RICESIM-ORYZA | 外部程序调用与日结果转换；需另行提供可执行程序和完整原生输入 |

RICESIM 配置见 [ORYZA.md](docs/ORYZA.md)，字段与单位见 [DATA_CONTRACT.md](docs/DATA_CONTRACT.md)。

## 输出

| 文件 | 内容 |
| --- | --- |
| `config.yaml`、`run.json` | 配置、版本、来源与文件哈希 |
| `weather.csv`、`trajectories.csv` | 天气和逐日状态 |
| `samples.csv`、`windows.npz` | 样本索引与预测窗口 |
| `ridge_model.npz` | 岭回归模型与训练集标准化参数 |
| `*_predictions.npz` | 预测值与目标值 |
| `metrics.csv`、`summary.txt` | 按变量和提前量计算的 MAE、RMSE、R² |

结果写入新的运行目录，已有目录拒绝覆盖。

## 检查

```bash
.venv/bin/python -m pytest -q --disable-warnings
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## 上游

- [PCSE](https://github.com/ajwdewit/pcse)
- [WOFOST 作物参数](https://github.com/ajwdewit/WOFOST_crop_parameters/tree/wofost72)
- [RICESIM-ORYZA](https://github.com/USDA-ARS-ACSL/RICESIM-ORYZA)
