# RICESIM-ORYZA 接入状态

当前版本固定为 `81ef4347f13f919c6cc535aca0c6c54590341b48`。源代码已拉取到 `external/ricesim_oryza`，尚未完成真实引擎编译和模拟。

## 已确认的缺项

上游 `input/CONTROL.DAT` 使用 Windows `E:/RICESIM_2022/...` 绝对路径，并引用仓库中不存在的文件：

- `reruns.test.2000.dat`
- `manage.xl753.exp`
- `xl753.crp`
- `PADDYIN-AR-LA.DAT`

仓库没有 Makefile/CMake 等构建配置，附带 `ttutil.lib`、`WEATHER.lib`、`OP_OBS.lib`；其中 `ttutil.lib` 是包含 `.obj` 的静态库。当前 PATH 无 `gfortran`，不能据此假定这些库可直接用于 Linux 构建。也不能用其他 ORYZA 版本的普通品种文件假定已覆盖 RICESIM 新增气体交换、温度响应和热胁迫参数。

## 当前可用入口

```bash
.venv/bin/rice-growth doctor
.venv/bin/rice-growth oryza-prepare --output artifacts/oryza_native_run
.venv/bin/rice-growth oryza-check --config artifacts/oryza_native_run/run.yaml
```

`oryza-prepare` 从 `templates/oryza/` 创建带明确缺项的材料工作区，已有目录拒绝覆盖。模板涵盖资产来源和 SHA-256、原生控制文件、运行映射、构建记录、过程定义及许可信息。未填写字段为 `null`，原生控制模板保留 `.in` 后缀，不会被识别为有效输入。

准备好兼容平台的可执行程序和完整原生输入后，将 `CONTROL.DAT` 与全部被引用的输入放入工作区。填写 `assets.yaml` 的真实文件、来源和哈希，核对逐日输出列名后将 `run.yaml` 的 `mapping_verified` 改为 `true`，通过 `oryza-check` 再执行。配置中的工作目录、程序、清单和标准化结果路径均相对于配置文件；原生 `output` 相对于 `workdir`。

```bash
.venv/bin/rice-growth oryza-run --config /absolute/path/to/oryza_run.yaml
```

运行器检查输入、材料登记和输出碰撞，使用显式工作目录调用引擎，保存标准输出/错误日志，超时也保留已捕获日志。结果转换支持 ISO 日期或年份+年积日，要求四项核心状态与逐日连续日期，标准化后保存 CSV。当前解析器支持单个空白分隔日表；遇到上游多表/其他表头格式时需据真实产物扩展，不能宣称通用格式已验证。

`oryza-check` 在运行材料不齐时返回退出码 1，并单独报告构建字段、参考结果和许可字段的登记状态。登记检查通过不等于完成数值验证或确认许可。完整缺项和向提供方索取材料的文本见 [RICESIM_MATERIALS.md](RICESIM_MATERIALS.md)。

`op.dat` 为季末汇总，不能作为逐日轨迹。当前解析/进程测试使用专门的格式夹具程序，未将其当作 ORYZA 引擎。通用 `Season` 适配接口已提供，但原生天气/管理文件自动生成、逐日状态读写和 EnKF 尚待真实参考案例验证。

上游参考：[源码仓库](https://github.com/USDA-ARS-ACSL/RICESIM-ORYZA)、[控制文件](https://github.com/USDA-ARS-ACSL/RICESIM-ORYZA/blob/81ef4347f13f919c6cc535aca0c6c54590341b48/input/CONTROL.DAT)。
