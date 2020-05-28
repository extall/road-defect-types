# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\deftui_imgpreview.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_frmImagePreview(object):
    def setupUi(self, frmImagePreview):
        frmImagePreview.setObjectName("frmImagePreview")
        frmImagePreview.resize(800, 429)
        self.centralwidget = QtWidgets.QWidget(frmImagePreview)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.layoutFigLeft = QtWidgets.QVBoxLayout()
        self.layoutFigLeft.setObjectName("layoutFigLeft")
        self.gridLayout.addLayout(self.layoutFigLeft, 0, 1, 1, 1)
        self.layoutFigRight = QtWidgets.QVBoxLayout()
        self.layoutFigRight.setObjectName("layoutFigRight")
        self.gridLayout.addLayout(self.layoutFigRight, 0, 2, 1, 1)
        self.btnPrevImage = QtWidgets.QPushButton(self.centralwidget)
        self.btnPrevImage.setObjectName("btnPrevImage")
        self.gridLayout.addWidget(self.btnPrevImage, 1, 1, 1, 1)
        self.btnNextImage = QtWidgets.QPushButton(self.centralwidget)
        self.btnNextImage.setObjectName("btnNextImage")
        self.gridLayout.addWidget(self.btnNextImage, 1, 2, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)
        frmImagePreview.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(frmImagePreview)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        frmImagePreview.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(frmImagePreview)
        self.statusbar.setObjectName("statusbar")
        frmImagePreview.setStatusBar(self.statusbar)

        self.retranslateUi(frmImagePreview)
        QtCore.QMetaObject.connectSlotsByName(frmImagePreview)

    def retranslateUi(self, frmImagePreview):
        _translate = QtCore.QCoreApplication.translate
        frmImagePreview.setWindowTitle(_translate("frmImagePreview", "MainWindow"))
        self.btnPrevImage.setText(_translate("frmImagePreview", "Previous image"))
        self.btnNextImage.setText(_translate("frmImagePreview", "Next image"))

