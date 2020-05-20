# -*- coding: utf-8 -*-
"""
Created on Wed May 20 20:22:00 2020

@author: Aleksei
"""

import cv2
import os
import geopandas as gpd

sdir = r"C:\Data\_ReachU-defectTypes\202004_Defect_types\20190417_075700_LD5"

fil = sdir + os.sep + "defects_categorized.shp"

deftps = gpd.read_file(fil)