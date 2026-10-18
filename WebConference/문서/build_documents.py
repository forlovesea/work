"""Build the two offline Korean manuals and their SVG flowcharts, using stdlib only."""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DIAGRAMS = ROOT / "diagrams"
DOCS = [("개발상세서.md", "개발상세서.html", "개발자와 유지보수 담당자", "구조 · 권한 · 데이터 · Flowchart · API · 배포"),
        ("사용매뉴얼.md", "화상회의_상세매뉴얼.html", "Master와 방장과 참석자", "역할별 시작 안내 · 공유 · 회의록 · 서버 운영")]


def esc(s):
    return html.escape(str(s), quote=True)


def label(x, y, lines, size=18):
    return '<text text-anchor="middle" fill="#172c44" font-size="%s">%s</text>' % (
        size, ''.join(f'<tspan x="{x}" y="{y + i * 26}">{esc(line)}</tspan>' for i, line in enumerate(lines)))


def node(x, y, lines, kind="process", width=300, height=76):
    colors = {"process": ("#f1f5fb", "#a6b8d0"), "decision": ("#fff5d8", "#c99d30"),
              "end": ("#e8f6ef", "#6ca58c"), "error": ("#fff0ee", "#cd948b")}
    fill, stroke = colors[kind]
    if kind == "decision":
        shape = f'<path d="M{x},{y-height/2} L{x+width/2},{y} L{x},{y+height/2} L{x-width/2},{y} Z" fill="{fill}" stroke="{stroke}"/>'
    else:
        shape = f'<rect x="{x-width/2}" y="{y-height/2}" width="{width}" height="{height}" rx="{height/2 if kind == "end" else 12}" fill="{fill}" stroke="{stroke}"/>'
    return shape + label(x, y - (len(lines)-1)*13 + 6, lines)


def edge(points, caption="", lx=None, ly=None, marker="arrow"):
    path = "M" + " L".join(f"{x},{y}" for x, y in points)
    result = f'<path d="{path}" fill="none" stroke="#526b88" stroke-width="2" marker-end="url(#{marker})"/>'
    if caption:
        result += f'<text x="{lx}" y="{ly}" font-size="16" fill="#365473" paint-order="stroke" stroke="white" stroke-width="6" stroke-linejoin="round">{esc(caption)}</text>'
    return result


def svg(title, description, body, height):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 {height}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><desc>{esc(description)}</desc>'
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8Z" fill="#526b88"/></marker></defs>'
            '<rect width="100%" height="100%" rx="16" fill="white"/>'
            '<g font-family="Malgun Gothic, Apple SD Gothic Neo, sans-serif">' + body + '</g></svg>')


def flow(name, title, steps):
    """Each step has text, optional decision branch, and a main-path label."""
    body = label(480, 34, [title], 21)
    for i, step in enumerate(steps):
        text, kind, side, below = step
        y = 100 + i * 132
        body += node(260, y, text.split("\n"), kind, height=88 if kind == "decision" else 76)
        if i < len(steps)-1:
            body += edge([(260, y+(44 if kind == "decision" else 38)), (260, y+94)], below, 278, y+76)
        if side:
            side_label, side_text, side_kind = side
            body += edge([(410, y), (550, y)], side_label, 435, y-12)
            body += node(720, y, side_text.split("\n"), side_kind, width=340)
    height = 168 + (len(steps)-1)*132
    joins = {"create": (1, 5), "moderation": (2, 4), "participant": (3, 5)}
    if name in joins:
        source, target = joins[name]
        start_y, end_y = 100+source*132, 100+target*132
        body += edge([(890,start_y),(922,start_y),(922,end_y),(410,end_y)])
    description = " → ".join(s[0].replace("\n", " ") for s in steps)
    (DIAGRAMS / f"{name}.svg").write_text(svg(title, description, body, height), encoding="utf-8")


