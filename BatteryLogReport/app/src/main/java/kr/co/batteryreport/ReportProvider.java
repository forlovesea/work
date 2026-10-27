package kr.co.batteryreport;
import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;
/** Read-only, temporary URI grants; no external storage permission required. */
public final class ReportProvider extends ContentProvider {
    public boolean onCreate(){return true;}
    private File resolve(Uri u)throws FileNotFoundException{
        try{File root=new File(getContext().getFilesDir(),"reports").getCanonicalFile();File f=new File(root,u.getPath().replaceFirst("^/","")).getCanonicalFile();
            if(!f.getPath().startsWith(root.getPath()+File.separator)||!f.isFile()||!f.getName().endsWith(".docx"))throw new FileNotFoundException();return f;
        }catch(IOException e){throw new FileNotFoundException("보고서 파일을 찾을 수 없습니다.");}
    }
    public static Uri uri(File folder,String name){return new Uri.Builder().scheme("content").authority("kr.co.batteryreport.files").appendPath(folder.getName()).appendPath(name).build();}
    public String getType(Uri uri){return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";}
    public Cursor query(Uri u,String[] projection,String selection,String[] args,String sort){try{File f=resolve(u);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor c=new MatrixCursor(cols);Object[] row=new Object[cols.length];for(int i=0;i<cols.length;i++)row[i]=cols[i].equals(OpenableColumns.DISPLAY_NAME)?f.getName():cols[i].equals(OpenableColumns.SIZE)?f.length():null;c.addRow(row);return c;}catch(FileNotFoundException e){return null;}}
    public ParcelFileDescriptor openFile(Uri u,String mode)throws FileNotFoundException{if(!mode.equals("r"))throw new FileNotFoundException("읽기 전용");return ParcelFileDescriptor.open(resolve(u),ParcelFileDescriptor.MODE_READ_ONLY);}
    public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    public int update(Uri u,ContentValues v,String w,String[] a){throw new UnsupportedOperationException();}
    public int delete(Uri u,String w,String[] a){throw new UnsupportedOperationException();}
}
