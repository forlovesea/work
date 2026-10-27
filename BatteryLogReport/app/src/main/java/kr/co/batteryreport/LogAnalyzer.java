package kr.co.batteryreport;

import java.io.*;
import java.nio.charset.*;
import java.time.*;
import java.time.format.*;
import java.util.*;
import java.util.zip.*;

/** Pure Java analysis shared by Android and the regression runner. No network. */
public final class LogAnalyzer {
    public static final DateTimeFormatter TIME=DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    public static final long MAX_EXPANDED=128L*1024*1024;
    public static class Data {
        public String kind;
        public final TreeMap<LocalDateTime,Double> current=new TreeMap<>(), soc=new TreeMap<>(), load=new TreeMap<>();
        public final TreeMap<LocalDateTime,String> source=new TreeMap<>(), status=new TreeMap<>();
        public int rows, missing, invalid;
        public final Set<String> equipmentIds=new HashSet<>();
    }
    public static class Unit {
        public String label;
        public Data minute, uncertain;
        public String minuteName="미제공", uncertainName="미제공";
        public Unit(String name){label=name;}
        public TreeMap<LocalDateTime,Double> currents(){return minute==null?new TreeMap<>():minute.current;}
        public TreeMap<LocalDateTime,Double> socs(){return minute==null?new TreeMap<>():minute.soc;}
        public TreeMap<LocalDateTime,Double> loads(){return minute==null?new TreeMap<>():minute.load;}
        public TreeMap<LocalDateTime,String> sources(){return uncertain==null?new TreeMap<>():uncertain.source;}
        public TreeMap<LocalDateTime,String> statuses(){return uncertain==null?new TreeMap<>():uncertain.status;}
    }
    public static class Site { public String name; public final List<Unit> units=new ArrayList<>(); public Site(String n){name=n;} }
    public static class Episode {
        public LocalDateTime start,last,end,charge,recovered;
        public double minCurrent=0,maxCharge=0,minSoc=Double.NaN,maxSoc=Double.NaN;
        public boolean socDropped;
    }
    public static class Result {
        public Unit unit;
        public LocalDateTime first,last,minSocAt,firstNegative,firstPositiveAfter,firstRecovery;
        public double minCurrent=Double.NaN,maxCurrent=Double.NaN,minSoc=Double.NaN,maxSoc=Double.NaN,minLoad=Double.NaN,maxLoad=Double.NaN;
        public LocalDateTime dischargeStatus,batterySource,unknownAfter,unknownBefore;
        public final List<Episode> episodes=new ArrayList<>();
        public final List<String> warnings=new ArrayList<>();
        public boolean corroborated;
        public String range(){return first==null?"기록 없음":first.format(TIME)+" ~ "+last.format(TIME);}
    }
    public static Data read(File file)throws IOException {
        try { return readWithCharset(file,StandardCharsets.UTF_8); }
        catch (CharacterCodingException ex){return readWithCharset(file,Charset.forName("MS949"));}
    }
    private static Data readWithCharset(File file,Charset charset)throws IOException {
        Data data=new Data(); int count=0;
        try(ZipFile zip=new ZipFile(file)){
            Enumeration<? extends ZipEntry> it=zip.entries();
            while(it.hasMoreElements()){
                ZipEntry e=it.nextElement(); String name=e.getName().replace('\\','/'); name=name.substring(name.lastIndexOf('/')+1).toLowerCase(Locale.ROOT);
                if(!name.equals("perfmg_minute.csv")&&!name.equals("perfmg_uncertain.csv"))continue;
                if(++count>1)throw new IOException("ZIP 하나에는 minute 또는 uncertain CSV 하나만 넣어 주세요.");
                if(e.getSize()>MAX_EXPANDED)throw new IOException("압축 해제 크기 제한(128 MB)을 초과했습니다.");
                data.kind=name.contains("minute")?"minute":"uncertain";
                try(InputStream raw=zip.getInputStream(e); Reader reader=new InputStreamReader(new LimitedInputStream(raw),charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT))){parse(reader,data);}
            }
        }
        if(count==0)throw new IOException("perfmg_minute.csv 또는 perfmg_uncertain.csv가 들어 있는 ZIP을 선택해 주세요.");
        if(data.current.isEmpty()&&data.soc.isEmpty()&&data.source.isEmpty()&&data.status.isEmpty())throw new IOException("분석 가능한 Lithium Battery Group 또는 Digital Power 기록이 없습니다.");
        return data;
    }
    private static class LimitedInputStream extends FilterInputStream {
        long total; LimitedInputStream(InputStream in){super(in);}
        void add(int n)throws IOException{if(n>0&&(total+=n)>MAX_EXPANDED)throw new IOException("압축 해제 크기 제한(128 MB) 초과");}
        public int read()throws IOException{int b=in.read();if(b>=0)add(1);return b;}
        public int read(byte[] b,int o,int l)throws IOException{int n=in.read(b,o,l);add(n);return n;}
    }
    static void parse(Reader reader,Data d)throws IOException {
        BufferedReader br=new BufferedReader(reader,65536); String line=br.readLine();
        if(line==null)throw new IOException("빈 CSV 파일입니다.");
        List<String> header=csv(line.replace("\uFEFF","")); Map<String,Integer> columns=new HashMap<>();
        for(int i=0;i<header.size();i++)columns.put(header.get(i),i);
        for(String key:new String[]{"Equipment","Equipment ID","Performance Data","Statistical Start Time","Value","Unit"})if(!columns.containsKey(key))throw new IOException("CSV 필수 열 누락: "+key);
        while((line=br.readLine())!=null){
            if(line.length()>1000000)throw new IOException("CSV 행 길이가 너무 큽니다.");
            if(line.trim().isEmpty())continue;
            if(++d.rows>2000000)throw new IOException("CSV 행 수 제한 초과");
            List<String> row=csv(line);
            String eq=get(row,columns,"Equipment"), p=get(row,columns,"Performance Data");
            boolean group=eq.equals("Lithium Battery Group"), digital=eq.equals("Digital Power");
            if(!(group&&(p.equals("Current")||p.equals("SOC")||p.equals("Battery Status")))&&!(digital&&(p.equals("Total DC Load Power")||p.equals("Power Supply Source"))))continue;
            String id=eq+"/"+get(row,columns,"Equipment ID");
            for(String other:d.equipmentIds)if(other.startsWith(eq+"/")&&!other.equals(id))throw new IOException("한 ZIP에서 여러 "+eq+" ID가 발견되었습니다. 시스템별로 분리해 주세요.");
            d.equipmentIds.add(id);
            String v=get(row,columns,"Value"),u=get(row,columns,"Unit");
            if(v.isEmpty()||v.equalsIgnoreCase("No Data")||v.equals("--")){d.missing++;continue;}
            LocalDateTime t;
            try{t=LocalDateTime.parse(get(row,columns,"Statistical Start Time"),TIME);}catch(Exception ex){d.invalid++;continue;}
            if(p.equals("Power Supply Source")){put(d.source,t,v);continue;}
            if(p.equals("Battery Status")){put(d.status,t,v);continue;}
            try{
                double value=Double.parseDouble(v);
                if(!Double.isFinite(value)){d.invalid++;continue;}
                if(p.equals("Current")){if(!u.equalsIgnoreCase("A")){d.invalid++;continue;}put(d.current,t,value);}
                else if(p.equals("SOC")){if(!u.equals("%")||value<0||value>100){d.invalid++;continue;}put(d.soc,t,value);}
                else {if(u.equalsIgnoreCase("kW"))value*=1000;else if(!u.equalsIgnoreCase("W")){d.invalid++;continue;}put(d.load,t,value);}
            }catch(NumberFormatException ex){d.invalid++;}
        }
    }
    static <T> void put(Map<LocalDateTime,T> m,LocalDateTime t,T v)throws IOException{T old=m.put(t,v);if(old!=null&&!old.equals(v))throw new IOException("동일 항목·시각의 값 충돌: "+t);}
    static String get(List<String> row,Map<String,Integer> c,String key){int i=c.get(key);return i<row.size()?row.get(i):"";}
    /** Huawei CSV has spaces before quotes, tab-padded values, and a trailing header comma. */
    public static List<String> csv(String line)throws IOException{
        List<String> out=new ArrayList<>();StringBuilder cell=new StringBuilder();boolean quote=false;
        for(int i=0;i<line.length();i++){
            char c=line.charAt(i);
            if(c=='"'){
                if(quote&&i+1<line.length()&&line.charAt(i+1)=='"'){cell.append('"');i++;}
                else quote=!quote;
            }else if(c==','&&!quote){out.add(cell.toString().trim());cell.setLength(0);}else cell.append(c);
        }
        if(quote)throw new IOException("닫히지 않은 CSV 따옴표가 있습니다.");
        out.add(cell.toString().trim());return out;
    }
    public static Result analyze(Unit u){
        Result r=new Result();r.unit=u;
        TreeMap<LocalDateTime,Double> current=u.currents(),soc=u.socs(),load=u.loads();
        TreeSet<LocalDateTime> times=new TreeSet<>();times.addAll(current.keySet());times.addAll(soc.keySet());times.addAll(load.keySet());
        if(times.isEmpty()){times.addAll(u.sources().keySet());times.addAll(u.statuses().keySet());}
        if(!times.isEmpty()){r.first=times.first();r.last=times.last();}
        r.minCurrent=min(current.values());r.maxCurrent=max(current.values());r.minSoc=min(soc.values());r.maxSoc=max(soc.values());
        for(Map.Entry<LocalDateTime,Double> e:soc.entrySet())if(e.getValue()==r.minSoc){r.minSocAt=e.getKey();break;}
        Episode active=null; LocalDateTime previous=null;
        for(Map.Entry<LocalDateTime,Double> e:current.entrySet()){
            LocalDateTime t=e.getKey();double v=e.getValue();
            if(active!=null&&previous!=null&&Duration.between(previous,t).toMinutes()>10){active=null;r.warnings.add("10분 초과 전류 기록 공백으로 방전 구간을 분리함.");}
            if(v<0){
                if(r.firstNegative==null)r.firstNegative=t;
                if(active==null){active=new Episode();active.start=t;r.episodes.add(active);}
                active.last=t;active.minCurrent=Math.min(active.minCurrent,v);
                Double power=load.get(t);if(power!=null){r.minLoad=Double.isNaN(r.minLoad)?power:Math.min(r.minLoad,power);r.maxLoad=Double.isNaN(r.maxLoad)?power:Math.max(r.maxLoad,power);}
            }else if(active!=null){active.end=t;active=null;}
            previous=t;
        }
        for(int i=0;i<r.episodes.size();i++){
            Episode ep=r.episodes.get(i);LocalDateTime limit=i+1<r.episodes.size()?r.episodes.get(i+1).start:r.last.plusSeconds(1);
            Map.Entry<LocalDateTime,Double> before=soc.lowerEntry(ep.start);double baseline=before!=null&&Duration.between(before.getKey(),ep.start).toMinutes()<=10?before.getValue():Double.NaN;
            for(Map.Entry<LocalDateTime,Double> e:soc.subMap(ep.start,true,limit,false).entrySet()){
                ep.minSoc=Double.isNaN(ep.minSoc)?e.getValue():Math.min(ep.minSoc,e.getValue());ep.maxSoc=Double.isNaN(ep.maxSoc)?e.getValue():Math.max(ep.maxSoc,e.getValue());
                if(Double.isNaN(baseline)&&!e.getKey().isAfter(ep.last))baseline=e.getValue();
                if(!e.getKey().isAfter(ep.last)&&e.getValue()<baseline)ep.socDropped=true;
            }
            for(Map.Entry<LocalDateTime,Double> e:current.subMap(ep.last,false,limit,false).entrySet())if(e.getValue()>0){if(ep.charge==null)ep.charge=e.getKey();ep.maxCharge=Math.max(ep.maxCharge,e.getValue());}
            if(ep.charge!=null&&ep.minSoc<100)for(Map.Entry<LocalDateTime,Double> e:soc.subMap(ep.charge,true,limit,false).entrySet())if(e.getValue()>=100){ep.recovered=e.getKey();break;}
        }
        if(!r.episodes.isEmpty()){Episode ep=r.episodes.get(0);r.firstPositiveAfter=ep.charge;r.firstRecovery=ep.recovered;}
        // State events may differ from five-minute samples; associate only within the observed discharge window ±10 min.
        for(Episode ep:r.episodes){
            LocalDateTime from=ep.start.minusMinutes(10),to=(ep.end==null?ep.last.plusMinutes(10):ep.end.plusMinutes(10));
            LocalDateTime bs=firstValue(u.sources(),"Battery",from,to),ds=firstValue(u.statuses(),"Discharge",from,to);
            if(r.batterySource==null&&bs!=null){r.batterySource=bs;Map.Entry<LocalDateTime,String> prev=u.sources().lowerEntry(bs);if(prev!=null&&prev.getValue().equals("Unknown"))r.unknownBefore=prev.getKey();
                r.unknownAfter=firstValue(u.sources(),"Unknown",bs,to.plusMinutes(10));}
            if(r.dischargeStatus==null&&ds!=null)r.dischargeStatus=ds;
            if(bs!=null&&ds!=null&&ep.socDropped)r.corroborated=true;
        }
        if(u.minute==null)r.warnings.add("perfmg_minute 미제공: 전류·SOC·부하 정량 분석 불가.");
        if(u.uncertain==null)r.warnings.add("perfmg_uncertain 미제공: 상태 전환 교차 확인 불가.");
        if(current.isEmpty())r.warnings.add("유효한 그룹 전류 기록 없음.");
        if(soc.isEmpty())r.warnings.add("유효한 SOC 기록 없음.");
        for(Data d:new Data[]{u.minute,u.uncertain})if(d!=null&&(d.missing>0||d.invalid>0))r.warnings.add(d.kind+": No Data/결측 "+d.missing+"건, 시각·수치·단위 오류 "+d.invalid+"건을 분석에서 제외함.");
        return r;
    }
    static LocalDateTime firstValue(TreeMap<LocalDateTime,String> m,String v,LocalDateTime from,LocalDateTime to){for(Map.Entry<LocalDateTime,String> e:m.subMap(from,true,to,true).entrySet())if(v.equals(e.getValue()))return e.getKey();return null;}
    static double min(Collection<Double> v){return v.isEmpty()?Double.NaN:Collections.min(v);}
    static double max(Collection<Double> v){return v.isEmpty()?Double.NaN:Collections.max(v);}
    public static String number(double n,int decimals){return Double.isNaN(n)?"확인 불가":String.format(Locale.KOREA,"%,."+decimals+"f",n);}
    public static String time(LocalDateTime t){return t==null?"확인 안 됨":t.format(TIME);}
    public static String summary(Result r){
        if(r.episodes.isEmpty())return "제공된 유효 전류 기록에서 음(-)의 방전 전류가 확인되지 않았음. 방전·재충전 기능 정상 여부를 판정할 근거가 부족함.";
        long charged=r.episodes.stream().filter(e->e.charge!=null).count(), recovered=r.episodes.stream().filter(e->e.recovered!=null).count();
        return "방전 전류 구간 "+r.episodes.size()+"회가 기록되었으며, 이후 양(+)의 재충전 전류 "+charged+"회 및 SOC 100% 회복 "+recovered+"회가 확인됨. "+(recovered==r.episodes.size()?"해당 관측 구간에서 방전·재충전 및 SOC 회복 동작을 확인하였음.":"완전 회복이 확인되지 않은 구간은 추가 로그 확인이 필요함.");
    }
}
