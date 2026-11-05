
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.pipeline import analyze_dataset, RESULT_DIR


app = FastAPI(
    title="RetailIQ - Demand Forecasting API",
    description="Dynamic Retail Data Analysis and Demand Forecasting",
    version="2.0.0"
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def home():
    return {
        "message": "RetailIQ API is running!",
        "status": "success"
    }


@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)):

    filename = Path(file.filename or "").name

    if not filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV or XLSX file."
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    upload_id = uuid4().hex[:10]
    extension = Path(filename).suffix.lower()
    saved_name = f"{Path(filename).stem}_{upload_id}{extension}"
    file_path = UPLOAD_DIR / saved_name

    try:
        file_path.write_bytes(content)

        result = analyze_dataset(file_path)

        return {
            "message": result["message"],
            "upload_id": upload_id,
            "filename": filename,
            "analysis": result
        }

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Dataset processing failed: {str(error)}"
        )

    finally:
        await file.close()


@app.get("/api/results/{upload_id}/{result_type}")
def download_result(upload_id: str, result_type: str):

    if not upload_id.isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid upload ID."
        )

    allowed_files = {
        "sales": "daily_sales.csv",
        "forecast": "forecast_results.csv",
        "inventory": "inventory_recommendations.csv",
        "performance": "model_comparison.csv"
    }

    if result_type not in allowed_files:
        raise HTTPException(
            status_code=404,
            detail="Unknown result type."
        )

    matching_dir = next(
        (
            directory for directory in RESULT_DIR.iterdir()
            if directory.is_dir()
            and directory.name.endswith(f"_{upload_id}")
        ),
        None
    )

    if matching_dir is None:
        raise HTTPException(
            status_code=404,
            detail="Results for this upload were not found."
        )

    result_file = matching_dir / allowed_files[result_type]

    if not result_file.exists():
        raise HTTPException(
            status_code=404,
            detail="This result is not available for the uploaded dataset."
        )

    return FileResponse(
        path=result_file,
        filename=allowed_files[result_type],
        media_type="text/csv"
    )
