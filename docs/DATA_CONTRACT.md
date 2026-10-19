# 数据格式

## 生育季

`season_id` 标识一个地块的完整生育季，附带 `site_id`、`year` 和 `variety`。`year` 为生育季所属年份，跨年时保持一致。

模拟轨迹使用 `source=mechanistic_simulation`，`engine` 记录引擎名称。示例天气使用 `weather_source=synthetic_demo`。

## 天气

| 字段 | 单位 |
| --- | --- |
| `date` | 当地日期，YYYY-MM-DD |
| `tmin_c`、`tmax_c` | °C |
| `radiation_mj_m2_day` | MJ/m²/day |
| `rain_mm_day` | mm/day |
| `vapour_pressure_kpa` | kPa |
| `wind_m_s` | m/s，2 米高度 |

天气须按日连续、递增且无缺失。PCSE 适配器转换为 J/m²/day、cm/day、hPa，并计算参考蒸散。

## 状态

| 字段 | 定义 |
| --- | --- |
| `lai_m2_m2` | 叶面积指数 |
| `biomass_aboveground_kg_ha` | 地上部干物质，kg/ha |
| `storage_organ_dry_kg_ha` | 贮藏器官干物质，kg/ha；实收产量须另行换算含水率 |
| `dvs` | 引擎原生生育进程；跨引擎比较须统一物候定义 |
| `soil_water_m3_m3` | 可选土壤体积含水率；WOFOST PP 下为设定值 |

前四项为核心状态，要求非负、有限，日期连续且 DVS 不倒退。

## 预测窗口

`windows.npz` 按 `train`、`validation`、`test` 保存 `x`、`y`、`last`：

- `x`：历史状态和天气，拼接未来天气情景。
- `y`：`[样本, 预测日, 目标变量]`，变量顺序为 LAI、地上部干物质、贮藏器官干物质、DVS。
- `last`：预测截止日的状态，用于持续性基线。

`samples.csv` 记录 split、数组索引、生育季、截止日及预测结束日。完整生育季先按年份划分，再生成窗口；标准化仅拟合训练集。未来状态仅用于监督和评分。