def build_diagrams():
    DIAGRAMS.mkdir(exist_ok=True)
    body = label(480, 35, ["제어 요청과 미디어 전송 경로"], 21)
    for x, y, text, kind in [
        (480,100,"PC 또는 스마트폰 브라우저", "end"),
        (235,255,"Nginx\nHTTPS 10443", "process"),
        (725,255,"aiortc 미디어 릴레이\nICE 직접 연결 또는 TURN", "process"),
        (235,435,"FastAPI와 Hub\nHTTP · WebSocket · 권한", "process"),
        (725,435,"로컬 음성 인식\nVosk 또는 Whisper", "process"),
        (235,615,"SQLite\n기록 · 승인 · 감사 이력", "end"),
        (725,615,"SMTP → Master 이메일\n일반 방장 승인 요청", "process")]:
        body += node(x,y,text.split("\n"),kind,width=380 if y==100 else 350)
    body += edge([(420,138),(420,175),(235,175),(235,217)],"HTTPS / WSS",245,163)
    body += edge([(540,138),(540,175),(725,175),(725,217)],"WebRTC 미디어",590,163)
    body += edge([(235,293),(235,397)],"127.0.0.1:8000",252,352)
    body += edge([(725,293),(725,397)],"발언권 적용 음성",742,352)
    body += edge([(410,435),(480,435),(480,255),(550,255)],"미디어 제어",493,327)
    body += edge([(235,473),(235,577)],"기록 저장",252,542)
    body += edge([(550,435),(515,435),(515,520),(235,520)],"전사 결과",525,507)
    body += edge([(410,450),(455,450),(455,615),(550,615)],"메일 요청",467,590)
    (DIAGRAMS / "architecture.svg").write_text(svg("전체 시스템 구성", "브라우저는 HTTPS와 WebSocket으로 Nginx 및 FastAPI와 연결하고 별도 WebRTC 경로로 aiortc와 통신한다. 음성 인식 결과와 승인 정보는 SQLite에 저장한다.", body, 695), encoding="utf-8")
    flow("create", "회의 생성과 승인 분기", [
        ("새 회의 만들기 선택", "end", None, ""),
        ("Master 세션 유효?", "decision", ("예", "이메일 승인 생략\n아래 생성 검증으로 진행", "end"), "아니요"),
        ("이름과 연락처 입력\n이메일 인증 요청", "process", None, ""),
        ("Master가 승인?", "decision", ("거절 / 만료", "새 요청 또는 사용자 확인\n생성 불가", "error"), "승인"),
        ("이름 · 연락처 · 기한 확인\n승인 1회 소비", "process", None, ""),
        ("방 수 · 입력 · 기록 설정 검증\n방과 방장 생성", "process", None, ""),
        ("새 회의 시작\n초대 링크 전달", "end", None, "")])
    flow("master", "Master 비밀번호 인증과 관리", [
        ("Master 인증 버튼\n키 입력", "end", None, ""),
        ("키 파일 · 시도 제한 정상?", "decision", ("아니요", "미설정 503 / 제한 429\n관리자 점검 또는 대기", "error"), "예"),
        ("키 해시 일치?", "decision", ("아니요", "인증 실패 401\n다시 입력 또는 서버 키 변경", "error"), "예"),
        ("최대 1시간 관리 세션 발급\n브라우저 메모리에 보관", "process", None, ""),
        ("요청 시 만료 · revision 유효?", "decision", ("아니요", "관리 요청 거부 401\n새 키로 재인증", "error"), "예"),
        ("방 생성 · 조회 · 입장\n강제 퇴장 · 방 삭제", "end", None, "")])
    flow("join", "방 입장과 WebRTC 연결", [
        ("초대 ID와 이름으로 참여\n또는 새 방 생성", "end", None, ""),
        ("방 존재 · 정원 확인", "decision", ("실패", "ID 오류 404 / 정원 409\n최신 초대 정보 확인", "error"), "통과"),
        ("참여 토큰 발급\nWebSocket 첫 메시지 인증", "process", None, ""),
        ("welcome과 현재 상태 수신\n송신 offer / answer 교환", "process", None, ""),
        ("ICE 연결 성공?", "decision", ("실패", "UDP · NAT · TURN 점검\n나간 뒤 재입장", "error"), "예"),
        ("다른 참석자 미디어 구독\n상태와 보드 동기화", "end", None, "")])
    flow("minutes", "자동 기록에서 파일 저장까지", [
        ("회의 모드에서 자동 기록 켜기", "end", None, ""),
        ("발표권과 마이크가 활성?", "decision", ("아니요", "해당 음성 기록 안 함\n권한과 장치 확인", "error"), "예"),
        ("음성 수집 → 인식 대기열\n텍스트 완료 후 DB 저장", "process", None, ""),
        ("저장 준비: 자동 기록 끄기", "process", None, ""),
        ("Whisper 대기 0건?", "decision", ("아니요", "완료까지 기다린 뒤 재확인\n처리 중 다운로드는 409", "error"), "예 / Vosk 완료 확인"),
        ("Word · PDF · TXT 선택\n원하면 요약 추가 체크", "process", None, ""),
        ("전체 저장 기록 내려받기\n파일 확인 후 나가기", "end", None, "")])
    flow("moderation", "강제 퇴장과 방 삭제", [
        ("Master가 대상 방 선택", "end", None, ""),
        ("Master 세션 유효?", "decision", ("아니요", "요청 거부\n재인증 필요", "error"), "예"),
        ("방 전체 삭제인가?", "decision", ("아니요: 퇴장", "초대 ID 갱신\n선택한 참가자만 정리", "process"), "예"),
        ("방 비활성화 · 목록 제거\n전체 참가자를 정리 대상으로", "process", None, ""),
        ("대상 토큰 폐기 · 명령 취소\nremoved 알림 · 연결 종료", "process", None, ""),
        ("PeerConnection과 트랙 정리\n빈 방 닫기 · 감사 기록", "process", None, ""),
        ("저장된 회의록 DB 유지", "end", None, "")])
    flow("deploy", "안전한 업데이트와 수동 롤백", [
        ("기록 대기 0건 · 회의 종료\nDB와 설정 백업", "end", None, ""),
        ("이전 current 경로 기록\ngit pull 후 installer 실행", "process", None, ""),
        ("새 환경 · 모델 준비 성공?", "decision", ("아니요", "오류 원인 확인\n활성 전환 여부 점검", "error"), "예"),
        ("Moa 정지 → current 전환\nMoa 시작", "process", None, ""),
        ("상태 및 외부 기능 정상?", "decision", ("아니요", "Moa 정지 → 이전 링크 복원\n시작 후 재검증", "error"), "예"),
        ("기존 서비스 영향 확인\n배포 커밋과 결과 기록", "end", None, "")])
    flow("participant", "참석자 빠른 시작", [
        ("초대 링크 열기", "end", None, ""),
        ("이름 · 장치 설정\n회의 참여하기", "process", None, ""),
        ("스피커 켜기\n상대방 소리 확인", "process", None, ""),
        ("회의 모드인가?", "decision", ("FREE Talk", "마이크를 켜고 대화\n공유는 발표자만 가능", "process"), "예"),
        ("손들기 → 방장의 발표 지정\n마이크를 켜고 발언", "process", None, ""),
        ("필요한 회의록 저장\n나가기", "end", None, "")])


