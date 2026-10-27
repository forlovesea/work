package kr.co.batteryreport;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.text.SimpleDateFormat;
import java.util.*;

/** Java 8 desktop storage and workflow. Shared analyzer/report code is compiled without modifications. */
public final class DesktopModel {
    public static final class Input {
        String name,path,hash,kind;long size;
        transient LogAnalyzer.Data data;
    }
    public static final class Unit {Input minute,uncertain;boolean populated(){return minute!=null||uncertain!=null;}}
    public static final class Site {
        String name;final List<Unit> units=new ArrayList<>();
        Site(String n){name=n;units.add(new Unit());}
        public String toString(){return name;}
    }
    public static final class ImportResult {int accepted,duplicates;final List<String> errors=new ArrayList<>();}
    final File home;final List<Site> sites=new ArrayList<>();File lastOutput;boolean changed;
    public DesktopModel(File home)throws IOException{this.home=home;if(!home.isDirectory()&&!home.mkdirs())throw new IOException("프로그램 데이터 폴더를 만들 수 없습니다: "+home);}
    public Site addSite(String name)throws IOException{
        name=name.trim();if(name.isEmpty()||name.length()>60)throw new IOException("설치장소를 1~60자로 입력해 주세요.");
        for(Site s:sites)if(s.name.equals(name))throw new IOException("이미 등록된 설치장소입니다.");
        Site site=new Site(name);sites.add(site);changed=true;save();return site;
    }
    public void rename(Site site,String name)throws IOException{
        name=name.trim();if(name.isEmpty()||name.length()>60)throw new IOException("설치장소를 1~60자로 입력해 주세요.");
        for(Site s:sites)if(s!=site&&s.name.equals(name))throw new IOException("이미 등록된 설치장소입니다.");site.name=name;changed=true;save();
    }
    public int unitCount(){int n=0;for(Site s:sites)for(Unit u:s.units)if(u.populated())n++;return n;}
    public int fileCount(){int n=0;for(Site s:sites)for(Unit u:s.units){if(u.minute!=null)n++;if(u.uncertain!=null)n++;}return n;}
    public ImportResult importFiles(Site site,int start,File[] files)throws IOException{
        if(!sites.contains(site)||start<0||start>=site.units.size())throw new IOException("등록할 설치장소·호기를 선택해 주세요.");
        if(files.length>40)throw new IOException("한 번에 최대 40개 파일을 선택해 주세요.");
        ImportResult result=new ImportResult();File dir=new File(home,"logs");if(!dir.isDirectory()&&!dir.mkdirs())throw new IOException("로그 보관 폴더를 만들 수 없습니다.");
        for(File source:files){File destination=null;try{
            if(!source.isFile())throw new IOException("파일을 읽을 수 없습니다.");
            if(source.length()>64L*1024*1024)throw new IOException("ZIP당 최대 64 MB까지 지원합니다.");
            Input in=new Input();in.name=source.getName();in.path=UUID.randomUUID()+".zip";destination=new File(dir,in.path);
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            try(InputStream src=new FileInputStream(source);OutputStream out=new FileOutputStream(destination)){
                byte[] buffer=new byte[65536];int n;while((n=src.read(buffer))!=-1){in.size+=n;if(in.size>64L*1024*1024)throw new IOException("파일 크기 제한 초과");digest.update(buffer,0,n);out.write(buffer,0,n);}
            }
            in.hash=hex(digest.digest());in.data=LogAnalyzer.read(destination);in.kind=in.data.kind;
            boolean duplicate=false;for(Site oldSite:sites)for(Unit u:oldSite.units)for(Input old:new Input[]{u.minute,u.uncertain})if(old!=null&&old.hash.equals(in.hash))duplicate=true;
            if(duplicate)result.duplicates++;
            int index=start;while(index<site.units.size()){
                Unit u=site.units.get(index);if(in.kind.equals("minute")?u.minute==null:u.uncertain==null)break;index++;
            }
            if(index==site.units.size())site.units.add(new Unit());Unit unit=site.units.get(index);
            if(in.kind.equals("minute"))unit.minute=in;else unit.uncertain=in;
            result.accepted++;changed=true;
        }catch(Exception ex){if(destination!=null)destination.delete();result.errors.add(source.getName()+": "+ex.getMessage());}}
        save();return result;
    }
    private LogAnalyzer.Data data(Input in)throws IOException{
        if(in.data==null){File f=stored(in.path);if(!f.isFile())throw new IOException("보관된 로그를 찾을 수 없습니다: "+in.name);in.data=LogAnalyzer.read(f);}return in.data;
    }
    public List<LogAnalyzer.Site> analysis()throws IOException{
        List<LogAnalyzer.Site> out=new ArrayList<>();for(Site s:sites){LogAnalyzer.Site target=new LogAnalyzer.Site(s.name);int i=0;for(Unit u:s.units){i++;if(!u.populated())continue;LogAnalyzer.Unit unit=new LogAnalyzer.Unit(i+"호");if(u.minute!=null){unit.minute=data(u.minute);unit.minuteName=u.minute.name;}if(u.uncertain!=null){unit.uncertain=data(u.uncertain);unit.uncertainName=u.uncertain.name;}target.units.add(unit);}if(!target.units.isEmpty())out.add(target);}return out;
    }
    public File generate(File parent)throws Exception{
        if(!parent.isDirectory())throw new IOException("보고서를 저장할 폴더를 선택해 주세요.");
        List<LogAnalyzer.Site> input=analysis();if(input.isEmpty())throw new IOException("먼저 로그파일을 업로드해 주세요.");
        File stage=Files.createTempDirectory(parent.toPath(),".battery-report-").toFile();
        try{
            DocxReports reports=new DocxReports(new ReportImages(new DesktopPainter()));
            reports.generate(template("charge"),true,input,new File(stage,DocxReports.CHARGE_NAME));
            reports.generate(template("outage"),false,input,new File(stage,DocxReports.OUTAGE_NAME));
            String stamp=new SimpleDateFormat("yyyyMMdd_HHmmss",Locale.ROOT).format(new Date());
            File output=new File(parent,"축전지_보고서_"+stamp+"_"+UUID.randomUUID().toString().substring(0,6));
            Files.move(stage.toPath(),output.toPath());lastOutput=output;changed=false;save();return output;
        }finally{if(stage.isDirectory()){File[] files=stage.listFiles();if(files!=null)for(File f:files)f.delete();stage.delete();}}
    }
    private InputStream template(String name)throws IOException{InputStream in=DesktopModel.class.getResourceAsStream("/templates/"+name+".docx");if(in==null)throw new IOException("내장 보고서 서식을 찾을 수 없습니다. 프로그램 압축을 다시 풀어 주세요.");return in;}
    public void clearUnit(Site s,int index)throws IOException{Unit u=s.units.get(index);u.minute=null;u.uncertain=null;changed=true;save();}
    public void save()throws IOException{
        Properties p=new Properties();p.setProperty("version","1");p.setProperty("sites",Integer.toString(sites.size()));p.setProperty("changed",Boolean.toString(changed));if(lastOutput!=null)p.setProperty("lastOutput",lastOutput.getAbsolutePath());
        for(int i=0;i<sites.size();i++){Site s=sites.get(i);String key="site."+i+".";p.setProperty(key+"name",s.name);p.setProperty(key+"units",Integer.toString(s.units.size()));for(int j=0;j<s.units.size();j++){Unit u=s.units.get(j);store(p,key+j+".minute.",u.minute);store(p,key+j+".uncertain.",u.uncertain);}}
        File state=new File(home,"session.properties"),temp=new File(home,"session.properties.tmp");
        try(OutputStream out=new FileOutputStream(temp)){p.store(out,"BatteryLogReport session; UTF-16 escapes preserve Korean");}
        if(state.isFile())Files.copy(state.toPath(),new File(home,"session.properties.bak").toPath(),StandardCopyOption.REPLACE_EXISTING);
        try{Files.move(temp.toPath(),state.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}catch(AtomicMoveNotSupportedException e){Files.move(temp.toPath(),state.toPath(),StandardCopyOption.REPLACE_EXISTING);}
    }
    private static void store(Properties p,String key,Input in){if(in==null)return;p.setProperty(key+"path",in.path);p.setProperty(key+"name",in.name);p.setProperty(key+"hash",in.hash);p.setProperty(key+"size",Long.toString(in.size));p.setProperty(key+"kind",in.kind);}
    public void load()throws IOException{
        File state=new File(home,"session.properties");if(!state.exists())return;
        Properties p=new Properties();try(InputStream in=new FileInputStream(state)){p.load(in);}
        List<Site> loaded=new ArrayList<>();try{
            int n=bounded(p,"sites",200);for(int i=0;i<n;i++){String key="site."+i+".";Site s=new Site(p.getProperty(key+"name","설치장소"));s.units.clear();int count=bounded(p,key+"units",200);for(int j=0;j<count;j++){Unit u=new Unit();u.minute=restore(p,key+j+".minute.");u.uncertain=restore(p,key+j+".uncertain.");s.units.add(u);}if(s.units.isEmpty())s.units.add(new Unit());loaded.add(s);}
            String last=p.getProperty("lastOutput","");File f=new File(last);if(!last.isEmpty()&&new File(f,DocxReports.CHARGE_NAME).isFile()&&new File(f,DocxReports.OUTAGE_NAME).isFile())lastOutput=f;
            changed=Boolean.parseBoolean(p.getProperty("changed","false"));sites.clear();sites.addAll(loaded);
        }catch(RuntimeException ex){throw new IOException("이전 등록 정보를 읽지 못했습니다. 데이터 폴더의 session.properties.bak를 확인해 주세요.",ex);}
    }
    private static int bounded(Properties p,String key,int maximum){int n=Integer.parseInt(p.getProperty(key,"0"));if(n<0||n>maximum)throw new IllegalArgumentException("등록 수 제한 초과");return n;}
    private Input restore(Properties p,String key)throws IOException{String path=p.getProperty(key+"path");if(path==null)return null;stored(path);Input in=new Input();in.path=path;in.name=p.getProperty(key+"name","log.zip");in.kind=p.getProperty(key+"kind","");in.hash=p.getProperty(key+"hash","");in.size=Long.parseLong(p.getProperty(key+"size","0"));return in;}
    private File stored(String path)throws IOException{if(!path.matches("[a-f0-9-]+\\.zip"))throw new IOException("올바르지 않은 로그 보관 경로");return new File(new File(home,"logs"),path);}
    static String hex(byte[] b){StringBuilder out=new StringBuilder();for(byte v:b)out.append(String.format(Locale.ROOT,"%02x",v));return out.toString();}
    static String size(long n){return n<1024?n+" B":n<1048576?String.format(Locale.KOREA,"%.1f KB",n/1024.0):String.format(Locale.KOREA,"%.2f MB",n/1048576.0);}
}
