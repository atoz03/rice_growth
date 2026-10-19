"""命令行入口。"""

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .schema import ROOT


def doctor():
    from .adapters.oryza import inspect_inputs

    return {
        "python": sys.version.split()[0],
        "pcse_installed": importlib.util.find_spec("pcse") is not None,
        "rice_parameters": (ROOT / "external/wofost_crop_parameters/rice.yaml").is_file(),
        "gfortran": shutil.which("gfortran"),
        "oryza": inspect_inputs(ROOT / "external/ricesim_oryza"),
        "oryza_note": "上游无构建脚本且包含 .obj 静态库；可编译性未确认。",
    }


def main():
    parser = argparse.ArgumentParser(description="水稻机理与预测研究管线")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查依赖和 ORYZA 输入缺项")
    demo = sub.add_parser("demo", help="执行人工天气、WOFOST 水稻模拟与多步预测闭环")
    demo.add_argument("--config", type=Path, default=ROOT / "configs/demo.yaml")
    demo.add_argument("--output", type=Path, default=None)
    oryza = sub.add_parser("oryza-run", help="调用已有 ORYZA 可执行程序，转换已定义格式的逐日结果")
    oryza.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        elif args.command == "demo":
            from .pipeline import run_demo
            output = args.output or ROOT / "artifacts" / datetime.now().strftime("demo_%Y%m%d_%H%M%S_%f")
            run_demo(args.config, output)
        else:
            import yaml
            from .adapters.oryza import run_oryza
            config = yaml.safe_load(args.config.read_text())
            normalized_output = Path(config.pop("normalized_output"))
            if normalized_output.exists():
                raise ValueError(f"结果文件已存在：{normalized_output}")
            frame = run_oryza(**config)
            normalized_output.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(normalized_output, index=False)
            print(f"ORYZA 轨迹已保存：{normalized_output}")
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(1, f"运行失败：{exc}\n")


if __name__ == "__main__":
    main()
