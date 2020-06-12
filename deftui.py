# Generic imports
import sys
import traceback
import os
import time
from datetime import timedelta, datetime, date
import subprocess
import numpy as np
from pathlib import Path
import pickle
import copy
import geopandas as gpd
import cv2
import configparser
import numpy as np
import matplotlib
import inspect
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
plt.ion()

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# Specific UI features
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtWidgets import QSplashScreen, QMessageBox, QGraphicsScene, QFileDialog

# The libraries
from lib import process_db
from lib.process_img import Orthoframe
from ui import deftui_ui, deftui_imgpreview_ui

# Descartes
from descartes import PolygonPatch

# Overall constants
PUBLISHER = "CentreForIntelligentSystems"
APP_TITLE = "Defect Type Database Preview and Preprocess"
APP_VERSION = "0.2-alpha"

# Some additional ones
CONFIG_DIR_NAME = "configs"
OUTPUT_DIR_NAME = "results"


# The Image Preview window class
class DeftImgPreviewUI(QtWidgets.QMainWindow, deftui_imgpreview_ui.Ui_frmImagePreview):

    # Different data color scheme
    # Generated using https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=9
    POLY_COLORS = ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00', '#cab2d6']

    label_color = None

    # Orthoframe placeholder
    orthoframe = None

    # Figure contents to be plotted
    img_left = None
    img_right = None
    img_right_boxes = None  # Will contain a list of cropped images with defect contents

    # Current patch ID
    current_patch_id = None
    current_patch = None

    # Figure on the left
    figure_view_L = None
    canvas_view_L = None
    toolbar_view_L = None
    axes_view_L = None

    # And the figure on the right
    figure_view_R = None
    canvas_view_R = None
    toolbar_view_R = None
    axes_view_R = None

    tune_param = {
        "CannyLow": 0,
        "CannyHigh": 255,
        "ThrLow": 0,
        "ThrHigh": 255,
        "BlurKernSize": 1,
        "OpenKernSize": 1,
        "AdaThrBlockSize": 1,
        "AdaThrC": 0
    }

    def __init__(self, parent=None):

        self.initializing = True
        super(DeftImgPreviewUI, self).__init__(parent)
        self.setupUi(self)

        self.figure_view_L = Figure()
        self.canvas_view_L = FigureCanvas(self.figure_view_L)
        self.toolbar_view_L = NavigationToolbar(self.canvas_view_L, self)
        self.layoutFigLeft.addWidget(self.toolbar_view_L)
        self.layoutFigLeft.addWidget(self.canvas_view_L)
        self.axes_view_L = self.figure_view_L.add_subplot(111)
        self.clear_axes(self.axes_view_L)
        self.display_nothing(self.axes_view_L)

        # Same for right panel
        self.figure_view_R = Figure()
        self.canvas_view_R = FigureCanvas(self.figure_view_R)
        self.toolbar_view_R = NavigationToolbar(self.canvas_view_R, self)
        self.layoutFigRight.addWidget(self.toolbar_view_R)
        self.layoutFigRight.addWidget(self.canvas_view_R)
        self.axes_view_R = self.figure_view_R.add_subplot(111)
        self.clear_axes(self.axes_view_R)
        self.display_nothing(self.axes_view_R)
        self.axes_view_R.set_xticks([])
        self.axes_view_R.set_yticks([])

        self.canvas_view_L.mpl_connect('pick_event', self.onpick_patch)

        self.setWindowTitle("Preview window")

        # Buttons to communicate with main UI
        self.btnNextImage.clicked.connect(self.parent().handle_next_image_req)
        self.btnPrevImage.clicked.connect(self.parent().handle_prev_image_req)

        self.initializing = False

    # Clear axes left
    @staticmethod
    def clear_axes(wa):
        wa.clear()
        wa.figure.canvas.draw()

    @staticmethod
    def display_nothing(wa):
        wa.text(-0.4, 0, "Nothing to show")
        wa.set_xlim(-1, 1)
        wa.set_ylim(-1, 1)
        wa.figure.canvas.draw()

    # Using the plot colors, assign them to the labels. Note that N_labels must be <= 9
    def assign_colors(self, labels):
        lc = {}
        for i, l in enumerate(labels):
            lc[l] = self.POLY_COLORS[i]
        self.label_color = lc

    def onpick_patch(self, event):
        if self.img_right_boxes is not None:
            self.clear_axes(self.axes_view_R)
            patch_id = event.artist.patch_id

            # Store the patch ID for possible future use
            self.current_patch_id = patch_id
            self.current_patch = self.img_right_boxes[self.current_patch_id][1]

            # Show the patch
            self.show_patch()

            # Open processing windows, if needed
            self.open_proc_windows()

    # Show a patch specified by current_patch_id
    def show_patch(self):

        # Preprocess the patch before display
        img = self.preprocess_patch(self.current_patch)

        # Actually show the patch
        self.axes_view_R.imshow(img)
        self.toolbar_view_R.update()
        self.axes_view_R.set_xticks([])
        self.axes_view_R.set_yticks([])
        self.axes_view_R.set_title("Defect type: " + self.img_right_boxes[self.current_patch_id][0])
        self.canvas_view_R.draw()

    # Preprocess patch: apply the selected filters/edge detection etc on it
    def preprocess_patch(self, img1):

        # Operate on the copy of the original patch
        img = img1.copy()

        # Need two images
        need_two_images = False

        # Check the enabled operations
        if self.actionApply_Canny.isChecked():
            # Process image with Canny
            p = self.tune_param
            img = cv2.Canny(img, p["CannyLow"], p["CannyHigh"])
            need_two_images = True

        # In the end, img must be RGB
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        if need_two_images:
            img = self.combine_images(img1, img)

        # Return processed image
        return img

    # Open all proc windows that are needed
    def open_proc_windows(self):
        if self.actionApply_Canny.isChecked():
            self.proc_canny_window()

        if self.actionThreshold.isChecked():
            self.proc_threshold_window()

        if self.actionAdaptive_threshold_3.isChecked():
            self.proc_ada_threshold_window()

        if self.actionBlob_detector.isChecked():
            self.proc_blob_detector()

    # Create a window to experiment with some parameters
    def proc_canny_window(self):
        p = self.tune_param
        cv2.namedWindow("ProcessCanny", cv2.WINDOW_NORMAL)
        cv2.imshow("ProcessCanny", self.current_patch)
        cv2.createTrackbar("CannyLow", "ProcessCanny", 0, 255, self.proc_canny_window_callback("CannyLow"))
        cv2.createTrackbar("CannyHigh", "ProcessCanny", 0, 255, self.proc_canny_window_callback("CannyHigh"))
        cv2.setTrackbarPos("CannyLow", "ProcessCanny", p["CannyLow"])
        cv2.setTrackbarPos("CannyHigh", "ProcessCanny", p["CannyHigh"])

    def proc_canny_window_callback(self, param):
        def proc_callback_closure(val):
            p = self.tune_param
            p[param] = val
            img = cv2.Canny(self.current_patch.copy(), p["CannyLow"], p["CannyHigh"])
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            cv2.namedWindow("ProcessCanny", cv2.WINDOW_NORMAL)
            cv2.imshow("ProcessCanny", img)
        return proc_callback_closure

    def proc_threshold_window(self):
        p = self.tune_param
        cv2.namedWindow("ProcessThreshold", cv2.WINDOW_NORMAL)
        cv2.imshow("ProcessThreshold", self.current_patch)
        cv2.createTrackbar("ThrLow", "ProcessThreshold", 0, 255, self.proc_threshold_window_callback("ThrLow"))
        cv2.createTrackbar("ThrHigh", "ProcessThreshold", 0, 255, self.proc_threshold_window_callback("ThrHigh"))
        cv2.setTrackbarPos("ThrLow", "ProcessThreshold", p["ThrLow"])
        cv2.setTrackbarPos("ThrHigh", "ProcessThreshold", p["ThrHigh"])

    def proc_threshold_window_callback(self, param):
        def proc_callback_closure(val):
            p = self.tune_param
            p[param] = val
            img = cv2.cvtColor(self.current_patch.copy(), cv2.COLOR_RGB2GRAY)
            th, img = cv2.threshold(img, p["ThrLow"], p["ThrHigh"], cv2.THRESH_BINARY)
            cv2.namedWindow("ProcessThreshold", cv2.WINDOW_NORMAL)
            cv2.imshow("ProcessThreshold", img)
        return proc_callback_closure

    def proc_ada_threshold_window(self):
        p = self.tune_param
        cv2.namedWindow("ProcessAdaThreshold", cv2.WINDOW_NORMAL)
        cv2.imshow("ProcessAdaThreshold", self.current_patch)
        cv2.createTrackbar("BlurKernSize", "ProcessAdaThreshold", 0, 200,
                           self.proc_ada_threshold_window_callback("BlurKernSize"))
        cv2.createTrackbar("AdaThrBlockSize", "ProcessAdaThreshold", 1, 200, self.proc_ada_threshold_window_callback("AdaThrBlockSize"))
        cv2.createTrackbar("AdaThrC", "ProcessAdaThreshold", 0, 255, self.proc_ada_threshold_window_callback("AdaThrC"))
        cv2.createTrackbar("OpenKernSize", "ProcessAdaThreshold", 0, 200,
                           self.proc_ada_threshold_window_callback("OpenKernSize"))
        cv2.setTrackbarPos("BlurKernSize", "ProcessAdaThreshold", p["BlurKernSize"])
        cv2.setTrackbarPos("AdaThrBlockSize", "ProcessAdaThreshold", p["AdaThrBlockSize"])
        cv2.setTrackbarPos("AdaThrC", "ProcessAdaThreshold", p["AdaThrC"])
        cv2.setTrackbarPos("OpenKernSize", "ProcessAdaThreshold", p["OpenKernSize"])

    def proc_ada_threshold_window_callback(self, param):
        def proc_callback_closure(val):
            p = self.tune_param
            p[param] = val
            img = cv2.cvtColor(self.current_patch.copy(), cv2.COLOR_RGB2GRAY)

            if self.action0_Gaussian_blur.isChecked():
                blr_size = p["BlurKernSize"] * 2 + 1
                img = cv2.GaussianBlur(img, (blr_size, blr_size), 0)

            blk_size = p["AdaThrBlockSize"]*2+1
            img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,
                                            blk_size, p["AdaThrC"])

            # Do also morphological opening with a certain kernel size to remove texture noise
            if self.action2_Morphological_opening.isChecked() and p["OpenKernSize"] > 0:
                krn_size = p["OpenKernSize"] * 2 + 1

                # Try different kernels. Square does not work well for our tasks
                # kernel = np.ones((krn_size, krn_size), np.uint8)  # This is the original one
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (krn_size, krn_size))
                img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)

            cv2.namedWindow("ProcessAdaThreshold", cv2.WINDOW_NORMAL)
            cv2.imshow("ProcessAdaThreshold", img)
        return proc_callback_closure

    def proc_blob_detector(self):
        cv2.namedWindow("ProcessBlobDetector", cv2.WINDOW_NORMAL)
        # Detect blobs with default settings
        img = cv2.cvtColor(self.current_patch.copy(), cv2.COLOR_RGB2GRAY)
        detector = cv2.SimpleBlobDetector_create()
        keypoints = detector.detect(img)
        img2 = cv2.drawKeypoints(self.current_patch, keypoints, np.array([]),
                                 (0, 0, 255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        cv2.imshow("ProcessBlobDetector", img2)

    # def proc_blob_detector_callback(self, param):
    #     def proc_callback_closure(val):
    #         p = self.tune_param
    #         p[param] = val
    #         img = cv2.Canny(self.current_patch.copy(), p["CannyLow"], p["CannyHigh"])
    #         img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    #         cv2.namedWindow("ProcessCanny", cv2.WINDOW_NORMAL)
    #         cv2.imshow("ProcessCanny", img)
    #     return proc_callback_closure

    # Combine two images in the most efficient way
    # (horizontally or vertically) so that they can
    # be easily compared. We assume images have same w/h
    @staticmethod
    def combine_images(img, img1):
        h, w = img.shape[0], img.shape[1]
        h1, w1 = img1.shape[0], img1.shape[1]

        if h != h1 or w != w1:
            raise ValueError("Dimensions of the images are not compatible")

        # If we pass the check of images having same dimensions,
        # we proceed with deciding how to combine them
        if h > w:  # Stack side-by-side
            new_img = cv2.hconcat([img, img1])
        else:  # Top-bottom
            new_img = cv2.vconcat([img, img1])

        return new_img

    # Load an image along with a db_entry describing the defects
    def load_image(self, path_img, db_entry):

        # Wont use mask for now, though given the path and image we can easily do it
        try:
            self.setWindowTitle("Preview: " + db_entry["fn"])

            self.orthoframe = Orthoframe(path_img + os.sep + db_entry["origin"], db_entry["fn"], db_entry["extent"])

            self.clear_axes(self.axes_view_L)
            self.clear_axes(self.axes_view_R)
            self.display_nothing(self.axes_view_R)
            self.axes_view_R.set_xticks([])
            self.axes_view_R.set_yticks([])
            self.canvas_view_R.draw()

            self.axes_view_L.imshow(self.orthoframe.img_content, extent=self.orthoframe.geo_extent)
            self.toolbar_view_L.update()

            # Now let's have the shapes mate. Thanks to the descartes package we can draw them up pretty quickly.
            segments = {}
            ind = 0
            for defect in db_entry["defects"]:
                segments[ind] = (defect[0], self.orthoframe.bounds_crop_img(defect[1].bounds), defect[1])
                patch = PolygonPatch(defect[1], ec='#ff0000', fc=self.label_color[defect[0]],
                                     alpha=0.4, zorder=1, picker=True)
                patch.patch_id = ind
                self.axes_view_L.add_patch(patch)
                ind += 1

            self.canvas_view_L.draw()
            self.img_right_boxes = segments

        except Exception as err:
            print("An error occured while trying to construct the preview figure: " + str(err))
            return

    def closeEvent(self, event):
        self.parent().handle_preview_close()


# Main UI class with all methods
class DeftUI(QtWidgets.QMainWindow, deftui_ui.Ui_mainWinDefectInfo):

    # Current file name (the one selected in the orthoframe combobox)
    # NB! This is not generally updated, but currently used only to point
    # to a filename for filtering operations: we need not reload the same image, if after filtering
    # the file list the first entry points to the same file
    current_fn = None

    # Applications states in status bar
    APP_STATUS_STATES = {"ready": "Ready.",
                         "processing": "Processing data"}

    # Config file name
    CONFIG_NAME = "deftui_config.ini"

    initializing = False
    app = None
    db_loaded = False  # Whether the database was loaded or not
    images_dir_selected = False  # Whether the images dir was selected

    raw_db = None  # Perhaps to be redone in the future. The original DB format is redundant
    db = None  # This holds the dataframe
    stats = None
    img_list = None

    img_preview_window = None

    # Configuration data
    config_data = None

    def __init__(self, parent=None):

        self.initializing = True

        # Setting up the base UI
        super(DeftUI, self).__init__(parent)
        self.setupUi(self)

        # Config file storage: config file stored in user directory
        self.config_path = self.fix_path(os.path.expanduser("~")) + "." + PUBLISHER + os.sep

        self.initializing = False

        # Set up the status bar
        self.status_bar_message("ready")

    # Add preview window separately
    def add_preview_window(self):
        self.img_preview_window = DeftImgPreviewUI(self)
        self.img_preview_window.show()

    # Handle closing of the preview window
    def handle_preview_close(self):
        self.actionPreview_window.setChecked(False)
        self.img_preview_window = None

    # Handlers from next/prev image requests
    def handle_next_image_req(self):
        count = self.listImages.count()
        # Already at the last image
        if self.listImages.currentIndex() + 1 >= count:
            return

        # Increase index
        self.listImages.setCurrentIndex(self.listImages.currentIndex()+1)

    def handle_prev_image_req(self):
        if self.listImages.currentIndex() == 0:
            return
        self.listImages.setCurrentIndex(self.listImages.currentIndex()-1)

    # Handle preview window toggle
    def handle_preview_toggle(self):
        if not self.actionPreview_window.isChecked():
            # Close the preview window, it will automatically untick the entry
            self.img_preview_window.close()
            self.img_preview_window = None
        else:
            self.actionPreview_window.setChecked(True)
            self.add_preview_window()
            self.update_image()

    # Group defects for this file in a compact form
    def get_file_entry(self, fn):

        if self.db is None:
            print("Database is not loaded")

        db_entry = {}
        defects = []

        entries = self.db[self.db["fn"] == fn]

        # Filter out the defect of interest
        filt_def = str(self.listFilterDefects.currentText())

        # ... if the following option is enabled
        show_only_this = self.chkShowOnlyWithSelectedDefect.isChecked()

        if entries.empty:
            print("No entries for this file")
            return

        for i, entry in entries.iterrows():
            if filt_def == "All" or (filt_def == entry["type"] \
                                     and show_only_this) or not show_only_this:
                db_entry["fn"] = fn  # Redundant, need TODO
                db_entry["origin"] = entry["origin"] # something about this
                db_entry["extent"] = entry["extent"]
                defects.append((entry["type"], entry["geometry"]))

        db_entry["defects"] = defects
        return db_entry

    # Set up those UI elements that depend on config
    def config_ui(self):

        # TODO: TEMP: For buttons, use .clicked.connect(self.*), for menu actions .triggered.connect(self.*),
        # TODO: TEMP: for checkboxes use .stateChanged, and for spinners .valueChanged
        self.btnBrowseDefectDb.clicked.connect(self.browse_defects_db)
        self.btnBrowseImgRoot.clicked.connect(self.browse_image_root_folder)

        # Changes in lists (new selections)
        self.listFilterDirs.currentTextChanged.connect(self.show_filtered_files)
        self.listFilterDefects.currentTextChanged.connect(self.show_filtered_files)

        # Change of filter state
        self.chkShowOnlyWithSelectedDefect.stateChanged.connect(self.update_image)

        # Menu actions
        self.actionPreview_window.triggered.connect(self.handle_preview_toggle)
        self.actionReload_image.triggered.connect(self.update_image)
        self.actionCreateMaskFromDefShapes.triggered.connect(self.create_mask_from_shapes)

    # Helper for QMessageBox
    @staticmethod
    def show_info_box(title, text):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(text)
        msg.setWindowTitle(title)
        msg.setModal(True)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    @staticmethod
    def sanitize_url(url):
        return url.replace(" ", "")

    @staticmethod
    def open_file_in_os(fn):
        if sys.platform == "win32":
            os.startfile(fn)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, fn])

    # Path related functions
    @staticmethod
    def fix_path(p):
        # Only if string is nonempty
        if len(p) > 0:
            p = p.replace("/", os.sep).replace("\\", os.sep)
            p = p + os.sep if p[-1:] != os.sep else p
            return p

    @staticmethod
    def fix_file_path(p):
        # Only if string is nonempty
        if len(p) > 0:
            p = p.replace("/", os.sep).replace("\\", os.sep)
            return p

    def check_paths(self):
        # Use this to check the paths
        print("Not implemented")
        # self.txtImageDir.setText(self.fix_path(self.txtImageDir.text())) # example

    # Logging
    def log(self, line):
        # Get the time stamp
        ts = datetime.fromtimestamp(time.time()).strftime('[%Y-%m-%d %H:%M:%S] ')
        self.txtStats.moveCursor(QtGui.QTextCursor.End)
        self.txtStats.insertPlainText(ts + line + os.linesep)

        # Only do this if app is already referenced in the GUI (TODO: a more elegant solution?)
        if self.app is not None:
            self.app.processEvents()

    # Show different messages in status bar
    def status_bar_message(self, msgid):
        self.statusbar.showMessage(self.APP_STATUS_STATES[msgid])
        if self.app is not None:
            self.app.processEvents()

    def browse_defects_db(self):
        fn = QtWidgets.QFileDialog.getOpenFileName(self, "Load database file", "", "Pickled database file (*.pkl)")

        if fn[0] != "":
            self.txtDefectFileLoc.setText(self.fix_file_path(fn[0]))
            self.config_update()
            self.config_save()
            self.update_db()

    def browse_image_root_folder(self):
        dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose images root directory")
        if dir:
            self.txtImageRootDir.setText(self.fix_path(dir))
            self.config_update()
            self.config_save()
            self.update_image()

    def update_db(self):

        db_file = self.config_data["MenuOptions"]["DefectDbFile"]

        self.log("Loading the defect database...")
        with open(db_file, "rb") as f:
            my_db = pickle.load(f)

        # Breaking change in this version (0.2): we do not process the
        # database anymore, but load it up directly (it comes preprocessed)
        self.db = my_db

        # Statistics
        unique_defects = self.db["type"].unique().tolist()
        stats = {}
        for deft in unique_defects:
            stats[deft] = self.db[self.db["type"] == deft].shape[0]

        # Store the statistics
        self.stats = stats

        # Populate the lists
        self.update_lists()

        self.log("Finished processing the database")
        self.print_stats()

    def print_stats(self):
        self.log("Defect type statistics for this dataset:")
        for deft, amt in self.stats.items():
            self.log(deft + ": " + str(amt))

    def update_lists(self):

        if self.db is not None:

            # Get all unique defects
            unique_defects = self.db["type"].unique().tolist()

            # Get all unique directories
            unique_dirs = self.db["origin"].unique().tolist()

            # Update all the lists
            self.listFilterDirs.clear()
            self.listFilterDirs.addItem("All")
            self.listFilterDirs.addItems(unique_dirs)

            self.listFilterDefects.clear()
            self.listFilterDefects.addItem("All")
            self.listFilterDefects.addItems(unique_defects)

            # Run the filter
            self.show_filtered_files()

    def handle_file_onchange(self, evstate):

        # Depending on evstate, either attach or detach filename changed handling
        if evstate:
            self.listImages.currentTextChanged.connect(self.update_image)
        else:
            try: self.listImages.disconnect()
            except: pass

    def show_filtered_files(self):

        # Remember current file name
        self.current_fn = str(self.listImages.currentText())

        # Detach filename onchange event
        self.handle_file_onchange(False)

        if self.db is None:
            self.log("Cannot filter the files: no database loaded")
            return

        # Get the conditions
        filter_cols = {}
        filt_dir = str(self.listFilterDirs.currentText())
        filt_def = str(self.listFilterDefects.currentText())

        if filt_dir != "All":
            filter_cols["origin"] = filt_dir

        if filt_def != "All":
            filter_cols["type"] = filt_def

        filt_db = self.db[np.logical_and.reduce([(self.db[k] == v) for k, v in filter_cols.items()])] \
            if filter_cols else self.db

        # All unique filenames from filtered database
        unique_files = filt_db["fn"].unique().tolist()

        self.listImages.clear()
        self.listImages.addItems(unique_files)

        # Reattach filename onchange
        self.handle_file_onchange(True)

        # Check if we need to update the image: this will run on initialization
        if str(self.listImages.currentText()) != self.current_fn:
            self.update_image()

    # Run this method whenever the preview window is accessed for whatever purpose
    def update_image(self):
        if self.img_preview_window is not None and self.stats is not None:

            # Assign colors to various defects
            self.img_preview_window.assign_colors(self.stats.keys())

            # Proceed with plotting the image
            root_path = str(self.txtImageRootDir.text())
            fn = str(self.listImages.currentText())
            db_entry = self.get_file_entry(fn)
            self.img_preview_window.load_image(root_path, db_entry)

    # Create mask based on the defect info
    def create_mask_from_shapes(self):

        # For now this is mostly for debug. But later this will be used to implement the
        # defect type mask creation for the

        # Current file information

        root_path = str(self.txtImageRootDir.text())
        fn = str(self.listImages.currentText())
        entry = self.get_file_entry(fn)

        # Load image mask to figure out image size
        img_mask = cv2.imread(root_path + os.sep + entry["origin"] + os.sep + fn + ".mask.png", cv2.IMREAD_GRAYSCALE)
        h,w = img_mask.shape

        # Create empty mask
        new_mask = np.zeros((h,w), dtype='uint8')



        h = plt.figure(0)
        plt.imshow(new_mask)


    # Everything related to configuration
    def config_load(self):

        # First check if the file exists there, if not, create it
        if os.path.isfile(self.config_path + self.CONFIG_NAME):

            # Read data back from the config file and set it up in the GUI
            config = configparser.ConfigParser()
            config.read(self.config_path + self.CONFIG_NAME)

            # Before we proceed, we must ensure that all sections and options are present
            config = self.check_config(config)

            self.config_data = config

            # Database file loc
            db_file = self.config_data['MenuOptions']['DefectDbFile']
            if db_file != "":
                self.txtDefectFileLoc.setText(db_file)

            img_root_dir = self.config_data['MenuOptions']['ImagesRootDirectory']
            if img_root_dir != "":
                self.txtImageRootDir.setText(img_root_dir)

        else:

            # Initialize the config file
            self.config_init()

    def config_save(self):
        if os.path.isfile(self.config_path + self.CONFIG_NAME) and not self.initializing:
            print("saving it")
            with open(self.config_path + self.CONFIG_NAME, 'w') as configFile:
                self.config_data.write(configFile)

    def config_update(self):
        self.config_data["MenuOptions"]["DefectDbFile"] = self.txtDefectFileLoc.text()
        self.config_data["MenuOptions"]["ImagesRootDirectory"] = self.txtImageRootDir.text()

    def check_config(self, config):

        # Load the defaults and check whether the config has all the options
        defs = self.config_defaults()
        secs = list(defs.keys())

        # Now go item by item and add those that are missing
        for k in range(len(secs)):
            opns = list(defs[secs[k]].keys())

            # Make sure corresponding section exists
            if not config.has_section(secs[k]):
                config.add_section(secs[k])

            # And check all the options as well
            for m in range(len(opns)):
                if not config.has_option(secs[k], opns[m]):
                    config[secs[k]][opns[m]] = str(defs[secs[k]][opns[m]])

        return config

    # Config defaults
    @staticmethod
    def config_defaults():
        config_defaults = {'MenuOptions': {'DefectDbFile': '',
                                           'ImagesRootDirectory': ''}}
        return config_defaults

    def config_init(self):
        os.makedirs(self.config_path, exist_ok=True)  # Create the directory if needed
        config = configparser.ConfigParser()

        # Set the default configs
        the_defs = self.config_defaults()
        secs = list(the_defs.keys())
        for k in range(len(secs)):
            opns = list(the_defs[secs[k]].keys())
            config.add_section(secs[k])
            for m in range(len(opns)):
                config[secs[k]][opns[m]] = str(the_defs[secs[k]][opns[m]])

        with open(self.config_path + self.CONFIG_NAME, 'w') as configFile:
            config.write(configFile)

        self.config_data = config

    def config_process(self):
        if self.config_data["MenuOptions"]["DefectDbFile"] != "":
            self.update_db()


def main():
    # Prepare and launch the GUI
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('res/cis.ico'))
    dialog = DeftUI()
    dialog.setWindowTitle(APP_TITLE + " - v." + APP_VERSION) # Window title
    dialog.app = app  # Store the reference
    dialog.show()

    # Add the preview window
    dialog.add_preview_window()

    # Now we have to load the app configuration file
    dialog.config_load()

    # And we also process the configs
    dialog.config_process()

    # After loading the config file, we need to set up relevant UI elements
    dialog.config_ui()
    dialog.app.processEvents()

    # And proceed with execution
    app.exec_()


# Run main loop
if __name__ == '__main__':
    # Set the exception hook
    sys.excepthook = traceback.print_exception
    main()
