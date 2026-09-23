"""规则模块：窑位装烧的领域模型与业务规则。

只负责规则判定与状态流转，不涉及任何文件读写。
- 装窑：温度档必须在窑支持的档位内；占用高度 + 本批高度不得超限；
        同一批次只能装一次；违规时整批退回，窑位保持不变。
- 改料：批次改泥种或釉料后，若已排定装窑，则退回待装（窑同步释放）。
- 烧成：装窑完成 -> 开烧 -> 烧成 -> 开窑释放高度，未烧成不得开窑。
"""

from dataclasses import dataclass, field
from enum import Enum

# ---- 温度档 ----
LOW = "低温"
MID = "中温"
HIGH = "高温"
TEMP_GEARS = (LOW, MID, HIGH)


class BatchStatus(str, Enum):
    """坯体批次状态。"""
    WAITING = "待装"        # 未入窑
    SCHEDULED = "已排定"    # 已装入某窑，等待开烧
    FIRING = "烧成中"       # 所在窑正在烧成
    DONE = "已烧成"         # 烧成完成并开窑取出


class KilnStatus(str, Enum):
    """窑状态。"""
    IDLE = "空闲"       # 未开烧，可继续装窑或开烧
    FIRING = "烧成中"   # 已开烧未结束，不能开窑
    FINISHED = "已烧成"  # 烧成结束，等待开窑取坯


class RuleError(Exception):
    """业务规则被违反；抛出时所有状态保持原样。"""


@dataclass
class Kiln:
    """一座窑。"""
    kid: str                    # 窑编号
    name: str                   # 窑名
    model: str                  # 窑型
    gears: tuple                # 支持的温度档
    height_limit: float         # 高度上限
    status: KilnStatus = KilnStatus.IDLE
    used_height: float = 0.0    # 已占高度
    batch_ids: list = field(default_factory=list)  # 窑内批次

    def can_accept(self, gear: str, need_height: float) -> tuple[bool, str]:
        """装窑前置校验（不改状态）。"""
        if self.status != KilnStatus.IDLE:
            return False, f"窑「{self.name}」当前{self.status.value}，不能装窑"
        if gear not in self.gears:
            return False, (
                f"温度档 {gear} 不在窑「{self.name}」支持的档位"
                f"（{'/'.join(self.gears)}），整批退回"
            )
        if self.used_height + need_height > self.height_limit:
            return False, (
                f"已占高度 {self.used_height:g} + 本批 {need_height:g} "
                f"超过上限 {self.height_limit:g}，整批退回"
            )
        return True, ""


@dataclass
class Batch:
    """一个坯体批次。"""
    bid: str                    # 批次编号
    name: str                   # 批次名称
    clay: str                   # 泥种
    glaze: str                  # 釉料
    gear: str                   # 所需温度档
    height: float               # 本批占用高度
    status: BatchStatus = BatchStatus.WAITING
    kiln_id: str | None = None  # 所在窑（待装时为 None）


