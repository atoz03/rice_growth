# 数据契约

## 生育季与来源

`season_id` 对应一个地块的一个完整生育季，同时保留 `site_id`、`year`、`variety`。`year` 表示该生育季所属年份，跨年季节仍保持一致。后续加入 `field_id`、地块范围、播栽/出苗日期及管理制度。

轨迹中的 `source=mechanistic_simulation` 与 `engine` 标明模拟引擎；演示天气为 `weather_source=synthetic_demo`。真实数据后续使用独立来源值，不覆盖模拟标识。

## 逐日天气

| 字段 | 单位 |
| --- | --- |
| `date` | 当地农事日期，ISO YYYY-MM-DD |
| `tmin_c`、`tmax_c` | °C |
| `radiation_mj_m2_day` | MJ/m²/day |
| `rain_mm_day` | mm/day |
| `vapour_pressure_kpa` | kPa |
| `wind_m_s` | m/s，2 米高度 |

机理引擎需要连续日天气，缺日会拒绝运行；原始观测的缺失处理必须另外记录。PCSE 适配器显式转换到 J/m²/day、cm/day、hPa，并从天气计算参考蒸散；不要求调用方猜测 PCSE 量纲。

## 逐日状态

| 字段 | 含义及限制 |
| --- | --- |
| `lai_m2_m2` | 叶面积指数 |
| `biomass_aboveground_kg_ha` | 地上部总干物质；须核对死亡器官是否计入 |
| `storage_organ_dry_kg_ha` | 贮藏器官干物质；实收产量需单独记录含水率及换算口径 |
| `dvs` | 引擎原生生育进程，保留引擎语义，不能直接等同于离散物候阶段 |
| `soil_water_m3_m3` | 可选土壤体积含水率；PP 下为模型设定值，非实测 |

当前核心四变量要求非负、有限，日期连续且原生 DVS 不倒退。株高、具体生育阶段、水氮胁迫等后续由具备实际输出或观测的引擎/数据源补充；不支持即缺失，不推造标签。

## 样本与信息边界

当前 `windows.npz` 存储各 split 的 `x`、`y` 和 `last`。输入是历史状态与天气，以及未来天气情景；输出为 `[样本, 预测日, 目标变量]`，目标顺序为 LAI、地上部干物质、贮藏器官干物质、DVS。`samples.csv` 对齐数组序号并记录季节、截止日、目标结束日和来源。

先按年份划分完整生育季，再生成窗口；标准化仅使用训练集。未来标签只用于训练监督和评分。当前历史状态是模拟器可观测的理想状态，真实数据稀疏时需增加掩码与可获取时刻，不能直接视作实用预测协议。

后续异步观测表增加 `observed_at`、`available_at`、`modality`、`quality_score`、`source_id`、`mask`；图像存 URI 与采集元数据，管理表存事件时间、剂量、单位和计划/实际标识。划分同时绑定原始季节及其派生样本。
