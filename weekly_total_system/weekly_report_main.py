from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QDateTimeEdit
from write_page_form import Ui_MainWindow
from PySide6.QtGui import QPixmap, QScreen
from PySide6.QtCore import Qt, QThread, QSize, Signal, QDateTime, Slot, QRect, QPoint
from PySide6.QtWidgets import QMessageBox, QDialog, QPushButton, QVBoxLayout, QToolTip
from socket import *
import requests, time, inspect, atexit, schedule
from PySide6 import QtGui

report_server_ip = "10.30.41.60"
report_server_port = 7878
report_server_addr_port = (report_server_ip, report_server_port)


def job(self):
    print("send e-mail~")
    self.do_it_schedule_sending_mail = 1    

def handle_exit(report_system):
    print("handle_exit!!!")
    report_system.msgProcess_thread.quit()
    report_system.msgProcess_thread.wait(5000)

class CustomMessageBox(QMessageBox):
    def __init__(self, *__args):
        QMessageBox.__init__(self)
        self.timeout = 0 
        self.autoclose = False
        self.currentTime = 0
        
    def showEvent(self, QShowEvent):
        self.currentTime = 0
        if self.autoclose:
            self.startTimer(1000)
    
    def timerEvent(self, *args, **kwargs):
        self.currentTime += 1
        if self.currentTime >= self.timeout:
            self.done(0)

