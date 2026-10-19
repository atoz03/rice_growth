# RICESIM 原生案例工作区

这是材料接收模板，不是可运行的参考案例。`null` 表示尚未取得或核验，不能用零值或任意默认参数替代。

1. 将真实输入放入 `input/`、天气放入 `weather/`、程序放入 `bin/`、参考结果放入 `reference/`。
2. 在 `assets.yaml` 登记文件相对路径、来源和 SHA-256；用 `sha256sum 文件路径` 获取校验值。
3. 填写 `build.yaml`、`rights.yaml` 和 `processes.yaml`，分别记录构建、使用许可及过程定义。
4. 根据真实案例填写 `input/CONTROL.DAT.in`，另存为 `input/CONTROL.DAT`。`.in` 文件不会被当作有效原生输入。
5. 配置 `run.yaml` 的真实输出列名，确认后将 `mapping_verified` 设为 `true`。默认的列名只用于说明映射结构。
6. `rice-growth oryza-check --config 工作区/run.yaml` 会分别报告运行、数值验证和发布材料是否就绪。

`run.yaml` 的工作目录、程序及标准化结果路径均相对于该配置文件；原生日表 `output` 相对于 `workdir`。必须用独立运行目录，程序执行前指定输出不能已存在。

放入文件不代表已经验证：本工具只检查登记材料、哈希、路径和输出契约；参数完整性、ABI、方程和数值一致性仍需通过真实引擎案例核验。
