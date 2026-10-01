from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fractions import Fraction
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from . import database
from .engine import Group, analyze_wiring, canonical_wiring, select_best_wiring
from .schemas import (
    CalculateRequest,
    serialize_group,
    serialize_wiring,
)

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    database.init_db()
    yield


app = FastAPI(title="光伏旁路组重接线试算台", version="1.0.0", lifespan=lifespan)


class SaveRecordPayload(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    input: CalculateRequest
    result: dict

    @model_validator(mode="after")
    def normalize_title(self) -> "SaveRecordPayload":
        if self.title is not None:
            self.title = self.title.strip() or None
        return self


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"] if part != "body")
        message = error["msg"].removeprefix("Value error, ")
        messages.append(f"{location}: {message}" if location else message)
    return JSONResponse(status_code=400, content={"detail": "；".join(messages)})


def to_groups(request: CalculateRequest) -> list[Group]:
    return [
        Group(id=item.id, voc=Fraction(item.voc), isc=Fraction(item.isc))
        for item in request.groups
    ]


@app.post("/api/calculate")
def calculate(request: CalculateRequest) -> dict:
    groups = to_groups(request)
    baseline_wiring = canonical_wiring(request.baseline)
    baseline = analyze_wiring(groups, baseline_wiring)
    optimal, candidate_count = select_best_wiring(groups)

    baseline_power = baseline.peak.power
    optimal_power = optimal.peak.power
    gain = optimal_power - baseline_power
    gain_ratio = gain / baseline_power if baseline_power else Fraction(0)

    return {
        "title": request.title,
        "candidateCount": candidate_count,
        "groups": [serialize_group(group) for group in groups],
        "baseline": serialize_wiring(baseline),
        "optimal": serialize_wiring(optimal),
        "comparison": {
            "powerGain": float(gain),
            "powerGainRatio": float(gain_ratio),
            "sameWiring": baseline.wiring == optimal.wiring,
        },
    }


@app.post("/api/records", status_code=201)
def create_record(payload: SaveRecordPayload) -> dict:
    record_payload = {
        "input": payload.input.model_dump(mode="json"),
        "result": payload.result,
    }
    return database.save_record(payload.title, record_payload)


@app.get("/api/records")
def records() -> list[dict]:
    return database.list_records()


@app.get("/api/records/{record_id}")
def record_detail(record_id: int) -> dict:
    record = database.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="试算记录不存在")
    return record


@app.delete("/api/records/{record_id}", status_code=204)
def remove_record(record_id: int) -> None:
    if not database.delete_record(record_id):
        raise HTTPException(status_code=404, detail="试算记录不存在")


static_directory = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_directory, html=True), name="static")
