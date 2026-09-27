import os
import sys

from PySide6.QtCore import QMarginsF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
)
from PySide6.QtPdf import QPdfDocument


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(
    BASE_DIR, "TBC1000B_고객용_MiniGUI_사용자매뉴얼_V1.0.pdf"
)
SCREENSHOT_PATH = os.path.join(BASE_DIR, "mini_manual.png")
PREVIEW_PATH = os.path.join(BASE_DIR, "mini_manual_pdf_preview_page1.png")
PREVIEW_PAGE2_PATH = os.path.join(BASE_DIR, "mini_manual_pdf_preview_page2.png")
FONT_REGULAR_PATH = r"C:\Windows\Fonts\NotoSansKR-VF.ttf"


class ManualWriter:
    NAVY = QColor("#173B76")
    BLUE = QColor("#246BFD")
    TEXT = QColor("#172033")
    MUTED = QColor("#667085")
    LINE = QColor("#DCE3EE")
    PANEL = QColor("#F4F7FB")
    GREEN = QColor("#039855")
    RED = QColor("#D92D20")
    ORANGE = QColor("#F79009")

    def __init__(self, output_path, font_family):
        self.font_family = font_family
        self.output_path = output_path
        self.page_width = 1240
        self.page_height = 1754
        self.pages = []
        self.image = None
        self.painter = None
        self._start_canvas()
        if not self.painter.isActive():
            raise RuntimeError("매뉴얼 페이지 렌더링을 시작할 수 없습니다.")
        self.rect = QRectF(70, 70, self.page_width - 140, self.page_height - 140)
        self.left = float(self.rect.left())
        self.top = float(self.rect.top())
        self.right = float(self.rect.right())
        self.bottom = float(self.rect.bottom())
        self.width = float(self.rect.width())
        self.height = float(self.rect.height())
        self.page = 1

    def _start_canvas(self):
        self.image = QImage(
            self.page_width, self.page_height, QImage.Format_ARGB32_Premultiplied
        )
        self.image.fill(QColor("white"))
        self.painter = QPainter(self.image)
        self.painter.setRenderHint(QPainter.Antialiasing, True)
        self.painter.setRenderHint(QPainter.TextAntialiasing, True)

    def font(self, size, bold=False):
        font = QFont(self.font_family, size)
        font.setBold(bold)
        return font

    def text(self, text, x, y, width, height, size=10, color=None,
             bold=False, align=Qt.AlignLeft | Qt.AlignTop):
        self.painter.setFont(self.font(size, bold))
        self.painter.setPen(color or self.TEXT)
        flags = align | Qt.TextWordWrap
        self.painter.drawText(QRectF(x, y, width, height), flags, text)

    def line(self, x1, y1, x2, y2, color=None, width=1):
        self.painter.setPen(QPen(color or self.LINE, width))
        self.painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def box(self, x, y, width, height, fill=None, border=None, radius=10):
        self.painter.setBrush(fill or Qt.NoBrush)
        if border is None or border == Qt.NoPen:
            self.painter.setPen(Qt.NoPen)
        else:
            self.painter.setPen(QPen(border, 1))
        self.painter.drawRoundedRect(QRectF(x, y, width, height), radius, radius)

    def page_header(self, title):
        self.text("TBC1000B Battery Control Mini", self.left, self.top,
                  self.width * 0.55, 34, 10, self.NAVY, True)
        self.text(title, self.left + self.width * 0.55, self.top,
                  self.width * 0.45, 34, 9, self.MUTED, False,
                  Qt.AlignRight | Qt.AlignTop)
        self.line(self.left, self.top + 38, self.right, self.top + 38)

    def page_footer(self):
        y = self.bottom - 44
        self.line(self.left, y - 8, self.right, y - 8)
        self.text("TBC1000B 고객용 MiniGUI 사용자 매뉴얼 · V1.0",
                  self.left, y, self.width * 0.8, 22, 8, self.MUTED)
        self.text(str(self.page), self.left + self.width * 0.8, y,
                  self.width * 0.2, 22, 8, self.MUTED, False,
                  Qt.AlignRight | Qt.AlignTop)

    def finish_page(self):
        self.page_footer()

    def new_page(self, title):
        self.finish_page()
        self.painter.end()
        self.pages.append(self.image)
        self._start_canvas()
        self.page += 1
        self.page_header(title)
        return self.top + 68

    def section_title(self, number, title, y):
        self.box(self.left, y, 34, 34, self.BLUE, self.BLUE, 8)
        self.text(str(number), self.left, y + 1, 34, 30, 11, QColor("white"),
                  True, Qt.AlignCenter)
        self.text(title, self.left + 48, y - 2, self.width - 48, 40,
                  17, self.NAVY, True)
        return y + 52

    def bullet(self, text, y, color=None, size=10, gap=8):
        self.painter.setBrush(color or self.BLUE)
        self.painter.setPen(Qt.NoPen)
        self.painter.drawEllipse(QRectF(self.left + 5, y + 8, 7, 7))
        self.text(text, self.left + 24, y, self.width - 30, 52,
                  size, self.TEXT)
        return y + 52 + gap

    def numbered_step(self, number, title, body, y, accent=None):
        accent = accent or self.BLUE
        self.box(self.left, y, self.width, 92, QColor("#F8FAFD"), self.LINE, 10)
        self.box(self.left + 16, y + 18, 38, 38, accent, accent, 19)
        self.text(str(number), self.left + 16, y + 21, 38, 32, 11,
                  QColor("white"), True, Qt.AlignCenter)
        self.text(title, self.left + 70, y + 13, self.width - 86, 28,
                  11, self.NAVY, True)
        self.text(body, self.left + 70, y + 43, self.width - 86, 42,
                  9, self.MUTED)
        return y + 108

    def close(self):
        self.finish_page()
        self.painter.end()
        self.pages.append(self.image)

        pdf = QPdfWriter(self.output_path)
        pdf.setTitle("TBC1000B Battery Control Mini 사용자 매뉴얼")
        pdf.setCreator("PANTECH C&I Engineering")
        pdf.setResolution(150)
        pdf.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.A4),
                QPageLayout.Portrait,
                QMarginsF(0, 0, 0, 0),
                QPageLayout.Millimeter,
            )
        )
        pdf_painter = QPainter(pdf)
        page_rect = pdf.pageLayout().paintRectPixels(pdf.resolution())
        for index, page_image in enumerate(self.pages):
            if index:
                pdf.newPage()
            pdf_painter.drawImage(QRectF(page_rect), page_image)
        pdf_painter.end()


