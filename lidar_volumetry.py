import csv
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import laspy
import numpy as np
import alphashape

""" Input file; summary CSV is written as '<stem>-las.csv' (e.g. las2018-las.csv) """
INPUT_FILE = "las2018.laz"
""" Downsampling step for boundary calculation; alphashape is expensive on millions of points. """
DOWNSAMPLE_STEP = 500
""" Alpha shape concavity; 0.0 gives the convex hull. """
ALPHA = 0.0
""" Downsampling step for 3D scatter plots. """
PLOT_STEP = 200


def load_point_cloud(path):
    """Reads laz or las files. Raises FileNotFoundError if missing, ValueError if empty."""
    try:
        las = laspy.read(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File '{path}' not found.")
    except Exception as e:
        raise OSError(f"Error reading file '{path}': {e}")
    if las.header.point_count == 0:
        raise ValueError("Error: Point cloud is empty.")
    return las


def print_header_info(las):
    """Prints potentially useful header information."""
    print(f"Point count: {las.header.point_count}")
    print(f"Bounds min (X, Y, Z): {[float(v) for v in las.header.mins]}")
    print(f"Bounds max (X, Y, Z): {[float(v) for v in las.header.maxs]}")
    print(f"LAS version: {las.header.version}")
    print(f"Offsets (X, Y, Z): {[float(v) for v in las.header.offsets]}")
    print(f"Scales (X, Y, Z): {[float(v) for v in las.header.scales]}")


def filter_above_average(x, y, z):
    """Keeps points above the mean elevation (likely non-ground).

    Returns (filtered_x, filtered_y, filtered_z, avg_z).
    Raises ValueError if no points are above the average.
    """
    zarray = np.array(z)
    avg_z = zarray.mean()
    print(f"Average elevation (Z_avg): {avg_z:.3f} m")
    mask = zarray > avg_z

    """ Filtering both x and y according to z as all data points are in the same order, so the mask can be applied to all three arrays. """
    filtered_z = zarray[mask]
    filtered_x = np.array(x)[mask]
    filtered_y = np.array(y)[mask]

    if len(filtered_z) == 0:
        raise ValueError("Error: No points above average height. Nothing to process.")

    print(f"High-ground points: {len(filtered_z)} (above Z_avg)")
    print(f"Filtered Z min: {filtered_z.min():.3f} m")
    print(f"Filtered X min (Easting): {filtered_x.min():.3f}")
    print(f"Filtered Y min (Northing): {filtered_y.min():.3f}")
    return filtered_x, filtered_y, filtered_z, avg_z


def compute_footprint(filtered_x, filtered_y, step=DOWNSAMPLE_STEP, alpha=ALPHA):
    """Computes the 2D footprint boundary and area via alphashape.

    Returns (boundary, area). Raises ValueError if points are insufficient
    or no valid boundary can be computed.
    """
    points_2d = np.column_stack((filtered_x, filtered_y))
    downsampled = points_2d[::step]

    if len(downsampled) < 3:
        raise ValueError("Error: Insufficient points (less than 3) after downsampling to compute boundary.")
    boundary = alphashape.alphashape(downsampled, alpha=alpha)
    if boundary.is_empty:
        raise ValueError("Error: Could not compute a valid boundary from downsampled points.")
    area = boundary.area
    print(f"Footprint area: {area:.2f} m²")
    return boundary, area


def estimate_volume(area, filtered_z, avg_z):
    """Estimates volume as footprint area times mean height above baseline."""
    heights = filtered_z - avg_z
    volume = area * heights.mean()
    print(f"Mean pile height above baseline: {heights.mean():.3f} m")
    print(f"Estimated stockpile volume: {volume:.2f} m³")
    return volume, heights


def summary_csv_path(input_file):
    """Returns the summary CSV path for an input file ('<stem>-las.csv')."""
    return f"{Path(input_file).stem}-las.csv"


def build_summary_rows(input_file, las, avg_z, filtered_x, filtered_y, filtered_z, area, heights, volume):
    """Builds (metric, value) rows for the summary CSV."""
    mins = [float(v) for v in las.header.mins]
    maxs = [float(v) for v in las.header.maxs]
    offsets = [float(v) for v in las.header.offsets]
    scales = [float(v) for v in las.header.scales]
    return [
        ("input_file", input_file),
        ("point_count", las.header.point_count),
        ("bounds_min_x", f"{mins[0]:.3f}"),
        ("bounds_min_y", f"{mins[1]:.3f}"),
        ("bounds_min_z_m", f"{mins[2]:.3f}"),
        ("bounds_max_x", f"{maxs[0]:.3f}"),
        ("bounds_max_y", f"{maxs[1]:.3f}"),
        ("bounds_max_z_m", f"{maxs[2]:.3f}"),
        ("las_version", str(las.header.version)),
        ("offset_x", f"{offsets[0]:.3f}"),
        ("offset_y", f"{offsets[1]:.3f}"),
        ("offset_z", f"{offsets[2]:.3f}"),
        ("scale_x", f"{scales[0]:.6f}"),
        ("scale_y", f"{scales[1]:.6f}"),
        ("scale_z", f"{scales[2]:.6f}"),
        ("avg_elevation_m", f"{avg_z:.3f}"),
        ("high_ground_points", len(filtered_z)),
        ("filtered_z_min_m", f"{float(filtered_z.min()):.3f}"),
        ("filtered_x_min", f"{float(filtered_x.min()):.3f}"),
        ("filtered_y_min", f"{float(filtered_y.min()):.3f}"),
        ("footprint_area_m2", f"{area:.2f}"),
        ("mean_pile_height_m", f"{float(heights.mean()):.3f}"),
        ("estimated_volume_m3", f"{volume:.2f}"),
    ]


def write_summary_csv(csv_path, rows):
    """Writes (metric, value) rows to CSV. Raises OSError on failure."""
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


def plot_results(x, y, z, filtered_x, filtered_y, filtered_z, boundary):
    """Saves and shows the filtered and complete point cloud figures."""
    """ Visualizing the point cloud. Using ::200 to downsample the data."""
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    sc = ax.scatter(filtered_x[::PLOT_STEP], filtered_y[::PLOT_STEP], filtered_z[::PLOT_STEP], c=filtered_z[::PLOT_STEP], cmap='terrain', s=1)
    x_bound, y_bound = boundary.exterior.xy
    ax.plot(x_bound, y_bound, zs=filtered_z.min(), color='red', linewidth=2, label="Footprint")


    """ elevation color bar """
    cbar = fig.colorbar(sc, ax=ax, pad=0.1)
    cbar.set_label('Elevation (m)')

    """ engineering-standard spatial reference system """
    ax.set_xlabel('Easting (X)')
    ax.set_ylabel('Northing (Y)')
    ax.set_zlabel('Elevation (Z)')
    ax.set_title('Topographic Point Cloud with Footprint Boundary')
    ax.legend()

    """ save and show the plot """
    plt.savefig("lidar_volumetry.png", dpi=300, bbox_inches='tight')
    plt.show()
    plt.close()

    """ Visualizing the complete point cloud (no filtering). Using ::200 to downsample the data."""
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    sc = ax.scatter(np.array(x)[::PLOT_STEP], np.array(y)[::PLOT_STEP], np.array(z)[::PLOT_STEP], c=np.array(z)[::PLOT_STEP], cmap='terrain', s=1)
    x_bound, y_bound = boundary.exterior.xy
    ax.plot(x_bound, y_bound, zs=np.array(z).min(), color='red', linewidth=2, label="Footprint")

    """ elevation color bar """
    cbar = fig.colorbar(sc, ax=ax, pad=0.1)
    cbar.set_label('Elevation (m)')

    """ engineering-standard spatial reference system """
    ax.set_xlabel('Easting (X)')
    ax.set_ylabel('Northing (Y)')
    ax.set_zlabel('Elevation (Z)')
    ax.set_title('Complete Point Cloud with Footprint Boundary')
    ax.legend()

    """ save and show the plot """
    plt.savefig("lidar_volumetry_complete.png", dpi=300, bbox_inches='tight')
    plt.show()
    plt.close()


def main(input_file=INPUT_FILE, downsample_step=DOWNSAMPLE_STEP, alpha=ALPHA):
    """Runs the full volumetry pipeline. Exits 1 with a message on failure."""
    try:
        las = load_point_cloud(input_file)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    """ Extracting potentially useful header information """
    print_header_info(las)

    """ Shortening the information we need to work with """
    x = las.x
    y = las.y
    z = las.z

    """ Calculating the average height and filtering out points below the average height, which are likely to be ground points."""
    try:
        filtered_x, filtered_y, filtered_z, avg_z = filter_above_average(x, y, z)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    """ If you wish you can extract the new las file and only work on that as it will be much smaller and easier to work with. Not preferred but you can."""
    # new_file = laspy.create(point_format=las.header.point_format, file_version=las.header.version)
    # new_file.points = las.points[mask]
    # new_file.write("high_ground_output.las")

    """ Calculating area and volume for the boundary. Using downsampling as alphashape can be computationally expensive.
    However, it is not best use for an actual project as it can lead to inaccuracies. """
    try:
        boundary, area = compute_footprint(filtered_x, filtered_y, step=downsample_step, alpha=alpha)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    volume, heights = estimate_volume(area, filtered_z, avg_z)

    """ Writing summary metrics to '<input-stem>-las.csv' """
    summary_rows = build_summary_rows(input_file, las, avg_z, filtered_x, filtered_y, filtered_z, area, heights, volume)
    csv_path = summary_csv_path(input_file)
    try:
        write_summary_csv(csv_path, summary_rows)
    except OSError as e:
        print(f"Error writing CSV '{csv_path}': {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Summary CSV written to: {csv_path}")

    try:
        plot_results(x, y, z, filtered_x, filtered_y, filtered_z, boundary)
    except Exception as e:
        print(f"Error during plotting: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
