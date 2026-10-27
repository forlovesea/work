package kr.co.batteryreport;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.zip.*;
import org.w3c.dom.*;

public class Regression {
    static int checks;
    static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
    static void equal(double actual,double expected,String name){check(Math.abs(actual-expected)<.001,name+": "+actual+" != "+expected);}
    static LogAnalyzer.Data synthetic(String kind,String data)throws Exception{
        LogAnalyzer.Data d=new LogAnalyzer.Data();d.kind=kind;LogAnalyzer.parse(new StringReader("Equipment,Equipment ID,Performance Data,Statistical Period,Statistical Start Time,Value,Unit,\n"+data),d);return d;
    }
    static String row(String item,String time,String value,String unit){return "Lithium Battery Group,0x60,"+item+",5 Min,2026-01-01 "+time+","+value+","+unit+"\n";}
    public static void main(String[] args)throws Exception{
        File root=new File(args[0]);File qa=new File(root,"qa/generated");qa.mkdirs();
        LogAnalyzer.Unit u=new LogAnalyzer.Unit("1호");u.minute=LogAnalyzer.read(new File(root,"references/perfmg_minute.zip"));u.uncertain=LogAnalyzer.read(new File(root,"references/perfmg_uncertain.zip"));u.minuteName="perfmg_minute.zip";u.uncertainName="perfmg_uncertain.zip";
        LogAnalyzer.Result r=LogAnalyzer.analyze(u);
        equal(r.minCurrent,-102.3,"최대 방전");equal(r.maxCurrent,106,"최대 충전");equal(r.minSoc,90,"SOC 최저");equal(r.maxSoc,100,"SOC 최고");equal(r.minLoad,4730,"최저 부하");equal(r.maxLoad,5020,"최고 부하");
        check(LogAnalyzer.time(r.firstRecovery).equals("2026-09-29 10:05:00"),"SOC 회복 "+r.firstRecovery);
        check(LogAnalyzer.time(r.dischargeStatus).equals("2026-09-29 08:15:53"),"방전 상태 시각");check(LogAnalyzer.time(r.batterySource).equals("2026-09-29 08:15:56"),"Battery 시각");check(LogAnalyzer.time(r.unknownAfter).equals("2026-09-29 08:57:34"),"Unknown 시각");check(r.corroborated,"교차 확인");check(r.episodes.size()==1,"방전 구간 수");
        ReportImages.CurrentEvidence evidence=ReportImages.currentEvidence(r);
        check(evidence.charging.size()==4,"four charging evidence rows");
        check(evidence.charging.get(0).equals(r.firstPositiveAfter),"first positive transition retained");
        check(evidence.charging.get(3).equals(evidence.chargeEnd),"late sustained charging retained");
        check(evidence.positiveCount>4,"samples span a longer charging run");
        for(LocalDateTime t:evidence.charging)check(u.minute.current.get(t)>0,"charging row must be positive");
        check(ReportImages.currentExplanation(r).contains("충전 유지 동작을 확인")&&ReportImages.currentExplanation(r).contains("SOC도"),"evidence-based charging narrative");
        Files.write(new File(root,"qa/charging-evidence.png").toPath(),new ReportImages(new DesktopPainter()).evidence(r,"current"));
        System.out.println("Charging evidence: "+evidence.charging+"; "+evidence.positiveCount+" positive samples");
        check(LogAnalyzer.csv("\"a,b\", \"\t3.4\",\"a\"\"b\"").equals(Arrays.asList("a,b","3.4","a\"b")),"CSV quotes and tabs");
        LogAnalyzer.Unit noDischarge=new LogAnalyzer.Unit("무방전");noDischarge.minute=synthetic("minute",row("Current","08:00:00","0","A")+row("SOC","08:00:00","100","%"));
        LogAnalyzer.Result nr=LogAnalyzer.analyze(noDischarge);check(nr.episodes.isEmpty(),"0A no discharge");check(nr.firstRecovery==null,"initial 100 is not recovery");check(!nr.corroborated,"no unsupported outage claim");
        check(ReportImages.currentEvidence(nr).charging.isEmpty(),"no discharge creates no charging transition");
        LogAnalyzer.Unit partial=new LogAnalyzer.Unit("미회복");partial.minute=synthetic("minute",row("Current","08:00:00","-10","A")+row("SOC","08:00:00","90","%")+row("Current","08:05:00","5","A")+row("SOC","08:05:00","95","%"));
        check(LogAnalyzer.analyze(partial).firstRecovery==null,"no false recovery");
        check(ReportImages.currentEvidence(LogAnalyzer.analyze(partial)).charging.size()==1,"single positive sample is not duplicated");
        check(ReportImages.currentExplanation(LogAnalyzer.analyze(partial)).contains("추가 확인"),"single positive sample does not prove sustained charge");
        LogAnalyzer.Unit twice=new LogAnalyzer.Unit("2회");twice.minute=synthetic("minute",row("Current","08:00:00","-10","A")+row("SOC","08:00:00","90","%")+row("Current","08:05:00","5","A")+row("SOC","08:05:00","100","%")+row("Current","08:10:00","-8","A")+row("SOC","08:10:00","95","%")+row("Current","08:15:00","4","A")+row("SOC","08:15:00","98","%"));
        LogAnalyzer.Result tr=LogAnalyzer.analyze(twice);check(tr.episodes.size()==2,"two cycles");check(tr.episodes.get(0).recovered!=null&&tr.episodes.get(1).recovered==null,"recovery cycle association");
        check(ReportImages.currentEvidence(tr).charging.size()==1,"charging evidence cannot cross a new discharge");
        LogAnalyzer.Unit gap=new LogAnalyzer.Unit("공백");gap.minute=synthetic("minute",row("Current","08:00:00","-10","A")+row("Current","09:00:00","-8","A"));check(LogAnalyzer.analyze(gap).episodes.size()==2,"gap split");
        check(ReportImages.currentEvidence(LogAnalyzer.analyze(gap)).charging.isEmpty(),"discharge-only omits all charging rows");
        check(ReportImages.currentExplanation(LogAnalyzer.analyze(gap)).contains("확인되지 않아"),"discharge-only narrative does not invent charging");
        LogAnalyzer.Unit chargeGap=new LogAnalyzer.Unit("충전공백");chargeGap.minute=synthetic("minute",row("Current","08:00:00","-10","A")+row("Current","08:05:00","5","A")+row("Current","08:10:00","6","A")+row("Current","09:00:00","4","A"));
        check(ReportImages.currentEvidence(LogAnalyzer.analyze(chargeGap)).charging.size()==2,"sustained charging cannot bridge a log gap");
        LogAnalyzer.Unit zeroStop=new LogAnalyzer.Unit("충전중단");zeroStop.minute=synthetic("minute",row("Current","08:00:00","-10","A")+row("Current","08:05:00","5","A")+row("Current","08:10:00","6","A")+row("Current","08:15:00","7","A")+row("Current","08:20:00","0","A")+row("Current","08:25:00","4","A"));
        check(ReportImages.currentEvidence(LogAnalyzer.analyze(zeroStop)).charging.size()==3,"only three positive samples are shown before zero current");
        StringBuilder longRows=new StringBuilder();for(int i=0;i<18;i++)longRows.append(row("Current",String.format(Locale.ROOT,"%02d:%02d:00",i/12,(i%12)*5),i<13?"-10":"5","A"));
        LogAnalyzer.Unit longDischarge=new LogAnalyzer.Unit("긴방전");longDischarge.minute=synthetic("minute",longRows.toString());LogAnalyzer.Result lr=LogAnalyzer.analyze(longDischarge);
        check(ReportImages.currentEvidence(lr).discharge.size()==12&&ReportImages.currentEvidence(lr).charging.size()==4,"long discharge reserves four extra charging rows");
        byte[] longImage=new ReportImages(new DesktopPainter()).evidence(lr,"current");
        check(java.nio.ByteBuffer.wrap(longImage,20,4).getInt()==110+16*43+45,"rendered evidence includes all sixteen rows, without twelve-row truncation");
        LogAnalyzer.Data invalid=synthetic("minute",row("Current","08:00:00","No Data","A")+row("SOC","08:00:00","101","%")+row("Current","08:05:00","10","mA"));check(invalid.missing==1&&invalid.invalid==2,"missing + invalid units/range");
        boolean conflict=false;try{synthetic("minute",row("Current","08:00:00","1","A")+row("Current","08:00:00","2","A"));}catch(IOException e){conflict=true;}check(conflict,"conflicting rows rejected");
        LogAnalyzer.Site s=new LogAnalyzer.Site("용인외사");s.units.add(u);
        DocxReports writer=new DocxReports(new ReportImages(new DesktopPainter()));
        for(boolean charge:new boolean[]{true,false}){File out=new File(qa,charge?DocxReports.CHARGE_NAME:DocxReports.OUTAGE_NAME);writer.generate(new FileInputStream(new File(root,"app/src/main/assets/"+(charge?"charge":"outage")+".docx")),charge,Arrays.asList(s),out);verify(out,charge,1);}
        LogAnalyzer.Site second=new LogAnalyzer.Site("추가 설치장소 & <시험>");second.units.add(noDischarge);second.units.add(partial);second.units.add(twice);
        for(boolean charge:new boolean[]{true,false}){File out=new File(qa,charge?"multi-charge.docx":"multi-outage.docx");writer.generate(new FileInputStream(new File(root,"app/src/main/assets/"+(charge?"charge":"outage")+".docx")),charge,Arrays.asList(s,second),out);verify(out,charge,4);}
        Files.write(new File(root,"qa/test-results.txt").toPath(),("PASS "+checks+" checks\n"+"Sample: -102.3 A / +106.0 A / SOC 90~100% / 4730~5020 W / recovery 2026-09-29 10:05:00\n").getBytes(StandardCharsets.UTF_8));
        System.out.println("PASS "+checks+" checks; reports: "+qa.getAbsolutePath());
    }
    static void verify(File file,boolean charge,int units)throws Exception{
        Map<String,byte[]> zip=DocxReports.readZip(new FileInputStream(file));Document d=DocxReports.parse(zip.get("word/document.xml"));String text=d.getDocumentElement().getTextContent();
        check(text.contains("용인외사"),"site inserted");check(!text.contains("-95.8")&&!text.contains("89.6")&&!text.contains("2026-10-14")&&!text.contains("2026-10-15"),"no stale sample values");
        if(units==1){check(!text.contains("2호"),"one unit means no unit 2");check(text.contains("1식"),"one unit count");}
        Document rels=DocxReports.parse(zip.get("word/_rels/document.xml.rels"));Map<String,String> links=new HashMap<>();for(Element e:DocxReports.children(rels.getDocumentElement()))links.put(e.getAttribute("Id"),e.getAttribute("Target"));
        NodeList pics=d.getElementsByTagNameNS(DocxReports.A,"blip");for(int i=0;i<pics.getLength();i++){String id=((Element)pics.item(i)).getAttributeNS(DocxReports.R,"embed");check(zip.containsKey("word/"+links.get(id)),"image resolves");}
        check(zip.keySet().stream().noneMatch(n->n.matches("word/media/image[123]\\.png")),"old sample images removed");
        check(d.getElementsByTagNameNS(DocxReports.W,"sectPr").getLength()==1,"section geometry retained");
        File template=new File(file.getParentFile().getParentFile().getParentFile(),"app/src/main/assets/"+(charge?"charge":"outage")+".docx");
        Map<String,byte[]> original=DocxReports.readZip(new FileInputStream(template));
        for(String key:original.keySet())if(!key.equals("word/document.xml")&&!key.equals("word/_rels/document.xml.rels")&&!key.startsWith("word/media/"))check(Arrays.equals(original.get(key),zip.get(key)),"preserved part "+key);
    }
}