LINKS = {"사용매뉴얼.md": "화상회의_상세매뉴얼.html", "개발상세서.md": "개발상세서.html"}


def inline(text):
    tokens = []
    def hold(fragment):
        tokens.append(fragment)
        return f"\x00{len(tokens)-1}\x00"
    text = re.sub(r"`([^`]+)`", lambda m: hold("<code>"+esc(m[1])+"</code>"), text)
    def link(m):
        href = LINKS.get(m[2], m[2][3:] if m[2].startswith("../") else m[2])
        return hold(f'<a href="{esc(href)}">{esc(m[1])}</a>')
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))
    return re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m[1])], text)


def render(text):
    lines = text.splitlines()
    parts, toc = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            lang, code = line[3:], []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i]); i += 1
            if i == len(lines):
                raise ValueError("Unclosed code fence")
            parts.append('<div class="codeblock"><div class="code-label">'+esc(lang)+'</div><pre><code>'+esc('\n'.join(code))+'</code></pre></div>')
            i += 1
            continue
        image = re.fullmatch(r"!\[([^\]]+)\]\((diagrams/[^)]+)\)", line)
        if image:
            content = (ROOT / image[2]).read_text(encoding="utf-8")
            # Every embedded diagram needs distinct fragment IDs.
            identifier = Path(image[2]).stem
            content = content.replace('id="arrow"', f'id="arrow-{identifier}"').replace('url(#arrow)', f'url(#arrow-{identifier})')
            parts.append(f'<figure class="diagram">{content}<figcaption>{esc(image[1])} · 도표가 작으면 가로로 스크롤하여 보세요</figcaption></figure>')
            i += 1
            continue
        heading = re.match(r"^(#{1,3}) (.+)$", line)
        if heading:
            level, title = len(heading[1]), heading[2]
            anchor = f"section-{len(toc)+1}" if level == 2 else f"heading-{i}"
            if level == 2:
                toc.append((anchor,title))
            parts.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in row):
                    rows.append(row)
                i += 1
            assert all(len(r) == len(rows[0]) for r in rows), "Unequal table columns"
            parts.append('<div class="table-wrap" tabindex="0"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>')
            continue
        unordered = line.startswith("- ")
        ordered = re.match(r"^(\d+)\. ", line)
        if unordered or ordered:
            tag = "ul" if unordered else "ol"
            start = '' if unordered else f' start="{ordered[1]}"'
            items = []
            while i < len(lines):
                m = re.match(r"^- (.+)$" if unordered else r"^\d+\. (.+)$", lines[i])
                if not m:
                    break
                items.append('<li>'+inline(m[1])+'</li>'); i += 1
            parts.append(f'<{tag}{start}>'+''.join(items)+f'</{tag}>')
            continue
        paragraph = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||- |\d+\. |!\[)", lines[i]):
            paragraph.append(lines[i]); i += 1
        if not paragraph:
            raise ValueError(f"Unsupported Markdown: {lines[i]}")
        parts.append('<p>'+inline(' '.join(paragraph))+'</p>')
    return ''.join(parts), toc


