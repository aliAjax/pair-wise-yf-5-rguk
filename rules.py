"""陶艺窑位装烧台 —— 业务规则模块。

只包含纯数据结构与业务判定，不读写文件、不处理输入输出，
方便单独测试，也与存档模块（storage.py）、入口模块（main.py）解耦。

数据模型：
  窑 kiln:   id / name / kind(窑型) / temps(温度档列表) /
             height_limit(高度上限 cm) / used_height(已占高度 cm) /
             status(空窑/已装窑/已烧成) / batches(在窑批次 id 列表)
  批次 batch: id / name / clay(泥种) / glaze(釉料) / temp(目标温度档) /
             height(本批高度 cm) / kiln_id(所在窑 id) /
             status(待装/已排定/已完成)
"""
from __future__ import annotations

from typing import Any

# ---- 窑状态 ----
EMPTY = "空窑"      # 窑内无批次，可装窑
LOADED = "已装窑"   # 已装入批次，尚未烧成
FIRED = "已烧成"    # 烧成结束，等待开窑

# ---- 批次状态 ----
PENDING = "待装"     # 尚未装窑
SCHEDULED = "已排定"  # 已装窑，占用窑位高度
DONE = "已完成"      # 开窑后烧成完成，窑位已释放


def default_data() -> dict[str, Any]:
    """预置两座窑和四个坯体批次的初始存档。"""
    return {
        "kilns": [
            {
                "id": "K1",
                "name": "一号燃气窑",
                "kind": "燃气梭式窑",
                "temps": ["素烧", "中温", "高温"],
                "height_limit": 120.0,
                "used_height": 0.0,
                "status": EMPTY,
                "batches": [],
            },
            {
                "id": "K2",
                "name": "二号电窑",
                "kind": "电窑",
                "temps": ["素烧", "中温"],
                "height_limit": 80.0,
                "used_height": 0.0,
                "status": EMPTY,
                "batches": [],
            },
        ],
        "batches": [
            {
                "id": "B1",
                "name": "青瓷茶杯批",
                "clay": "龙泉青瓷土",
                "glaze": "梅子青釉",
                "temp": "高温",
                "height": 40.0,
                "kiln_id": None,
                "status": PENDING,
            },
            {
                "id": "B2",
                "name": "白瓷餐盘批",
                "clay": "德化白瓷土",
                "glaze": "透明釉",
                "temp": "中温",
                "height": 30.0,
                "kiln_id": None,
                "status": PENDING,
            },
            {
                "id": "B3",
                "name": "粗陶花器批",
                "clay": "宜兴粗陶土",
                "glaze": "无釉",
                "temp": "素烧",
                "height": 55.0,
                "kiln_id": None,
                "status": PENDING,
            },
            {
                "id": "B4",
                "name": "天目茶碗批",
                "clay": "建盏铁胎土",
                "glaze": "兔毫天目釉",
                "temp": "高温",
                "height": 35.0,
                "kiln_id": None,
                "status": PENDING,
            },
        ],
    }


# ---------------- 查找工具 ----------------

def find_kiln(data: dict[str, Any], kiln_id: str) -> dict[str, Any] | None:
    for kiln in data["kilns"]:
        if kiln["id"] == kiln_id:
            return kiln
    return None


def find_batch(data: dict[str, Any], batch_id: str) -> dict[str, Any] | None:
    for batch in data["batches"]:
        if batch["id"] == batch_id:
            return batch
    return None


# ---------------- 装窑规则 ----------------

def load_batch(data: dict[str, Any], kiln_id: str, batch_id: str) -> tuple[bool, str]:
    """把一整个批次装入指定窑。

    规则：
      1. 同一批次只能装一次（已排定/已完成的批次不能再装）；
      2. 批次目标温度档必须在该窑支持的档位内；
      3. 窑内已占高度 + 本批高度不得超过高度上限；
      4. 已烧成未开窑的窑不能再装。
    任何一条不满足：整批退回，窑位保持不变（本函数在全部校验
    通过前不修改任何数据）。
    """
    kiln = find_kiln(data, kiln_id)
    batch = find_batch(data, batch_id)
    if kiln is None:
        return False, f"没有窑号为 {kiln_id} 的窑。"
    if batch is None:
        return False, f"没有批号为 {batch_id} 的批次。"

    # 规则 1：同一批次只装一次
    if batch["status"] == SCHEDULED:
        return False, (
            f"批次 {batch['id']}（{batch['name']}）已排定装入 "
            f"{batch['kiln_id']}，同一批次只装一次，整批退回，窑位不变。"
        )
    if batch["status"] == DONE:
        return False, f"批次 {batch['id']}（{batch['name']}）已烧成完成，不能再次装窑。"

    # 规则 4：烧成未结束不得再装
    if kiln["status"] == FIRED:
        return False, (
            f"{kiln['name']} 已烧成但尚未开窑，不能装窑；请先开窑释放高度。"
        )

    # 规则 2：温度档必须是该窑支持的档位
    if batch["temp"] not in kiln["temps"]:
        return False, (
            f"温度档不符：{batch['name']} 需要【{batch['temp']}】，"
            f"而 {kiln['name']}（{kiln['kind']}）只有档位 "
            f"{'/'.join(kiln['temps'])}。整批退回，窑位不变。"
        )

    # 规则 3：高度校验
    new_used = kiln["used_height"] + batch["height"]
    if new_used > kiln["height_limit"] + 1e-9:
        return False, (
            f"高度超限：{kiln['name']} 已占 {kiln['used_height']:g}cm，"
            f"本批高 {batch['height']:g}cm，合计 {new_used:g}cm，"
            f"超过上限 {kiln['height_limit']:g}cm。整批退回，窑位不变。"
        )

    # 全部通过，落位：占用高度，批次排定
    kiln["used_height"] = round(new_used, 6)
    kiln["batches"].append(batch["id"])
    kiln["status"] = LOADED
    batch["kiln_id"] = kiln["id"]
    batch["status"] = SCHEDULED
    return True, (
        f"装窑成功：{batch['name']}（{batch['temp']}，{batch['height']:g}cm）"
        f"进入 {kiln['name']}，已占高度 "
        f"{kiln['used_height']:g}/{kiln['height_limit']:g}cm。"
    )


