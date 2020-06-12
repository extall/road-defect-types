# This is a temporary script that MAY be useful later.
# What it does is creates origin folders based on file names

import os
import shutil
from tqdm import tqdm

WHERE_TO_COPY = r"C:\Users\Aleksei\Desktop\origin_folders".replace("\\", "/")
FROM_COPY = r"F:\_ReachU-defectTypes\__new_2020_06\orthos".replace("\\", "/")

vrts = os.listdir(FROM_COPY)

# Only consider VRT files at this point, though need to copy many types
vrts = [vrt for vrt in vrts if vrt.endswith(".vrt")]

exts_to_copy = ('.jpg', '.mask.png', '.predicted_defects.png', '.vrt')

# Alright, let's go
folder_names = []

# Create necessary dirs and copy files to 'em
print("Copying files...")
for fn in tqdm(vrts):
    fbn = fn.split(".")[0]
    ffbn = fbn.split("-")[0]
    if ffbn not in folder_names:
        folder_names.append(ffbn)
        os.makedirs(WHERE_TO_COPY + "/" + ffbn)
    for ext in exts_to_copy:
        fnm = fbn + ext
        shutil.copyfile(FROM_COPY + "/" + fnm,
                        WHERE_TO_COPY + "/" + ffbn + "/" + fnm)