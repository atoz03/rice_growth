"""获取锁定版本的上游；已有源码存在修改或版本不符时停止。"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bootstrap():
    for name, spec in json.loads((ROOT / "external.lock.json").read_text()).items():
        dest = ROOT / "external" / name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", spec["url"], str(dest)], check=True)
            subprocess.run(["git", "-C", str(dest), "checkout", "--detach", spec["commit"]], check=True)
        actual = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
        # pip 生成的 egg-info 与参数读取缓存不属于上游源码修改。
        dirty = subprocess.check_output(["git", "-C", str(dest), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
        if actual != spec["commit"] or dirty:
            raise RuntimeError(f"{dest} 的版本或工作区与锁文件不符，请单独检查；未覆盖本地文件。")
        print(f"{name}: {actual[:12]}")


if __name__ == "__main__":
    bootstrap()
