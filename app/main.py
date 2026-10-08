from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile
import json
import shutil

import geopandas as gpd
from fastapi import FastAPI, File, HTTPException, UploadFile
from shapely.geometry import mapping
from sqlalchemy import Column, String, Integer, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "aereo.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    crs = Column(String, nullable=True)
    feature_count = Column(Integer, default=0)
    status = Column(String, nullable=False)
    features_json = Column(Text, nullable=False, default="[]")


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Aereo Geospatial File Measurement API",
    version="1.0.0"
)

ALLOWED_EXTENSIONS = {".kml", ".zip"}


def safe_properties(row):
    result = {}

    for key, value in row.items():
        if key == "geometry":
            continue

        if value is None:
            result[key] = None
            continue

        try:
            if gpd.pd.isna(value):
                result[key] = None
                continue
        except (TypeError, ValueError):
            pass

        try:
            json.dumps(value)
            result[key] = value
        except TypeError:
            result[key] = str(value)

    return result


def find_shapefile(directory: Path) -> Path:
    files = list(directory.glob("*.shp"))

    if not files:
        raise ValueError(
            "ZIP file does not contain a Shapefile (.shp)"
        )

    return files[0]


def read_geospatial_file(path: Path) -> gpd.GeoDataFrame:
    suffix = path.suffix.lower()

    if suffix == ".zip":
        extract_dir = path.parent / path.stem
        extract_dir.mkdir(exist_ok=True)

        with ZipFile(path, "r") as zf:
            zf.extractall(extract_dir)

        shp = find_shapefile(extract_dir)
        return gpd.read_file(shp)

    if suffix == ".kml":
        return gpd.read_file(path, driver="KML")

    raise ValueError(
        "Only .kml and .zip files are supported"
    )


def projected_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError(
            "Input file has no CRS. A CRS is required for accurate measurements."
        )

    if not gdf.crs.is_geographic:
        return gdf

    estimated = gdf.estimate_utm_crs()

    if estimated is None:
        raise ValueError(
            "Could not determine a suitable projected CRS for measurement."
        )

    return gdf.to_crs(estimated)


def process_features(gdf: gpd.GeoDataFrame):
    measurement_gdf = projected_gdf(gdf)
    processed = []

    for index, (original_row, measured_geometry) in enumerate(
        zip(gdf.iterrows(), measurement_gdf.geometry)
    ):
        original_index, row = original_row
        geometry = row.geometry

        geometry_type = (
            geometry.geom_type
            if geometry is not None
            else "Unknown"
        )

        item = {
            "feature_id": index,
            "geometry_type": geometry_type,
            "geometry": (
                mapping(geometry)
                if geometry is not None and not geometry.is_empty
                else None
            ),
            "crs": (
                gdf.crs.to_string()
                if gdf.crs
                else None
            ),
            "properties": safe_properties(row),
            "measurement": None,
            "measurement_unit": None,
        }

        if (
            measured_geometry is not None
            and not measured_geometry.is_empty
        ):
            if geometry_type in {"Polygon", "MultiPolygon"}:
                item["measurement"] = measured_geometry.area
                item["measurement_unit"] = "square_meters"

            elif geometry_type in {
                "LineString",
                "MultiLineString"
            }:
                item["measurement"] = measured_geometry.length
                item["measurement_unit"] = "meters"

        processed.append(item)

    return processed


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/files/", status_code=201)
async def upload_file(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .kml or .zip files are supported"
        )

    file_id = str(uuid4())
    destination = UPLOAD_DIR / f"{file_id}{extension}"

    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        gdf = read_geospatial_file(destination)
        features = process_features(gdf)

        crs = (
            gdf.crs.to_string()
            if gdf.crs
            else None
        )

        db = SessionLocal()

        record = UploadedFile(
            id=file_id,
            filename=file.filename,
            file_path=str(destination),
            crs=crs,
            feature_count=len(features),
            status="COMPLETED",
            features_json=json.dumps(
                features,
                default=str,
                allow_nan=False
            ),
        )

        db.add(record)
        db.commit()
        db.close()

        return {
            "id": file_id,
            "filename": file.filename,
            "feature_count": len(features),
            "crs": crs,
            "status": "COMPLETED",
        }

    except Exception as exc:
        if destination.exists():
            destination.unlink()

        raise HTTPException(
            status_code=400,
            detail=f"File processing failed: {exc}"
        ) from exc


@app.get("/api/files/{file_id}")
def file_information(file_id: str):
    db = SessionLocal()
    record = db.get(UploadedFile, file_id)
    db.close()

    if not record:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return {
        "id": record.id,
        "filename": record.filename,
        "feature_count": record.feature_count,
        "crs": record.crs,
        "status": record.status,
    }


@app.get("/api/files/{file_id}/measurements/")
def measurements(file_id: str):
    db = SessionLocal()
    record = db.get(UploadedFile, file_id)
    db.close()

    if not record:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return {
        "id": record.id,
        "filename": record.filename,
        "crs": record.crs,
        "feature_count": record.feature_count,
        "measurements": json.loads(record.features_json),
    }