CSS = """
:root{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:#22334a;background:#f3f5f9;font-size:16px;line-height:1.85}*{box-sizing:border-box}body{margin:0}a{color:#2556a3;text-underline-offset:4px}a:focus-visible,button:focus-visible{outline:3px solid #b78319;outline-offset:3px}.skip{position:absolute;left:-10000px}.skip:focus{left:20px;top:10px;background:white;padding:10px;z-index:5}.top{padding:22px 4vw;background:#132d49;color:white;display:flex;justify-content:space-between;gap:20px;align-items:center}.top b{font-size:20px}.top a{color:#fff}.top nav{display:flex;gap:22px;flex-wrap:wrap;font-size:14px}.layout{max-width:1530px;margin:auto;display:grid;grid-template-columns:260px minmax(0,1fr);gap:32px;padding:32px}.contents{position:sticky;top:20px;align-self:start;max-height:calc(100vh - 40px);overflow-y:auto;padding:12px}.contents h2{font-size:14px;margin:0 0 16px;color:#5b7089}.contents a{display:block;text-decoration:none;color:#42556c;padding:6px 8px;font-size:13px;border-radius:6px;line-height:1.6}.contents a:hover{background:#e2eaf6;color:#204f91}.contents p{font-size:12px;color:#64758c}.contents details>summary{font-weight:bold;margin-bottom:12px;cursor:pointer}main{min-width:0;background:white;border:1px solid #e0e6ee;border-radius:14px;padding:42px 52px}.eyebrow{font-size:12px;color:#457c79;font-weight:bold;letter-spacing:1px;margin:0 0 12px}h1{font-size:34px;line-height:1.4;letter-spacing:-1px;color:#142d47;margin:12px 0 22px}h2{font-size:24px;line-height:1.5;color:#172e48;margin:56px 0 20px;scroll-margin-top:24px}h3{font-size:19px;color:#314e6d;margin:30px 0 14px;scroll-margin-top:24px}p{margin:14px 0}li{margin:9px 0}strong{color:#162e49}.table-wrap{overflow:auto;margin:22px 0;border:1px solid #d9e1eb;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.7}th,td{padding:12px 14px;border:1px solid #d9e1eb;vertical-align:top;overflow-wrap:anywhere}th{background:#223f60;color:white;text-align:left}tbody tr:nth-child(even){background:#f4f7fb}td:first-child{min-width:130px}code{font-family:Consolas,'Malgun Gothic',monospace;font-size:.9em;background:#eef3f9;border-radius:4px;padding:2px 4px;overflow-wrap:anywhere}.codeblock{margin:22px 0;border:1px solid #d8e1ec;border-radius:8px;overflow:hidden}.code-label{font-size:11px;letter-spacing:1px;background:#eaf0f7;padding:5px 16px;color:#516983}pre{margin:0;padding:18px;overflow:auto;background:#f7f9fc;line-height:1.7;font-size:13px}pre code{background:transparent;padding:0;white-space:pre;overflow-wrap:normal}.diagram{margin:28px 0;padding:14px;border:1px solid #d9e3ef;border-radius:12px;overflow:auto;background:white}.diagram svg{display:block;width:100%;min-width:620px;height:auto}.diagram figcaption{font-size:12px;color:#61748d;margin-top:8px}.footer{font-size:12px;color:#6a7b90;text-align:center;padding:24px}.print{border:1px solid #62768e;border-radius:6px;background:transparent;color:white;padding:8px 14px;cursor:pointer}.back{display:block;text-align:right;margin:30px 0 0;font-size:13px}
@media(max-width:1000px){.layout{grid-template-columns:210px minmax(0,1fr);gap:18px;padding:18px}main{padding:30px}.contents{padding:5px}h1{font-size:29px}}
@media(max-width:760px){.top{display:block;padding:20px}.top nav{margin-top:12px;gap:14px}.layout{display:block;padding:12px}.contents{position:static;max-height:none;background:#eaf0f8;border-radius:9px;padding:16px;margin-bottom:16px}.contents a{font-size:14px}main{padding:23px 18px}h1{font-size:27px}h2{font-size:22px;margin-top:40px}h3{font-size:18px}table{min-width:600px}pre{font-size:12px}.diagram{padding:8px}.diagram svg{min-width:740px}}
@media print{@page{size:A4;margin:17mm}body{background:white;font-size:10pt}.top,.contents,.footer,.back,.eyebrow{display:none}.layout{display:block;padding:0}main{border:0;padding:0}h1{font-size:24pt}h2{font-size:16pt;margin-top:26pt}h3{font-size:12pt}h1,h2,h3{break-after:avoid}table{font-size:8pt;min-width:0}th,td{padding:7px}tr{break-inside:avoid}thead{display:table-header-group}.table-wrap{overflow:visible}pre{font-size:8pt;white-space:pre-wrap}pre code{white-space:pre-wrap;overflow-wrap:anywhere}.diagram{break-inside:avoid;padding:5px;border:0}.diagram svg{min-width:0;max-height:220mm}.diagram figcaption{font-size:8pt}a{color:inherit;text-decoration:none}}
"""


