"""陶艺窑位装烧台 —— 本地存档模块。

只用标准库：json 序列化、tempfile + os 实现原子写入，
避免写入中途中断导致存档损坏。数据保存在本地文件，重启后原样保留。
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import rules

# 默认存档放在本模块同目录，随程序携带
DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiln_save.json")


def load_data(path: str = DEFAULT_PATH) -> tuple[dict[str, Any], str]:
    """读取本地存档；不存在或损坏时退回预置数据。

    返回 (数据, 提示信息)。
    """
    if not os.path.exists(path):
        return rules.default_data(), f"未找到存档 {path}，已载入预置的两座窑与四个批次。"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return rules.default_data(), f"存档读取失败（{exc}），已重置为预置数据。"

    # 基本结构校验，缺字段就视为坏档重建，避免运行期 KeyError
    if not isinstance(data, dict) or "kilns" not in data or "batches" not in data:
        return rules.default_data(), "存档结构不正确，已重置为预置数据。"
    return data, f"已读取本地存档：{path}。"


def save_data(data: dict[str, Any], path: str = DEFAULT_PATH) -> tuple[bool, str]:
    """原子写入存档：先写同目录临时文件，再 os.replace 替换正式文件。"""
    directory = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp", prefix=".kiln_save_", dir=directory
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            # 写坏了只清临时文件，不动原有正式存档
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except OSError as exc:
        return False, f"存档写入失败：{exc}"
    return True, f"数据已保存到 {path}。"
