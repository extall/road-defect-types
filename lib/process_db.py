import geopandas as gpd
from datetime import datetime
import time

# Framework for processing the defect database

# Process the database: extract all the files and create a geopandas dataframe
# with columns {"fn": filename, "defect_type": defect_type, "geometry": geometry, "origin": image folder}
FILE_LOOKUP_DB_COLS = ["fn", "extent", "defect_type", "origin", "geometry"]


# Print with timestamp
def printt(*args):
    print(datetime.fromtimestamp(time.time()).strftime('[%Y-%m-%d %H:%M:%S]'), *args)


def create_defect_geodataframe(db):

    defects_list = []

    for thedir, filedb in db["defect_db"].items():
        for fn, fn_defects in filedb["files"].items():
            for defs in fn_defects[0]:
                defects_list.append(
                    [fn, fn_defects[1], defs[0], thedir, defs[1]]
                )

    return gpd.GeoDataFrame(defects_list, columns=FILE_LOOKUP_DB_COLS)