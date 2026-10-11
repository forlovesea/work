"""Generate a Word development guide with excerpts from the actual source."""
import ast
import re
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/package/2006/relationships'


def excerpt(filename,classname,function):
    source=(ROOT/filename).read_text(encoding='utf-8-sig')
    tree=ast.parse(source)
    nodes=tree.body
    if classname:
        nodes=next(n for n in nodes if isinstance(n,ast.ClassDef) and n.name==classname).body
    node=next(n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function)
    lines=source.splitlines()[node.lineno-1:node.end_lineno]
    indent=len(lines[0])-len(lines[0].lstrip())
    return '\n'.join(line[indent:] for line in lines)


examples=[]
for filename,cls,fn,description in [
 ('engine.py',None,'read_bars','CSV는 열 이름·숫자·날짜 순서가 올바른지 확인한 뒤 모의 엔진에 전달합니다.'),
 ('app.py',None,'return_series','기간 시작 직전 평가액을 기준으로 수익률을 계산합니다. 0% 기준점은 비교를 위한 값입니다.'),
 ('broker.py','TossBroker','request','실전 플래그가 없으면 GET 이외 요청을 막습니다. 인증 후 API 응답 형식을 확인합니다.'),
 ('live.py','Store','save','장부를 임시 파일에 쓴 다음 교체합니다. 일반 텍스트 로그처럼 삭제해서는 안 됩니다.'),
 ('live.py','LiveBot','observe','목표 도달 상태·낙폭·기간 수익률과 GUI용 일별 관측 기록을 갱신합니다.')]:
    examples.append(f'### {filename} / {cls+"." if cls else ""}{fn}\n\n{description}\n\n```python\n{excerpt(filename,cls,fn)}\n```\n')
source=(ROOT/'DEVELOPMENT_GUIDE.md').read_text(encoding='utf-8')
source=source.replace('## 14. 공식 참고 문서','\n'.join(examples)+'\n## 14. 공식 참고 문서')
# Keep the readable companion in sync with the exact excerpts used in Word.
(ROOT/'DEVELOPMENT_GUIDE_WITH_SOURCE.md').write_text(source,encoding='utf-8')

def plain(text):
    return re.sub(r'\[([^]]+)\]\(([^)]+)\)',r'\1 (\2)',text).replace('`','')

def para(text,style='Normal'):
    runs='<w:br/>'.join('<w:t xml:space="preserve">'+escape(s)+'</w:t>' for s in text.split('\n'))
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r>{runs}</w:r></w:p>'

def table(rows):
    count=len(rows[0]); width=9300//count
    result='<w:tbl><w:tblPr><w:tblW w:w="9300" w:type="dxa"/><w:tblBorders>'
    for edge in ('top','left','bottom','right','insideH','insideV'):
        result+=f'<w:{edge} w:val="single" w:sz="4" w:color="D8E1EA"/>'
    result+='</w:tblBorders><w:tblCellMar><w:top w:w="85" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="85" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>'
    result+=''.join(f'<w:gridCol w:w="{width}"/>' for _ in range(count))+'</w:tblGrid>'
    for i,row in enumerate(rows):
        result+='<w:tr><w:trPr><w:cantSplit/>'+('<w:tblHeader/>' if i==0 else '')+'</w:trPr>'
        for value in row:
            shade='DCEDE9' if i==0 else 'F3F6F9' if i%2 else 'FFFFFF'
            result+=f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:shd w:fill="{shade}"/></w:tcPr>'+para(plain(value),'TableText')+'</w:tc>'
        result+='</w:tr>'
    return result+'</w:tbl>'

body=[]; rows=[]; code=False
for line in source.splitlines():
    if line.startswith('|'):
        cells=[c.strip() for c in line.strip('|').split('|')]
        if not all(re.fullmatch('[-: ]+',c) for c in cells):rows.append(cells)
        continue
    if rows:body.append(table(rows));rows=[]
    if line.startswith('```'):code=not code;continue
    if code:
        # Preserve code exactly, including indentation; allow Word to wrap long lines.
        body.append(para(line,'Code'));continue
    if not line.strip():continue
    if line.startswith('### '):body.append(para(line[4:],'Heading2'))
    elif line.startswith('## '):body.append(para(line[3:],'Heading1'))
    elif line.startswith('# '):body.append(para(line[2:],'Title'))
    else:body.append(para(plain(line)))
if rows:body.append(table(rows))

styles=f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="맑은 고딕"/><w:sz w:val="21"/><w:color w:val="172B4D"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="110" w:line="280" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>'
for name,size,color in [('Normal',21,'172B4D'),('Title',38,'172B4D'),('Heading1',28,'176B63'),('Heading2',23,'176B63'),('Code',17,'22354A'),('TableText',19,'172B4D')]:
    props=''
    if name in ('Heading1','Heading2','Title'):props+='<w:keepNext/>'
    if name=='Heading1':props+='<w:pageBreakBefore/><w:outlineLvl w:val="0"/>'
    if name=='Heading2':props+='<w:outlineLvl w:val="1"/>'
    if name=='Code':props+='<w:shd w:fill="EEF2F6"/><w:spacing w:after="0" w:line="220" w:lineRule="auto"/>'
    styles+=f'<w:style w:type="paragraph" w:styleId="{name}"><w:name w:val="{name}"/><w:pPr>{props}</w:pPr><w:rPr><w:sz w:val="{size}"/><w:color w:val="{color}"/>'+('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="맑은 고딕"/>' if name=='Code' else '')+('<w:b/>' if name in ('Title','Heading1','Heading2') else '')+'</w:rPr></w:style>'
styles+='</w:styles>'
document=f'<w:document xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'+''.join(body)+'<w:sectPr><w:footerReference w:type="default" r:id="rId2"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1100" w:right="1300" w:bottom="1100" w:left="1300" w:footer="450"/></w:sectPr></w:body></w:document>'
files={
'[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>',
'_rels/.rels':f'<Relationships xmlns="{R}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
'word/_rels/document.xml.rels':f'<Relationships xmlns="{R}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>',
'word/document.xml':document,'word/styles.xml':styles,
'word/footer1.xml':f'<w:ftr xmlns:w="{W}">'+para('KoreanStockBot · 개발 상세서','TableText')+'<w:p><w:fldSimple w:instr="PAGE"/></w:p></w:ftr>'}
target=ROOT/'KoreanStockBot_개발상세서.docx'
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    for name,xml in files.items():
        ET.fromstring(xml)
        archive.writestr(name,'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+xml)
with ZipFile(target) as archive:
    assert archive.testzip() is None
    text=''.join(ET.fromstring(archive.read('word/document.xml')).itertext())
    for required in ('EXE','return_series','observe','py_compile','인증','일별'):assert required in text,required
print(target)
print('Validated DOCX XML, archive integrity and source excerpts from 5 functions.')
