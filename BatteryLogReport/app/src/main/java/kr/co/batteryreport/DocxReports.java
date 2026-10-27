package kr.co.batteryreport;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.zip.*;
import javax.xml.parsers.*;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.*;
import static kr.co.batteryreport.LogAnalyzer.*;

/** Patches the supplied Word package. Styles, numbering, theme and page geometry are retained. */
public final class DocxReports {
    static final String W="http://schemas.openxmlformats.org/wordprocessingml/2006/main",R="http://schemas.openxmlformats.org/officeDocument/2006/relationships",A="http://schemas.openxmlformats.org/drawingml/2006/main",WP="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",REL="http://schemas.openxmlformats.org/package/2006/relationships";
    public static final String CHARGE_NAME="축전지 충·방전 로그 분석.docx",OUTAGE_NAME="AC 정전시 LFP에서 AC 정전을 유추.docx";
    private final ReportImages images;
    private Document doc,rels;private Element body;private List<Element> original;private Map<String,byte[]> parts;private int imageId;
    public DocxReports(ReportImages images){this.images=images;}
    public void generate(InputStream template,boolean charge,List<Site> sites,File out)throws Exception{
        if(sites.isEmpty()||sites.stream().allMatch(s->s.units.isEmpty()))throw new IOException("보고서에 포함할 축전지 로그가 없습니다.");
        parts=readZip(template);doc=parse(parts.get("word/document.xml"));rels=parse(parts.get("word/_rels/document.xml.rels"));
        body=(Element)doc.getElementsByTagNameNS(W,"body").item(0);original=children(body);
        for(Element e:original)body.removeChild(e);
        // All original illustrations contain sample measurements and must not survive in output.
        for(Element e:new ArrayList<>(children(rels.getDocumentElement())))if(e.getAttribute("Type").endsWith("/image"))rels.getDocumentElement().removeChild(e);
        parts.keySet().removeIf(k->k.startsWith("word/media/"));imageId=100;
        boolean first=true;
        for(Site site:sites){
            if(site.units.isEmpty())continue;
            if(!first)pageBreak(); first=false;
            List<Result> results=new ArrayList<>();for(Unit unit:site.units)results.add(analyze(unit));
            if(charge)charge(site,results);else outage(site,results);
        }
        body.appendChild(doc.importNode(original.get(original.size()-1),true));
        parts.put("word/document.xml",xml(doc));parts.put("word/_rels/document.xml.rels",xml(rels));
        // Generated PNG names reuse the template's existing PNG content-type declaration.
        try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(out))){for(Map.Entry<String,byte[]> part:parts.entrySet()){zip.putNextEntry(new ZipEntry(part.getKey()));zip.write(part.getValue());zip.closeEntry();}}
    }
    private String range(List<Result> rr){LocalDateTime from=null,to=null;for(Result r:rr)if(r.first!=null){if(from==null||r.first.isBefore(from))from=r.first;if(to==null||r.last.isAfter(to))to=r.last;}return from==null?"유효 기록 없음":from.toLocalDate()+" ~ "+to.toLocalDate();}
    private String today(){return LocalDate.now(ZoneId.of("Asia/Seoul")).toString();}
    private void charge(Site site,List<Result> rr)throws Exception{
        p(0,"축전지 시스템 "+rr.size()+"식 충·방전");keep(1);
        p(2,"SKT 제출용 | 설치장소: "+site.name+" | 분석 대상: "+range(rr)+" | 작성일: "+today());
        keep(3);for(Result r:rr)p(4,site.name+" "+r.unit.label+": "+summary(r));
        keep(5);
        String[] labels={"항목","최대 방전 전류","최대 충전 전류","최저 SOC","최고 SOC","SOC 100% 회복 시각","방전 중 최소 DC 부하","방전 중 최대 DC 부하"};
        List<String[]> values=new ArrayList<>();
        for(Result r:rr)values.add(new String[]{r.unit.label+" 시스템",r.minCurrent<0?number(r.minCurrent,1)+" A":"확인 안 됨",r.maxCurrent>0?"+"+number(r.maxCurrent,1)+" A":"확인 안 됨",number(r.minSoc,0)+"%",number(r.maxSoc,0)+"%",time(r.firstRecovery),number(r.minLoad,0)+" W",number(r.maxLoad,0)+" W"});
        tables(6,labels,values);
        keep(7);p(8,"자료: 설치장소별 등록 원본 ZIP > perfmg_minute.csv (호기별 원본 파일명은 운전 이력에 표시)");
        for(Result r:rr){p(17,site.name+" "+r.unit.label+" / 방전 실측 시점의 DC 부하");picture(9,images.evidence(r,"load"),5486400);}
        keep(10);
        p(11,"분석 범위는 "+range(rr)+"이며, 호기별 유효 원본 기록 전체에서 계측 최솟값·최댓값을 산출하였음. 날짜가 다른 기록을 같은 시각으로 합치지 않았음.");
        p(12,"그래프는 실측 전류·SOC·DC 부하를 표시함. 선은 인접 실측점을 연결하며 10분 초과 기록 공백은 연결하지 않음. 상태 변경 기록은 별도 시각으로 취급함.");
        int i=1;for(Result r:rr){
            pageBreak();p(13,"4-"+(i++)+". "+site.name+" "+r.unit.label+" 시스템 운전 이력");
            p(14,"분석 범위: "+r.range()+". 방전 전류 최저 "+(r.minCurrent<0?number(r.minCurrent,1)+" A":"확인 안 됨")+", 충전 전류 최고 "+(r.maxCurrent>0?"+"+number(r.maxCurrent,1)+" A":"확인 안 됨")+"로 기록되었음.");
            p(15,"SOC는 최저 "+number(r.minSoc,0)+"% ("+time(r.minSocAt)+"), 최고 "+number(r.maxSoc,0)+"%임. 첫 방전 구간 이후 SOC 100% 회복: "+time(r.firstRecovery)+". 방전 시점에 직접 기록된 DC 부하는 "+number(r.minLoad,0)+" ~ "+number(r.maxLoad,0)+" W임.");
            picture(16,images.chart(r),5486400);keep(17);p(18,r.unit.minuteName+" > perfmg_minute.csv");keep(19);
            p(14,summary(r));
            for(Episode e:r.episodes)p(15,"방전 실측 구간: "+time(e.start)+" ~ "+time(e.last)+" / 이후 충전: "+time(e.charge)+" / SOC 100% 회복: "+time(e.recovered));
            for(String warning:r.warnings)p(15,warning);
        }
        keep(31);keep(32);
    }
    private void outage(Site site,List<Result> rr)throws Exception{
        keep(0);keep(1);keep(2);p(3,"*분석 대상: "+range(rr)+" / "+site.name+" 축전지 시스템 "+rr.size()+"식 | 작성: "+today());
        keep(4);
        for(Result r:rr)p(5,r.unit.label+": "+(r.corroborated?"동일 방전 구간에서 Power Supply Source = Battery, Battery Status = Discharge, 음(-)의 전류 및 SOC 감소가 확인됨. 축전지 방전 및 배터리 전원 공급 상태를 교차 확인하였음.":"전류·SOC·전원 공급원·방전 상태의 네 가지 조건이 동일 구간에서 모두 확인되지는 않았음. 제공 기록 범위에서 교차 검증이 제한됨.")+" "+summary(r));
        p(8,"다만 AC 입력 정전 발생 및 정확한 복전 시각은 직접 확인된 사실이 아니라 추정임.");keep(9);
        p(10,"방전 이후 Power Supply Source가 Battery에서 Unknown으로 변경된 경우에도 Unknown만으로 AC 복전을 확정할 수 없음. 양(+)의 충전 전류 및 SOC 회복을 함께 확인해야 함.");
        keep(11);String[] labels={"항목","방전 상태 시작","Power Supply Source: Battery","Power Supply Source: Unknown"};List<String[]> values=new ArrayList<>();
        for(Result r:rr)values.add(new String[]{r.unit.label+" 시스템",time(r.dischargeStatus),time(r.batterySource),time(r.unknownAfter)});tables(12,labels,values);
        p(13,"2-2. 로그 해석");p(14,"정상 운전 추정 (해석 기준)");keep(15);keep(16);keep(17);p(18,"Power Supply Source = Battery / Battery Status = Discharge");keep(19);keep(20);keep(21);
        for(Result r:rr){keep(22);p(23,site.name+" "+r.unit.label+": "+r.unit.uncertainName+" > perfmg_uncertain.csv");picture(24,images.evidence(r,"states"),6400800);}
        keep(26);p(27,"perfmg_minute.csv의 Lithium Battery Group / Current, SOC를 상태 전환 구간과 대조함.");
        for(Result r:rr){keep(28);p(29,site.name+" "+r.unit.label+": "+r.unit.minuteName+" > perfmg_minute.csv");picture(30,images.evidence(r,"current"),6400800);}
        keep(33);
        for(Result r:rr){
            p(34,r.unit.label+": Battery 공급 전환 "+time(r.batterySource)+", 방전 상태 전환 "+time(r.dischargeStatus)+", 이후 Unknown 전환 "+time(r.unknownAfter)+".");
            p(35,"첫 방전 실측 시각 "+time(r.firstNegative)+", 이후 양(+) 전류 "+time(r.firstPositiveAfter)+", SOC 100% 회복 "+time(r.firstRecovery)+". "+(r.corroborated?"방전 및 배터리 공급의 교차 근거가 확인됨.":"상태와 계측 기록의 교차 확인 근거가 충분하지 않음."));
            for(String warning:r.warnings)p(36,r.unit.label+": "+warning);
        }
        p(37,"전원 공급원 변경과 전류·SOC 변화를 종합하여 AC 정전 및 복전 가능성을 간접적으로 검토할 수 있음. 방전 원인은 AC 정전 외에도 존재하므로 AC 입력 또는 정류기 측 기록과 대조가 필요함.");keep(38);keep(40);keep(41);
        for(Result r:rr)p(42,r.unit.label+": Battery 전환 직전 Unknown 기록 "+time(r.unknownBefore)+", 방전 이후 Unknown 기록 "+time(r.unknownAfter)+".");
        p(43,"Unknown은 상태값의 문자 그대로 ‘미확인’이므로 AC 정상 공급 또는 복전을 의미하는 코드로 확정할 수 없음.");
        keep(45);p(46,"이번 분석 입력은 perfmg_minute / perfmg_uncertain 성능 로그임. historyalarm.csv와 alarmg_active.csv는 분석 입력에 포함되지 않아 알람 발생 유무를 판정하지 않았음.");p(48,"별도 AC 입력 이벤트·정류기 알람을 확인하려면 해당 항목을 수집한 장비 로그가 필요함.");
        keep(49);p(50,"“제공된 LFP 성능 로그의 Power Supply Source, Battery Status와 전류·SOC를 상호 대조하여 축전지 방전 운전 여부를 검토하였음. 호기별 확인 시각과 미확인 항목은 위 표와 같음. Unknown 값은 AC 정상 또는 복전의 직접 증거가 아니므로 AC 정전의 원인·정확한 발생 및 복구 시각은 AC 입력·정류기 측 로그와 교차 확인이 필요함.”");
        p(55,"자료 구분: 원본 파일명이 같아도 설치장소·축전지 호기별로 구분하였음. 수치·시각은 업로드한 CSV에서 추출하였으며, 상태 비교 표에는 첫 방전 관련 전환을 표시하였음.");
        for(int i=56;i<=62;i++)keep(i);
    }
    private void tables(int template,String[] labels,List<String[]> values){
        // Keep template's three-column geometry; repeat tables for >2 units instead of shrinking type.
        for(int start=0;start<values.size();start+=2){
            Element tbl=(Element)doc.importNode(original.get(template),true);List<Element> rows=direct(tbl,"tr");
            while(rows.size()>labels.length){tbl.removeChild(rows.remove(rows.size()-1));}
            int cols=Math.min(2,values.size()-start);
            for(int r=0;r<rows.size();r++){
                List<Element> cells=direct(rows.get(r),"tc");text(cells.get(0),labels[r]);
                for(int c=1;c<=cols;c++)text(cells.get(c),values.get(start+c-1)[r]);
                for(int c=cells.size()-1;c>cols;c--)rows.get(r).removeChild(cells.get(c));
                for(Element cell:direct(rows.get(r),"tc")){NodeList widths=cell.getElementsByTagNameNS(W,"tcW");if(widths.getLength()>0)((Element)widths.item(0)).setAttributeNS(W,"w:w",Integer.toString((template==6?8640:10080)/(cols+1)));}
                if(r==0){Element pr=firstOrCreate(rows.get(r),"trPr");Element repeat=doc.createElementNS(W,"w:tblHeader");pr.appendChild(repeat);}
            }
            List<Element> grids=direct(tbl,"tblGrid");if(!grids.isEmpty()){Element grid=grids.get(0);while(grid.hasChildNodes())grid.removeChild(grid.getFirstChild());for(int c=0;c<=cols;c++){Element g=doc.createElementNS(W,"w:gridCol");g.setAttributeNS(W,"w:w",Integer.toString((template==6?8640:10080)/(cols+1)));grid.appendChild(g);}}
            body.appendChild(tbl);
        }
    }
    private void keep(int index){body.appendChild(doc.importNode(original.get(index),true));}
    private void p(int index,String s){Element e=(Element)doc.importNode(original.get(index),true);text(e,s);body.appendChild(e);}
    private void text(Element e,String s){
        // Preserve paragraph and first-run formatting, including Korean font and exact spacing.
        NodeList paragraphs=e.getElementsByTagNameNS(W,"p");Element p=e.getLocalName().equals("p")?e:paragraphs.getLength()>0?(Element)paragraphs.item(0):null;
        if(p==null)return;
        Element firstRun=null;for(Element child:children(p))if(child.getLocalName().equals("r")&&firstRun==null)firstRun=child;
        Element run=doc.createElementNS(W,"w:r");if(firstRun!=null){List<Element> props=direct(firstRun,"rPr");if(!props.isEmpty())run.appendChild(props.get(0).cloneNode(true));}
        for(Element child:new ArrayList<>(children(p)))if(!child.getLocalName().equals("pPr"))p.removeChild(child);
        Element t=doc.createElementNS(W,"w:t");t.setAttributeNS("http://www.w3.org/XML/1998/namespace","xml:space","preserve");t.setTextContent(s);run.appendChild(t);p.appendChild(run);
        if(e!=p){for(int i=paragraphs.getLength()-1;i>=1;i--){Node extra=paragraphs.item(i);extra.getParentNode().removeChild(extra);}}
    }
    private void pageBreak(){Element p=doc.createElementNS(W,"w:p"),r=doc.createElementNS(W,"w:r"),br=doc.createElementNS(W,"w:br");br.setAttributeNS(W,"w:type","page");r.appendChild(br);p.appendChild(r);body.appendChild(p);}
    private void picture(int template,byte[] png,long width)throws Exception{
        int id=++imageId;String rid="rIdGenerated"+id,name="generated"+id+".png";
        parts.put("word/media/"+name,png);Element rel=rels.createElementNS(REL,"Relationship");rel.setAttribute("Id",rid);rel.setAttribute("Type",R+"/image");rel.setAttribute("Target","media/"+name);rels.getDocumentElement().appendChild(rel);
        Element p=(Element)doc.importNode(original.get(template),true);
        NodeList blips=p.getElementsByTagNameNS(A,"blip");for(int i=0;i<blips.getLength();i++)((Element)blips.item(i)).setAttributeNS(R,"r:embed",rid);
        int pw=((png[16]&255)<<24)|((png[17]&255)<<16)|((png[18]&255)<<8)|(png[19]&255),ph=((png[20]&255)<<24)|((png[21]&255)<<16)|((png[22]&255)<<8)|(png[23]&255);
        long h=width*ph/pw;
        for(String namespace:new String[]{WP,A})for(String tag:new String[]{"extent","ext"}){NodeList ext=p.getElementsByTagNameNS(namespace,tag);for(int i=0;i<ext.getLength();i++){Element e=(Element)ext.item(i);if(e.hasAttribute("cx")){e.setAttribute("cx",Long.toString(width));e.setAttribute("cy",Long.toString(h));}}}
        NodeList props=p.getElementsByTagNameNS(WP,"docPr");for(int i=0;i<props.getLength();i++){Element e=(Element)props.item(i);e.setAttribute("id",Integer.toString(id));e.setAttribute("name","로그 분석 "+id);e.setAttribute("descr","업로드한 원본 로그에서 생성한 계측 자료");}
        body.appendChild(p);
    }
    private Element firstOrCreate(Element parent,String tag){List<Element> c=direct(parent,tag);if(!c.isEmpty())return c.get(0);Element e=doc.createElementNS(W,"w:"+tag);parent.insertBefore(e,parent.getFirstChild());return e;}
    static List<Element> children(Element e){List<Element> list=new ArrayList<>();for(Node n=e.getFirstChild();n!=null;n=n.getNextSibling())if(n instanceof Element)list.add((Element)n);return list;}
    static List<Element> direct(Element e,String tag){List<Element> out=new ArrayList<>();for(Element c:children(e))if(c.getLocalName().equals(tag))out.add(c);return out;}
    static Document parse(byte[] bytes)throws Exception{DocumentBuilderFactory f=DocumentBuilderFactory.newInstance();f.setNamespaceAware(true);try{f.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);}catch(Exception ignored){}return f.newDocumentBuilder().parse(new ByteArrayInputStream(bytes));}
    static byte[] xml(Document d)throws Exception{ByteArrayOutputStream b=new ByteArrayOutputStream();Transformer t=TransformerFactory.newInstance().newTransformer();t.setOutputProperty(OutputKeys.ENCODING,"UTF-8");t.setOutputProperty(OutputKeys.STANDALONE,"yes");t.transform(new DOMSource(d),new StreamResult(b));return b.toByteArray();}
    static Map<String,byte[]> readZip(InputStream in)throws IOException{Map<String,byte[]> map=new LinkedHashMap<>();try(ZipInputStream zip=new ZipInputStream(in)){ZipEntry e;while((e=zip.getNextEntry())!=null){ByteArrayOutputStream b=new ByteArrayOutputStream();byte[] buf=new byte[16384];int n;while((n=zip.read(buf))!=-1)b.write(buf,0,n);map.put(e.getName(),b.toByteArray());}}return map;}
}
