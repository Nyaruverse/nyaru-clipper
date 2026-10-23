from __future__ import annotations

from typing import Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field, model_validator

DatabaseState = Literal["N", "R", "C"]
ReceiptState = Literal["missing", "corrupt", "valid"]
OutputState = Literal["zero", "partial", "all", "bad"]


class ReceiptError(ValueError):
    pass


class OutputMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    staging: str
    target: str
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PreparedReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    publication_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_id: str
    step_id: str
    attempt: int = Field(ge=1)
    execution_token: str
    snapshot_sha256: str
    input_sha256: str
    configuration_sha256: str
    child_snapshot_sha256: str
    document_sha256: str | None
    sqlite_journal_mode: Literal["delete", "truncate", "persist", "wal"]
    sqlite_synchronous: int = Field(ge=2, le=3)
    outputs: tuple[OutputMember, ...] = Field(min_length=1)
    set_sha256: str

    @model_validator(mode="after")
    def distinct_members(self) -> PreparedReceipt:
        for values in ([member.role for member in self.outputs], [member.target for member in self.outputs]):
            if len(set(values)) != len(values):
                raise ReceiptError("publication members must be unique")
        return self


def recovery_decision(database: DatabaseState, receipt: ReceiptState, outputs: OutputState,
                      eligible: bool, staging: bool) -> str:
    if receipt == "corrupt":
        return "J00"
    if not eligible:
        return "J14" if database == "C" else "J01"
    if receipt == "missing":
        if database != "N":
            return "J04"
        return "J02" if outputs == "zero" else "J03"
    match database:
        case "N":
            if outputs != "zero":
                return "J07"
            return "J05" if staging else "J06"
        case "R":
            match outputs:
                case "all":
                    return "J10"
                case "bad":
                    return "J11"
                case "zero" | "partial":
                    return "J08" if staging else "J09"
                case _:
                    assert_never(outputs)
        case "C":
            return "J12" if outputs == "all" else "J13"
        case _:
            assert_never(database)
