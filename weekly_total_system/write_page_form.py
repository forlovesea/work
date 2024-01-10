# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'write_page.ui'
##
## Created by: Qt User Interface Compiler version 6.4.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QMainWindow,
    QMenuBar, QPushButton, QSizePolicy, QStatusBar,
    QTextEdit, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(497, 687)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_main = QLabel(self.centralwidget)
        self.label_main.setObjectName(u"label_main")

        self.gridLayout.addWidget(self.label_main, 0, 0, 1, 1)

        self.label_this_week = QLabel(self.centralwidget)
        self.label_this_week.setObjectName(u"label_this_week")

        self.gridLayout.addWidget(self.label_this_week, 1, 0, 1, 1)

        self.pushButton_this_week = QPushButton(self.centralwidget)
        self.pushButton_this_week.setObjectName(u"pushButton_this_week")

        self.gridLayout.addWidget(self.pushButton_this_week, 2, 0, 1, 1)

        self.textEdit_this_week = QTextEdit(self.centralwidget)
        self.textEdit_this_week.setObjectName(u"textEdit_this_week")

        self.gridLayout.addWidget(self.textEdit_this_week, 3, 0, 1, 3)

        self.label_next_week = QLabel(self.centralwidget)
        self.label_next_week.setObjectName(u"label_next_week")

        self.gridLayout.addWidget(self.label_next_week, 4, 0, 1, 1)

        self.pushButton_next_week = QPushButton(self.centralwidget)
        self.pushButton_next_week.setObjectName(u"pushButton_next_week")

        self.gridLayout.addWidget(self.pushButton_next_week, 5, 0, 1, 1)

        self.textEdit_next_week = QTextEdit(self.centralwidget)
        self.textEdit_next_week.setObjectName(u"textEdit_next_week")

        self.gridLayout.addWidget(self.textEdit_next_week, 6, 0, 1, 3)

        self.pushButton_reserve_send = QPushButton(self.centralwidget)
        self.pushButton_reserve_send.setObjectName(u"pushButton_reserve_send")

        self.gridLayout.addWidget(self.pushButton_reserve_send, 7, 0, 1, 1)

        self.pushButton_now_send = QPushButton(self.centralwidget)
        self.pushButton_now_send.setObjectName(u"pushButton_now_send")

        self.gridLayout.addWidget(self.pushButton_now_send, 7, 1, 1, 1)

        self.pushButton_exit = QPushButton(self.centralwidget)
        self.pushButton_exit.setObjectName(u"pushButton_exit")

        self.gridLayout.addWidget(self.pushButton_exit, 7, 2, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 497, 22))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.pushButton_next_week.clicked.connect(MainWindow.clicked_remove_next_week_contents)
        self.pushButton_reserve_send.clicked.connect(MainWindow.clicked_send_reserved_msg)
        self.pushButton_now_send.clicked.connect(MainWindow.clicked_send_now_msg)
        self.pushButton_exit.clicked.connect(MainWindow.clicked_program_exit)
        self.pushButton_this_week.clicked.connect(MainWindow.clicked_remove_this_week_contents)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label_main.setText(QCoreApplication.translate("MainWindow", u"\ubcf4\uace0 \uc2dc\uc2a4\ud15c", None))
        self.label_this_week.setText(QCoreApplication.translate("MainWindow", u"\uae08\uc8fc", None))
        self.pushButton_this_week.setText(QCoreApplication.translate("MainWindow", u"\uae08\uc8fc \ub0b4\uc6a9 \uc0ad\uc81c", None))
        self.label_next_week.setText(QCoreApplication.translate("MainWindow", u"\ucc28\uc8fc", None))
        self.pushButton_next_week.setText(QCoreApplication.translate("MainWindow", u"\ucc28\uc8fc \ub0b4\uc6a9 \uc0ad\uc81c", None))
        self.pushButton_reserve_send.setText(QCoreApplication.translate("MainWindow", u"\uc608\uc57d\uc804\uc1a1", None))
        self.pushButton_now_send.setText(QCoreApplication.translate("MainWindow", u"\ubc14\ub85c \uc804\uc1a1", None))
        self.pushButton_exit.setText(QCoreApplication.translate("MainWindow", u"\uc885\ub8cc", None))
    # retranslateUi

