from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QDateTimeEdit
from write_page_form import Ui_MainWindow
from login import Ui_LoginForm
from PySide6.QtGui import QPixmap, QScreen
from PySide6.QtCore import Qt, QThread, QSize, Signal, QDateTime, Slot, QRect, QPoint
from PySide6.QtWidgets import QMessageBox, QDialog, QPushButton, QVBoxLayout, QHBoxLayout, QToolTip
from socket import *
import requests, time, inspect, atexit, schedule
from PySide6 import QtGui
from werkzeug.security import generate_password_hash, check_password_hash

report_server_ip = "10.30.41.60"
report_server_port = 7878
report_server_addr_port = (report_server_ip, report_server_port)

dict_team_one = { 'jihyun':'pbkdf2:sha256:600000$F9xFhm45FlQuEbBJ$72968532db2b077748dafc0f476bcf3ea5b49853ae393b7f20d71d5255b854f5'}

def job(self):
    print("send e-mail~")
    self.do_it_schedule_sending_mail = 1    

def handle_exit(report_system):
    print("handle_exit!")
    if report_system.class_id == 0 :
        pass
    elif report_system.class_id == 1 :
        if report_system.msgProcess_thread.is_running == True:
            report_system.msgProcess_thread.quit()
            report_system.msgProcess_thread.wait(2000)

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
        retry = 0
        contents = None
        while True:
            print("schedul test: "+ QDateTime.currentDateTime().toString())
            schedule.run_pending()
            if self.trs.do_it_schedule_sending_mail == 1 :
                self.trs.req_send_message = 2
                print("cancel schedule_sending_mail~")                
                self.trs.do_it_schedule_sending_mail = 0                
                schedule.cancel_job(self.trs.schedule_sending_mail)            
            
            if self.trs.req_send_message > 0:
                retry = 5

            if retry > 0:
                print("print textEdit~")
                if ( contents == None):
                    thisWeek_Text = self.trs.textEdit_this_week.toPlainText()
                    nextWeek_Text = self.trs.textEdit_next_week.toPlainText()
                    contents = self.trs.lid + "|" + thisWeek_Text +"|"+nextWeek_Text
                res = self.trs.send_msg_toServer(contents)
                if res == 1:
                    contents = None                    
                    print("메시지 전송 성공")
                    retry = 0
                    self.user_signal.emit(self.trs.req_send_message)
                    self.trs.req_send_message = 0
                else:
                    retry -= 1
            else:
                if self.trs.req_send_message > 0:
                    print("메시지 전송 실패!!!")
                    retry = 0
                    contents = None                    
                    self.user_signal.emit(self.trs.req_send_message-2)
                    self.trs.req_send_message = 0
                
            time.sleep(1)

    def stop(self):
        self.is_running = False
        self.quit()
        self.wait(2000) #2000ms
    print("Thread End")

#==================================================================================================
#==================================================================================================
#==================================================================================================
    
