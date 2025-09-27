# main.py
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import csv
from pathlib import Path
from typing import List, Dict, Any, Literal
from datetime import datetime

app = FastAPI()

# CSV パス
BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "tasks.csv"
PRE_BIRTH_CSV_PATH = BASE_DIR / "pre_birth_tasks.csv"
POST_BIRTH_CSV_PATH = BASE_DIR / "post_birth_tasks.csv"
SCHEDULE_CSV_PATH = BASE_DIR / "schedule_tasks.csv"

# 想定カラム名（小文字で管理）
REQUIRED = ["id", "task", "preference_type", "preference_order"]
SCHEDULE_REQUIRED = ["id", "task", "time"]

# CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://202509-hackathon.vercel.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_header(name: str) -> str:
    return (
        name.replace("\ufeff", "")  # BOM 除去
        .strip()
        .lower()
    )

def load_tasks_from(csv_path: Path) -> List[Dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV が見つかりません: {csv_path.name}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV ヘッダ行が見つかりません。先頭行にヘッダを追加してください。")

        original_fields = reader.fieldnames
        norm_map = {h: normalize_header(h) for h in original_fields}
        norm_set = set(norm_map.values())
        missing = [col for col in REQUIRED if col not in norm_set]
        if missing:
            raise ValueError(
                f"CSV の必須カラムが見つかりません: {missing}. "
                f"検出されたヘッダ: {original_fields}"
            )

        tasks: List[Dict[str, Any]] = []
        for row in reader:
            norm_row = {norm_map[k]: v for k, v in row.items()}
            try:
                item = {
                    "id": int(str(norm_row.get("id", "")).strip()),
                    "task": str(norm_row.get("task", "")).strip(),
                    "preference_type": str(norm_row.get("preference_type", "")).strip(),
                    "preference_order": str(norm_row.get("preference_order", "")).strip(),
                }
            except ValueError as e:
                raise ValueError(f"行の値の型が不正です: {norm_row} ({e})")
            tasks.append(item)
        return tasks


def load_schedule_from(csv_path: Path, *, sort: bool = True) -> List[Dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV が見つかりません: {csv_path.name}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV ヘッダ行が見つかりません。先頭行にヘッダを追加してください。")

        original_fields = reader.fieldnames
        norm_map = {h: normalize_header(h) for h in original_fields}
        norm_set = set(norm_map.values())
        missing = [col for col in SCHEDULE_REQUIRED if col not in norm_set]
        if missing:
            raise ValueError(
                f"CSV の必須カラムが見つかりません: {missing}. "
                f"検出されたヘッダ: {original_fields}"
            )

        schedules: List[Dict[str, Any]] = []
        for row in reader:
            norm_row = {norm_map[k]: v for k, v in row.items()}
            try:
                # time を厳密に "HH:MM:SS" へ正規化
                t_raw = str(norm_row.get("time", "")).strip()
                t_obj = datetime.strptime(t_raw, "%H:%M:%S").time()  # 例: 09:30:00
                item = {
                    "id": int(str(norm_row.get("id", "")).strip()),
                    "task": str(norm_row.get("task", "")).strip(),
                    "time": t_obj.strftime("%H:%M:%S"),
                }
            except ValueError as e:
                raise ValueError(f"行の値の型が不正です: {norm_row} ({e})")
            schedules.append(item)

        if sort:
            schedules.sort(key=lambda x: datetime.strptime(x["time"], "%H:%M:%S").time())
        return schedules

@app.get("/")
def root():
    return {"message": "Use GET /tasks?phase=before|after|current, /tasks/before, /tasks/after, or /tasks/all"}

# 既存 /tasks を拡張：phase で before/after/current を切替
@app.get("/tasks")
def get_tasks(phase: Literal["before", "after", "current"] = Query("current")):
    try:
        if phase == "before":
            return load_tasks_from(PRE_BIRTH_CSV_PATH)
        elif phase == "after":
            return load_tasks_from(POST_BIRTH_CSV_PATH)
        else:
            return load_tasks_from(CSV_PATH)
    except FileNotFoundError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ショートカット
@app.get("/tasks/pre_birth")
def get_tasks_before():
    try:
        return load_tasks_from(PRE_BIRTH_CSV_PATH)
    except FileNotFoundError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/tasks/post_birth")
def get_tasks_after():
    try:
        return load_tasks_from(POST_BIRTH_CSV_PATH)
    except FileNotFoundError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/tasks/schedule")
def get_tasks_schedule(sort: bool = Query(True)):
    try:
        return load_schedule_from(SCHEDULE_CSV_PATH, sort=sort)
    except FileNotFoundError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/tasks/all")
def get_tasks_all():
    try:
        before = load_tasks_from(PRE_BIRTH_CSV_PATH)
        after = load_tasks_from(POST_BIRTH_CSV_PATH)
        schedule = load_schedule_from(SCHEDULE_CSV_PATH, sort=True)
        return {"before": before, "after": after, "schedule": schedule}
    except FileNotFoundError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