class KilnStation:
    """窑位装烧台：聚合所有窑与批次，承载全部业务规则。"""

    def __init__(self, kilns=None, batches=None):
        self.kilns: dict[str, Kiln] = kilns or {}
        self.batches: dict[str, Batch] = batches or {}

    # ---- 预置数据 ----
    @classmethod
    def default(cls):
        """预置两座窑、四个坯体批次。"""
        kilns = {
            "K1": Kiln(
                kid="K1", name="一号柴窑", model="柴窑",
                gears=(LOW, MID), height_limit=100.0,
            ),
            "K2": Kiln(
                kid="K2", name="二号气窑", model="气窑",
                gears=(MID, HIGH), height_limit=80.0,
            ),
        }
        batches = {
            "B1": Batch("B1", "青瓷碗批", "龙泉土", "青釉", MID, 40.0),
            "B2": Batch("B2", "白瓷杯批", "高岭土", "透明釉", HIGH, 30.0),
            "B3": Batch("B3", "陶土花器批", "粗陶土", "无釉", LOW, 50.0),
            "B4": Batch("B4", "釉里红盘批", "高岭土", "铜红釉", MID, 45.0),
        }
        return cls(kilns, batches)

    # ---- 内部查找 ----
    def _kiln(self, kid: str) -> Kiln:
        kiln = self.kilns.get(kid)
        if kiln is None:
            raise RuleError(f"没有编号为 {kid} 的窑")
        return kiln

    def _batch(self, bid: str) -> Batch:
        batch = self.batches.get(bid)
        if batch is None:
            raise RuleError(f"没有编号为 {bid} 的批次")
        return batch

    # ---- 装窑 ----
    def load(self, kid: str, bid: str) -> str:
        """把批次装入窑。

        校验失败（档位不符 / 超高 / 重复装窑 / 窑状态不对）时抛出
        RuleError，整批退回、窑位不变（本实现先校验后改状态，
        任何失败路径都不会产生部分修改）。
        """
        kiln = self._kiln(kid)
        batch = self._batch(bid)

        if batch.status != BatchStatus.WAITING:
            raise RuleError(
                f"批次「{batch.name}」当前{batch.status.value}，"
                "同一批次只能装一次"
            )
        ok, reason = kiln.can_accept(batch.gear, batch.height)
        if not ok:
            raise RuleError(reason)

        # 全部通过后才落状态
        kiln.used_height += batch.height
        kiln.batch_ids.append(bid)
        batch.status = BatchStatus.SCHEDULED
        batch.kiln_id = kid
        return (
            f"已将批次「{batch.name}」装入窑「{kiln.name}」："
            f"占用 {batch.height:g}，已占 {kiln.used_height:g}/"
            f"{kiln.height_limit:g}"
        )

    # ---- 改泥种 / 釉料 ----
    def change_material(self, bid: str, *, clay: str | None = None,
                        glaze: str | None = None) -> str:
        """修改泥种或釉料；若批次已排定装窑，退回待装并释放窑位。

        烧成中、已烧成的批次不允许再改料。只改其中一项时另一项保持不变。
        """
        batch = self._batch(bid)
        if batch.status in (BatchStatus.FIRING, BatchStatus.DONE):
            raise RuleError(
                f"批次「{batch.name}」{batch.status.value}，不能再改泥种或釉料"
            )
        if clay is None and glaze is None:
            raise RuleError("未指定要修改的泥种或釉料")

        old_clay, old_glaze = batch.clay, batch.glaze
        was_scheduled = batch.status == BatchStatus.SCHEDULED

        changes = []
        if clay is not None and clay != old_clay:
            changes.append(f"泥种 {old_clay} → {clay}")
        if glaze is not None and glaze != old_glaze:
            changes.append(f"釉料 {old_glaze} → {glaze}")
        if not changes:
            return f"批次「{batch.name}」泥种釉料未变化"

        batch.clay = clay if clay is not None else old_clay
        batch.glaze = glaze if glaze is not None else old_glaze

        note = ""
        if was_scheduled:
            kiln = self.kilns[batch.kiln_id]
            kiln.used_height -= batch.height
            kiln.batch_ids.remove(bid)
            batch.status = BatchStatus.WAITING
            batch.kiln_id = None
            note = "，已排定装窑回到待装，窑位已释放"

        return f"批次「{batch.name}」{'；'.join(changes)}{note}"

    # ---- 开烧 ----
    def start_firing(self, kid: str) -> str:
        """窑开烧：装有待烧批次的空闲窑进入烧成中。"""
        kiln = self._kiln(kid)
        if kiln.status != KilnStatus.IDLE:
            raise RuleError(f"窑「{kiln.name}」当前{kiln.status.value}，不能开烧")
        if not kiln.batch_ids:
            raise RuleError(f"窑「{kiln.name}」内没有批次，不能空烧")

        kiln.status = KilnStatus.FIRING
        for bid in kiln.batch_ids:
            self.batches[bid].status = BatchStatus.FIRING
        return f"窑「{kiln.name}」开烧，批次 {len(kiln.batch_ids)} 个，烧成中"

    # ---- 烧成 ----
    def finish_firing(self, kid: str) -> str:
        """烧成结束：烧成中 → 已烧成，但必须开窑后才释放高度。"""
        kiln = self._kiln(kid)
        if kiln.status != KilnStatus.FIRING:
            raise RuleError(
                f"窑「{kiln.name}」当前{kiln.status.value}，没有正在进行的烧成"
            )
        kiln.status = KilnStatus.FINISHED
        for bid in kiln.batch_ids:
            self.batches[bid].status = BatchStatus.DONE
        return f"窑「{kiln.name}」烧成完毕，等待开窑取坯"

    # ---- 开窑 ----
    def open_kiln(self, kid: str) -> str:
        """开窑取坯，释放占用高度。未烧成不得开窑。"""
        kiln = self._kiln(kid)
        if kiln.status == KilnStatus.IDLE:
            raise RuleError(f"窑「{kiln.name}」本就空闲，无需开窑")
        if kiln.status == KilnStatus.FIRING:
            raise RuleError(f"窑「{kiln.name}」烧成未结束，不得开窑")

        taken = len(kiln.batch_ids)
        for bid in kiln.batch_ids:
            batch = self.batches[bid]
            batch.kiln_id = None  # 已烧成取出
        released = kiln.used_height
        kiln.used_height = 0.0
        kiln.batch_ids = []
        kiln.status = KilnStatus.IDLE
        return f"窑「{kiln.name}」开窑，取出 {taken} 个批次，释放高度 {released:g}"

    # ---- 序列化 ----
    def to_dict(self) -> dict:
        return {
            "kilns": [
                {
                    "kid": k.kid, "name": k.name, "model": k.model,
                    "gears": list(k.gears), "height_limit": k.height_limit,
                    "status": k.status.value, "used_height": k.used_height,
                    "batch_ids": list(k.batch_ids),
                }
                for k in self.kilns.values()
            ],
            "batches": [
                {
                    "bid": b.bid, "name": b.name, "clay": b.clay,
                    "glaze": b.glaze, "gear": b.gear, "height": b.height,
                    "status": b.status.value, "kiln_id": b.kiln_id,
                }
                for b in self.batches.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KilnStation":
        kilns = {}
        for row in data.get("kilns", []):
            kilns[row["kid"]] = Kiln(
                kid=row["kid"], name=row["name"], model=row["model"],
                gears=tuple(row["gears"]), height_limit=row["height_limit"],
                status=KilnStatus(row["status"]),
                used_height=row["used_height"],
                batch_ids=list(row["batch_ids"]),
            )
        batches = {}
        for row in data.get("batches", []):
            batches[row["bid"]] = Batch(
                bid=row["bid"], name=row["name"], clay=row["clay"],
                glaze=row["glaze"], gear=row["gear"], height=row["height"],
                status=BatchStatus(row["status"]), kiln_id=row["kiln_id"],
            )
        return cls(kilns, batches)