def main():
    build_diagrams()
    for source, output, audience, subtitle in DOCS:
        body, toc = render((ROOT/source).read_text(encoding="utf-8"))
        nav = ''.join(f'<a href="#{anchor}">{esc(title)}</a>' for anchor,title in toc)
        title = "모아 화상회의 개발상세서" if source == "개발상세서.md" else "모아 화상회의 역할별 사용 매뉴얼"
        page = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body id="top"><a class="skip" href="#content">본문 바로가기</a><header class="top"><b>모아 문서실</b><nav aria-label="문서 이동"><a href="개발상세서.html">개발상세서</a><a href="화상회의_상세매뉴얼.html">사용 매뉴얼</a><button class="print" onclick="window.print()">인쇄</button></nav></header><div class="layout"><aside class="contents"><details open><summary>목차</summary><nav aria-label="장별 목차">{nav}</nav></details><p>2026년 10월 18일<br>구현 기준 fd1a7d0<br>Ctrl+F 검색 · Ctrl+P 인쇄<br>Flowchart 포함 · 오프라인 열람</p></aside><main id="content"><p class="eyebrow">{esc(audience)}<br>{esc(subtitle)}</p>{body}<a class="back" href="#top">맨 위로 이동 ↑</a></main></div><footer class="footer">원문 문서/{esc(source)} · 도표 포함 오프라인 HTML · 키와 비밀번호는 별도 관리</footer></body></html>'
        (PROJECT/output).write_text(page,encoding="utf-8")
        print(f"Built {output}: {len(toc)} chapters, {page.count('<svg ')} diagrams, {(PROJECT/output).stat().st_size} bytes")


if __name__ == "__main__":
    main()
