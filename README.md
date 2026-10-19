# 水稻生长预测 Pipeline

首版已跑通：**人工天气 → PCSE/WOFOST 水稻机理模拟 → 生育季分组 → 条件多步预测 → 评测与溯源**。

这是根据本地研究报告搭建的研究工程起点。真实项目数据后续对齐；当前数据为人工天气与机理模拟标签，不能作为真实田间预测精度。研究报告保留本地，代码运行不依赖报告文件。

## 快速运行

在仓库根目录执行。建议 Python 3.11；当前环境已使用 `xiaenv` 的 Python 创建 `.venv`。

```bash
python3 scripts/bootstrap.py
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps ./external/pcse
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/rice-growth doctor
.venv/bin/rice-growth demo
.venv/bin/python -m pytest -q --disable-warnings
```

首次安装需联网，下载三个上游仓库和 Python 依赖；模拟阶段读取本地参数，不下载在线天气。`bootstrap.py` 验证上游版本及已跟踪源码，发现不符时停止。PCSE 首次导入会按上游行为创建用户目录下的 `.pcse` 配置和示例数据库。

```bash
# 指定配置和新的结果目录，避免覆盖已有实验
.venv/bin/rice-growth demo --config configs/demo.yaml --output artifacts/my_first_run
```

默认运行 2 个虚拟地点、3 个年份和 2 个水稻品种，使用 14 天历史直接预测未来 7 天。按 2021/2022/2023 年分别构建训练、验证和测试集；未来天气为已知人工情景。

## 模型接入状态

| 引擎 | 当前状态 | 范围 |
| --- | --- | --- |
| PCSE / WOFOST 7.2 PP | 已运行完整水稻生育季 | 使用上游 Rice_IR64、Rice_IR72 参数；潜在生产条件，不模拟水氮限制管理效果 |
| RICESIM-ORYZA | 源码已锁定，缺项检查、进程运行入口和日结果转换已实现 | 上游缺品种、土壤、管理和 rerun 输入，无构建脚本，附带 `.obj` 库；尚未完成真实引擎编译和运行 |

ORYZA 接入说明见 [docs/ORYZA.md](docs/ORYZA.md)。两种引擎保留各自名称和原生物候定义，不能直接视为相同真值。

## 输出

每次运行生成独立目录 `artifacts/demo_<时间>/`：

| 文件 | 内容 |
| --- | --- |
| `config.yaml`、`run.json` | 配置、随机种子、上游提交、代码及产物哈希、来源和运行状态 |
| `weather.csv`、`trajectories.csv` | 人工天气、逐日标准化机理状态 |
| `samples.csv`、`windows.npz` | 生育季划分、观测截止日和预测窗口 |
| `ridge_model.npz` | 仅用训练集拟合的标准化参数和直接多步岭回归模型 |
| `*_predictions.npz`、`metrics.csv` | 验证/测试预测，以及按变量和提前量计算的 MAE、RMSE、R² |
| `summary.txt` | 汇总结果；保留各变量量纲，不混合成无定义的“综合误差” |

预测目标包括 LAI、地上部干物质、贮藏器官干物质和原生 DVS。贮藏器官干物质不是自动换算后的实收产量；株高、水氮胁迫、遥感和图像暂未接入。当前岭回归输出保留原始预测，用于基线评估，尚未加入农学软约束。

## 后续实现

完整路线见 [docs/PLAN.md](docs/PLAN.md)，数据契约见 [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md)。按“机理数据与基线 → 校准同化 → 异步多模态 → MoE 与探测引导 PEFT → 泛化与部署”逐级推进。

源码位于 `src/rice_growth/`，配置在 `configs/`。上游源码、虚拟环境和生成结果不纳入版本控制；三个上游提交固定在 `external.lock.json`，Python 依赖固定在 `requirements.lock.txt`。

## 验证记录

首版完整示例生成 **12 个生育季、1107 条逐日状态、132 个预测窗口**；7 项测试通过，覆盖单位换算、缺测检查、未来目标隔离、年份互斥、ORYZA 缺项/格式解析及真实 PCSE 端到端执行。PCSE 的 traitlets 依赖会产生已知弃用警告，不影响本次运行。

上游来源：[PCSE](https://github.com/ajwdewit/pcse)、[WOFOST 水稻参数](https://github.com/ajwdewit/WOFOST_crop_parameters/tree/wofost72)、[RICESIM-ORYZA](https://github.com/USDA-ARS-ACSL/RICESIM-ORYZA)。上游许可和署名保留在各自下载目录中。