# ---------------- 烧成规则 ----------------

def fire_kiln(data: dict[str, Any], kiln_id: str) -> tuple[bool, str]:
    """点火烧成。只有已装窑（窑内有批次）的窑可以烧成。"""
    kiln = find_kiln(data, kiln_id)
    if kiln is None:
        return False, f"没有窑号为 {kiln_id} 的窑。"
    if kiln["status"] == FIRED:
        return False, f"{kiln['name']} 已在烧成结束状态，等待开窑，不能重复点火。"
    if kiln["status"] == EMPTY or not kiln["batches"]:
        return False, f"{kiln['name']} 内没有批次，空窑不能烧成。"

    kiln["status"] = FIRED
    return True, f"{kiln['name']} 点火烧成完成，共 {len(kiln['batches'])} 个批次，开窑后方可释放高度。"


# ---------------- 开窑规则 ----------------

def open_kiln(data: dict[str, Any], kiln_id: str) -> tuple[bool, str]:
    """开窑：烧成结束后才能开窑，开窑释放全部已占高度，批次转为已完成。"""
    kiln = find_kiln(data, kiln_id)
    if kiln is None:
        return False, f"没有窑号为 {kiln_id} 的窑。"
    if kiln["status"] != FIRED:
        return False, f"{kiln['name']} 烧成未结束，不得开窑（请先点火烧成）。"

    finished = list(kiln["batches"])
    for bid in finished:
        batch = find_batch(data, bid)
        if batch is not None:
            batch["status"] = DONE  # kiln_id 保留为烧成记录
    kiln["batches"] = []
    kiln["used_height"] = 0.0
    kiln["status"] = EMPTY
    return True, (
        f"{kiln['name']} 开窑完成，释放全部高度（恢复 0/{kiln['height_limit']:g}cm），"
        f"批次 {'、'.join(finished)} 烧成完成。"
    )


# ---------------- 改泥种 / 釉料规则 ----------------

def modify_batch(
    data: dict[str, Any],
    batch_id: str,
    clay: str | None = None,
    glaze: str | None = None,
) -> tuple[bool, str]:
    """修改批次泥种和/或釉料。

    待装批次：直接修改。
    已排定批次：改泥种或釉料后必须回到待装 —— 自动从所在窑撤出，
    释放该批占用的高度；若所在窑已经烧成（未开窑），则禁止修改。
    已完成批次：禁止修改。
    clay/glaze 传 None 或空串表示该项不改。
    """
    batch = find_batch(data, batch_id)
    if batch is None:
        return False, f"没有批号为 {batch_id} 的批次。"
    if batch["status"] == DONE:
        return False, f"{batch['name']} 已烧成完成，泥种与釉料不能再改。"

    new_clay = clay.strip() if clay and clay.strip() else None
    new_glaze = glaze.strip() if glaze and glaze.strip() else None
    if new_clay is None and new_glaze is None:
        return False, "未填写任何修改内容。"

    reverted = False
    if batch["status"] == SCHEDULED:
        kiln = find_kiln(data, batch["kiln_id"])
        if kiln is not None and kiln["status"] == FIRED:
            return False, (
                f"{batch['name']} 所在的 {kiln['name']} 已烧成尚未开窑，"
                f"不能更改泥种/釉料。"
            )
        if kiln is not None:
            # 撤出窑位、释放高度，回到待装
            kiln["batches"] = [b for b in kiln["batches"] if b != batch["id"]]
            kiln["used_height"] = round(
                max(0.0, kiln["used_height"] - batch["height"]), 6
            )
            kiln["status"] = EMPTY if not kiln["batches"] else LOADED
            kiln_name = kiln["name"]
            batch["kiln_id"] = None
            batch["status"] = PENDING
            reverted = True
        else:
            # 理论上不会出现：状态数据异常时兜底回到待装
            batch["kiln_id"] = None
            batch["status"] = PENDING

    changes = []
    if new_clay is not None and new_clay != batch["clay"]:
        changes.append(f"泥种 {batch['clay']} → {new_clay}")
        batch["clay"] = new_clay
    if new_glaze is not None and new_glaze != batch["glaze"]:
        changes.append(f"釉料 {batch['glaze']} → {new_glaze}")
        batch["glaze"] = new_glaze

    if not changes:
        return False, "填写的内容与现状一致，没有改动。"

    msg = f"{batch['name']} 已修改：{'；'.join(changes)}。"
    if reverted:
        msg += f" 因泥种/釉料变更，已从 {kiln_name} 撤出，回到待装，释放高度 {batch['height']:g}cm。"
    return True, msg
