# LiDAR Point Cloud Volumetric Parser (MVP)

A lightweight Python pipeline designed to parse massive raw LiDAR datasets, isolate high-ground topographical features, and calculate surface areas and volumetric payloads.

## 🚀 Project Overview

This repository serves as a Minimum Viable Product (MVP) demonstrating how open-source Python libraries can bypass expensive, heavy CAD software to perform rapid spatial data analysis.

**Status:** Portfolio Demonstration / Proof of Concept (Not intended for commercial/production-grade engineering deployment)

**Development:** Code written by hand with AI assistance to understand the logic and workflow

**Target Audience:** Civil Project Managers, Survey Technicians, and Field Engineers looking to automate earthwork workflows

## 📊 Dataset Credit & Sourcing

The sample data used to develop and test this pipeline was sourced from the [USGS National Map Lidar Explorer](https://viewer.nationalmap.gov/basic/).

- **Format Used:** .laz (Compressed LiDAR)
- **Scale Precision:** Millimeter (0.001m)
- **Data Source:** USGS National Map Lidar Explorer

### Getting Sample Data

To test this code yourself:
1. Download any tile in .las or .laz format
2. Place it in your working directory
3. Update the file name in the script

## 🛠️ How the Workflow Works

The script executes a data-processing pipeline using the following steps:

1. **Metadata Inspection:** Reads the LAS/LAZ header to retrieve site boundaries (bounding boxes), coordinate scale systems, and total point counts (2.2M+ points in test set)

2. **High-Performance Masking:** Converts raw coordinate arrays into native NumPy arrays. It calculates the average elevation baseline (Z_avg) and creates a boolean "stencil" mask to isolate points above it

3. **Synchronized Slicing:** Applies the boolean mask across the X, Y, and Z arrays simultaneously, ensuring coordinates remain perfectly synchronized in space

4. **Data Downsampling:** Reduces the dataset density using an efficient index slice (`[::500]`) to ensure the boundary calculation remains computationally light for localized environments (NOT recommended for production use without further optimization)

5. **Boundary Generation:** Passes the horizontal coordinates to the alphashape engine to generate a 2D convex hull polygon boundary of the stockpiled asset

6. **Volumetric Integration:** Solves a 3D integration problem by multiplying the bounded 2D footprint area by the average vertical thickness of the isolated material to output the final volume in cubic meters (m³)

## 📦 Installation & Setup

### Prerequisites

- **Python:** 3.13 or higher
- **Package Manager:** [uv](https://github.com/astral-sh/uv) (recommended for fast, reliable installations)

### Quick Start

Clone this repository and install dependencies using `uv`:

```bash
git clone https://github.com/gokserpirik/lidar-point-cloud-volumetric-parser.git
cd lidar-point-cloud-volumetric-parser
uv sync
```

This will install all dependencies from `pyproject.toml`, including:
- `laspy[lazrs]` – LAS/LAZ file I/O with compression support
- `numpy` – High-performance numerical computing
- `matplotlib` – Visualization
- `pandas` – Data manipulation
- `rasterio` – Raster data I/O
- `geopandas` – Geospatial data handling
- `shapely` – Geometric operations
- `alphashape` – Boundary generation

### Alternative: Using pip

If you prefer `pip` over `uv`:

```bash
pip install -e .
```

## ▶️ Running the Pipeline

Ensure your data file is in the same directory as `lidar_volumetry.py` (or update the file path inside the script), then execute:

```bash
python lidar_volumetry.py
```

## 💡 Expected Output

When you run `python lidar_volumetry.py`, the script outputs metadata and volumetric analysis results:

```
2200000                    # Total point count
[123456.5, 654321.2, ...]  # Bounding box (min coordinates)
[234567.8, 765432.4, ...]  # Bounding box (max coordinates)
145.32                     # Average elevation baseline (Z_avg)
2847500.50                 # Area of isolated feature (m²)
1254.87                    # Volumetric payload (m³)
```

### Key Metrics

- **Point Count:** Total LiDAR points in dataset
- **Average Elevation (Z_avg):** Baseline used to separate high-ground from ground points
- **Area (m²):** 2D footprint of isolated features
- **Volume (m³):** Total material volume above baseline
