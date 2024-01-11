from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from write_page_form import Ui_MainWindow
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QThread, QSize, Signal
from PySide6.QtWidgets import QMessageBox
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
                                
class Class_Total_Report_System(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(Class_Total_Report_System, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle("Total Report System~")
        self.setFixedSize(QSize(950, 575))
        self.msgProcess_thread = MsgProcess(self)
        
    def clicked_remove_next_week_contents(self):
        print("clicked_remove_next_week_contents")
        pass
    def clicked_send_reserved_msg(self):
        print("clicked_send_reserved_msg")
        pass
    def clicked_send_now_msg(self):
        print("clicked_send_now_msg")
        pass
    def clicked_program_exit(self):        
        print("clicked_program_exit!")
        if self.msgProcess_thread.is_running == True:
            self.msgProcess_thread.stop()
        else:
            print("thread is empty!")
        self.close()
        
    def clicked_remove_this_week_contents(self):        
        print("clicked_remove_this_week_contents")
        pass
    
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
    