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

# The library
from ui import deftui_ui

# Overall constants
PUBLISHER = "AlphaControlLab"
APP_TITLE = "Defect Type Database Preview and Preprocess"
APP_VERSION = "0.1-alpha"

# Some additional ones
CONFIG_DIR_NAME = "configs"
OUTPUT_DIR_NAME = "results"


# Main UI class with all methods
class DeftUI(QtWidgets.QMainWindow, deftui_ui.Ui_mainWinDefectInfo):

    # Applications states in status bar
    APP_STATUS_STATES = {"ready": "Ready.",
                         "processing": "Processing data"}

    initializing = False
    app = None
    db_loaded = False  # Whether the database was loaded or not
    images_dir_selected = False  # Whether the images dir was selected

    db = None
    img_list = None

    # Embedded pyplot graph
    figure_view = None
    canvas_view = None
    toolbar_view = None
    axes_view = None

    def __init__(self, parent=None):

        self.initializing = True

        # Setting up the base UI
        super(DeftUI, self).__init__(parent)
        self.setupUi(self)

        # Add the FigureCanvas
        self.figure_view = Figure()
        self.canvas_view = FigureCanvas(self.figure_view)
        self.toolbar_view = NavigationToolbar(self.canvas_view, self)
        self.layoutPreview.addWidget(self.toolbar_view)
        self.layoutPreview.addWidget(self.canvas_view)

        # Add axes
        self.axes_view = self.figure_view.add_subplot(111)

        # Do plot
        self.do_plot()

        # Set up the status bar
        self.status_bar_message("ready")

    def do_plot(self):

        x = [1,2,3]
        vals = [10, 30, 40]

        self.axes_view.plot(x, vals, color="blue", zorder=1)
        self.axes_view.scatter(x, vals, color="red", zorder=2)

    # Set up those UI elements that depend on config
    def config_ui(self):

        # TODO: TEMP: For buttons, use .clicked.connect(self.*), for menu actions .triggered.connect(self.*),
        # TODO: TEMP: for checkboxes use .stateChanged, and for spinners .valueChanged
        self.btnBrowseDefectDb.clicked.connect(self.browse_defects_db)
        self.btnBrowseImgRoot.clicked.connect(self.browse_image_root_folder)

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
            with open(fn[0], "rb") as f:
                my_db = pickle.load(f)
            self.db = my_db
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
        pass

    def update_images(self):
        pass


def main():
    # Prepare and launch the GUI
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('res/A.ico'))
    dialog = DeftUI()
    dialog.setWindowTitle(APP_TITLE + " - v." + APP_VERSION) # Window title
    dialog.app = app  # Store the reference
    dialog.show()

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
