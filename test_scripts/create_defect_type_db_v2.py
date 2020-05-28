# -*- coding: utf-8 -*-
"""
Created on Wed May 20 20:22:00 2020

@author: Aleksei
"""

import os
import rasterio
import geopandas as gpd
from shapely.geometry import Polygon
import pickle
import cv2
from tqdm import tqdm
from skimage.measure import find_contours, approximate_polygon

# For simplification of polygons
POLY_APPROX_TOLERANCE = 5

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
def get_mask_shape_polygon(mask, extent):

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


# Build the dir lists
shpdirs = os.listdir(dt_dirs_root)
imgdirs = os.listdir(im_dirs_root)

# Check that every shapefile dir has the original images dir
for d in shpdirs:
    if d not in imgdirs:
        raise Exception("An image dir corresponding to " + d + " not found.")


# For counting values (remember, dict is passed by ref)
def inc_dict(d, key, val=1):
    if key in d:
        d[key] += 1
    else:
        d[key] = val


# If everything is ALL RIGHT, we proceed to process the data
defect_db = {}

# The procedure is as follows. For every dir, create an entry in the dict
# that points to a dict pointing to
# (1) statistics dict
# (2) file dict -> dataframe with defects
for d in shpdirs:

    print("Processing dir " + d + "...")

    mystats = {}
    myfiles = {}

    # Load the shapefile
    shp = gpd.read_file(os.path.join(dt_dirs_root + os.path.sep + d, shpf_name))

    # Get unique categories: this is needed to count the amount of defects
    cats = shp["type"].unique().tolist()

    # Find the undefined entries
    und = [i for i, v in enumerate(cats) if v == None]
    for i in und:
        cats[i] = lbl_undefined  # Estonian for undefined

    # Now we go through all the files in the image dir, finding the shapes that correspond to that file
    vrts = os.listdir(im_dirs_root + os.path.sep + d)
    vrts = [vrt for vrt in vrts if vrt.endswith(".vrt")]  # Only VRT files

    for f in tqdm(vrts):

        f_ind = f.replace(".vrt", "")

        # Need to find file bounds: this is now at V2
        rvrt = rasterio.open(os.path.join(im_dirs_root + os.path.sep + d, f))

        # CRS check. Perhaps useful if someone is going to use it in the future
        # TODO: This stopped working for some reason. Maybe it has to do with rasterio/GDAL bug. To be investigated
        # Indeed, Spyder is launched from CMD after properly switching the conda env, everything works as expected
        if rvrt.crs.data["init"] != shp.crs["init"]:
            raise Exception("CRS is different, need reprojection, script not designed to handle this situation.")

        # Bounds of the orthoframe
        rbnd = rvrt.bounds
        bl, bb, br, bt = rbnd.left, rbnd.bottom, rbnd.right, rbnd.top
        extent = [bl, br, bb, bt]  # Extent of image

        # Get the mask
        mask = cv2.imread(os.path.join(im_dirs_root + os.path.sep + d, f_ind + ".mask.png"), -1)

        ibpoly, _ = get_mask_shape_polygon(mask, extent)
        rvrt.close()

        # Now we go through all shapefile entries locating those that fit into the image polygon
        # (an hence belong to that orthoframe)
        geom_list = []
        drop_ind = []  # This is needed for deleting the rows later
        for ind, row in shp.iterrows():
            if row["geometry"].within(ibpoly):

                # What is the defect type
                defect_type = row["type"]
                if defect_type is None:
                    defect_type = lbl_undefined

                # Add as a tuple (defect type, corresponding geometry)
                geom_list.append((defect_type, row["geometry"]))
                drop_ind.append(ind)

                # Some statistics
                inc_dict(mystats, defect_type)

        # To speed things up, drop the shapefiles found on this dataframe
        # shp.drop(drop_ind)
        # TODO: the above line will not work, and should not be used anyway, since
        # sometimes defects can appear across several images, but only on certain
        # ones they will be correctly aligned with the actual defect on the pavement.

        # Store defect shape info for the file
        myfiles[f_ind] = (geom_list, extent)

    # Store the entry
    defect_db[d] = {"stats": mystats, "files": myfiles}

# Once we're ready, let's save the file to root of shape files
# This could potentially contain personal information as we are saving absolute
# paths of relevant directories
datas = {"shapefile_dirs_root": dt_dirs_root, "image_dirs_root": im_dirs_root, "defect_db": defect_db}
with open(os.path.join(dt_dirs_root, "defect_db.pkl"), "wb") as f:
    pickle.dump(datas, f)