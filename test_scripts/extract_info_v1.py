# -*- coding: utf-8 -*-
"""
Created on Wed May 20 20:22:00 2020

@author: Aleksei
"""

import cv2
import os
import rasterio
import rasterio.plot as rplot

import geopandas as gpd
from shapely.geometry import Polygon

test_shape = r"C:\Data\_ReachU-defectTypes\202004_Defect_types\20190417_075700_LD5\defects_categorized.shp"
test_vrt = r"C:\Data\_ReachU-defectTypes\201904_Origs\20190417_075700_LD5\20190417_075700_LD5-000.vrt"

# This loads the shapefile
deftps = gpd.read_file(test_shape)

# This loads and shows particular image
raster_vrt = rasterio.open(test_vrt)
rasterio.plot.show(raster_vrt)
raster_vrt.close()

# Make sure CRS is the same!
rast_crs = raster_vrt.crs.data["init"]
shp_crs = deftps.crs["init"]

print("CRS the same?", "Yes" if rast_crs == shp_crs else "No, need reprojection")

# Bounds of the projected image
rast_bnd = raster_vrt.bounds

# Need to construct a polygon from this
bl, bb, br, bt = rast_bnd.left, rast_bnd.bottom, rast_bnd.right, rast_bnd.top
ibpoly = Polygon([(bl, bb), (bl, bt), (br, bt), (br, bb)])