package kr.co.batteryreport;
import java.awt.*;
import java.awt.image.*;
import java.io.*;
import javax.imageio.ImageIO;
public final class DesktopPainter implements ReportImages.Painter {
    BufferedImage image;Graphics2D g;
    public void begin(int w,int h){if(g!=null)g.dispose();image=new BufferedImage(w,h,BufferedImage.TYPE_INT_RGB);g=image.createGraphics();g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);}
    public void rect(float x,float y,float w,float h,int c){g.setColor(new Color(c,true));g.fill(new java.awt.geom.Rectangle2D.Float(x,y,w,h));}
    public void line(float x,float y,float xx,float yy,int c,float width){g.setColor(new Color(c,true));g.setStroke(new BasicStroke(width));g.draw(new java.awt.geom.Line2D.Float(x,y,xx,yy));}
    public void text(String s,float x,float y,float size,int c,boolean bold){g.setColor(new Color(c,true));g.setFont(new Font("Malgun Gothic",bold?Font.BOLD:Font.PLAIN,(int)size));g.drawString(s,x,y);}
    public byte[] png()throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();ImageIO.write(image,"png",out);return out.toByteArray();}
}
