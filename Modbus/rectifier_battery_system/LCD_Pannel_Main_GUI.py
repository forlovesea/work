# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'LCD_Pannel_Main_GUI.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
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
from PySide6.QtWidgets import (QApplication, QDateEdit, QGraphicsView, QLabel,
    QMainWindow, QMenuBar, QPushButton, QSizePolicy,
    QStatusBar, QTimeEdit, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1061, 853)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(400, 50, 191, 51))
        font = QFont()
        font.setPointSize(20)
        self.label.setFont(font)
        self.label_2 = QLabel(self.centralwidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(580, 190, 191, 41))
        font1 = QFont()
        font1.setPointSize(12)
        self.label_2.setFont(font1)
        self.label_3 = QLabel(self.centralwidget)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(580, 240, 191, 41))
        self.label_3.setFont(font1)
        self.label_4 = QLabel(self.centralwidget)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setGeometry(QRect(580, 290, 191, 41))
        self.label_4.setFont(font1)
        self.label_5 = QLabel(self.centralwidget)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setGeometry(QRect(580, 340, 81, 41))
        self.label_5.setFont(font1)
        self.B_temper = QLabel(self.centralwidget)
        self.B_temper.setObjectName(u"B_temper")
        self.B_temper.setGeometry(QRect(790, 190, 81, 41))
        self.B_temper.setFont(font1)
        self.B_soc = QLabel(self.centralwidget)
        self.B_soc.setObjectName(u"B_soc")
        self.B_soc.setGeometry(QRect(790, 340, 81, 41))
        self.B_soc.setFont(font1)
        self.B_volt = QLabel(self.centralwidget)
        self.B_volt.setObjectName(u"B_volt")
        self.B_volt.setGeometry(QRect(790, 240, 81, 41))
        self.B_volt.setFont(font1)
        self.B_cur = QLabel(self.centralwidget)
        self.B_cur.setObjectName(u"B_cur")
        self.B_cur.setGeometry(QRect(790, 290, 81, 41))
        self.B_cur.setFont(font1)
        self.timeEdit = QTimeEdit(self.centralwidget)
        self.timeEdit.setObjectName(u"timeEdit")
        self.timeEdit.setGeometry(QRect(870, 10, 118, 22))
        self.timeEdit.setCalendarPopup(True)
        self.dateEdit = QDateEdit(self.centralwidget)
        self.dateEdit.setObjectName(u"dateEdit")
        self.dateEdit.setGeometry(QRect(760, 10, 110, 22))
        self.pushButton_alarms = QPushButton(self.centralwidget)
        self.pushButton_alarms.setObjectName(u"pushButton_alarms")
        self.pushButton_alarms.setGeometry(QRect(310, 480, 81, 31))
        self.pushButton_alarms.setFont(font1)
        self.pushButton_runnInfo = QPushButton(self.centralwidget)
        self.pushButton_runnInfo.setObjectName(u"pushButton_runnInfo")
        self.pushButton_runnInfo.setGeometry(QRect(434, 480, 81, 31))
        self.pushButton_runnInfo.setFont(font1)
        self.pushButton_settings = QPushButton(self.centralwidget)
        self.pushButton_settings.setObjectName(u"pushButton_settings")
        self.pushButton_settings.setGeometry(QRect(584, 480, 81, 31))
        self.pushButton_settings.setFont(font1)
        self.pushButton_runnCtrl = QPushButton(self.centralwidget)
        self.pushButton_runnCtrl.setObjectName(u"pushButton_runnCtrl")
        self.pushButton_runnCtrl.setGeometry(QRect(734, 480, 81, 31))
        self.pushButton_runnCtrl.setFont(font1)
        self.graphicsView = QGraphicsView(self.centralwidget)
        self.graphicsView.setObjectName(u"graphicsView")
        self.graphicsView.setGeometry(QRect(310, 170, 101, 221))
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1061, 22))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"System Status", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Battery temperature(C):", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Battery voltage(V):", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Battery current(A):", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"SOC(%):", None))
        self.B_temper.setText(QCoreApplication.translate("MainWindow", u"---", None))
        self.B_soc.setText(QCoreApplication.translate("MainWindow", u"---", None))
        self.B_volt.setText(QCoreApplication.translate("MainWindow", u"---", None))
        self.B_cur.setText(QCoreApplication.translate("MainWindow", u"---", None))
        self.pushButton_alarms.setText(QCoreApplication.translate("MainWindow", u"Alarms", None))
        self.pushButton_runnInfo.setText(QCoreApplication.translate("MainWindow", u"Runn.Info", None))
        self.pushButton_settings.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.pushButton_runnCtrl.setText(QCoreApplication.translate("MainWindow", u"Runn.Ctrl", None))
    # retranslateUi

