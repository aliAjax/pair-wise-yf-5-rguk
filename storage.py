"""存档模块：装烧台数据的本地持久化。

只用标准库（json / os / tempfile）。写入采用临时文件 + os.replace
原子替换，避免写入中途崩溃损坏存档。重启后由入口模块调用 load，
读不到存档时返回 None（由规则模块生成预置数据）。
"""

import json
import os
import tempfile

from rules import KilnStation

# 存档固定放在本目录下
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "kiln_save.json")


def save(station: KilnStation, path: str = SAVE_PATH) -> None:
    """把装烧台状态写入本地存档。"""
    directory = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(station.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)  # 原子替换
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def load(path: str = SAVE_PATH) -> KilnStation | None:
    """从本地存档读取；没有存档返回 None。"""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return KilnStation.from_dict(data)
