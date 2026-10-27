package kr.co.batteryreport;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.security.*;
import java.text.*;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    static final int PICK=101,SAVE=102;static final int INK=0xff172c42,MUTED=0xff576d83,TEAL=0xff087e8b;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final ArrayList<SiteRecord> sites=new ArrayList<>();private int selectedSite=0,selectedUnit=0;
    private LinearLayout root,statusBox,controls;private TextView progress;private Spinner siteSpinner,unitSpinner;private boolean busy=false,binding=false;
    private File outputDir;private String message="설치장소를 추가하고 로그파일을 업로드하세요.";
    private SiteRecord pendingSite;private int pendingUnit;
    static class LogFile {String path,name,kind,hash;long size;LogAnalyzer.Data data;}
    static class UnitRecord {LogFile minute,uncertain;}
    static class SiteRecord {String name;ArrayList<UnitRecord> units=new ArrayList<>();SiteRecord(String n){name=n;units.add(new UnitRecord());}}
    public void onCreate(Bundle state){super.onCreate(state);load();draw();}
    private int dp(float n){return (int)(getResources().getDisplayMetrics().density*n+.5f);}
    private TextView text(String s,int size,int color,boolean bold){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);if(bold)t.setTypeface(null,Typeface.BOLD);t.setPadding(0,dp(5),0,dp(5));return t;}
    private GradientDrawable bg(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(16));return d;}
    private LinearLayout card(){LinearLayout l=new LinearLayout(this);l.setOrientation(1);l.setPadding(dp(18),dp(14),dp(18),dp(14));l.setBackground(bg(Color.WHITE));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(12),0,0);l.setLayoutParams(lp);return l;}
    private Button button(String title,boolean primary,Runnable action){Button b=new Button(this);b.setText(title);b.setAllCaps(false);b.setTextSize(16);b.setTextColor(primary?Color.WHITE:TEAL);b.setBackground(bg(primary?TEAL:0xffe7f3f4));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(52));lp.setMargins(0,dp(8),0,0);b.setLayoutParams(lp);b.setOnClickListener(v->{if(!busy)action.run();});b.setEnabled(!busy);return b;}
    private void draw(){
        binding=true;
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(0xfff3f6fa);
        root=new LinearLayout(this);root.setOrientation(1);root.setPadding(dp(20),dp(20),dp(20),dp(24));scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(dp(20),dp(20)+insets.getSystemWindowInsetTop(),dp(20),dp(24)+insets.getSystemWindowInsetBottom());return insets;});root.requestApplyInsets();
        root.addView(text("BATTERY LOG REPORT",12,TEAL,true));root.addView(text("축전지 로그 보고서",27,INK,true));root.addView(text("설치장소별 로그를 모아\n충·방전 분석과 AC 정전 추정 보고서를 만듭니다.",14,MUTED,false));
        statusBox=card();root.addView(statusBox);statusBox.addView(text("업로드 상황",18,INK,true));renderStatus();
        controls=card();root.addView(controls);controls.addView(text("01  설치장소 · 축전지 선택",17,INK,true));
        siteSpinner=new Spinner(this);ArrayList<String> names=new ArrayList<>();for(SiteRecord s:sites)names.add("설치장소: "+s.name);if(names.isEmpty())names.add("설치장소를 추가하세요");
        siteSpinner.setAdapter(adapter(names));controls.addView(siteSpinner);if(!sites.isEmpty())siteSpinner.setSelection(Math.min(selectedSite,sites.size()-1));
        controls.addView(button("+ 설치장소 추가",false,()->siteDialog(false)));
        if(!sites.isEmpty()){
            controls.addView(button("설치장소 이름 변경",false,()->siteDialog(true)));
            unitSpinner=new Spinner(this);ArrayList<String> units=new ArrayList<>();for(int i=0;i<site().units.size();i++){UnitRecord u=site().units.get(i);units.add((i+1)+"호 축전지 · "+(u.minute!=null&&u.uncertain!=null?"2개 로그 등록":u.minute!=null||u.uncertain!=null?"1개 로그 등록":"대기"));}unitSpinner.setAdapter(adapter(units));controls.addView(unitSpinner);selectedUnit=Math.min(selectedUnit,site().units.size()-1);unitSpinner.setSelection(selectedUnit);
            controls.addView(button("+ 같은 설치장소에 축전지 추가",false,()->{site().units.add(new UnitRecord());selectedUnit=site().units.size()-1;persist();draw();}));
            unitSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onNothingSelected(AdapterView<?> a){}public void onItemSelected(AdapterView<?> a,View v,int p,long id){selectedUnit=p;}});
        }
        controls.addView(text("02  ZIP 로그 업로드",17,INK,true));controls.addView(text("minute + uncertain 한 쌍 = 축전지 1식\n하나씩 또는 여러 파일을 한 번에 추가할 수 있습니다. 같은 종류가 여러 개면 선택한 호기부터 순서대로 배정합니다.",13,MUTED,false));
        Button upload=button("로그파일 업로드",true,this::pick);upload.setEnabled(!busy&&!sites.isEmpty());controls.addView(upload);
        LinearLayout generation=card();root.addView(generation);generation.addView(text("03  Word 보고서 만들기",17,INK,true));generation.addView(text("등록된 모든 설치장소를 두 개의 보고서에 포함합니다.\n인터넷 연결 없이 기기에서 분석합니다.",13,MUTED,false));
        Button generate=button("보고서 생성",true,this::generate);generate.setEnabled(!busy&&fileCount()>0);generation.addView(generate);
        progress=text(message,13,MUTED,false);generation.addView(progress);
        if(outputDir!=null){generation.addView(button("보고서 2개 폴더에 저장",false,this::chooseFolder));generation.addView(button("보고서 2개 공유",false,this::share));generation.addView(button("충·방전 분석 보고서 열기",false,()->open(DocxReports.CHARGE_NAME)));generation.addView(button("AC 정전 추정 보고서 열기",false,()->open(DocxReports.OUTAGE_NAME)));}
        root.addView(button("등록 내용 초기화",false,()->new AlertDialog.Builder(this).setTitle("등록 내용 초기화").setMessage("설치장소와 업로드한 로그 목록을 초기화합니다. 이미 저장한 Word 파일은 유지됩니다.").setNegativeButton("취소",null).setPositiveButton("초기화",(d,w)->{sites.clear();selectedSite=0;selectedUnit=0;message="등록 내용을 초기화했습니다.";persist();draw();}).show()));
        siteSpinner.setEnabled(!busy);siteSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onNothingSelected(AdapterView<?> a){}public void onItemSelected(AdapterView<?> a,View v,int p,long id){if(!binding&&p!=selectedSite){selectedSite=p;selectedUnit=0;draw();}}});binding=false;
    }
    private ArrayAdapter<String> adapter(List<String> names){ArrayAdapter<String> a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,names);a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);return a;}
    private SiteRecord site(){return sites.get(selectedSite);}
    private void renderStatus(){
        if(sites.isEmpty()){statusBox.addView(text("아직 등록된 파일이 없습니다.",14,MUTED,false));return;}
        for(int i=0;i<sites.size();i++){
            SiteRecord s=sites.get(i);int count=0;for(UnitRecord u:s.units)if(u.minute!=null||u.uncertain!=null)count++;
            statusBox.addView(text((i+1)+"번 설치장소: "+s.name+"  ·  "+count+"식",15,INK,true));
            for(int j=0;j<s.units.size();j++){
                UnitRecord u=s.units.get(j);String line=(j+1)+"호 로그파일: "+describe(u.minute)+", "+describe(u.uncertain);statusBox.addView(text(line,13,MUTED,false));
                if(u.minute!=null||u.uncertain!=null){final UnitRecord target=u;Button remove=button((j+1)+"호 로그 삭제",false,()->new AlertDialog.Builder(this).setTitle("호기 로그 삭제").setMessage("이 호기에 등록된 로그를 삭제할까요?").setNegativeButton("취소",null).setPositiveButton("삭제",(d,w)->{target.minute=null;target.uncertain=null;persist();draw();}).show());LinearLayout.LayoutParams lp=(LinearLayout.LayoutParams)remove.getLayoutParams();lp.height=dp(40);statusBox.addView(remove);}
            }
        }
        statusBox.addView(text("✓ 등록 파일 "+fileCount()+"개 · 파일명 중복 가능",12,TEAL,true));
    }
    private String describe(LogFile f){return f==null?"미등록":"\""+f.name+"\" ("+android.text.format.Formatter.formatFileSize(this,f.size)+")";}
    private int fileCount(){int n=0;for(SiteRecord s:sites)for(UnitRecord u:s.units){if(u.minute!=null)n++;if(u.uncertain!=null)n++;}return n;}
    private void siteDialog(boolean edit){EditText input=new EditText(this);input.setSingleLine();input.setHint("예: 용인외사");if(edit)input.setText(site().name);input.setPadding(dp(20),dp(12),dp(20),dp(12));AlertDialog dialog=new AlertDialog.Builder(this).setTitle(edit?"설치장소 이름 변경":"설치장소 추가").setView(input).setNegativeButton("취소",null).setPositiveButton("저장",null).create();dialog.setOnShowListener(v->dialog.getButton(-1).setOnClickListener(b->{String name=input.getText().toString().trim();if(name.isEmpty()||name.length()>60){input.setError("설치장소를 1~60자로 입력하세요.");return;}for(SiteRecord s:sites)if(s.name.equals(name)&&(!edit||s!=site())){input.setError("이미 등록된 설치장소입니다.");return;}if(edit)site().name=name;else{sites.add(new SiteRecord(name));selectedSite=sites.size()-1;selectedUnit=0;}persist();dialog.dismiss();draw();}));dialog.show();}
    private void pick(){pendingSite=site();pendingUnit=selectedUnit;Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("*/*");i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/zip","application/x-zip-compressed","application/octet-stream"});startActivityForResult(i,PICK);}
    protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null)return;
        if(request==PICK){ArrayList<Uri> uris=new ArrayList<>();if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++){Uri uri=data.getClipData().getItemAt(i).getUri();if(!uris.contains(uri))uris.add(uri);}else if(data.getData()!=null)uris.add(data.getData());if(pendingSite==null){message="설치장소를 선택한 뒤 다시 업로드해 주세요.";draw();return;}importFiles(uris,pendingSite,pendingUnit);}
        if(request==SAVE&&data.getData()!=null)saveReports(data.getData());
    }
    private void setBusy(String s){busy=true;message=s;draw();}
    private void finish(String s){busy=false;message=s;persist();draw();}
    private void importFiles(List<Uri> uris,SiteRecord target,int start){
        if(uris.size()>40){message="한 번에 최대 40개 파일을 선택해 주세요.";draw();return;}
        setBusy("로그파일 확인 중…");
        worker.execute(()->{ArrayList<LogFile> accepted=new ArrayList<>();ArrayList<String> errors=new ArrayList<>();for(Uri uri:uris){File dest=null;try{
            LogFile f=new LogFile();f.name="로그.zip";try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())f.name=c.getString(0);}
            File dir=new File(getFilesDir(),"logs");dir.mkdirs();dest=new File(dir,UUID.randomUUID()+".zip");MessageDigest digest=MessageDigest.getInstance("SHA-256");
            try(InputStream in=getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(dest)){if(in==null)throw new IOException("파일을 읽을 수 없습니다.");byte[] buf=new byte[65536];int n;while((n=in.read(buf))!=-1){f.size+=n;if(f.size>64L*1024*1024)throw new IOException("ZIP 파일은 64 MB 이하로 선택해 주세요.");out.write(buf,0,n);digest.update(buf,0,n);}}
            f.path=dest.getName();f.hash=hex(digest.digest());f.data=LogAnalyzer.read(dest);f.kind=f.data.kind;accepted.add(f);
        }catch(Exception e){if(dest!=null)dest.delete();errors.add(e.getMessage()==null?e.toString():e.getMessage());}}
        runOnUiThread(()->{int duplicate=0;for(LogFile f:accepted){boolean same=false;for(SiteRecord s:sites)for(UnitRecord u:s.units)for(LogFile old:new LogFile[]{u.minute,u.uncertain})if(old!=null&&old.hash.equals(f.hash))same=true;if(same)duplicate++;
            int pos=start;while(pos<target.units.size()){UnitRecord u=target.units.get(pos);if(f.kind.equals("minute")?u.minute==null:u.uncertain==null)break;pos++;}if(pos==target.units.size())target.units.add(new UnitRecord());UnitRecord u=target.units.get(pos);if(f.kind.equals("minute"))u.minute=f;else u.uncertain=f;
        }
        finish(accepted.size()+"개 업로드 완료"+(duplicate>0?" · 동일 내용 "+duplicate+"개는 별도 호기로 등록됨. 실제 장비 구분을 확인해 주세요.":"")+(errors.isEmpty()?"":"\n실패 "+errors.size()+"개: "+String.join("\n",errors)));});});
    }
    private void generate(){
        setBusy("원본 로그 분석 및 Word 보고서 2개 생성 중…");
        worker.execute(()->{File staging=null;try{
            ArrayList<LogAnalyzer.Site> analysis=new ArrayList<>();
            for(SiteRecord s:sites){LogAnalyzer.Site a=new LogAnalyzer.Site(s.name);for(int i=0;i<s.units.size();i++){UnitRecord u=s.units.get(i);if(u.minute==null&&u.uncertain==null)continue;LogAnalyzer.Unit unit=new LogAnalyzer.Unit((i+1)+"호");if(u.minute!=null){unit.minute=loadData(u.minute);unit.minuteName=u.minute.name;}if(u.uncertain!=null){unit.uncertain=loadData(u.uncertain);unit.uncertainName=u.uncertain.name;}a.units.add(unit);}if(!a.units.isEmpty())analysis.add(a);}
            if(analysis.isEmpty())throw new IOException("분석할 로그가 없습니다.");
            File reports=new File(getFilesDir(),"reports");reports.mkdirs();String stamp=new SimpleDateFormat("yyyyMMdd_HHmmss",Locale.US).format(new Date())+"_"+UUID.randomUUID().toString().substring(0,6);staging=new File(reports,stamp+".partial");staging.mkdirs();
            DocxReports writer=new DocxReports(new ReportImages(new AndroidPainter()));
            writer.generate(getAssets().open("charge.docx"),true,analysis,new File(staging,DocxReports.CHARGE_NAME));
            writer.generate(getAssets().open("outage.docx"),false,analysis,new File(staging,DocxReports.OUTAGE_NAME));
            File finalDir=new File(reports,stamp);if(!staging.renameTo(finalDir))throw new IOException("보고서 저장 마무리 실패");
            runOnUiThread(()->{outputDir=finalDir;finish("보고서 2개 생성 완료. 아래에서 폴더에 저장하거나 공유하세요.");});
        }catch(Exception e){if(staging!=null){File[] files=staging.listFiles();if(files!=null)for(File f:files)f.delete();staging.delete();}runOnUiThread(()->finish("보고서 생성 실패: "+e.getMessage()));}});
    }
    private LogAnalyzer.Data loadData(LogFile f)throws IOException{if(f.data==null)f.data=LogAnalyzer.read(new File(new File(getFilesDir(),"logs"),f.path));return f.data;}
    private void chooseFolder(){startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE),SAVE);}
    private void saveReports(Uri tree){File source=outputDir;setBusy("선택한 폴더에 보고서 저장 중…");worker.execute(()->{Uri folder=null;ArrayList<Uri> created=new ArrayList<>();try{
        Uri parent=DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree));folder=DocumentsContract.createDocument(getContentResolver(),parent,DocumentsContract.Document.MIME_TYPE_DIR,"축전지_보고서_"+source.getName());if(folder==null)throw new IOException("폴더 생성 실패");
        for(String name:new String[]{DocxReports.CHARGE_NAME,DocxReports.OUTAGE_NAME}){Uri uri=DocumentsContract.createDocument(getContentResolver(),folder,"application/vnd.openxmlformats-officedocument.wordprocessingml.document",name);if(uri==null)throw new IOException("문서 생성 실패");created.add(uri);try(InputStream in=new FileInputStream(new File(source,name));OutputStream out=getContentResolver().openOutputStream(uri)){if(out==null)throw new IOException("저장 위치에 쓸 수 없습니다.");byte[] buf=new byte[65536];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);}}
        runOnUiThread(()->finish("보고서 2개 저장 완료: 축전지_보고서_"+source.getName()));
    }catch(Exception e){for(Uri uri:created)try{DocumentsContract.deleteDocument(getContentResolver(),uri);}catch(Exception ignored){}if(folder!=null)try{DocumentsContract.deleteDocument(getContentResolver(),folder);}catch(Exception ignored){}runOnUiThread(()->finish("외부 폴더 저장 실패: "+e.getMessage()+"\n앱 안의 완성 보고서는 유지됩니다. 다른 폴더를 선택해 주세요."));}});}
    private void share(){ArrayList<Uri> uris=new ArrayList<>();uris.add(ReportProvider.uri(outputDir,DocxReports.CHARGE_NAME));uris.add(ReportProvider.uri(outputDir,DocxReports.OUTAGE_NAME));Intent i=new Intent(Intent.ACTION_SEND_MULTIPLE);i.setType("application/vnd.openxmlformats-officedocument.wordprocessingml.document");i.putParcelableArrayListExtra(Intent.EXTRA_STREAM,uris);ClipData clip=ClipData.newRawUri("보고서",uris.get(0));clip.addItem(new ClipData.Item(uris.get(1)));i.setClipData(clip);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);startActivity(Intent.createChooser(i,"보고서 2개 공유"));}
    private void open(String name){Uri uri=ReportProvider.uri(outputDir,name);Intent i=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.openxmlformats-officedocument.wordprocessingml.document");i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);try{startActivity(i);}catch(ActivityNotFoundException e){new AlertDialog.Builder(this).setMessage("Word 문서를 열 수 있는 앱이 없습니다. 보고서를 폴더에 저장하거나 공유해 주세요.").setPositiveButton("확인",null).show();}}
    private static String hex(byte[] bytes){StringBuilder b=new StringBuilder();for(byte v:bytes)b.append(String.format(Locale.US,"%02x",v));return b.toString();}
    private JSONObject json(LogFile f)throws JSONException{if(f==null)return null;return new JSONObject().put("path",f.path).put("name",f.name).put("kind",f.kind).put("hash",f.hash).put("size",f.size);}
    private LogFile file(JSONObject j)throws JSONException{if(j==null)return null;LogFile f=new LogFile();f.path=j.getString("path");if(!f.path.matches("[a-f0-9-]+\\.zip"))throw new JSONException("잘못된 저장 경로");f.name=j.getString("name");f.kind=j.getString("kind");f.hash=j.getString("hash");f.size=j.getLong("size");return f;}
    private void persist(){try{JSONArray a=new JSONArray();for(SiteRecord s:sites){JSONArray units=new JSONArray();for(UnitRecord u:s.units)units.put(new JSONObject().put("minute",json(u.minute)).put("uncertain",json(u.uncertain)));a.put(new JSONObject().put("name",s.name).put("units",units));}getSharedPreferences("state",MODE_PRIVATE).edit().putString("sites",a.toString()).putString("output",outputDir==null?"":outputDir.getName()).apply();}catch(JSONException e){message="등록 정보 저장 실패: "+e.getMessage();}}
    private void load(){try{android.content.SharedPreferences prefs=getSharedPreferences("state",MODE_PRIVATE);JSONArray a=new JSONArray(prefs.getString("sites","[]"));for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);SiteRecord s=new SiteRecord(o.getString("name"));s.units.clear();JSONArray units=o.getJSONArray("units");for(int j=0;j<units.length();j++){UnitRecord u=new UnitRecord();u.minute=file(units.getJSONObject(j).optJSONObject("minute"));u.uncertain=file(units.getJSONObject(j).optJSONObject("uncertain"));s.units.add(u);}if(s.units.isEmpty())s.units.add(new UnitRecord());sites.add(s);}String last=prefs.getString("output","");if(last.matches("[0-9]{8}_[0-9]{6}_[a-f0-9]{6}")){File dir=new File(new File(getFilesDir(),"reports"),last);if(new File(dir,DocxReports.CHARGE_NAME).isFile()&&new File(dir,DocxReports.OUTAGE_NAME).isFile())outputDir=dir;}if(!sites.isEmpty())message="이전에 등록한 설치장소와 로그를 불러왔습니다.";}catch(Exception e){sites.clear();message="등록 정보를 불러오지 못했습니다: "+e.getMessage();}}
    protected void onDestroy(){worker.shutdown();super.onDestroy();}
}
