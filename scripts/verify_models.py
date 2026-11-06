"""校验本地模型资产；退出码 0=齐全，1=缺失/清单错误，不下载文件。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.model_catalog import inspect_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="检查本地 CT2 模型与 VAD 必需文件。")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "models" / "manifest.json",
        help="本地 manifest 路径",
    )
    arguments = parser.parse_args()
    report = inspect_manifest(arguments.manifest, ROOT)
    print(f"模型清单：{report['manifest_path']}")
    for error in report["errors"]:
        print(f"错误：{error}")
    for model in report["models"]:
        state = "OK" if model["ok"] else "缺失"
        print(f"模型 {model['id']}：{state}（{model['path']}）")
        for check in model["files"]:
            print(f"  {'OK' if check['ok'] else '缺失'}：{check['path']}")
    if report["vad"]:
        print(f"VAD：{'OK' if report['vad']['ok'] else '缺失'}")
        for check in report["vad"]["files"]:
            print(f"  {'OK' if check['ok'] else '缺失'}：{check['path']}")
    print(
        "模型文件检查通过。"
        if report["models_ok"]
        else "模型文件未齐全，请按上述路径准备本地资产；未执行下载。"
    )
    return 0 if report["models_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
