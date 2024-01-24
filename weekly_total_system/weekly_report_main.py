from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QDateTimeEdit
from write_page_form import Ui_MainWindow
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QThread, QSize, Signal, QDateTime
from PySide6.QtWidgets import QMessageBox, QDialog, QPushButton, QVBoxLayout
from socket import *

import requests
import time
import inspect
import atexit



def handle_exit(report_system):
    print("called out")
    report_system.msgProcess_thread.quit()
    report_system.msgProcess_thread.wait(5000)

class MsgProcess(QThread):
    signalInA = Signal(str)
    def __init__(self, parent=None):
        super(MsgProcess, self).__init__(parent)
        self.trs = parent
        self.is_running = False    
        
    def run(self):
        self.is_running = True
        print("Thread Start~")        
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait(5000) #5000ms

#==================================================================================================
#==================================================================================================
#==================================================================================================
class Class_Total_Report_System(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(Class_Total_Report_System, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle("Total Report System~")
        self.setFixedSize(QSize(950, 575))
        self.msgProcess_thread = MsgProcess(self)
        self.dialog = QDialog()
        self.datetimeedit = QDateTimeEdit(self.dialog)

    def clicked_remove_this_week_contents(self):        
        print("clicked_remove_this_week_contents")
        if self.textEdit_this_week.toPlainText() != None :
            self.textEdit_this_week.clear()
            
        pass

    def clicked_remove_next_week_contents(self):
        print("clicked_remove_next_week_contents")
        if self.textEdit_next_week.toPlainText() != None :
            self.textEdit_next_week.clear()
        pass

    def clicked_send_reserved_msg(self):
        datetime = QDateTime.currentDateTime()
        self.dialog.setWindowTitle('예약시간 설정')
        """
            Qt.NonModal        : 값은 0 이며, 다른 윈도우 화면 입력을 차단하지 않습니다. 모달리스입니다.
            Qt.WindowModal     : 값은 1 이며, 화면에 있는 모든 윈도우 창의 입력을 차단합니다. 
                                현재 다이얼로그를 실행시킨 부모 프로그램뿐만 아니라 다른 윈도우들도 제어를 막습니다.
            Qt.ApplicationModal: 값은 2 이며, 다이얼로그를 실행시킨 부모 프로그램만 제어를 막습니다
        """        
        #self.dialog.setWindowModality(Qt.NonModal)
        #self.dialog.setWindowModality(Qt.WindowModal)
        self.dialog.setWindowModality(Qt.ApplicationModal)        
        self.dialog.resize(300, 200)
        lbl = QLabel(' 예약일정 설정', self.dialog)        
        
        self.datetimeedit.setDateTime(QDateTime.currentDateTime())
        self.datetimeedit.setDateTimeRange(QDateTime(2024, 1, 1, 00, 00, 00), QDateTime(2100, 1, 1, 00, 00, 00))
        self.datetimeedit.setDisplayFormat('yyyy.MM.dd hh:mm:ss')
        self.datetimeedit.move(50,50)
        #datetimeedit.setGeometry(10, 10, 200, 50)
        btnDialog = QPushButton("확인", self.dialog)
        btnDialog.move(100, 100)
        btnDialog.clicked.connect(self.dialog_close)
        
        vbox = QVBoxLayout()
        vbox.addWidget(lbl)
        vbox.addWidget(self.datetimeedit)
        vbox.addStretch()
        self.dialog.setLayout(vbox)
        
        self.dialog.show()
        print(datetime.toString())
        print("clicked_send_reserved_msg")
        pass
    
    def dialog_close(self):
        self.dialog.close()
        print(self.datetimeedit.dateTime().toString())
        
    def clicked_send_now_msg(self):
        print("clicked_send_now_msg")
        pass
    def clicked_program_exit(self):        
        print("clicked_program_exit!")
        if self.msgProcess_thread.is_running == True:
            self.msgProcess_thread.stop()
        else:
            print("thread is empty!!!")
        self.close()        
    
    
    
#app = QApplication([])
#window = QMainWindow()
#ui = Ui_MainWindow()
#ui.setupUi(window)
#window.show()
#app.exec()

if __name__== '__main__':
    app = QApplication()
    window = Class_Total_Report_System()
    atexit.register(handle_exit, window)
    window.show()
    window.repaint()
    app.exec()
    