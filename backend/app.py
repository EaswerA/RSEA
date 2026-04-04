from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import shutil
import os
import re
from datetime import datetime
from pydantic import BaseModel

try:
    from .parser import extract_text_from_pdf
    from .utils import chunk_text
    from .extractor import extract_requirements, ExtractionServiceError
    from .normalizer import normalize_data
    from .excel_writer import save_to_excel
    from .mongo_store import (
        create_user,
        get_records as fetch_records,
        init_db,
        issue_token,
        store_extractions,
        store_processing_log,
        verify_token,
        verify_user,
    )
except ImportError:
    from parser import extract_text_from_pdf
    from utils import chunk_text
    from extractor import extract_requirements, ExtractionServiceError
    from normalizer import normalize_data
    from excel_writer import save_to_excel
    from mongo_store import (
        create_user,
        get_records as fetch_records,
        init_db,
        issue_token,
        store_extractions,
        store_processing_log,
        verify_token,
        verify_user,
    )

app = FastAPI()
auth_scheme = HTTPBearer(auto_error=False)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")

UPLOAD_DIR_PATH = os.path.join(BASE_DIR, UPLOAD_DIR)
OUTPUT_DIR_PATH = os.path.join(BASE_DIR, OUTPUT_DIR)

os.makedirs(UPLOAD_DIR_PATH, exist_ok=True)
os.makedirs(OUTPUT_DIR_PATH, exist_ok=True)

init_db()

app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


class LoginRequest(BaseModel):
    username: str
    password: str


def sanitize_component(component: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", component)
    return cleaned.strip("._") or "file"


def get_current_username(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")

    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.post("/auth/register")
def register(payload: LoginRequest):
    username = payload.username.strip().lower()
    password = payload.password
    if len(username) < 3 or len(password) < 6:
        raise HTTPException(status_code=400, detail="Username must be >= 3 chars and password >= 6 chars")

    created = create_user(username, password)
    if not created:
        raise HTTPException(status_code=409, detail="Username already exists")

    return {"message": "User created"}


@app.post("/auth/login")
def login(payload: LoginRequest):
    username = payload.username.strip().lower()
    if not verify_user(username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = issue_token(username)
    return {"token": token, "username": username}


@app.get("/auth/me")
def me(username: str = Depends(get_current_username)):
    return {"username": username}


@app.get("/records/")
def get_records(limit: int = 25, username: str = Depends(get_current_username)):
    return fetch_records(username=username, limit=limit)


@app.get("/files/{filename}")
def get_output_file(filename: str, token: str = Query(default="")):
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    safe_name = sanitize_component(filename)
    file_path = os.path.join(OUTPUT_DIR_PATH, username, safe_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=safe_name)


@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    username: str = Depends(get_current_username),
):
    safe_input_name = sanitize_component(file.filename)

    user_upload_dir = os.path.join(UPLOAD_DIR_PATH, username)
    user_output_dir = os.path.join(OUTPUT_DIR_PATH, username)
    os.makedirs(user_upload_dir, exist_ok=True)
    os.makedirs(user_output_dir, exist_ok=True)

    file_path = os.path.join(user_upload_dir, safe_input_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract text
    text = extract_text_from_pdf(file_path)

    # Chunk text
    chunks = chunk_text(text)

    all_data = []
    status = "success"
    error_message = ""

    try:
        for chunk in chunks:
            raw = extract_requirements(chunk)
            normalized = normalize_data(raw)
            all_data.extend(normalized)
    except ExtractionServiceError as e:
        status = "failed"
        error_message = str(e)
        store_processing_log(safe_input_name, "", 0, status, username, error_message)
        raise HTTPException(status_code=503, detail=f"Extraction failed: {e}")

    # Save output
    safe_name = os.path.splitext(safe_input_name)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{safe_name}_{timestamp}.xlsx"
    output_path = os.path.join(user_output_dir, output_filename)
    output_file = output_filename
    save_to_excel(all_data, output_path)

    store_extractions(all_data, safe_input_name, output_file, username)
    store_processing_log(safe_input_name, output_file, len(all_data), status, username, error_message)

    return {
        "message": "Done",
        "file": output_file,
        "items_extracted": len(all_data)
    }
