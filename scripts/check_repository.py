"""检查本地 Git 工程基础；不运行应用或模型，不依赖第三方包。"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_TRACKED_BYTES = 10 * 1024 * 1024
REQUIRED_FILES = (
    "AGENT.md",
    "README.md",
    "STATUS.md",
    "CONTRIBUTING.md",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "scripts/check_repository.py",
)


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> int:
    try:
        location = git("rev-parse", "--show-toplevel")
    except FileNotFoundError:
        print("检查失败：未找到 Git，请先安装或确认 PATH。")
        return 1

    if location.returncode != 0:
        print("检查失败：尚未初始化本项目 Git 仓库。")
        return 1
    if Path(location.stdout.strip()).resolve() != ROOT:
        print("检查失败：当前使用的是父目录仓库，请为本项目建立独立仓库。")
        return 1

    problems: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            problems.append(f"缺少基础文件：{relative}")

    for arguments in (("diff", "--check"), ("diff", "--cached", "--check")):
        result = git(*arguments)
        if result.returncode != 0:
            details = (result.stdout + result.stderr).strip()
            problems.append(f"Git 差异检查失败（{' '.join(arguments)}）：\n{details}")

    ignored = git("ls-files", "--cached", "--ignored", "--exclude-standard", "-z")
    if ignored.returncode != 0:
        problems.append(f"无法检查误跟踪文件：{ignored.stderr.strip()}")
    else:
        for relative in filter(None, ignored.stdout.split("\0")):
            problems.append(f"不应被 Git 跟踪的忽略文件：{relative}")

    tracked = git("ls-files", "--cached", "-z")
    if tracked.returncode != 0:
        problems.append(f"无法列出跟踪文件：{tracked.stderr.strip()}")
    else:
        for relative in filter(None, tracked.stdout.split("\0")):
            path = ROOT / relative
            if not path.is_file():
                continue
            try:
                if path.stat().st_size > MAX_TRACKED_BYTES:
                    problems.append(f"跟踪文件超过 10 MiB，请确认是否误提交：{relative}")
                if path.suffix == ".py":
                    ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeError, SyntaxError) as error:
                problems.append(f"文件读取或 Python 语法检查失败：{relative}（{error}）")

    if problems:
        print("仓库基础检查失败：")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("仓库基础检查通过：基础文件、Git 差异、忽略文件、大文件和已跟踪 Python 语法。")
    print("范围说明：未暂存的新文件不在跟踪文件检查内；暂存后请再运行。")
    print("此结果不代表应用、模型、依赖兼容性或安装包已通过验收。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