class Class_Login_System(QWidget, Ui_LoginForm):
    def __init__(self, parent=None):
        super(Class_Login_System, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle("--- Total Report System LOGIN ---")
        self.class_id = 0        
        #self.setFixedSize(QSize(950, 575))

    def click_login_button(self):
        print("Login Clicked")
        login_id = self.lineEdit_id.text()
        login_passwd = self.lineEdit_passwd.text()
        encrpyt_passwd = generate_password_hash(login_passwd, method="pbkdf2:sha256", salt_length=16)
        print("password:"+ login_passwd + "hash:" + encrpyt_passwd)

        find_key = None
        for key in dict_team_one:
            if ( key == login_id ):
                find_key = key
                break
        print("find_key:" , find_key)
        if find_key != None and check_password_hash(dict_team_one[find_key], login_passwd) == 1 :
            self.popup_inform("로그인 결과", "로그인 성공", True, 1)            
            self.hide()        
            self.second = Class_Total_Report_System(login_id)
            atexit.register(handle_exit, self.second)
            self.second.show()
            self.second.repaint()
        else:
            if find_key == None :
                self.popup_inform("로그인 결과", "로그인 실패: 등록되지 않은 사용자", True, 2)                
            else: 
                self.popup_inform("로그인 결과", "로그인 실패: 패스워드 오류", True, 2)            
            self.lineEdit_id.clear()
            self.lineEdit_passwd.clear()        
    
    def popup_inform(self, title, msg, autoclose, timeoutSec):        
        msgBox = CustomMessageBox()
        
        msgBox.autoclose = autoclose
        msgBox.timeout = timeoutSec # 3seconds        
        
        msgBox.move(self.frameGeometry().center())
        
        msgBox.setWindowTitle(title)
        msgBox.setText(msg)
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setDefaultButton(QMessageBox.Ok)
        
        msgBox.exec()

    def click_exit_button(self):
        print("Exit Clicked")            
        self.close()
        pass
    
#==================================================================================================
#==================================================================================================
#==================================================================================================
class Class_Total_Report_System(QMainWindow, Ui_MainWindow):
    def __init__(self, login_ID):
        super(Class_Total_Report_System, self).__init__()
        self.setupUi(self)
        self.setWindowTitle("Total Report System~")
        self.setFixedSize(QSize(950, 575))
        self.class_id = 1
        self.msgProcess_thread = MsgProcess(self)        
        self.msgProcess_thread.user_signal[int].connect(self.user_slot)
        self.dialog = QDialog()
        self.datetimeedit = QDateTimeEdit(self.dialog)
        self.lbl = QLabel(' 시간 설정 ', self.dialog)        
        self.btnDialog = QPushButton("확인", self.dialog)
        self.do_it_schedule_sending_mail = 0
        self.req_send_message = 0
        self.init_socket()
        self.msgProcess_thread.start()
        #Tab Focus 창이동으로 변경, if False, using edit tab "  "
        self.textEdit_this_week.setTabChangesFocus(True)
        self.textEdit_next_week.setTabChangesFocus(True)
        self.lid = login_ID
        self.reserved_send_check = 0
        
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
        if self.reserved_send_check == 0:
            datetime = QDateTime.currentDateTime()
            self.dialog.setWindowTitle('예약전송시간 설정')
            """
                Qt.NonModal        : 값은 0 이며, 다른 윈도우 화면 입력을 차단하지 않음 - 모달리스
                Qt.WindowModal     : 값은 1 이며, 화면에 있는 모든 윈도우 창의 입력을 차단 
                                                현재 다이얼로그를 실행시킨 부모 프로그램뿐만 아니라 다른 윈도우들도 제어를 막음
                Qt.ApplicationModal: 값은 2 이며, 다이얼로그를 실행시킨 부모 프로그램만 제어를 막을 수 있음
            """        
            #self.dialog.setWindowModality(Qt.NonModal)
            #self.dialog.setWindowModality(Qt.WindowModal)
            self.dialog.setWindowModality(Qt.ApplicationModal)        
            self.dialog.resize(300, 100)
            #lbl = QLabel(' 예약일정 설정', self.dialog)        
            
            self.datetimeedit.setDateTime(QDateTime.currentDateTime())
            self.datetimeedit.setDateTimeRange(QDateTime(2024, 1, 1, 00, 00, 00), QDateTime(2100, 1, 1, 00, 00, 00))
            #self.datetimeedit.setDisplayFormat('yyyy.MM.dd hh:mm:ss')
            #초(sec) 생략
            self.datetimeedit.setDisplayFormat('yyyy.MM.dd hh:mm')
            #self.datetimeedit.move(50,50)
            #datetimeedit.setGeometry(10, 10, 200, 50)
            
            #self.btnDialog.move(100, 100)
            self.btnDialog.clicked.connect(self.dialog_close)
            
            #hbox = QHBoxLayout()
            #hbox.addStretch(1)
            #hbox.addWidget(self.lbl)        
            #hbox.addWidget(self.datetimeedit)
            #hbox.addWidget(self.btnDialog)
            #hbox.addStretch(1)

            hbox = QHBoxLayout()
            hbox.addStretch(1)
            hbox.addWidget(self.lbl)
            hbox.addStretch(1)
            vbox = QVBoxLayout()
            vbox.addStretch(1)
            #vbox.addWidget(self.lbl)        
            vbox.addLayout(hbox)
            vbox.addWidget(self.datetimeedit)
            vbox.addWidget(self.btnDialog)
            vbox.addStretch(1)

            self.dialog.setLayout(vbox)
            #self.dialog.show()
            self.dialog.exec()
            
            print(datetime.toString())
            print("clicked_send_reserved_msg")
        else:
            print("예약 전송 취소")
            self.reserved_send_check = 0
            self.do_it_schedule_sending_mail = 0                
            schedule.cancel_job(self.schedule_sending_mail) 
            self.pushButton_reserve_send.setStyleSheet("")
            self.pushButton_reserve_send.setToolTip("")
            self.pushButton_reserve_send.setText("예약전송")
            self.popup_inform("실행 결과", "예약 전송이 취소 되었습니다.", True, 3)
    
    def dialog_close(self):        
        cal_trigger_date = self.datetimeedit.date()
        cal_trigger_time = self.datetimeedit.time()
        
        print("Yahoo day: ", cal_trigger_date.year(), cal_trigger_date.month(), cal_trigger_date.day(), cal_trigger_date.weekNumber() )
        print("Yahoo time: ", cal_trigger_time.hour(), cal_trigger_time.minute())
        trigger_time  = str(cal_trigger_date.year()) + "." +str(cal_trigger_date.month()) + "."+ str(cal_trigger_date.day())+ " "+ str(cal_trigger_time.hour()).zfill(2)+ ":"+ str(cal_trigger_time.minute()).zfill(2)
        
        self.reserved_send_check = 1
        self.pushButton_reserve_send.setText("예약전송 취소") 
        self.pushButton_reserve_send.setStyleSheet("background-color: yellow")
        self.pushButton_reserve_send.setToolTip("<font color=""red""<b>"+trigger_time+"</b></font>")
        self.pushButton_reserve_send.move(50,50)
        #self.pushButton_reserve_send.setText("예약전송" + self.datetimeedit.dateTime().toString())
        
        #schedule.every().month
        self.reserved_action_timer()
        self.dialog.close()
        
    def clicked_send_now_msg(self):
        print("clicked_send_now_msg")
        if ( self.req_send_message > 0 ):
            self.popup_inform("실행 결과", "이전 메시지 전송 처리중: 실패", True, 2)
            return -1
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
        if result < 1:
            if result == -1:
                stype = "메시지 전송: 실패"                
            else :                
                stype = "예약 메시지 전송: 실패"
        else:
            self.textEdit_this_week.clear();
            self.textEdit_next_week.clear();
            if result == 1:
                stype = "메시지 전송: 성공"                
            else:                
                stype = "예약 메시지 전송: 성공"

        self.popup_inform("실행 결과", stype, True, 3)
        if result == 0 or result == 2:
            self.pushButton_reserve_send.setStyleSheet("")
            self.pushButton_reserve_send.setToolTip("")
            self.pushButton_reserve_send.setText("예약전송")
            self.reserved_send_check = 0

    def popup_inform(self, title, msg, autoclose, timeoutSec):        
        msgBox = CustomMessageBox()
        
        msgBox.autoclose = autoclose
        msgBox.timeout = timeoutSec # 3seconds
        
        #print(self.frameGeometry().topLeft().toPointF, self.frameGeometry().center().toPointF)
        #msgBox.move(self.frameGeometry().topLeft())
        msgBox.move(self.frameGeometry().center())
        
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

    login_widget = Class_Login_System()
    atexit.register(handle_exit, login_widget)
    login_widget.show()

    #if0
    #window = Class_Total_Report_System()
    #atexit.register(handle_exit, window)
    #window.show()
    #window.repaint()
    #endif

    #center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
    #geo = window.frameGeometry()
    #geo.moveCenter(center)
    #window.move(geo.topLeft())

    app.exec()
    