# main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import csv
from pathlib import Path
from typing import List, Dict, Any

app = FastAPI()
CSV_PATH = Path(__file__).parent / "tasks.csv"

# 想定カラム名（小文字で管理）
REQUIRED = ["id", "task", "preference_type", "preference_order"]

origins = [
    "http://localhost:5173",   # Vite / Vue / React dev server
    "http://127.0.0.1:5173",
    # ngrok の公開URLもここに追加すると便利
    # 例: "https://1234-56-78-90-123.ngrok-free.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # 許可するオリジン
    allow_credentials=True,
    allow_methods=["*"],          # GET, POST, PUT など全許可
    allow_headers=["*"],          # 全てのヘッダを許可
)

def normalize_header(name: str) -> str:
    # BOM 対策 + 前後空白 + 全角/半角のごく基本だけ処理
    return (
        name.replace("\ufeff", "")  # BOM除去
            .strip()                # 前後空白除去
            .lower()               # 小文字化
    )

def load_tasks() -> List[Dict[str, Any]]:
    # utf-8-sig で BOM を自動除去
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV ヘッダ行が見つかりません。先頭行にヘッダを追加してください。")

        # 元のヘッダ -> 正規化ヘッダ のマップを作る
        original_fields = reader.fieldnames
        norm_map = {h: normalize_header(h) for h in original_fields}

        # 必須カラムが存在するか（正規化後の名前で）チェック
        norm_set = set(norm_map.values())
        missing = [col for col in REQUIRED if col not in norm_set]
        if missing:
            # デバッグしやすいメッセージ
            raise ValueError(
                f"CSV の必須カラムが見つかりません: {missing}. "
                f"検出されたヘッダ: {original_fields}"
            )

        tasks: List[Dict[str, Any]] = []
        for row in reader:
            # 行のキーを正規化キーに張り替え
            norm_row = {norm_map[k]: v for k, v in row.items()}

            # 型整形（ご要望の JSON 仕様に合わせる）
            # id は数値、preference_* は文字列で返す
            try:
                item = {
                    "id": int(str(norm_row.get("id", "")).strip()),
                    "task": str(norm_row.get("task", "")).strip(),
                    "preference_type": str(norm_row.get("preference_type", "")).strip(),
                    "preference_order": str(norm_row.get("preference_order", "")).strip(),
                }
            except ValueError as e:
                # 数値変換できないなどの行はスキップ or エラー
                raise ValueError(f"行の値の型が不正です: {norm_row} ({e})")

            tasks.append(item)

        return tasks

@app.get("/")
def root():
    return {"message": "Use GET /tasks to fetch JSON from tasks.csv"}

@app.get("/tasks")
def get_tasks():
    try:
        return load_tasks()
    except Exception as e:
        # 失敗時は 500 と詳細（ヘッダずれの診断に役立つ）
        return JSONResponse(status_code=500, content={"error": str(e)})