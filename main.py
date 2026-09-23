#!/usr/bin/env python3
"""陶艺窑位装烧台 —— 入口模块（命令行）。

依赖：rules（规则）、storage（本地存档），均只用 Python 标准库。
每次成功执行会自动保存，程序重启后窑位/高度/批次状态全部保留。

运行：python3 main.py
"""
from __future__ import annotations

import storage
import rules


class Station:
    """装烧台交互会话：持有当前数据并在每次变更后存档。"""

    def __init__(self) -> None:
        self.data, msg = storage.load_data()
        self.saved = True
        print(msg)

    # ---- 存档 ----
    def persist(self) -> None:
        ok, msg = storage.save_data(self.data)
        self.saved = ok
        print(msg if ok else f"⚠ {msg}")

    # ---- 展示 ----
    def show(self) -> None:
        print("\n========== 窑位现状 ==========")
        for kiln in self.data["kilns"]:
            print(
                f"[{kiln['id']}] {kiln['name']}（{kiln['kind']}）"
                f" 温度档：{'/'.join(kiln['temps'])}"
            )
            print(
                f"    状态：{kiln['status']}    "
                f"高度：{kiln['used_height']:g}/{kiln['height_limit']:g}cm"
            )
            if kiln["batches"]:
                print(f"    在窑批次：{'、'.join(kiln['batches'])}")
        print("------ 坯体批次 ------")
        for b in self.data["batches"]:
            place = f"，在 {b['kiln_id']}" if b["kiln_id"] else ""
            print(
                f"[{b['id']}] {b['name']} | 泥种：{b['clay']} | 釉料：{b['glaze']} "
                f"| 目标：{b['temp']} | 高度：{b['height']:g}cm "
                f"| {b['status']}{place}"
            )
        print("==============================")

    # ---- 选择工具 ----
    def choose_kiln(self) -> str | None:
        for kiln in self.data["kilns"]:
            print(f"  {kiln['id']}  {kiln['name']}（{kiln['kind']}）")
        kid = input("请输入窑号（直接回车取消）：").strip()
        if not kid:
            print("已取消。")
            return None
        if rules.find_kiln(self.data, kid) is None:
            print("没有这座窑。")
            return None
        return kid

    def choose_batch(self) -> str | None:
        for b in self.data["batches"]:
            print(f"  {b['id']}  {b['name']}（{b['status']}）")
        bid = input("请输入批号（直接回车取消）：").strip()
        if not bid:
            print("已取消。")
            return None
        if rules.find_batch(self.data, bid) is None:
            print("没有这个批次。")
            return None
        return bid

    # ---- 各操作 ----
    def do_load(self) -> None:
        print("\n-- 装窑 --")
        kid = self.choose_kiln()
        if kid is None:
            return
        bid = self.choose_batch()
        if bid is None:
            return
        ok, msg = rules.load_batch(self.data, kid, bid)
        print(("✔ " if ok else "✘ ") + msg)
        if ok:
            self.persist()

    def do_fire(self) -> None:
        print("\n-- 烧成 --")
        kid = self.choose_kiln()
        if kid is None:
            return
        ok, msg = rules.fire_kiln(self.data, kid)
        print(("✔ " if ok else "✘ ") + msg)
        if ok:
            self.persist()

    def do_open(self) -> None:
        print("\n-- 开窑 --")
        kid = self.choose_kiln()
        if kid is None:
            return
        ok, msg = rules.open_kiln(self.data, kid)
        print(("✔ " if ok else "✘ ") + msg)
        if ok:
            self.persist()

    def do_modify(self) -> None:
        print("\n-- 修改泥种 / 釉料 --")
        bid = self.choose_batch()
        if bid is None:
            return
        batch = rules.find_batch(self.data, bid)
        assert batch is not None
        print(f"当前泥种：{batch['clay']}；当前釉料：{batch['glaze']}")
        clay = input("新泥种（直接回车表示不改）：").strip()
        glaze = input("新釉料（直接回车表示不改）：").strip()
        ok, msg = rules.modify_batch(self.data, bid, clay or None, glaze or None)
        print(("✔ " if ok else "✘ ") + msg)
        if ok:
            self.persist()

    # ---- 主循环 ----
    MENU = """
请选择操作：
  1. 查看窑位与批次
  2. 装窑（选窑与批次）
  3. 烧成（点火）
  4. 开窑（仅烧成后可开，释放高度）
  5. 修改批次泥种/釉料
  0. 退出
"""

    def run(self) -> None:
        actions = {
            "1": self.show,
            "2": self.do_load,
            "3": self.do_fire,
            "4": self.do_open,
            "5": self.do_modify,
        }
        self.show()
        while True:
            print(self.MENU)
            try:
                choice = input("输入选项：").strip()
            except EOFError:
                print("\n输入结束，退出。")
                break
            if choice == "0":
                print("再见。")
                break
            action = actions.get(choice)
            if action is None:
                print("无效选项，请重新输入。")
                continue
            action()


def main() -> None:
    Station().run()


if __name__ == "__main__":
    main()
