# RICESIM 运行目录

1. 放入 `bin/ricesim`、`input/` 和 `weather/` 文件。
2. 填写 `assets.yaml` 的路径、来源及 SHA-256。
3. 替换 `input/CONTROL.DAT.in` 的路径，另存为 `input/CONTROL.DAT`。
4. 填写 `run.yaml` 的生育季信息、输出映射，并设置 `mapping_verified: true`。

```bash
rice-growth oryza-check --config run.yaml
rice-growth oryza-run --config run.yaml
```

配置路径相对于 `run.yaml`，原生 `output` 相对于 `workdir`。结果文件须使用新路径。
