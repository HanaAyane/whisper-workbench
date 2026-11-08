"""按任务隔离临时文件，并在正常或异常退出时清理。"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import Settings

_JOB_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


@contextmanager
def job_temp_directory(job_id: str, *, base_dir: str | Path | None = None) -> Iterator[Path]:
    """创建 ``data/tmp/<job-id>`` 等价目录，离开上下文即递归删除。"""

    if not _JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("任务 ID 只能包含 ASCII 字母、数字、下划线和连字符，最长 128 字符。")
    root = Path(base_dir) if base_dir is not None else Settings.from_env().temp_dir
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / job_id
    try:
        workspace.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f"任务临时目录已存在，拒绝覆盖：{workspace}") from exc
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace)
