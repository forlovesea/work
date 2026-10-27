from pathlib import Path
import zipfile, xml.etree.ElementTree as E, json, csv, io, hashlib
ROOT = Path(__file__).resolve().parents[1]
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
for name in ('charge','outage'):
    path=ROOT/'app/src/main/assets'/f'{name}.docx'
    with zipfile.ZipFile(path) as z:
        root=E.fromstring(z.read('word/document.xml'))
        rows=[]
        for i,e in enumerate(root.find(W+'body')):
            rows.append({'index':i,'tag':e.tag.split('}')[-1], 'text':''.join(e.itertext()) if False else ''.join(t.text or '' for t in e.iter(W+'t')), 'xml':E.tostring(e,encoding='unicode')})
        (ROOT/'qa'/f'{name}-structure.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
        print(name, 'sections', E.tostring(root.find('.//'+W+'sectPr'),encoding='unicode'))
        print(z.read('word/_rels/document.xml.rels').decode())
        print('drawings',[(r['index'],r['xml']) for r in rows if 'drawing' in r['xml']])
for name in ('minute','uncertain'):
    with zipfile.ZipFile(ROOT/'references'/f'perfmg_{name}.zip') as z:
        rows=list(csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]),encoding='utf-8-sig'),skipinitialspace=True))
    rows=[{k:(v or '').strip() for k,v in row.items() if k} for row in rows]
    selected=[r for r in rows if (r['Equipment']=='Lithium Battery Group' and r['Performance Data'] in ('Current','SOC','Battery Status')) or (r['Equipment']=='Digital Power' and r['Performance Data'] in ('Power Supply Source','Total DC Load Power'))]
    (ROOT/'qa'/f'{name}-selected.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,len(rows),len(selected))
    for eq,param in [('Lithium Battery Group','Current'),('Lithium Battery Group','SOC'),('Digital Power','Total DC Load Power'),('Digital Power','Power Supply Source'),('Lithium Battery Group','Battery Status')]:
        rr=[r for r in selected if r['Equipment']==eq and r['Performance Data']==param]
        if name=='minute':
            valid=[float(r['Value']) for r in rr if r['Value']!='No Data']
            if valid: print(param,min(valid),max(valid))
        else:
            if param in ('Power Supply Source','Battery Status'):print(param,rr)
