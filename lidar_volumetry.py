import laspy
import numpy as np
import alphashape

""" Reads laz or las files """
las = laspy.read("las2018.laz")

""" Extracting potentially useful header information """
print(las.header.point_count)
print(las.header.mins)
print(las.header.maxs)
print(las.header.version)
print(las.header.offsets)
print(las.header.scales)

""" Shortening the information we need to work with """
x = las.x
y = las.y
z = las.z

""" Calculating the average height and filtering out points below the average height, which are likely to be ground points."""
zarray = np.array(z)
avg_z = zarray.mean()
print(avg_z)
mask = zarray > avg_z 

""" Filtering both x and y according to z as all data points are in the same order, so the mask can be applied to all three arrays. """
filtered_z = zarray[mask]
filtered_x = np.array(x)[mask]
filtered_y = np.array(y)[mask]

print(filtered_z.min())
print(filtered_x.min())
print(filtered_y.min())

""" If you wish you can extract the new las file and only work on that as it will be much smaller and easier to work with. Not preferred but you can."""
# new_file = laspy.create(point_format=las.header.point_format, file_version=las.header.version)
# new_file.points = las.points[mask]
# new_file.write("high_ground_output.las")

""" Calculating area and volume for the boundary. Using ::500 to downsample the data as alphashape can be computationally expensive.
However, it is not best use for an actual project as it can lead to inaccuracies. """
points_2d = np.column_stack((filtered_x, filtered_y))
downsampled = points_2d[::500]
boundary = alphashape.alphashape(downsampled, alpha=0.0)
area = boundary.area
print(area)

heights = filtered_z - avg_z
volume = area * heights.mean()
print(volume)