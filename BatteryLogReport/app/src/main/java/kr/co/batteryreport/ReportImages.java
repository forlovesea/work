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
        }else{
            for(Map.Entry<LocalDateTime,Double> e:r.unit.currents().entrySet()){
                if(e.getValue()>=0)continue;
                String t=LogAnalyzer.time(e.getKey());
                if(kind.equals("load"))rows.add(new String[]{"Digital Power","DC Load Power (W)",t,LogAnalyzer.number(r.unit.loads().getOrDefault(e.getKey(),Double.NaN),0)});
                else rows.add(new String[]{"Lithium Battery Group","Current / SOC",t,LogAnalyzer.number(e.getValue(),1)+" A / "+LogAnalyzer.number(r.unit.socs().getOrDefault(e.getKey(),Double.NaN),0)+"%"});
            }
        }
        int total=rows.size();if(total>12)rows=new ArrayList<>(rows.subList(0,12));
        if(rows.isEmpty())rows.add(new String[]{"기록 없음","해당 조건 미확인","—","—"});
        int height=110+rows.size()*43+45;p.begin(1800,height);p.rect(0,0,1800,height,0xffffffff);
        p.text(r.unit.label+" | "+(kind.equals("states")?"상태 변경 원본 기록":kind.equals("load")?"방전 시점의 DC 부하 원본 기록":"방전 전류 · SOC 원본 기록"),18,35,26,INK,true);
        int[] x={10,430,950,1445,1790};String[] labels={"Equipment","Performance Data","Statistical Start Time","Value"};
        p.rect(10,52,1780,44,0xffeaf0f4);
        for(int c=0;c<4;c++)p.text(labels[c],x[c]+10,82,23,INK,true);
        int y=96;
        for(String[] row:rows){for(int c=0;c<4;c++){p.text(row[c],x[c]+10,y+30,23,INK,false);p.line(x[c],y,x[c],y+43,GRID,1);}p.line(10,y+43,1790,y+43,GRID,1);y+=43;}
        p.text("원본 실측값 · "+total+"건 중 "+Math.min(total,12)+"건 표시"+(total>12?" (시간순 첫 12건; 전체 구간은 본문 분석에 반영)":""),18,y+35,21,INK,false);
        return p.png();
    }
}
