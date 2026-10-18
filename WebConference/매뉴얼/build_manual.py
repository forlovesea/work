"""Render this repository's manuals to a self-contained offline HTML document.

Only the Markdown subset used by these files is needed: headings, paragraphs,
fences, flat lists, tables, bold, inline code and links. No third-party packages.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = [
    ("00_매뉴얼_안내.md", "overview", "처음 읽기"),
    ("01_일반_참여자_사용법.md", "participant", "일반 참여자"),
    ("02_방장_사용법.md", "host", "방장"),
    ("03_중계서버_설치와_실행.md", "server", "서버 설치와 실행"),
    ("04_부팅_자동시작과_장애대응.md", "startup", "자동 시작과 장애 대응"),
]
LINKS = {filename: "#" + anchor for filename, anchor, _ in DOCS}


def inline(value):
    tokens = []

    def hold(fragment):
        tokens.append(fragment)
        return f"\x00{len(tokens) - 1}\x00"

    value = re.sub(r"`([^`]+)`", lambda m: hold("<code>" + html.escape(m[1]) + "</code>"), value)

    def link(match):
        label, href = match[1], match[2]
        href = LINKS.get(href, href)
        attrs = ' target="_blank" rel="noopener noreferrer"' if href.startswith("https://") else ""
        return hold(f'<a href="{html.escape(href, quote=True)}"{attrs}>{html.escape(label)}</a>')

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    return re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m[1])], value)


def render(text, anchor):
    lines = text.splitlines()
    output, contents = [], []
    index, section = 0, 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            code = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index]); index += 1
            if index == len(lines):
                raise ValueError("Unclosed code fence")
            body = html.escape("\n".join(code))
            output.append(f'<div class="codeblock"><div class="code-label">{html.escape(language or "text")}</div><pre><code>{body}</code></pre></div>')
            index += 1
            continue
        heading = re.match(r"^(#{1,6}) (.+)$", line)
        if heading:
            level = len(heading[1])
            section += 1
            identifier = f"{anchor}-{section}"
            output.append(f'<h{level} id="{identifier}">{inline(heading[2])}</h{level}>')
            if level == 2:
                contents.append(f'<a href="#{identifier}">{html.escape(heading[2])}</a>')
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in row):
                    rows.append(row)
                index += 1
            header = "".join(f"<th>{inline(cell)}</th>" for cell in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>" for row in rows[1:])
            output.append(f'<div class="table-wrap"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>')
            continue
        unordered, ordered = line.startswith("- "), re.match(r"^(\d+)\. (.+)$", line)
        if unordered or ordered:
            tag = "ul" if unordered else "ol"
            attr = "" if unordered else f' start="{ordered[1]}"'
            items = []
            while index < len(lines):
                match = re.match(r"^- (.+)$" if unordered else r"^\d+\. (.+)$", lines[index])
                if not match:
                    break
                items.append("<li>" + inline(match[1]) + "</li>"); index += 1
            output.append(f"<{tag}{attr}>" + "".join(items) + f"</{tag}>")
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip():
            if re.match(r"^(#|```|\||- |\d+\. )", lines[index]):
                break
            paragraph.append(lines[index]); index += 1
        if not paragraph:
            raise ValueError(f"Unsupported Markdown: {lines[index]}")
        output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    title, *body = output
    toc = '<details class="section-index"><summary>이 장의 목차</summary><div>' + "".join(contents) + "</div></details>"
    return title + toc + "".join(body)


CSS = """
:root{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:#243248;background:#f3f6fb;line-height:1.85;font-size:15px}
*{box-sizing:border-box}body{margin:0}a{color:#2f55c8;text-underline-offset:3px}header.cover{padding:48px 5vw;background:#142c46;color:#fff}header.cover .label{font-size:12px;letter-spacing:2px;color:#8fcfc9}header.cover h1{font-size:34px;line-height:1.4;margin:12px 0}header.cover p{color:#d1dfe9;margin:6px 0;max-width:840px}.meta{display:flex;gap:10px;margin-top:22px;flex-wrap:wrap}.meta span{background:#ffffff12;border:1px solid #ffffff25;border-radius:20px;padding:4px 14px;font-size:12px}.layout{max-width:1500px;margin:auto;display:grid;grid-template-columns:245px minmax(0,1fr);gap:34px;padding:30px}aside{position:sticky;top:20px;align-self:start}aside b{font-size:12px;color:#738097}aside a{display:block;padding:10px 12px;text-decoration:none;border-radius:7px;margin:5px 0;color:#35465e;font-size:14px}aside a:hover{background:#e5edf8;color:#214bbd}.hint{font-size:12px;line-height:1.8;color:#7e8a9c;border-top:1px solid #dfe5ee;padding-top:18px;margin-top:20px}main{min-width:0}article{background:white;padding:38px 44px;border:1px solid #e0e7f1;border-radius:14px;margin-bottom:30px;scroll-margin-top:24px}article>h1{font-size:28px;margin:0 0 15px;line-height:1.45;letter-spacing:-.7px}h2{font-size:21px;color:#193954;border-top:1px solid #e4eaf2;margin-top:40px;padding-top:27px;scroll-margin-top:24px}h3{font-size:17px;margin-top:27px;color:#365d7c;scroll-margin-top:24px}p{margin:14px 0}li{margin:8px 0}strong{color:#182f49}code{font-family:Consolas,'Malgun Gothic',monospace;background:#f0f4f9;padding:2px 5px;border-radius:4px;font-size:.9em;overflow-wrap:anywhere}.codeblock{border:1px solid #dce5ef;border-radius:9px;overflow:hidden;margin:18px 0}.code-label{background:#eaf0f7;color:#65778c;padding:5px 16px;font-size:11px;font-weight:700;letter-spacing:.5px}pre{margin:0;padding:17px 20px;background:#f6f8fc;overflow:auto;line-height:1.7;font-size:12px}pre code{padding:0;background:transparent;white-space:pre;font-size:inherit;overflow-wrap:normal}.table-wrap{overflow:auto;margin:19px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.75}th{text-align:left;background:#edf3fa;color:#224564;font-weight:700}td,th{padding:11px 13px;border:1px solid #dfe7f1;vertical-align:top}td:first-child{min-width:115px}td{overflow-wrap:anywhere}.section-index{background:#f6f9fd;border:1px solid #e1eaf4;border-radius:8px;padding:10px 16px;margin:20px 0}.section-index summary{cursor:pointer;font-size:13px;font-weight:700;color:#406584}.section-index div{display:grid;gap:4px;margin-top:10px}.section-index a{font-size:12px}.back-top{font-size:12px;text-align:right;margin-top:28px}footer{padding:10px 30px 30px;text-align:center;font-size:12px;color:#7a899d}
@media(max-width:850px){.layout{display:block;padding:15px}aside{position:static;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:3px}aside a{font-size:12px;background:#e8eef7;padding:7px 10px}aside b,aside .hint{display:none}article{padding:25px 20px}header.cover{padding:30px 24px}header.cover h1{font-size:27px}article>h1{font-size:23px}h2{font-size:19px}table{min-width:500px}pre{font-size:11px}}
@media print{body{background:white;font-size:10pt}.layout{display:block;padding:0}aside,.hint,.section-index,.back-top{display:none}header.cover{background:white;color:#142c46;padding:20mm 0 15mm;border-bottom:2px solid #142c46}header.cover p,header.cover .label{color:#42566c}.meta span{color:#42566c;border:1px solid #ccd7e3}article{border:0;border-radius:0;padding:0;break-before:page}article>h1{font-size:22pt}h2{font-size:15pt}h3{font-size:12pt}h1,h2,h3{break-after:avoid}pre{white-space:pre-wrap;font-size:8pt}pre code{white-space:pre-wrap;overflow-wrap:anywhere}.table-wrap{overflow:visible}table{font-size:8pt}tr{break-inside:avoid}a{color:#223c59}footer{padding:10mm 0}@page{size:A4;margin:18mm}}
"""


def main():
    # Keep the historical command as a compatible entry point.
    import runpy
    runpy.run_path(str(ROOT.parent / '문서' / 'build_documents.py'), run_name='__main__')


if __name__ == "__main__":
    main()
