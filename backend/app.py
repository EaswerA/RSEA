from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import shutil
import os
from datetime import datetime

try:
    from .parser import extract_text_from_pdf
    from .utils import chunk_text
    from .extractor import extract_requirements, ExtractionServiceError
    from .normalizer import normalize_data
    from .excel_writer import save_to_excel
    from .mongo_store import init_db, store_extractions, store_processing_log, get_records as fetch_records
except ImportError:
    from parser import extract_text_from_pdf
    from utils import chunk_text
    from extractor import extract_requirements, ExtractionServiceError
    from normalizer import normalize_data
    from excel_writer import save_to_excel
    from mongo_store import init_db, store_extractions, store_processing_log, get_records as fetch_records

app = FastAPI()

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
app.mount("/files", StaticFiles(directory=OUTPUT_DIR_PATH), name="files")


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/records/")
def get_records(limit: int = 25):
    return fetch_records(limit)


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR_PATH, file.filename)

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
        store_processing_log(file.filename, "", 0, status, error_message)
        raise HTTPException(status_code=503, detail=f"Extraction failed: {e}")

    # Save output
    safe_name = os.path.splitext(file.filename)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{safe_name}_{timestamp}.xlsx"
    output_path = os.path.join(OUTPUT_DIR_PATH, output_filename)
    output_file = f"{OUTPUT_DIR}/{output_filename}"
    save_to_excel(all_data, output_path)

    store_extractions(all_data, file.filename, output_file)
    store_processing_log(file.filename, output_file, len(all_data), status, error_message)

    return {
        "message": "Done",
        "file": output_file,
        "items_extracted": len(all_data)
    }
