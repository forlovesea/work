package kr.co.batteryreport;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** Runs against the packaged JAR, templates and bundled Java 8, including the native launcher. */
public final class DesktopSelfTest {
    private static int checks;
    static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
    public static void run(File project)throws Exception{
        File qa=new File(project,"qa");qa.mkdirs();File result=new File(qa,"windows-test-results.txt");
        try{
            check(System.getProperty("os.arch").contains("64"),"64-bit runtime");
            check(System.getProperty("java.version").startsWith("1.8."),"Java 8 runtime");
            File session=Files.createTempDirectory(qa.toPath(),"windows-self-test-").toFile();DesktopModel model=new DesktopModel(session);
            DesktopModel.Site site=model.addSite("용인외사");File minute=new File(project,"references/perfmg_minute.zip"),uncertain=new File(project,"references/perfmg_uncertain.zip");
            DesktopModel.ImportResult first=model.importFiles(site,0,new File[]{minute});check(first.accepted==1,"single upload");check(model.unitCount()==1&&model.fileCount()==1,"partial unit count");
            DesktopModel.ImportResult additional=model.importFiles(site,0,new File[]{uncertain});check(additional.accepted==1,"additional upload");check(model.unitCount()==1&&model.fileCount()==2,"one pair is one unit");
            LogAnalyzer.Result analyzed=LogAnalyzer.analyze(model.analysis().get(0).units.get(0));
            check(analyzed.minCurrent==-102.3&&analyzed.maxCurrent==106,"sample current");check(analyzed.minSoc==90&&analyzed.maxSoc==100,"sample SOC");check(analyzed.minLoad==4730&&analyzed.maxLoad==5020,"sample load");check(LogAnalyzer.time(analyzed.firstRecovery).equals("2026-09-29 10:05:00"),"sample recovery");check(analyzed.corroborated,"sample corroboration");
            File outputParent=new File(qa,"windows-output");outputParent.mkdirs();File one=model.generate(outputParent);check(one.isDirectory(),"report output created");verify(one,1);
            DesktopModel.ImportResult second=model.importFiles(site,0,new File[]{minute,uncertain});check(second.accepted==2&&second.duplicates==2,"repeated names preserved with duplicate warning");check(model.unitCount()==2&&model.fileCount()==4,"two pairs are two units");check(site.units.get(0).minute!=site.units.get(1).minute,"inputs not overwritten");check(model.changed,"previous report stale flag");
            DesktopModel restored=new DesktopModel(session);restored.load();check(restored.unitCount()==2&&restored.fileCount()==4,"restart persistence");check(restored.sites.get(0).name.equals("용인외사"),"Korean persisted");check(restored.analysis().get(0).units.size()==2,"reparse stored originals");check(restored.lastOutput.equals(one),"report remembered");
            DesktopModel.Site extra=restored.addSite("서버실 & <시험>");restored.importFiles(extra,0,new File[]{minute,uncertain,minute,uncertain,minute,uncertain});check(restored.unitCount()==5,"multi-site counts");
            File multi=restored.generate(outputParent);check(!multi.equals(one),"no overwrite");verify(multi,5);check(!restored.changed,"fresh output flag");
            File bad=new File(session,"bad.zip");Files.write(bad.toPath(),"not a ZIP".getBytes(StandardCharsets.UTF_8));DesktopModel.ImportResult rejected=restored.importFiles(extra,0,new File[]{bad});check(rejected.accepted==0&&rejected.errors.size()==1,"invalid ZIP rejected");check(restored.fileCount()==10,"failed import does not change inputs");
            restored.clearUnit(extra,2);check(restored.unitCount()==4,"delete affects unit count");check(new File(one,DocxReports.CHARGE_NAME).isFile(),"delete retains generated reports");
            boolean duplicateName=false;try{restored.addSite("용인외사");}catch(IOException e){duplicateName=true;}check(duplicateName,"duplicate site rejected");
            // Empty/unknown values must never become claims of outage or recovery.
            LogAnalyzer.Unit empty=new LogAnalyzer.Unit("미제공");LogAnalyzer.Result emptyResult=LogAnalyzer.analyze(empty);check(!emptyResult.corroborated&&emptyResult.firstRecovery==null&&emptyResult.episodes.isEmpty(),"missing data stays unknown");
            String info="PASS "+checks+" Windows package checks\nJava: "+System.getProperty("java.runtime.version")+"\nArchitecture: "+System.getProperty("os.arch")+"\nOS tested: "+System.getProperty("os.name")+" "+System.getProperty("os.version")+"\nSingle-pair reports: "+one.getAbsolutePath()+"\nMulti-site reports: "+multi.getAbsolutePath()+"\n";
            Files.write(result.toPath(),info.getBytes(StandardCharsets.UTF_8));System.out.print(info);
        }catch(Throwable t){Files.write(result.toPath(),("FAILED: "+t.toString()).getBytes(StandardCharsets.UTF_8));throw t;}
    }
    private static void verify(File folder,int units)throws Exception{
        for(boolean charge:new boolean[]{true,false}){
            File f=new File(folder,charge?DocxReports.CHARGE_NAME:DocxReports.OUTAGE_NAME);check(f.length()>20000,"non-empty DOCX");Map<String,byte[]> parts=DocxReports.readZip(new FileInputStream(f));String content=DocxReports.parse(parts.get("word/document.xml")).getDocumentElement().getTextContent();
            check(content.contains("용인외사"),"site in report");check(!content.contains("-95.8")&&!content.contains("+89.6"),"sample second-unit measurements absent");
            if(units==1){check(content.contains("1식")&&!content.contains("2호"),"single-unit text");}else check(content.contains("2식")&&content.contains("3식")&&content.contains("서버실 & <시험>"),"multi-site counts and escaping");
            Map<String,byte[]> template=DocxReports.readZip(DesktopSelfTest.class.getResourceAsStream("/templates/"+(charge?"charge":"outage")+".docx"));
            for(String name:template.keySet())if(!name.equals("word/document.xml")&&!name.equals("word/_rels/document.xml.rels")&&!name.startsWith("word/media/"))check(Arrays.equals(template.get(name),parts.get(name)),"preserved template part "+name);
        }
    }
}
