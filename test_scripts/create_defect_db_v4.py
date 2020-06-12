## This is an alternative approach to previous PAINFULLY SLOW method
#  Here we use set operations with overlay from geopandas

import os
import rasterio
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import pickle
import cv2
from tqdm import tqdm
from skimage.measure import find_contours, approximate_polygon

from annotmask import get_sqround_mask

# In this version, narrower masks are used to check defect inclusion

# For simplification of polygons
POLY_APPROX_TOLERANCE = 5
DEFECT_DB_FILE = "defect_db_v4.pkl"

# Make a narrower mask
NARROW_MASK = True

# This script is used to build a database of ALL defect types found on a particular road segment
# It should be run on a particular machine that shall handle the task of defect type preprocessing for ML
# because it stores absolute paths necessary to access the image files for the task
dt_dirs_root = r"C:\Data\_ReachU-defectTypes\202004_Defect_types"  # Root dir that contains the folders with shapefiles
im_dirs_root = r"C:\Data\_ReachU-defectTypes\201904_Origs"  # Root dir with image folders

# Shapefile naming convention
shpf_name = "defects_categorized.shp"

# Undefined label
lbl_undefined = "määramata"  # Estonian for undefined


# Needed to create a mask shape
def transform_to_geo_coordinates(extent, xy):

    # Get data from tuple
    x, y = xy
    xmin, xmax, ymin, ymax = extent
    h, w = 4096, 4096

    gx = xmin + (xmax - xmin) * (x / w)
    gy = ymin + (ymax - ymin) * (1 - y / h)

    return gx, gy


# Send in the mask here.
def get_mask_shape_polygon(mask, extent, want_narrow=False):

    # Should the mask become narrower?
    if want_narrow:
        mask = get_sqround_mask(mask)

    # Find the contours
    contours = find_contours(mask, 1)
    contour = contours[0]  # We know there's only ONE contour
    contour = approximate_polygon(contour, tolerance=POLY_APPROX_TOLERANCE)

    # Construct the <polygon> shape
    poly_points_x = []
    poly_points_y = []
    for r in contour:
        gx, gy = transform_to_geo_coordinates(extent, (r[1], r[0]))
        poly_points_x.append(gx)
        poly_points_y.append(gy)

    polygon_geom = Polygon(zip(poly_points_x, poly_points_y))
    polygon = gpd.GeoDataFrame(index=[0], crs={'init': 'espg:3301'}, geometry=[polygon_geom])

    return polygon_geom, polygon

# For counting values (remember, dict is passed by ref)
def inc_dict(d, key, val=1):
    if key in d:
        d[key] += 1
    else:
        d[key] = val


# Process a folder with VRT files - create a GeoPandas dataframe
# with relevant information about file and the mask shape
# Returns a dataframe with this information
def process_vrt_folder(path, want_narrow=False):

    path = path.replace("\\", "/")  # Standard sanitizing
    if not path.endswith("/"):
        path += "/"

    print("Creating shapes for masks...")

    vrts = os.listdir(path)
    vrts = [vrt for vrt in vrts if vrt.endswith(".vrt")]  # Only VRT files

    ortho_data_cols = ['fn', 'extent']
    ortho_data = []
    ortho_shapes = []

    for f in tqdm(vrts):

        f_ind = f.replace(".vrt", "")

        # Find ortho bounds
        rvrt = rasterio.open(os.path.join(path, f))
        rbnd = rvrt.bounds
        bl, bb, br, bt = rbnd.left, rbnd.bottom, rbnd.right, rbnd.top
        extent = [bl, br, bb, bt]  # Extent of image

        # Get the mask
        mask = cv2.imread(os.path.join(path, f_ind + ".mask.png"), cv2.IMREAD_GRAYSCALE)

        maskpoly, _ = get_mask_shape_polygon(mask, extent, want_narrow=want_narrow)
        rvrt.close()

        # Append info
        ortho_data.append([f_ind, extent])
        ortho_shapes.append(maskpoly)

    df = pd.DataFrame(data=ortho_data, columns=ortho_data_cols)

    # Once all over, create and return the dataframe
    return gpd.GeoDataFrame(df, crs={'init': 'espg:3301'}, geometry=ortho_shapes)


# Join N geopandas dataframes
def join_gdf(gdf_list, ignore_index=True):
    if not gdf_list:
        # Return empty geodataframe
        return gpd.GeoDataFrame()

    # Take the CRS from the first entry and check all others
    crs = gdf_list[0].crs

    # Check all the merged dataframes so that the CRS is exactly the same everywhere
    for gdf in gdf_list:
        if gdf.crs != crs:
            raise ValueError("Cannot join GeoDataFrames with different CRS")

    # Finally, join the geodataframes resetting the index
    return gpd.GeoDataFrame(pd.concat(gdf_list, ignore_index=ignore_index), crs=crs)


# Get list of top level dirs to process, absolute paths with os.sep converted
# to / since python understands it even in windows
def get_paths_to_process(base_path, add_file=None):
    base_path = base_path.replace("\\", "/")
    base_path = base_path[:-1] if base_path.endswith("/") else base_path  # Typical sanitization
    dirs = next(os.walk(base_path))[1]
    return {d: base_path + "/" + d + (("/" + add_file) if add_file else "") for d in dirs}


# Define the paths to process
ortho_dir = r"C:\Data\_ReachU-defectTypes\201904_Origs"
shp_dir = r"C:\Data\_ReachU-defectTypes\202004_Defect_types"

ortho_dirs = get_paths_to_process(ortho_dir)
shp_dirs = get_paths_to_process(shp_dir, shpf_name)

# Check that all keys are there
if set(ortho_dirs.keys()) != set(shp_dirs.keys()):
    raise KeyError("Error in matching ortho/shapefile folders.")

# Go through all folders and create the relevant GeoDataFrames
gdf_list = []
for k in ortho_dirs:
    orthoshapes = process_vrt_folder(ortho_dirs[k], want_narrow=True)
    shp = gpd.read_file(shp_dirs[k])

    # explode() at the end explodes multipolygons to polygons while duplicating entries
    # replace() replaces Type=None with "määramata"
    ovrl = gpd.overlay(orthoshapes, shp, how='intersection').explode()
    ovrl.replace(to_replace=[None], value=lbl_undefined, inplace=True)

    gdf_list.append(ovrl)

# Finally, put it all together
full_defect_db = join_gdf(gdf_list)

# Add the origin column
origins = []
for i, k in full_defect_db.iterrows():
    origins.append(k["fn"].split("-")[0])

# Add the column
full_defect_db["origin"] = origins

# Save the database
datas = {"shapefile_dirs_root": shp_dir, "image_dirs_root": ortho_dir, "defect_db": full_defect_db}
with open(os.path.join(ortho_dir, DEFECT_DB_FILE), "wb") as f:
    pickle.dump(datas, f)