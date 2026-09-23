"""入口模块：窑位装烧台交互界面。

运行：python main.py
只用标准库。每次操作成功后自动写入本地存档（kiln_save.json），
重启程序自动读回，数据保留。
"""

from rules import KilnStation, RuleError
import storage

MENU = """
====== 陶艺窑位装烧台 ======
1. 查看状态
2. 装窑（选窑 + 选批次）
3. 开烧
4. 烧成结束
5. 开窑（释放高度）
6. 改泥种 / 釉料
0. 退出
=========================="""


def show(station: KilnStation) -> None:
    print("\n--- 窑位 ---")
    for k in station.kilns.values():
        inside = "、".join(
            station.batches[b].name for b in k.batch_ids
        ) or "（空）"
        print(
            f"[{k.kid}] {k.name}｜窑型:{k.model}｜档位:{'/'.join(k.gears)}"
            f"｜高度:{k.used_height:g}/{k.height_limit:g}"
            f"｜状态:{k.status.value}｜坯体:{inside}"
        )
    print("--- 坯体批次 ---")
    for b in station.batches.values():
        place = f"，在 {station.kilns[b.kiln_id].name}" if b.kiln_id else ""
        print(
            f"[{b.bid}] {b.name}｜泥种:{b.clay}｜釉料:{b.glaze}"
            f"｜温档:{b.gear}｜高度:{b.height:g}"
            f"｜状态:{b.status.value}{place}"
        )


def ask(prompt: str) -> str:
    return input(prompt).strip()


def do_load(st: KilnStation) -> None:
    kid = ask("窑编号（如 K1）: ")
    bid = ask("批次编号（如 B1）: ")
    print(st.load(kid, bid))


def do_start(st: KilnStation) -> None:
    print(st.start_firing(ask("窑编号: ")))


def do_finish(st: KilnStation) -> None:
    print(st.finish_firing(ask("窑编号: ")))


def do_open(st: KilnStation) -> None:
    print(st.open_kiln(ask("窑编号: ")))


def do_change(st: KilnStation) -> None:
    bid = ask("批次编号: ")
    clay = ask("新泥种（直接回车表示不改）: ") or None
    glaze = ask("新釉料（直接回车表示不改）: ") or None
    print(st.change_material(bid, clay=clay, glaze=glaze))


ACTIONS = {
    "1": ("查看状态", None),
    "2": ("装窑", do_load),
    "3": ("开烧", do_start),
    "4": ("烧成结束", do_finish),
    "5": ("开窑", do_open),
    "6": ("改泥种/釉料", do_change),
}


def main() -> None:
    station = storage.load()
    if station is None:
        station = KilnStation.default()
        storage.save(station)
        print("（首次运行，已预置两座窑、四个坯体批次并建档）")
    else:
        print("（已从本地存档恢复）")

    while True:
        print(MENU)
        choice = ask("请选择: ")
        if choice == "0":
            storage.save(station)
            print("已存档，再见。")
            break
        if choice == "1":
            show(station)
            continue
        action = ACTIONS.get(choice)
        if action is None:
            print("无效选项，请重新输入")
            continue
        try:
            action[1](station)
        except RuleError as e:
            print(f"操作被拒：{e}")
            continue
        storage.save(station)
        print("（已自动存档）")


if __name__ == "__main__":
    main()