class MsgProcess(QThread):
    user_signal = Signal(int)
    def __init__(self, parent=None):
        super(MsgProcess, self).__init__(parent)
        self.trs = parent        
        self.is_running = False
        send_ok = 0
        
        
    def run(self):
        self.is_running = True        
        print("Thread Start~")
        while True:
            print("schedul test: "+ QDateTime.currentDateTime().toString())
            schedule.run_pending()
            if self.trs.do_it_schedule_sending_mail == 1 :
                print("cancel schedule_sending_mail~")
                self.trs.do_it_schedule_sending_mail = 0
                schedule.cancel_job(self.trs.schedule_sending_mail)            
            
            while True:
                if self.trs.req_send_message == 1:
                    retry = 0
                    while (retry < 5):
                        print("print textEdit~")
                        thisWeek_Text = self.trs.textEdit_this_week.toPlainText()
                        nextWeek_Text = self.trs.textEdit_next_week.toPlainText()
                        contents = thisWeek_Text +"|"+nextWeek_Text
                        res = self.trs.send_msg_toServer(contents)
                        if res == 1:
                            self.trs.req_send_message = 0
                            break
                        retry += 1
                    if res == 0:
                        print("Fail to send he message!!!")
                        break
                    res = self.trs.recv_msg_fromServer()
                    if  res == 1:
                        print("메시지 전송 성공")
                        self.user_signal.emit(1)
                    else:                        
                        print("메시지 전송 실패!!!")
                        self.user_signal.emit(0)
                
            time.sleep(1)

    def stop(self):
        self.is_running = False
        self.quit()
        self.wait(2000) #2000ms
    print("Thread End")

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
        self.msgProcess_thread.user_signal[int].connect(self.user_slot)
        self.dialog = QDialog()
        self.datetimeedit = QDateTimeEdit(self.dialog)
        self.lbl = QLabel(' 예약일정 설정', self.dialog)        
        self.btnDialog = QPushButton("확인", self.dialog)
        self.do_it_schedule_sending_mail = 0
        self.req_send_message = 0
        self.init_socket()
        self.msgProcess_thread.start()
        #Tab Focus 창이동으로 변경, if False, using edit tab "  "
        self.textEdit_this_week.setTabChangesFocus(True)
        self.textEdit_next_week.setTabChangesFocus(True)
        
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
            Qt.NonModal        : 값은 0 이며, 다른 윈도우 화면 입력을 차단하지 않음 - 모달리스
            Qt.WindowModal     : 값은 1 이며, 화면에 있는 모든 윈도우 창의 입력을 차단 
                                             현재 다이얼로그를 실행시킨 부모 프로그램뿐만 아니라 다른 윈도우들도 제어를 막음
            Qt.ApplicationModal: 값은 2 이며, 다이얼로그를 실행시킨 부모 프로그램만 제어를 막을 수 있음
        """        
        #self.dialog.setWindowModality(Qt.NonModal)
        #self.dialog.setWindowModality(Qt.WindowModal)
        self.dialog.setWindowModality(Qt.ApplicationModal)        
        self.dialog.resize(300, 200)
        #lbl = QLabel(' 예약일정 설정', self.dialog)        
        
        self.datetimeedit.setDateTime(QDateTime.currentDateTime())
        self.datetimeedit.setDateTimeRange(QDateTime(2024, 1, 1, 00, 00, 00), QDateTime(2100, 1, 1, 00, 00, 00))
        #self.datetimeedit.setDisplayFormat('yyyy.MM.dd hh:mm:ss')
        #초(sec) 생략
        self.datetimeedit.setDisplayFormat('yyyy.MM.dd hh:mm')
        self.datetimeedit.move(50,50)
        #datetimeedit.setGeometry(10, 10, 200, 50)
        
        self.btnDialog.move(100, 100)
        self.btnDialog.clicked.connect(self.dialog_close)
        
        vbox = QVBoxLayout()
        vbox.addWidget(self.lbl)
        vbox.addWidget(self.datetimeedit)
        vbox.addStretch()
        self.dialog.setLayout(vbox)
        self.dialog.show()
        
        print(datetime.toString())
        print("clicked_send_reserved_msg")
        pass
    
    def dialog_close(self):        
        cal_trigger_date = self.datetimeedit.date()
        cal_trigger_time = self.datetimeedit.time()
        
        print("Yahoo day: ", cal_trigger_date.year(), cal_trigger_date.month(), cal_trigger_date.day(), cal_trigger_date.weekNumber() )
        print("Yahoo time: ", cal_trigger_time.hour(), cal_trigger_time.minute())
        trigger_time  = str(cal_trigger_date.year()) + "." +str(cal_trigger_date.month()) + "."+ str(cal_trigger_date.day())+ " "+ str(cal_trigger_time.hour()).zfill(2)+ ":"+ str(cal_trigger_time.minute()).zfill(2)
        
        #self.pushButton_reserve_send.setText("하이") 
        self.pushButton_reserve_send.setStyleSheet("background-color: yellow")
        self.pushButton_reserve_send.setToolTip("<font color=""red""<b>"+trigger_time+"</b></font>")
        self.pushButton_reserve_send.move(50,50)
        #self.pushButton_reserve_send.setText("예약전송" + self.datetimeedit.dateTime().toString())
        
        #schedule.every().month
        self.reserved_action_timer()
        self.dialog.close()
        
    def clicked_send_now_msg(self):
        print("clicked_send_now_msg")
        self.req_send_message = 1
        pass

    def clicked_program_exit(self):        
        print("clicked_program_exit!")
        if self.msgProcess_thread.is_running == True:
            self.msgProcess_thread.stop()
        else:
            print("thread is empty!!!")
        self.close()

    def reserved_action_timer(self):
        cal_trigger_time = self.datetimeedit.time()
        trigger_time  = str(cal_trigger_time.hour()).zfill(2)+ ":"+ str(cal_trigger_time.minute()).zfill(2)
        print("***** Trigger time: " + trigger_time)
        self.schedule_sending_mail = schedule.every().day.at(trigger_time).do(job, self)        
        pass

    def init_socket(self):
        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.settimeout(5)

    def send_msg_toServer(self, mText):
        tx_ok = 1
        
        try:
            self.sock.sendto(mText.encode('utf-8'), report_server_addr_port )
        except:
            print("Fail: translate message!")
            tx_ok = 0
        return tx_ok    

    def recv_msg_fromServer(self):
        rx_ok = 1
        try:
            data = self.sock.recv(1024)
            msg = data.decode()
            msg = msg.replace(" ", "")
        except:
            print("Fail: receive message!")
            rx_ok = 0
        return rx_ok

    def view_ok(self, result):
        print("clicked_send_now_msg")        
        if result == 1:
            self.popup_inform("실행 결과", "메시지 전송: 성공", True, 3)
        else:
            self.popup_inform("실행 결과", "메시지 전송: 실패", True, 3)

    def popup_inform(self, title, msg, autoclose, timeoutSec):        
        msgBox = CustomMessageBox()
        
        msgBox.autoclose = autoclose
        msgBox.timeout = timeoutSec # 3seconds
        
        print(self.frameGeometry().topLeft().toPointF, self.frameGeometry().center().toPointF)
        
        msgBox.setWindowTitle(title)
        msgBox.setText(msg)
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setDefaultButton(QMessageBox.Ok)
        
        msgBox.exec()
    @Slot(int)
    def user_slot(self, arg1):
        self.view_ok(arg1)        

if __name__== '__main__':
    app = QApplication()
    window = Class_Total_Report_System()
    atexit.register(handle_exit, window)
    window.show()
    window.repaint()

    #center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
    #geo = window.frameGeometry()
    #geo.moveCenter(center)
    #window.move(geo.topLeft())

    app.exec()
    