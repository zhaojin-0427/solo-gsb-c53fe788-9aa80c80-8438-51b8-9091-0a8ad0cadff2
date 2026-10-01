from fractions import Fraction
import re
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator

ID_PATTERN = re.compile(r"^[\w一-鿿][\w一-鿿.-]{0,31}$", re.UNICODE)
DECIMAL_PATTERN = re.compile(r"^\d+(?:\.\d{1,2})?$")


class GroupInput(BaseModel):
    id: str
    voc: str
    isc: str

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("编号必须是字符串")
        value = value.strip()
        if not value or not ID_PATTERN.match(value):
            raise ValueError(
                "编号需为 1～32 个字符，可含中英文、数字、下划线、点或连字符"
            )
        return value

    @field_validator("voc", "isc", mode="before")
    @classmethod
    def validate_decimal(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("电气参数必须使用字符串提交")
        value = value.strip()
        if not DECIMAL_PATTERN.match(value) or Fraction(value) <= 0:
            raise ValueError("参数必须是正数，且至多保留两位小数")
        return value

    def fraction(self, name: str) -> Fraction:
        return Fraction(getattr(self, name))


class CalculateRequest(BaseModel):
    title: Annotated[str | None, Field(max_length=80)] = None
    groups: list[GroupInput] = Field(min_length=3, max_length=9)
    baseline: list[list[str]] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_model(self) -> "CalculateRequest":
        ids = [group.id for group in self.groups]
        if len(set(ids)) != len(ids):
            raise ValueError("旁路组编号必须唯一")

        for group in self.groups:
            voc = group.fraction("voc")
            isc = group.fraction("isc")
            if not (0 < voc <= 100):
                raise ValueError(f"组 {group.id} 的开路电压 Voc 必须满足 0 < Voc ≤ 100 V")
            if not (0 < isc <= 30):
                raise ValueError(f"组 {group.id} 的短路电流 Isc 必须满足 0 < Isc ≤ 30 A")

        if len(self.baseline) < 1 or len(self.baseline) > 3:
            raise ValueError("基线接线必须包含 1～3 个串")

        normalized: list[list[str]] = []
        seen: set[str] = set()
        for index, string in enumerate(self.baseline, start=1):
            if not string:
                raise ValueError(f"基线第 {index} 串不能为空")
            cleaned: list[str] = []
            for group_id in string:
                if not isinstance(group_id, str) or not group_id.strip():
                    raise ValueError("基线中的组编号必须是非空字符串")
                group_id = group_id.strip()
                if group_id not in ids:
                    raise ValueError(f"基线包含不存在的组编号：{group_id}")
                if group_id in seen:
                    raise ValueError(f"组 {group_id} 在基线中必须恰好出现一次")
                seen.add(group_id)
                cleaned.append(group_id)
            normalized.append(cleaned)

        if seen != set(ids):
            missing = sorted(set(ids) - seen)
            raise ValueError("每组必须在基线中恰好出现一次，缺少：" + "、".join(missing))

        object.__setattr__(self, "baseline", normalized)
        if self.title is not None:
            object.__setattr__(self, "title", self.title.strip() or None)
        return self


def number(value: Fraction) -> float:
    return float(value)


def serialize_group(group) -> dict[str, object]:
    return {"id": group.id, "voc": number(group.voc), "isc": number(group.isc)}


def serialize_curve(curve) -> dict[str, object]:
    return {
        "voc": number(curve.voc),
        "segments": [
            {
                "v0": number(segment.v0),
                "v1": number(segment.v1),
                "a": number(segment.a),
                "b": number(segment.b),
            }
            for segment in curve.segments
        ],
    }


def serialize_wiring(result) -> dict[str, object]:
    return {
        "strings": [list(group_ids) for group_ids in result.wiring],
        "stringCount": len(result.wiring),
        "peak": {
            "voltage": number(result.peak.voltage),
            "current": number(result.peak.current),
            "power": number(result.peak.power),
        },
        "curve": serialize_curve(result.curve),
    }
