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
    parser = argparse.ArgumentParser(description="水稻机理模拟与生长轨迹预测")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查依赖和 ORYZA 输入缺项")
    demo = sub.add_parser("demo", help="运行 WOFOST 水稻模拟与多步预测示例")
    demo.add_argument("--config", type=Path, default=ROOT / "configs/demo.yaml")
    demo.add_argument("--output", type=Path, default=None)
    oryza = sub.add_parser("oryza-run", help="运行 ORYZA 并转换逐日结果")
    oryza.add_argument("--config", type=Path, required=True)
    prepare = sub.add_parser("oryza-prepare", help="创建 RICESIM 运行目录")
    prepare.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("oryza-check", help="检查输入和运行配置")
    check.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        elif args.command == "demo":
            from .pipeline import run_demo

            output = args.output or ROOT / "artifacts" / datetime.now().strftime(
                "demo_%Y%m%d_%H%M%S_%f"
            )
            run_demo(args.config, output)
        elif args.command == "oryza-prepare":
            from .oryza_workspace import prepare_workspace

            print(f"运行目录已创建：{prepare_workspace(args.output)}")
        elif args.command == "oryza-check":
            from .oryza_workspace import check_workspace

            status = check_workspace(args.config)
            print(json.dumps(status, ensure_ascii=False, indent=2))
            if not status["ready"]:
                parser.exit(1)
        else:
            from .adapters.oryza import run_oryza
            from .oryza_workspace import check_workspace, load_config

            status = check_workspace(args.config)
            if not status["ready"]:
                raise ValueError("；".join(status["run_blockers"]))
            config = load_config(args.config)
            config.pop("asset_manifest", None)
            config.pop("mapping_verified", None)
            normalized_output = Path(config.pop("normalized_output"))
            if normalized_output.exists():
                raise ValueError(f"结果文件已存在：{normalized_output}")
            frame = run_oryza(**config)
            normalized_output.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(normalized_output, index=False)
            print(f"ORYZA 轨迹已保存：{normalized_output}")
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"运行失败：{exc}\n")


if __name__ == "__main__":
    main()
