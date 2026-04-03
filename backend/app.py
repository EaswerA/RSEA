from fastapi import FastAPI, UploadFile, File
import shutil
import os

from parser import extract_text_from_pdf
from utils import chunk_text
from extractor import extract_requirements
from normalizer import normalize_data
from excel_writer import save_to_excel

app = FastAPI()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_path = f"{UPLOAD_DIR}/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract text
    text = extract_text_from_pdf(file_path)

    # Chunk text
    chunks = chunk_text(text)

    all_data = []

    for chunk in chunks:
        raw = extract_requirements(chunk)
        normalized = normalize_data(raw)
        all_data.extend(normalized)

    # Save output
    output_file = f"{OUTPUT_DIR}/{file.filename}.xlsx"
    save_to_excel(all_data, output_file)

    return {
        "message": "Done",
        "file": output_file,
        "items_extracted": len(all_data)
    }
