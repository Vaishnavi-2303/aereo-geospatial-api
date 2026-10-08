# Aereo Geospatial File Measurement API

A FastAPI-based REST API that accepts KML files or ZIP archives containing Shapefiles, extracts geospatial features, preserves their original CRS and properties, and calculates spatial measurements for supported geometries.

## Features

* Upload KML files
* Upload ZIP archives containing Shapefiles
* Extract feature ID/index, geometry type, geometry, CRS, and properties
* Calculate Polygon and MultiPolygon area in square metres
* Calculate LineString and MultiLineString length in metres
* Return Point features without a measurement
* Gracefully handle unsupported geometry types
* Transform geographic CRS to a suitable projected CRS before measurement
* Persist uploaded file metadata and processed features using SQLite
* REST API with automatic Swagger/OpenAPI documentation
* Input validation and appropriate HTTP error responses
* Automated API tests using pytest

## Technology Stack

* Python
* FastAPI
* GeoPandas
* Shapely
* PyProj
* Fiona
* SQLAlchemy
* SQLite
* Pytest
* HTTPX

## Project Structure

```text
aereo_geospatial_api/
|-- app/
|   `-- main.py
|-- data/
|   `-- uploads/
|-- tests/
|   |-- conftest.py
|   |-- sample.kml
|   `-- test_api.py
|-- README.md
|-- requirements.txt
|-- .gitignore
`-- aereo.db
```

The SQLite database and uploaded files are ignored by Git.

## Setup

### 1. Create a virtual environment

Windows CMD:

```cmd
python -m venv .venv
```

### 2. Activate the virtual environment

```cmd
.venv\Scripts\activate
```

### 3. Install dependencies

```cmd
pip install -r requirements.txt
```

### 4. Start the API

```cmd
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

### 1. Upload and Process File

```text
POST /api/files/
```

Accepts:

* `.kml`
* `.zip` containing a Shapefile

Example response:

```json
{
  "id": "uuid",
  "filename": "survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

The uploaded file is processed synchronously before the API returns the completed response.

### 2. Get File Information

```text
GET /api/files/{id}
```

Returns:

* File ID
* Filename
* Feature count
* Original CRS
* Processing status

Example:

```json
{
  "id": "uuid",
  "filename": "survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### 3. Get Measurements

```text
GET /api/files/{id}/measurements/
```

Returns every processed feature together with its geometry, properties, and measurement where applicable.

Example:

```json
{
  "id": "uuid",
  "filename": "survey.kml",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "measurements": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "measurement": 12016.99,
      "measurement_unit": "square_meters"
    },
    {
      "feature_id": 1,
      "geometry_type": "LineString",
      "measurement": 155.04,
      "measurement_unit": "meters"
    },
    {
      "feature_id": 2,
      "geometry_type": "Point",
      "measurement": null,
      "measurement_unit": null
    }
  ]
}
```

## Geometry Measurement Rules

| Geometry Type        | Measurement                  |
| -------------------- | ---------------------------- |
| Polygon              | Area in square metres        |
| MultiPolygon         | Area in square metres        |
| LineString           | Length in metres             |
| MultiLineString      | Length in metres             |
| Point                | No measurement               |
| Unsupported geometry | Returned without measurement |

Unsupported geometry types do not cause the complete file processing operation to fail.

## CRS Handling

Spatial measurements must not be calculated directly using latitude/longitude degrees.

For example, KML files commonly use:

```text
EPSG:4326
```

EPSG:4326 is a geographic CRS whose coordinates are expressed in degrees.

The application therefore follows this process:

```text
Input File
    |
Read Original CRS
    |
Is CRS Geographic?
    |
Yes -> Estimate Suitable UTM Projected CRS
    |
Transform Geometry
    |
Calculate Area / Length
    |
Return Measurements
```

GeoPandas `estimate_utm_crs()` is used to determine a suitable projected UTM CRS for geographic input data.

The API response continues to report the original CRS so that the returned geometry remains associated with its source coordinate system.

If the input file has no CRS, the API rejects the file because accurate area and distance measurements cannot be guaranteed.

## Architecture

The application follows a simple processing flow:

1. Client uploads a KML or ZIP file.
2. The API validates the file extension.
3. The source file is stored locally.
4. GeoPandas reads the geospatial data.
5. Feature geometry, properties, and CRS are extracted.
6. Geographic CRS data is transformed to a projected UTM CRS for measurement.
7. Measurements are calculated according to geometry type.
8. Processed feature data is serialized and stored in SQLite.
9. The API returns file information and measurement results.

### Main Components

* **FastAPI** - API routing, request handling, and validation
* **GeoPandas** - Geospatial file reading and CRS operations
* **Shapely** - Geometry representation and spatial operations
* **PyProj** - Coordinate reference system transformations
* **Fiona** - Geospatial file format support
* **SQLAlchemy** - Database persistence
* **SQLite** - Lightweight relational storage

## Processing Strategy

The current implementation uses synchronous processing.

This approach was selected because the assignment focuses on correctness, API design, and geospatial processing, and the expected files are manageable for a lightweight internship implementation.

For very large files or production workloads, the processing step could be moved to a background worker or task queue such as Celery or RQ.

## Error Handling

The API handles common invalid inputs using appropriate HTTP responses.

Examples:

* Unsupported file extension -> `400 Bad Request`
* Invalid or unreadable geospatial file -> `400 Bad Request`
* File ID not found -> `404 Not Found`
* Missing CRS -> processing error because accurate measurement cannot be guaranteed
* Empty or unsupported geometries -> returned without measurement where possible

## Testing

The project includes automated API tests covering:

* Health endpoint
* KML upload
* File information retrieval
* Polygon area calculation
* LineString length calculation
* Point handling
* Invalid file rejection
* Missing file handling
* Missing measurement request handling

Run the tests with:

```cmd
pytest -q
```

Current test result:

```text
7 passed
```

## Design Decisions

### Why FastAPI?

FastAPI provides:

* Simple REST API development
* Automatic Swagger/OpenAPI documentation
* Request validation
* Good Python type-hint integration
* Lightweight architecture suitable for this assignment

### Why GeoPandas?

GeoPandas provides a practical interface for reading geospatial files, managing CRS information, transforming coordinate systems, and working with spatial data.

### Why SQLite?

SQLite keeps the project self-contained and easy to run locally without requiring an external database.

For production, the persistence layer can be migrated to PostgreSQL/PostGIS.

### Why UTM Projection?

Area and distance calculations in latitude/longitude degrees are not physically meaningful as metres or square metres.

A projected CRS such as UTM provides coordinates in linear units suitable for spatial measurement.

## Learning

This project provided hands-on experience with:

* FastAPI REST API development
* Multipart file uploads
* Geospatial file processing
* KML and Shapefile handling
* GeoPandas and Shapely
* Coordinate Reference Systems
* CRS transformation
* Spatial area and distance calculations
* SQLite and SQLAlchemy
* API testing with pytest
* Error handling and validation
* Git and GitHub project organization

## Future Scope

Potential improvements for a production-ready version include:

* Background processing for large files
* Job progress tracking
* PostgreSQL/PostGIS integration
* Cloud object storage
* File size and resource limits
* Authentication and authorization
* Structured logging and monitoring
* Spatial indexing
* Containerized deployment with Docker
* Additional GIS validation
* Support for more geospatial formats
* More comprehensive automated test coverage
* Asynchronous task queues for large datasets

## API Documentation

After starting the application, Swagger UI is available at:

```text
http://127.0.0.1:8000/docs
```

The OpenAPI specification is automatically generated by FastAPI.
