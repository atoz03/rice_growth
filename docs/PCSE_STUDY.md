# PCSE 学习与水稻模型实现路线

当前工作重点是学习 PCSE 的运行框架，将团队模型中已明确的过程逐步实现为 Python 模块，再通过参考案例验证，形成可开源的水稻机理模型版本。团队模型身份、方程、参数和许可尚待材料确认；RICESIM 先作为可阅读的过程参考，不直接等同于团队模型。

## 推荐阅读顺序

执行 `python3 scripts/bootstrap.py` 后，在锁定版本源码中按下列顺序阅读。

| 顺序 | 本地源码 | 需要弄清的问题 | 形成的材料 |
| --- | --- | --- | --- |
| 1 | `external/pcse/pcse/engine.py` | 初始化、逐日速率计算、积分和终止的时序 | 日步进调用图 |
| 2 | `external/pcse/pcse/base/simulationobject.py`、`states_rates.py`、`variablekiosk.py` | 参数、状态、速率如何定义和交换 | 状态与量纲表 |
| 3 | `external/pcse/pcse/conf/Wofost72_PP.conf`、`crop/wofost72.py` | 如何组合过程、管理和输出 | 最小水稻运行说明 |
| 4 | `external/pcse/pcse/crop/phenology.py`、`assimilation.py`、`respiration.py`、`partitioning.py` | 物候、同化、呼吸与分配的方程和参数 | 方程与依赖图 |
| 5 | `external/pcse/pcse/crop/leaf_dynamics.py`、`root_dynamics.py`、`stem_dynamics.py`、`storage_organ_dynamics.py` | 器官状态更新、衰老、质量平衡和状态写接口 | 状态更新与不变量清单 |
| 6 | `external/pcse/pcse/agromanager.py`、`input/`、`soil/` | 天气量纲、事件触发及水分过程适用边界 | 输入契约与管理事件表 |
| 7 | `external/pcse/pcse/tests/`、`external/pcse/tests/` | 上游如何设置参考数据和过程测试 | 我方参考案例验收协议 |

以上路径中的缩写目录在其对应 `external/pcse/pcse/` 下解析。当前 PP 演示用于理解框架；水氮限制和稻田淹水过程需另外验证，不从潜在生产结果推断灌溉施肥效应。

## 与 RICESIM 对照的过程

| 过程 | RICESIM 阅读入口 | 待确认后才能实现的内容 |
| --- | --- | --- |
| 温度与物候 | `PHENOL2.f90`、`SUBDDB.f90` | `SWIPHENO` 分支、日内温度响应、品种系数 |
| 叶片/冠层气体交换 | `SGPL3.F90`、`photosynthesis.f90`、`StomatalConductance.f90`、`EnergyBalance.f90` | `IACC` 分支、气体交换参数表、冠层积分及时间单位 |
| 生物量与分配 | `ORYZA1.f90` | 同化呼吸换算、活/死器官口径、分配与守恒 |
| 叶面积 | `SUBLAI5.f90` 等 | 实际调用版本、叶重与叶面积关系、衰老和状态更新 |
| 水氮 | `Paddy.f90`、`Ncrop2.f90`、`nsoil.f90`、`WStress.f90` | 土壤分层、稻田水量平衡、氮平衡和胁迫反馈 |
| 热胁迫与结实 | `SUBGRN5.f90` | `SWIHEAT` 分支、硬编码系数、适用品种与实验依据 |

这些是候选阅读入口，须追踪真实调用和开关后确认启用过程。材料接收模板 `templates/oryza/processes.yaml` 用于记录方程、参数、单位和参考案例，不将未实现模块注册为可用模型。

## 实现顺序与验收

1. 固定现有 WOFOST 水稻结果，保存完整输入、关键物候日期和逐日状态作为框架回归基线。
2. 确认团队模型的名称、版本、可用方程与参数；建立与 PCSE/RICESIM 的过程差异表。
3. 优先实现物候，再实现同化、分配与器官生长；水氮和热胁迫依赖前面过程稳定后接入。
4. 每个过程先校验单位、边界和局部参考值，再做完整生育季对照；不一致时定位方程、参数或积分时序差异。
5. 在冻结的参考案例上定义各变量绝对/相对容差及关键阶段日期容差，再评价数值一致性；容差暂不随意指定。
6. 开源发布前整理模型名称、版本、理论说明、适用范围、可公开参数和许可证；参数与代码分别保留来源及署名。

现有预测与数据 pipeline 保留为模拟结果消费方；多模态、MoE、PEFT 在机理模型可复现后推进。

参考资料：[PCSE 官方文档](https://pcse.readthedocs.io/)、[PCSE 上游源码](https://github.com/ajwdewit/pcse)、[RICESIM 上游源码](https://github.com/USDA-ARS-ACSL/RICESIM-ORYZA)。学习时应以锁定版本源码为准，文档可能对应其他版本。
