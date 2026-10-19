# RICESIM-ORYZA

通过独立进程调用 RICESIM，将逐日日表转换为统一状态表。可执行程序和原生输入由用户提供。

## 配置与执行

```bash
.venv/bin/rice-growth oryza-prepare --output artifacts/oryza_run
# 配置 artifacts/oryza_run/run.yaml、assets.yaml 和 input/CONTROL.DAT
.venv/bin/rice-growth oryza-check --config artifacts/oryza_run/run.yaml
.venv/bin/rice-growth oryza-run --config artifacts/oryza_run/run.yaml
```

| 路径 | 内容 |
| --- | --- |
| `bin/ricesim` | 当前平台的可执行程序 |
| `input/` | 品种、土壤、管理、rerun 和 `CONTROL.DAT` |
| `weather/` | 原生天气文件 |
| `assets.yaml` | 输入与程序的路径、来源和 SHA-256 |
| `run.yaml` | 运行目录、输出映射和生育季标识 |
| `output/` | 原生结果 |
| `normalized/trajectory.csv` | 标准化逐日状态 |

将 `input/CONTROL.DAT.in` 中的路径替换后保存为 `input/CONTROL.DAT`。引擎以 80 字符读取文件名，`FILEI*` 路径不得超过该长度；以 `*` 开头的行和引号外 `!` 之后的内容视为注释。配置中的 `workdir`、`executable`、`asset_manifest` 和 `normalized_output` 相对于配置文件；`output` 相对于 `workdir`。

填写 `assets.yaml` 的文件路径、来源及 SHA-256，并将 `run.yaml` 的 `season_id`、`year`、`site_id`、`variety` 设为案例值。按实际日表填写 `mapping`，确认后设置 `mapping_verified: true`。

## 日结果格式

支持空白分隔、单表头的逐日日表，星号行视为注释。日期使用 ISO `YYYY-MM-DD` 或年份与年积日。目标列为 LAI、地上部干物质、贮藏器官干物质和 DVS；具体列名由 `mapping` 指定。

日序列须连续、无重复，状态非负且有限，DVS 单调不减。季末汇总 `op.dat` 不适用于日轨迹转换。

## 检查与日志

`oryza-check` 检查配置、输入引用、程序权限、资产哈希和输出冲突。通过返回 0，存在缺项返回 1。运行生成 `runner.stdout.log` 与 `runner.stderr.log`，超时保留已捕获日志。

## 引擎依赖

锁定的 [RICESIM 上游](https://github.com/USDA-ARS-ACSL/RICESIM-ORYZA)未附完整构建配置及以下案例输入：`xl753.crp`、`manage.xl753.exp`、`PADDYIN-AR-LA.DAT`、`reruns.test.2000.dat`。本仓库不提供预编译 RICESIM 程序。
