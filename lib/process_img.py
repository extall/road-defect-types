import numpy as np
import cv2
import math
import os
from matplotlib import patches

# We assume the ext is ".jpg"
ORTHOFRAME_RASTER_EXT = ".jpg"  # TODO: Potential bug here. Need to make sure we search for the file instead
ORTHOFRAME_MASK_EXT = ".mask.png"


# The orthoframe class
class Orthoframe:

    img_content = None
    geo_extent = None
    shape = None

    def __init__(self, file_path, fn, extent):

        full_raster_path = file_path + os.sep + fn + ORTHOFRAME_RASTER_EXT

        img = cv2.imread(full_raster_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Store the image content and other meta
        self.img_content = img
        self.geo_extent = extent
        self.shape = img.shape

    def transform_from_geo_coordinates(self, geoxy):

        # Get data from tuple
        x, y = geoxy
        xmin, xmax, ymin, ymax = self.geo_extent
        h, w, _ = self.shape

        bx = (x - xmin) / (xmax - xmin)
        by = 1 - (y - ymin) / (ymax - ymin)

        bxp = math.floor(w * bx)
        byp = math.floor(h * by)

        return bxp, byp

    def bounds_transform_from_geo_coordinates(self, geopatch):
        x1, y1, x2, y2 = geopatch
        bx1p, by1p = self.transform_from_geo_coordinates((x1, y1))
        bx2p, by2p = self.transform_from_geo_coordinates((x2, y2))
        return bx1p, bx2p, by1p, by2p

    def bounds_crop_img(self, geopatch):
        x1, x2, y1, y2 = self.bounds_transform_from_geo_coordinates(geopatch)

        # Make sure ranges are adequate
        if y1 > y2:
            y1, y2 = y2, y1

        if x1 > x2:
            x1, x2 = x2, x1

        return self.img_content[y1:y2, x1:x2, ...]
