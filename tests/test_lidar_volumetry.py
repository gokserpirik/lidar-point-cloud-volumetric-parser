"""Tests for lidar_volumetry.py.

Unit tests use small synthetic arrays/files so the suite stays fast
(no multi-million-point datasets). One integration test runs the full
pipeline on a small synthetic mound.
"""

import csv
import os

import matplotlib

matplotlib.use("Agg")

import laspy
import numpy as np
import pytest

import lidar_volumetry as lv


def make_las(path, xs, ys, zs):
    """Writes a minimal LAS file with the given coordinates."""
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.offsets = [0.0, 0.0, 0.0]
    header.scales = [0.01, 0.01, 0.01]
    las = laspy.LasData(header)
    las.x = np.asarray(xs, dtype=float)
    las.y = np.asarray(ys, dtype=float)
    las.z = np.asarray(zs, dtype=float)
    las.write(path)
    return path


# --- load_point_cloud ---


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        lv.load_point_cloud(str(tmp_path / "nope.las"))


def test_load_empty_cloud_raises(tmp_path):
    path = make_las(str(tmp_path / "empty.las"), [], [], [])
    with pytest.raises(ValueError, match="empty"):
        lv.load_point_cloud(path)


def test_load_valid_file(tmp_path):
    path = make_las(str(tmp_path / "ok.las"), [1, 2], [3, 4], [5, 6])
    las = lv.load_point_cloud(path)
    assert las.header.point_count == 2


# --- filter_above_average ---


def test_filter_above_average():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([0.0, 0.0, 0.0, 0.0])
    z = np.array([0.0, 0.0, 10.0, 10.0])
    fx, fy, fz, avg = lv.filter_above_average(x, y, z)
    assert avg == pytest.approx(5.0)
    assert list(fz) == [10.0, 10.0]
    assert list(fx) == [2.0, 3.0]
    assert list(fy) == [0.0, 0.0]


def test_filter_above_average_all_equal_raises():
    x = y = z = np.array([1.0, 1.0, 1.0])
    with pytest.raises(ValueError, match="No points above average"):
        lv.filter_above_average(x, y, z)


# --- compute_footprint ---


def test_compute_footprint_unit_square():
    # 5x5 grid over the unit square -> convex hull area ~1.0
    gx, gy = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 5))
    boundary, area = lv.compute_footprint(gx.ravel(), gy.ravel(), step=1)
    assert not boundary.is_empty
    assert area == pytest.approx(1.0, rel=0.05)


def test_compute_footprint_insufficient_points_raises():
    with pytest.raises(ValueError, match="Insufficient points"):
        lv.compute_footprint(np.array([0.0, 1.0]), np.array([0.0, 1.0]), step=1)


# --- estimate_volume ---


def test_estimate_volume():
    volume, heights = lv.estimate_volume(100.0, np.array([12.0, 14.0]), 10.0)
    assert list(heights) == [2.0, 4.0]
    assert volume == pytest.approx(300.0)


# --- CSV helpers ---


def test_summary_csv_path():
    assert lv.summary_csv_path("las2018.laz") == "las2018-las.csv"
    assert lv.summary_csv_path("data/survey.las") == "survey-las.csv"


def test_write_summary_csv_roundtrip(tmp_path):
    csv_path = str(tmp_path / "out-las.csv")
    lv.write_summary_csv(csv_path, [("point_count", 42), ("estimated_volume_m3", "1.23")])
    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["metric", "value"]
    assert ["point_count", "42"] in rows
    assert ["estimated_volume_m3", "1.23"] in rows


# --- main() ---


def test_main_missing_file_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        lv.main(input_file="missing.laz")
    assert exc.value.code == 1
    assert "not found" in capsys.readouterr().err


def test_main_plotting_failure_exits_1(tmp_path, monkeypatch, capsys):
    """A plotting backend/file error must fail fast, not traceback."""
    monkeypatch.chdir(tmp_path)
    gx, gy = np.meshgrid(np.linspace(0, 20, 5), np.linspace(0, 20, 5))
    xs, ys = gx.ravel(), gy.ravel()
    center = (xs >= 5) & (xs <= 15) & (ys >= 5) & (ys <= 15)
    make_las("mound.las", xs, ys, np.where(center, 15.0, 10.0))
    monkeypatch.setattr(lv, "plot_results", lambda *a: (_ for _ in ()).throw(RuntimeError("no display")))
    with pytest.raises(SystemExit) as exc:
        lv.main(input_file="mound.las", downsample_step=1)
    assert exc.value.code == 1
    assert "Error during plotting" in capsys.readouterr().err


def test_main_integration_synthetic_mound(tmp_path, monkeypatch, capsys):
    """End-to-end run on a small synthetic mound: ground + raised center."""
    monkeypatch.chdir(tmp_path)
    gx, gy = np.meshgrid(np.linspace(0, 20, 21), np.linspace(0, 20, 21))
    xs, ys = gx.ravel(), gy.ravel()
    # raised 10x10m block in the middle
    center = (xs >= 5) & (xs <= 15) & (ys >= 5) & (ys <= 15)
    zs = np.where(center, 15.0, 10.0)
    make_las("mound.las", xs, ys, zs)

    lv.main(input_file="mound.las", downsample_step=1)

    out = capsys.readouterr().out
    assert "Point count: 441" in out
    assert "Summary CSV written to: mound-las.csv" in out
    assert os.path.exists("mound-las.csv")
    assert os.path.exists("lidar_volumetry.png")
    assert os.path.exists("lidar_volumetry_complete.png")

    with open("mound-las.csv", newline="") as f:
        data = {row[0]: row[1] for row in list(csv.reader(f))[1:]}
    assert data["point_count"] == "441"
    assert float(data["footprint_area_m2"]) == pytest.approx(100.0, rel=0.1)
    assert float(data["estimated_volume_m3"]) > 0
