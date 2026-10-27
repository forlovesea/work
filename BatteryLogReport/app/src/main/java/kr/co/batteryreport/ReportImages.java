package kr.co.batteryreport;

import java.io.*;
import java.time.*;
import java.time.format.*;
import java.util.*;

/** A small drawing interface keeps Android and desktop verification on the same chart code. */
public final class ReportImages {
    public interface Painter {
        void begin(int w,int h);
        void rect(float x,float y,float w,float h,int color);
        void line(float x,float y,float xx,float yy,int color,float width);
        void text(String s,float x,float y,float size,int color,boolean bold);
        byte[] png()throws IOException;
    }
    private final Painter p;
    /** One discharge cycle and its first uninterrupted positive-current run. */
    public static final class CurrentEvidence {
        public final List<LocalDateTime> discharge=new ArrayList<>(),charging=new ArrayList<>();
        public LocalDateTime chargeStart,chargeEnd;
        public int positiveCount;
    }
    public static CurrentEvidence currentEvidence(LogAnalyzer.Result r){
        CurrentEvidence out=new CurrentEvidence();
        if(r.episodes.isEmpty())return out;
        LogAnalyzer.Episode selected=r.episodes.get(0);
        for(LogAnalyzer.Episode e:r.episodes)if(e.charge!=null){selected=e;break;}
        for(Map.Entry<LocalDateTime,Double> e:r.unit.currents().subMap(selected.start,true,selected.last,true).entrySet())if(e.getValue()<0)out.discharge.add(e.getKey());
        // Keep both ends when a long discharge needs a compact evidence table.
        sample(out.discharge,12);
        if(selected.charge==null)return out;
        LocalDateTime previous=null;
        List<LocalDateTime> run=new ArrayList<>();
        for(Map.Entry<LocalDateTime,Double> e:r.unit.currents().tailMap(selected.charge,true).entrySet()){
            if(e.getValue()<=0||(previous!=null&&Duration.between(previous,e.getKey()).getSeconds()>600))break;
            run.add(e.getKey());previous=e.getKey();
        }
        if(!run.isEmpty()){
            out.chargeStart=run.get(0);out.chargeEnd=run.get(run.size()-1);out.positiveCount=run.size();
            sample(run,4);out.charging.addAll(run);
        }
        return out;
    }
    private static void sample(List<LocalDateTime> times,int limit){
        if(times.size()<=limit)return;
        List<LocalDateTime> selected=new ArrayList<>();
        for(int i=0;i<limit;i++)selected.add(times.get((int)Math.round(i*(times.size()-1.0)/(limit-1))));
        times.clear();times.addAll(selected);
    }
    public static String currentExplanation(LogAnalyzer.Result r){
        CurrentEvidence e=currentEvidence(r);
        if(e.discharge.isEmpty())return "음(-)의 방전 전류가 확인되지 않아 방전 후 충전으로 전환되는 동작은 확인할 수 없음.";
        if(e.charging.isEmpty())return "음(-)의 전류로 방전 동작은 확인되었으나, 이후 양(+)의 충전 전류는 확인되지 않아 충전 전환·유지 기록은 표시하지 않았음.";
        String s="음(-)의 전류로 방전한 이후 "+LogAnalyzer.time(e.chargeStart)+"에 양(+)의 충전 전류가 처음 실측되었음. ";
        if(e.positiveCount==1)return s+"충전 방향 전환은 확인되었으나 양수 기록이 1개뿐이므로 충전 유지 여부는 추가 확인이 필요함.";
        s+=LogAnalyzer.time(e.chargeEnd)+"까지 양수 전류 "+e.positiveCount+"개 실측값이 이어져, 해당 관측 구간에서 방전 후 충전 전환 및 충전 유지 동작을 확인하였음. ";
        Double first=r.unit.socs().get(e.chargeStart),last=r.unit.socs().get(e.chargeEnd);
        if(first!=null&&last!=null&&last>first)s+="같은 시각의 SOC도 "+LogAnalyzer.number(first,0)+"%에서 "+LogAnalyzer.number(last,0)+"%로 증가하여 재충전 동작을 교차 확인하였음.";
        else s+="충전 구간의 SOC 증가 여부는 해당 SOC 기록을 추가 대조해야 함.";
        return s;
    }
    static final int INK=0xff182638,GRID=0xffe3e8ec,BLUE=0xff2866a6,TEAL=0xff71afa6,ORANGE=0xffbb6d20;
    public ReportImages(Painter painter){p=painter;}
    public byte[] chart(LogAnalyzer.Result r)throws IOException{
        int width=1800,height=1236;p.begin(width,height);p.rect(0,0,width,height,0xffffffff);
        p.text(r.unit.label+" 축전지 시스템 | 방전 · 재충전 · SOC · 부하 전력",65,48,29,INK,true);
        List<LocalDateTime> all=new ArrayList<>(r.unit.currents().keySet());
        LocalDateTime from=r.first,to=r.last;
        if(!r.episodes.isEmpty()){
            from=r.episodes.get(0).start.minusMinutes(15);
            LogAnalyzer.Episode last=r.episodes.get(r.episodes.size()-1);
            to=last.recovered!=null?last.recovered.plusMinutes(15):(last.end!=null?last.end.plusHours(2):last.last.plusMinutes(15));
            if(r.last!=null&&to.isAfter(r.last))to=r.last;
        }
        if(from==null){from=LocalDateTime.of(2000,1,1,0,0);to=from.plusHours(1);}
        if(!to.isAfter(from))to=from.plusMinutes(5);
        panel(r.unit.currents(),from,to,90,420,"그룹 전류 (A)",BLUE,false);
        panel(r.unit.socs(),from,to,555,250,"SOC (%)",TEAL,true);
        panel(r.unit.loads(),from,to,850,260,"DC 부하 전력 (W)",ORANGE,false);
        p.text("전류: "+LogAnalyzer.number(r.minCurrent,1)+" ~ "+LogAnalyzer.number(r.maxCurrent,1)+" A   |   SOC: "+LogAnalyzer.number(r.minSoc,0)+" ~ "+LogAnalyzer.number(r.maxSoc,0)+"%",120,1181,24,INK,true);
        p.text("실측값 표시 · 선은 인접 실측점을 연결함 · 10분 초과 기록 공백은 연결하지 않음",120,1217,22,INK,false);
        return p.png();
    }
    private void panel(TreeMap<LocalDateTime,Double> data,LocalDateTime from,LocalDateTime to,int top,int h,String name,int color,boolean bars){
        int left=120,right=1740;SortedMap<LocalDateTime,Double> points=data.subMap(from,true,to,true);
        double min=bars?0:Math.min(0,LogAnalyzer.min(points.values())),max=bars?100:LogAnalyzer.max(points.values());
        if(Double.isNaN(min)||Double.isNaN(max)){min=0;max=1;}
        if(max<=min)max=min+1;
        if(!bars){double margin=(max-min)*.08;max+=margin;min-=margin;}
        p.text(name,left,top-15,24,INK,true);
        for(int i=0;i<=4;i++){
            float y=top+h-h*i/4f;p.line(left,y,right,y,GRID,1.2f);
            p.text(LogAnalyzer.number(min+(max-min)*i/4,0),8,y+7,21,INK,false);
        }
        long span=Math.max(1,Duration.between(from,to).getSeconds());
        for(int i=0;i<=6;i++){
            float x=left+(right-left)*i/6f;p.line(x,top,x,top+h,GRID,1);
            LocalDateTime tick=from.plusSeconds(span*i/6);
            p.text(tick.format(DateTimeFormatter.ofPattern(span>86400?"MM-dd HH:mm":"HH:mm")),x-40,top+h+28,19,INK,false);
        }
        LocalDateTime prev=null;float px=0,py=0;int n=points.size();float bw=Math.max(1,Math.min(24,(right-left)/(float)Math.max(1,n)*.65f));
        for(Map.Entry<LocalDateTime,Double> e:points.entrySet()){
            float x=left+(right-left)*Duration.between(from,e.getKey()).getSeconds()/(float)span;
            float y=(float)(top+h-h*(e.getValue()-min)/(max-min));
            if(bars)p.rect(x-bw/2,y,bw,top+h-y,color);
            else {if(prev!=null&&Duration.between(prev,e.getKey()).toMinutes()<=10)p.line(px,py,x,y,color,2.5f);p.rect(x-2,y-2,4,4,color);}
            prev=e.getKey();px=x;py=y;
        }
        if(points.isEmpty())p.text("해당 구간의 유효 기록 없음",left+100,top+h/2f,26,INK,false);
    }
    public byte[] evidence(LogAnalyzer.Result r,String kind)throws IOException{
        List<String[]> rows=new ArrayList<>();
        if(kind.equals("states")){
            for(Map.Entry<LocalDateTime,String> e:r.unit.sources().entrySet())rows.add(new String[]{"Digital Power", "Power Supply Source",LogAnalyzer.time(e.getKey()),e.getValue()});
            for(Map.Entry<LocalDateTime,String> e:r.unit.statuses().entrySet())if(e.getValue().equals("Discharge"))rows.add(new String[]{"Lithium Battery Group","Battery Status",LogAnalyzer.time(e.getKey()),e.getValue()});
            rows.sort(Comparator.comparing(a->a[2]));
        }else if(kind.equals("current")){
            CurrentEvidence evidence=currentEvidence(r);
            List<LocalDateTime> times=new ArrayList<>(evidence.discharge);times.addAll(evidence.charging);
            for(LocalDateTime t:times){double current=r.unit.currents().get(t);rows.add(new String[]{"Lithium Battery Group","Current / SOC",LogAnalyzer.time(t),(current>0?"+":"")+LogAnalyzer.number(current,1)+" A / "+LogAnalyzer.number(r.unit.socs().getOrDefault(t,Double.NaN),0)+"%"});}
        }else{
            for(Map.Entry<LocalDateTime,Double> e:r.unit.currents().entrySet()){
                if(e.getValue()>=0)continue;
                String t=LogAnalyzer.time(e.getKey());
                if(kind.equals("load"))rows.add(new String[]{"Digital Power","DC Load Power (W)",t,LogAnalyzer.number(r.unit.loads().getOrDefault(e.getKey(),Double.NaN),0)});
                else rows.add(new String[]{"Lithium Battery Group","Current / SOC",t,LogAnalyzer.number(e.getValue(),1)+" A / "+LogAnalyzer.number(r.unit.socs().getOrDefault(e.getKey(),Double.NaN),0)+"%"});
            }
        }
        int total=rows.size();if(!kind.equals("current")&&total>12)rows=new ArrayList<>(rows.subList(0,12));
        if(rows.isEmpty())rows.add(new String[]{"기록 없음","해당 조건 미확인","—","—"});
        int height=110+rows.size()*43+45;p.begin(1800,height);p.rect(0,0,1800,height,0xffffffff);
        p.text(r.unit.label+" | "+(kind.equals("states")?"상태 변경 원본 기록":kind.equals("load")?"방전 시점의 DC 부하 원본 기록":currentEvidence(r).charging.isEmpty()?"방전 전류 · SOC 원본 기록":"방전·충전 전류 · SOC 원본 기록"),18,35,26,INK,true);
        int[] x={10,430,950,1445,1790};String[] labels={"Equipment","Performance Data","Statistical Start Time","Value"};
        p.rect(10,52,1780,44,0xffeaf0f4);
        for(int c=0;c<4;c++)p.text(labels[c],x[c]+10,82,23,INK,true);
        int y=96;
        for(String[] row:rows){for(int c=0;c<4;c++){p.text(row[c],x[c]+10,y+30,23,INK,false);p.line(x[c],y,x[c],y+43,GRID,1);}p.line(10,y+43,1790,y+43,GRID,1);y+=43;}
        String footer="원본 실측값 · "+total+"건 중 "+Math.min(total,12)+"건 표시"+(total>12?" (시간순 첫 12건; 전체 구간은 본문 분석에 반영)":"");
        if(kind.equals("current")){CurrentEvidence e=currentEvidence(r);footer="원본 실측값 · 방전 "+e.discharge.size()+"건"+(e.charging.isEmpty()?"":" + 충전 전환·유지 "+e.charging.size()+"건 (첫 양수 시점과 유지 구간에서 발췌)");}
        p.text(footer,18,y+35,21,INK,false);
        return p.png();
    }
}
