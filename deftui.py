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
import numpy as np

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
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
from ui import deftui_ui, deftui_imgpreview_ui

# Overall constants
PUBLISHER = "AlphaControlLab"
APP_TITLE = "Defect Type Database Preview and Preprocess"
APP_VERSION = "0.1-alpha"

# Some additional ones
CONFIG_DIR_NAME = "configs"
OUTPUT_DIR_NAME = "results"


# The Image Preview window class
class DeftImgPreviewUI(QtWidgets.QMainWindow, deftui_imgpreview_ui.Ui_frmImagePreview):

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

        # Same for right panel
        self.figure_view_R = Figure()
        self.canvas_view_R = FigureCanvas(self.figure_view_R)
        self.toolbar_view_R = NavigationToolbar(self.canvas_view_R, self)
        self.layoutFigRight.addWidget(self.toolbar_view_R)
        self.layoutFigRight.addWidget(self.canvas_view_R)
        self.axes_view_R = self.figure_view_R.add_subplot(111)

        self.initializing = False

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

    # Applications states in status bar
    APP_STATUS_STATES = {"ready": "Ready.",
                         "processing": "Processing data"}

    initializing = False
    app = None
    db_loaded = False  # Whether the database was loaded or not
    images_dir_selected = False  # Whether the images dir was selected

    raw_db = None  # Perhaps to be redone in the future. The original DB format is redundant
    db = None  # This holds the dataframe
    stats = None
    img_list = None

    img_preview_window = None

    def __init__(self, parent=None):

        self.initializing = True

        # Setting up the base UI
        super(DeftUI, self).__init__(parent)
        self.setupUi(self)

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
        self.actionReload_image.triggered.connect(self.img_preview_window.do_plot)

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
            self.log("Loading the defect database...")
            with open(fn[0], "rb") as f:
                my_db = pickle.load(f)
            self.raw_db = my_db
            self.log("Loaded database file from " + fn[0])
            self.txtDefectFileLoc.setText(fn[0])
            self.update_db()

    def browse_image_root_folder(self):
        dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose images root directory")
        if dir:
            self.txtImageRootDir.setText(self.fix_path(dir))
            self.update_images()

    # TODO: Implement this
    def update_db(self):
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

    def show_filtered_files(self):

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

    def update_image(self):
        pass


def main():
    # Prepare and launch the GUI
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('res/A.ico'))
    dialog = DeftUI()
    dialog.setWindowTitle(APP_TITLE + " - v." + APP_VERSION) # Window title
    dialog.app = app  # Store the reference
    dialog.show()

    # Add the preview window
    dialog.add_preview_window()

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
