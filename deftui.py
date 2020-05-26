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
APP_VERSION = "0.1-alpha"

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
    img_left_polys = None  # Will contain a list of polygons to plot over the image
    img_right = None
    img_right_boxes = None  # Will contain a list of cropped images with defect contents

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

        self.initializing = False

    # Clear axes left
    @staticmethod
    def clear_axes(wa):
        wa.clear()

    @staticmethod
    def display_nothing(wa):
        wa.text(-0.4, 0, "Nothing to show")
        wa.set_xlim(-1, 1)
        wa.set_ylim(-1, 1)

    # Using the plot colors, assign them to the labels. Note that N_labels must be <= 9
    def assign_colors(self, labels):
        lc = {}
        for i, l in enumerate(labels):
            lc[l] = self.POLY_COLORS[i]
        self.label_color = lc

    def onpick_patch(self):
        print("Picked patch")

    # Load an image along with a db_entry describing the defects
    def load_image(self, path_img, db_entry):

        # TODO: This, for now, is something we use to debug the thing
        #

        self.orthoframe = Orthoframe(path_img + os.sep + db_entry["origin"], db_entry["fn"], db_entry["extent"])

        self.clear_axes(self.axes_view_L)
        self.axes_view_L.imshow(self.orthoframe.img_content, extent=self.orthoframe.geo_extent)

        # Now let's have the shapes mate. Thanks to the descartes package we can draw them up pretty quickly.
        # One thing though... we also need to map the bounding boxes of them
        patches = []
        segments = []
        ind = 0
        for defect in db_entry["defects"]:
            segments.append(self.orthoframe.bounds_crop_img(defect[1].bounds))
            patches.append(PolygonPatch(defect[1], fc=self.label_color[defect[0]],
                                        alpha=0.4, zorder=1, picker=True))
            ind += 1

        self.axes_view_L.add_collection(PatchCollection(patches, match_original=True))
        self.canvas_view_L.draw()
        self.canvas_view_L.mpl_connect('pick_event', self.onpick_patch)

        #
        #
        # END DEBUG

        # Wont use mask for now, though given the path and image we can easily do it
        try:
            # Load the JPG file
            pass

        except:
            print("Cannot read file.")
            return

    # TODO: debug
    def do_plot(self):

        x = [1,2,3]
        vals = [10, 30, 40]

        self.axes_view_L.plot(x, vals, color="blue", zorder=1)
        self.axes_view_L.scatter(x, vals, color="red", zorder=2)

        self.canvas_view_L.draw()

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

    # Handle preview window toggle
    def handle_preview_toggle(self):
        if not self.actionPreview_window.isChecked():
            # Close the preview window, it will automatically untick the entry
            self.img_preview_window.close()
            self.img_preview_window = None
        else:
            self.actionPreview_window.setChecked(True)
            self.add_preview_window()

    # Test plot
    def test_plot(self):
        root_path = str(self.txtImageRootDir.text())
        fn = str(self.listImages.currentText())
        db_entry = self.get_file_entry(fn)
        self.img_preview_window.load_image(root_path, db_entry)

    # Group defects for this file in a compact form
    def get_file_entry(self, fn):

        if self.db is None:
            print("Database is not loaded")

        db_entry = {}
        defects = []

        entries = self.db[self.db["fn"] == fn]

        # Filter out the defect of interest
        filt_def = str(self.listFilterDefects.currentText())

        if entries.empty:
            print("No entries for this file")
            return

        for i, entry in entries.iterrows():
            if filt_def == "All" or filt_def == entry["defect_type"]:
                db_entry["fn"] = fn  # Redundant, need TODO
                db_entry["origin"] = entry["origin"] # something about this
                db_entry["extent"] = entry["extent"]
                defects.append((entry["defect_type"], entry["geometry"]))

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

        self.actionPreview_window.triggered.connect(self.handle_preview_toggle)

        # TODO: temp actions
        self.actionReload_image.triggered.connect(self.test_plot)

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

    # TODO: Implement this
    def update_db(self):

        db_file = self.config_data["MenuOptions"]["DefectDbFile"]

        self.log("Loading the defect database...")
        with open(db_file, "rb") as f:
            my_db = pickle.load(f)
        self.raw_db = my_db
        self.log("Loaded database file from " + db_file)

        self.log("Processing the database...")

        # Create the dataframe
        self.db = process_db.create_defect_geodataframe(self.raw_db)

        # Statistics
        unique_defects = self.db["defect_type"].unique().tolist()
        stats = {}
        for deft in unique_defects:
            stats[deft] = self.db[self.db["defect_type"] == deft].shape[0]

        # Store the statistics
        self.stats = stats

        # Populate the lists
        self.update_lists()

        # Update image
        self.update_image()

        self.log("Finished processing the database")
        self.print_stats()

    def print_stats(self):
        self.log("Defect type statistics for this dataset:")
        for deft, amt in self.stats.items():
            self.log(deft + ": " + str(amt))

    def update_lists(self):

        if self.db is not None:

            # Get all unique defects
            unique_defects = self.db["defect_type"].unique().tolist()

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
            self.listImages.disconnect()

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
            filter_cols["defect_type"] = filt_def

        filt_db = self.db[np.logical_and.reduce([(self.db[k] == v) for k, v in filter_cols.items()])] \
            if filter_cols else self.db

        # All unique filenames from filtered database
        unique_files = filt_db["fn"].unique().tolist()

        self.listImages.clear()
        self.listImages.addItems(unique_files)

        # Reattach filename onchange
        self.handle_file_onchange(True)

        # Check if we need to update the image
        if str(self.listImages.currentText()) != self.current_fn:
            self.update_image()

    # Run this method whenever the preview window is accessed for whatever purpose
    def update_image(self):
        if self.img_preview_window is not None and self.stats is not None:
            self.img_preview_window.assign_colors(self.stats.keys())

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
