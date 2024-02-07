# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QWidget)

class Ui_LoginForm(object):
    def setupUi(self, LoginForm):
        if not LoginForm.objectName():
            LoginForm.setObjectName(u"LoginForm")
        LoginForm.resize(367, 247)
        self.gridLayout = QGridLayout(LoginForm)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_2 = QLabel(LoginForm)
        self.label_2.setObjectName(u"label_2")
        font = QFont()
        font.setPointSize(10)
        self.label_2.setFont(font)
        self.label_2.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.label_3 = QLabel(LoginForm)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font)
        self.label_3.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.pushButton_exit = QPushButton(LoginForm)
        self.pushButton_exit.setObjectName(u"pushButton_exit")

        self.gridLayout.addWidget(self.pushButton_exit, 3, 2, 1, 1)

        self.label = QLabel(LoginForm)
        self.label.setObjectName(u"label")
        font1 = QFont()
        font1.setPointSize(20)
        self.label.setFont(font1)
        self.label.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 4)

        self.pushButton_login = QPushButton(LoginForm)
        self.pushButton_login.setObjectName(u"pushButton_login")

        self.gridLayout.addWidget(self.pushButton_login, 3, 1, 1, 1)

        self.lineEdit_passwd = QLineEdit(LoginForm)
        self.lineEdit_passwd.setObjectName(u"lineEdit_passwd")
        self.lineEdit_passwd.setEchoMode(QLineEdit.Password)

        self.gridLayout.addWidget(self.lineEdit_passwd, 2, 1, 1, 2)

        self.lineEdit_id = QLineEdit(LoginForm)
        self.lineEdit_id.setObjectName(u"lineEdit_id")

        self.gridLayout.addWidget(self.lineEdit_id, 1, 1, 1, 2)

        QWidget.setTabOrder(self.lineEdit_id, self.lineEdit_passwd)
        QWidget.setTabOrder(self.lineEdit_passwd, self.pushButton_login)
        QWidget.setTabOrder(self.pushButton_login, self.pushButton_exit)

        self.retranslateUi(LoginForm)
        self.pushButton_exit.clicked.connect(LoginForm.click_exit_button)
        self.pushButton_login.clicked.connect(LoginForm.click_login_button)
        self.lineEdit_passwd.editingFinished.connect(LoginForm.click_login_button)

        QMetaObject.connectSlotsByName(LoginForm)
    # setupUi

    def retranslateUi(self, LoginForm):
        LoginForm.setWindowTitle(QCoreApplication.translate("LoginForm", u"Form", None))
        self.label_2.setText(QCoreApplication.translate("LoginForm", u"ID", None))
        self.label_3.setText(QCoreApplication.translate("LoginForm", u"PASSWORD", None))
        self.pushButton_exit.setText(QCoreApplication.translate("LoginForm", u"\uc885\ub8cc", None))
        self.label.setText(QCoreApplication.translate("LoginForm", u"\uc2dc\uc2a4\ud15c", None))
        self.pushButton_login.setText(QCoreApplication.translate("LoginForm", u"\ub85c\uadf8\uc778", None))
    # retranslateUi

