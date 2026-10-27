package kr.co.batteryreport;
import android.graphics.*;
import java.io.*;
public final class AndroidPainter implements ReportImages.Painter {
    private Bitmap bitmap;private Canvas canvas;private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    public void begin(int w,int h){if(bitmap!=null)bitmap.recycle();bitmap=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);canvas=new Canvas(bitmap);}
    public void rect(float x,float y,float w,float h,int c){paint.setColor(c);paint.setStyle(Paint.Style.FILL);canvas.drawRect(x,y,x+w,y+h,paint);}
    public void line(float x,float y,float xx,float yy,int c,float width){paint.setColor(c);paint.setStrokeWidth(width);canvas.drawLine(x,y,xx,yy,paint);}
    public void text(String s,float x,float y,float size,int c,boolean bold){paint.setColor(c);paint.setTextSize(size);paint.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));canvas.drawText(s,x,y,paint);}
    public byte[] png()throws IOException{ByteArrayOutputStream b=new ByteArrayOutputStream();if(!bitmap.compress(Bitmap.CompressFormat.PNG,100,b))throw new IOException("그래프 이미지 생성 실패");return b.toByteArray();}
}