def build_manual():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    regular_font_id = QFontDatabase.addApplicationFont(FONT_REGULAR_PATH)
    if regular_font_id < 0:
        raise RuntimeError("Noto Sans KR 글꼴을 등록할 수 없습니다.")
    font_families = QFontDatabase.applicationFontFamilies(regular_font_id)
    if not font_families:
        raise RuntimeError("등록한 한글 글꼴의 패밀리 정보를 찾을 수 없습니다.")

    writer = ManualWriter(OUTPUT_PATH, font_families[0])

    # 표지
    writer.box(writer.left, writer.top, writer.width, writer.height - 40,
               writer.PANEL, Qt.NoPen, 18)
    writer.box(writer.left, writer.top, 18, writer.height - 40,
               writer.BLUE, writer.BLUE, 9)
    writer.text("TBC1000B", writer.left + 60, writer.top + 180,
                writer.width - 120, 70, 31, writer.NAVY, True)
    writer.text("Battery Control Mini", writer.left + 60, writer.top + 250,
                writer.width - 120, 55, 21, writer.BLUE, True)
    writer.text("고객용 사용자 매뉴얼", writer.left + 60, writer.top + 340,
                writer.width - 120, 70, 25, writer.TEXT, True)
    writer.line(writer.left + 60, writer.top + 430,
                writer.right - 60, writer.top + 430, writer.LINE, 2)
    writer.text("시스템 접속 · SOC 충전제한 · EPO 전체 차단/복구",
                writer.left + 60, writer.top + 470,
                writer.width - 120, 70, 13, writer.MUTED)
    writer.box(writer.left + 60, writer.bottom - 250,
               writer.width - 120, 110, QColor("white"), writer.LINE, 12)
    writer.text("문서 버전", writer.left + 82, writer.bottom - 225,
                150, 28, 9, writer.MUTED, True)
    writer.text("V1.0", writer.left + 250, writer.bottom - 225,
                180, 28, 10, writer.TEXT, True)
    writer.text("작성일", writer.left + 82, writer.bottom - 183,
                150, 28, 9, writer.MUTED, True)
    writer.text("2026-08-06", writer.left + 250, writer.bottom - 183,
                180, 28, 10, writer.TEXT, True)

    # 화면 구성
    y = writer.new_page("1. 화면 구성")
    y = writer.section_title(1, "화면 구성", y)
    image = QImage(SCREENSHOT_PATH)
    if image.isNull():
        raise FileNotFoundError(SCREENSHOT_PATH)
    max_w = writer.width
    max_h = 760
    scale = min(max_w / image.width(), max_h / image.height())
    draw_w = image.width() * scale
    draw_h = image.height() * scale
    writer.painter.drawImage(
        QRectF(writer.left + (writer.width - draw_w) / 2, y, draw_w, draw_h),
        image,
    )
    y += draw_h + 24
    items = [
        "시스템 접속: 장비 IP와 SNMP Port를 입력하고 접속을 시작하거나 종료합니다.",
        "접속 상태: ONLINE/READY 상태와 마지막 정상 업데이트 시각을 확인합니다.",
        "SOC 충전제한: 현재 제한값을 확인하고 90%, 95%, 100% 또는 미사용으로 변경합니다.",
        "EPO(전체모듈): 모든 축전지 모듈의 출력을 일괄 차단하거나 복구합니다.",
    ]
    for item in items:
        y = writer.bullet(item, y, size=9, gap=0)

    # 접속
    y = writer.new_page("2. 시스템 접속")
    y = writer.section_title(2, "시스템 접속", y)
    writer.box(writer.left, y, writer.width, 76, QColor("#FFF7E8"),
               QColor("#FEDF89"), 10)
    writer.text("접속 전 확인", writer.left + 18, y + 12,
                150, 26, 10, writer.ORANGE, True)
    writer.text("PC와 축전지 시스템의 네트워크 연결 및 장비 IP를 먼저 확인하십시오.",
                writer.left + 18, y + 39, writer.width - 36, 28,
                9, writer.TEXT)
    y += 96
    y = writer.numbered_step(1, "시스템 IP 입력",
                             "접속할 축전지 시스템의 IPv4 주소를 입력합니다. 예: 10.0.0.3", y)
    y = writer.numbered_step(2, "SNMP Port 확인",
                             "기본 포트는 161입니다. 현장 설정이 다른 경우 지정된 포트를 입력합니다.", y)
    y = writer.numbered_step(3, "접속시작 선택",
                             "접속 시험이 성공하면 상단 배지가 ONLINE으로 바뀌고 접속 상태에 정상 접속이 표시됩니다.", y)
    y = writer.numbered_step(4, "최종 업데이트 확인",
                             "마지막으로 정상 데이터를 수신한 시간이 계속 갱신되는지 확인합니다.", y)
    y += 12
    writer.text("접속 종료", writer.left, y, writer.width, 30,
                12, writer.NAVY, True)
    writer.text("작업을 마친 뒤 ‘접속종료’를 선택합니다. 종료 후에는 SOC 설정과 EPO 버튼이 비활성화됩니다.",
                writer.left, y + 34, writer.width, 55, 10, writer.TEXT)

    # SOC
    y = writer.new_page("3. SOC 충전제한")
    y = writer.section_title(3, "SOC 충전제한 설정", y)
    writer.text("SOC 충전제한은 축전지 시스템의 충전 상한을 지정하는 기능입니다. 화면의 ‘현재 설정’에서 적용값을 확인할 수 있습니다.",
                writer.left, y, writer.width, 64, 10, writer.TEXT)
    y += 80
    y = writer.numbered_step(1, "설정 변경 선택",
                             "장비가 정상 접속된 상태에서 SOC 충전제한 영역의 ‘설정 변경’을 선택합니다.", y)
    y = writer.numbered_step(2, "제한값 선택",
                             "90%, 95%, 100% 또는 ‘사용안함’ 중 현장 운용 기준에 맞는 항목을 선택합니다.", y)
    y = writer.numbered_step(3, "확인 및 적용",
                             "확인을 누르면 SNMP SET과 응답 검증이 수행됩니다. 성공 메시지가 표시될 때까지 기다립니다.", y)
    y = writer.numbered_step(4, "현재 설정 재확인",
                             "화면에 선택한 값이 표시되는지 확인합니다. 미사용 상태에서는 ‘미사용’으로 표시됩니다.", y)
    y += 18
    writer.box(writer.left, y, writer.width, 112, QColor("#EEF4FF"),
               QColor("#B2CCFF"), 10)
    writer.text("중요", writer.left + 18, y + 14, 90, 28,
                10, writer.BLUE, True)
    writer.text("SOC 설정값은 현장 운용 정책과 배터리 제조사의 권장 조건을 확인한 담당자만 변경하십시오. 통신 오류 메시지가 나오면 반복 조작하지 말고 연결 상태를 먼저 확인하십시오.",
                writer.left + 18, y + 44, writer.width - 36, 60,
                9, writer.TEXT)

    # EPO
    y = writer.new_page("4. EPO 전체모듈")
    y = writer.section_title(4, "EPO 전체 차단 및 복구", y)
    writer.box(writer.left, y, writer.width, 118, QColor("#FEF3F2"),
               QColor("#FECDCA"), 10)
    writer.text("경고 — 운용 영향이 큰 기능입니다", writer.left + 18, y + 14,
                writer.width - 36, 30, 12, writer.RED, True)
    writer.text("전체 차단은 모든 축전지 모듈의 출력을 일괄 차단합니다. 반드시 권한이 있는 담당자가 부하 및 현장 안전 상태를 확인한 후 실행하십시오.",
                writer.left + 18, y + 48, writer.width - 36, 62,
                9, writer.TEXT)
    y += 142
    y = writer.numbered_step(1, "사전 확인",
                             "대상 시스템 IP, ONLINE 상태, 최종 업데이트 시각과 작업 승인 여부를 확인합니다.", y, writer.RED)
    y = writer.numbered_step(2, "전체 차단",
                             "‘전체 차단’을 선택하고 확인 창의 내용을 다시 검토한 뒤 승인합니다. 작업 결과 메시지를 확인합니다.", y, writer.RED)
    y = writer.numbered_step(3, "전체 복구",
                             "복구 조건이 충족된 후 ‘전체 복구’를 선택하고 확인 창을 승인합니다. 시스템 출력을 현장에서 재확인합니다.", y, writer.GREEN)
    y += 18
    writer.text("조작 후 필수 확인", writer.left, y, writer.width, 34,
                12, writer.NAVY, True)
    checks = [
        "성공 또는 실패 메시지를 확인하고 작업 기록에 결과를 남깁니다.",
        "원격 명령 성공만으로 현장 상태를 단정하지 말고 실제 출력 상태를 확인합니다.",
        "응답 불일치나 시간 초과가 발생하면 연속 클릭하지 말고 네트워크 및 장비 상태를 점검합니다.",
    ]
    y += 38
    for check in checks:
        y = writer.bullet(check, y, writer.RED, 9, 0)

    # 상태 및 장애 대응
    y = writer.new_page("5. 상태 확인 및 장애 대응")
    y = writer.section_title(5, "상태 확인 및 장애 대응", y)
    rows = [
        ("READY / 접속 대기", "장비에 접속하지 않은 상태입니다. IP와 Port를 확인한 뒤 접속을 시작하십시오."),
        ("CONNECTING / 접속 중", "접속 시험이 진행 중입니다. 완료될 때까지 입력과 버튼 조작을 기다리십시오."),
        ("ONLINE / 정상 접속", "장비 접속이 완료된 상태입니다. 최종 업데이트 시간이 갱신되는지 확인하십시오."),
        ("SOC 값이 ‘-’", "아직 값을 받지 못했거나 통신 응답이 실패한 상태입니다. 잠시 기다린 뒤 네트워크를 확인하십시오."),
        ("설정 또는 EPO 실패", "IP, Port, 장비 상태 및 권한을 확인하십시오. 동일 명령을 무분별하게 반복하지 마십시오."),
    ]
    for title, body in rows:
        writer.box(writer.left, y, writer.width, 88, QColor("#F8FAFD"),
                   writer.LINE, 8)
        writer.text(title, writer.left + 16, y + 14, 230, 52,
                    10, writer.NAVY, True)
        writer.text(body, writer.left + 250, y + 13,
                    writer.width - 266, 62, 9, writer.TEXT)
        y += 102
    y += 12
    writer.box(writer.left, y, writer.width, 118, QColor("#FFF7E8"),
               QColor("#FEDF89"), 10)
    writer.text("장애 발생 시 전달할 정보", writer.left + 18, y + 14,
                writer.width - 36, 28, 11, writer.ORANGE, True)
    writer.text("발생 시각, 시스템 IP, 표시된 상태와 오류 메시지, 수행한 작업(SOC/EPO), 재현 여부를 기록하여 유지보수 담당자에게 전달하십시오.",
                writer.left + 18, y + 48, writer.width - 36, 58,
                9, writer.TEXT)

    # 안전/종료
    y = writer.new_page("6. 운용 안전 및 종료")
    y = writer.section_title(6, "운용 안전 및 프로그램 종료", y)
    safety = [
        "본 프로그램은 승인된 축전지 시스템과 관리 네트워크에서만 사용하십시오.",
        "SOC 설정과 EPO 명령은 운용 정책을 숙지한 권한 보유자만 수행하십시오.",
        "원격 명령 전후에 대상 시스템 IP를 다시 확인하여 오조작을 예방하십시오.",
        "통신 실패 시 명령을 반복 전송하지 말고 장비 및 네트워크 상태를 먼저 점검하십시오.",
        "작업 완료 후 접속을 종료하고 프로그램 창을 닫으십시오.",
    ]
    for item in safety:
        y = writer.bullet(item, y, writer.GREEN, 10, 4)
    y += 16
    writer.box(writer.left, y, writer.width, 180, QColor("#EEF4FF"),
               QColor("#B2CCFF"), 12)
    writer.text("권장 종료 순서", writer.left + 22, y + 18,
                writer.width - 44, 32, 13, writer.NAVY, True)
    writer.text("1. 진행 중인 설정 또는 EPO 작업이 없는지 확인합니다.\n"
                "2. 최종 상태와 작업 결과를 기록합니다.\n"
                "3. ‘접속종료’를 선택합니다.\n"
                "4. READY 상태를 확인한 뒤 프로그램 창을 닫습니다.",
                writer.left + 22, y + 58, writer.width - 44, 108,
                10, writer.TEXT)
    y += 214
    writer.text("문의 시 프로그램명과 문서 버전(V1.0)을 함께 알려주십시오.",
                writer.left, y, writer.width, 42, 10, writer.MUTED, True,
                Qt.AlignCenter | Qt.AlignTop)

    writer.close()
    return OUTPUT_PATH


def render_page_preview(pdf_path, page_index, output_path):
    document = QPdfDocument()
    if document.load(pdf_path) != QPdfDocument.Error.None_:
        raise RuntimeError("생성된 PDF를 다시 열 수 없습니다.")
    if document.pageCount() <= page_index:
        raise RuntimeError("생성된 PDF에 페이지가 없습니다.")
    page_size = document.pagePointSize(page_index)
    preview_width = 1000
    preview_height = round(preview_width * page_size.height() / page_size.width())
    image = document.render(page_index, QSize(preview_width, preview_height))
    if image.isNull() or not image.save(output_path, "PNG"):
        raise RuntimeError("PDF 검증용 미리보기를 만들 수 없습니다.")
    return output_path


if __name__ == "__main__":
    output = build_manual()
    preview = render_page_preview(output, 0, PREVIEW_PATH)
    preview_page2 = render_page_preview(output, 1, PREVIEW_PAGE2_PATH)
    print(output)
    print(preview)
    print(preview_page2)
