package kr.co.batteryreport;

import javax.swing.*;
import javax.swing.border.*;
import javax.swing.filechooser.FileNameExtensionFilter;
import javax.swing.table.*;
import java.awt.*;
import java.awt.event.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;
import java.util.List;
import java.util.concurrent.Callable;
import javax.imageio.ImageIO;

public final class DesktopApp extends JFrame {
    static final Color BACK=new Color(243,246,250),INK=new Color(23,44,66),MUTED=new Color(87,109,131),TEAL=new Color(8,126,139);
    private final DesktopModel model;
    private final JComboBox<DesktopModel.Site> siteBox=new JComboBox<>();
    private final JComboBox<String> unitBox=new JComboBox<>();
    private final DefaultTableModel tableModel=new DefaultTableModel(new String[]{"번호","설치장소","축전지","종류","업로드 파일","크기","상태"},0){public boolean isCellEditable(int r,int c){return false;}};
    private final JTable table=new JTable(tableModel);private final JLabel counts=new JLabel(),lastReport=new JLabel();
    private final JTextArea message=new JTextArea(3,40);private final JProgressBar progress=new JProgressBar();
    private final List<JButton> buttons=new ArrayList<>();private JButton upload,generate,openFolder,openCharge,openOutage;
    private boolean busy,binding;
    private File chooserDir;
    private static FileLock instanceLock;private static FileChannel instanceChannel;
    public DesktopApp(DesktopModel model){
        super("축전지 로그 보고서 · Windows 64비트");this.model=model;
        setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);addWindowListener(new WindowAdapter(){public void windowClosing(WindowEvent e){if(busy){JOptionPane.showMessageDialog(DesktopApp.this,"진행 중인 작업이 끝난 뒤 닫아 주세요.");return;}dispose();releaseLock();}});
        Rectangle desktop=GraphicsEnvironment.getLocalGraphicsEnvironment().getMaximumWindowBounds();setMinimumSize(new Dimension(Math.min(960,desktop.width),Math.min(720,desktop.height)));setSize(Math.min(1100,desktop.width),Math.min(820,desktop.height));setLocationRelativeTo(null);setIconImage(icon());
        JPanel root=new JPanel(new BorderLayout(0,16));root.setBackground(BACK);root.setBorder(new EmptyBorder(22,26,22,26));setContentPane(root);
        JPanel heading=new JPanel();heading.setOpaque(false);heading.setLayout(new BoxLayout(heading,BoxLayout.Y_AXIS));
        JLabel eyebrow=label("BATTERY LOG REPORT  /  WINDOWS x64",12,TEAL,true);heading.add(eyebrow);
        heading.add(label("축전지 로그 보고서",28,INK,true));heading.add(label("설치장소별 로그를 업로드하고 Word 보고서 2개를 생성합니다.",14,MUTED,false));root.add(heading,BorderLayout.NORTH);
        JPanel content=new JPanel();content.setOpaque(false);content.setLayout(new BoxLayout(content,BoxLayout.Y_AXIS));root.add(content,BorderLayout.CENTER);
        JPanel status=card("업로드 상황");status.setLayout(new BorderLayout(8,8));JPanel statusHead=new JPanel(new BorderLayout());statusHead.setOpaque(false);statusHead.add(label("업로드 상황",18,INK,true),BorderLayout.WEST);statusHead.add(counts,BorderLayout.EAST);status.add(statusHead,BorderLayout.NORTH);
        table.setRowHeight(31);table.setFillsViewportHeight(true);table.setShowGrid(false);table.setIntercellSpacing(new Dimension(0,0));table.getTableHeader().setFont(new Font("Malgun Gothic",Font.BOLD,13));table.getTableHeader().setPreferredSize(new Dimension(0,34));table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);table.setAutoCreateRowSorter(true);
        int[] widths={45,130,75,90,300,90,90};for(int i=0;i<widths.length;i++)table.getColumnModel().getColumn(i).setPreferredWidth(widths[i]);
        JScrollPane tableScroll=new JScrollPane(table);tableScroll.setColumnHeaderView(table.getTableHeader());tableScroll.setPreferredSize(new Dimension(850,220));tableScroll.setBorder(BorderFactory.createLineBorder(new Color(225,232,239)));status.add(tableScroll);content.add(status);content.add(Box.createVerticalStrut(14));
        JPanel form=card("설치장소 · 로그파일");form.setLayout(new BoxLayout(form,BoxLayout.Y_AXIS));form.add(label("01  설치장소 · 축전지 선택",16,INK,true));
        JPanel sitesLine=row();sitesLine.add(label("설치장소",13,INK,true));siteBox.setPreferredSize(new Dimension(260,34));sitesLine.add(siteBox);sitesLine.add(button("+ 설치장소 추가",false,()->siteDialog(false)));sitesLine.add(button("이름 변경",false,()->siteDialog(true)));sitesLine.add(button("설치장소 삭제",false,this::removeSite));form.add(sitesLine);
        JPanel unitsLine=row();unitsLine.add(label("축전지 호기",13,INK,true));unitBox.setPreferredSize(new Dimension(245,34));unitsLine.add(unitBox);unitsLine.add(button("+ 같은 장소에 축전지 추가",false,this::addUnit));unitsLine.add(button("선택 호기 로그 삭제",false,this::clearUnit));form.add(unitsLine);
        JPanel uploadLine=row();upload=button("로그파일 업로드",true,this::chooseFiles);upload.setPreferredSize(new Dimension(190,42));uploadLine.add(upload);uploadLine.add(label("ZIP 한 개 또는 여러 개 선택 · 같은 호기에 추가 업로드 가능",13,MUTED,false));form.add(uploadLine);
        form.add(label("minute + uncertain 한 쌍 = 1식. 같은 종류가 여러 개면 선택한 호기부터 순서대로 배정됩니다.",12,MUTED,false));content.add(form);
        JPanel bottom=card("보고서 생성");bottom.setLayout(new BoxLayout(bottom,BoxLayout.Y_AXIS));JPanel action=row();generate=button("보고서 생성",true,this::chooseOutput);generate.setPreferredSize(new Dimension(190,44));action.add(generate);openFolder=button("저장 폴더 열기",false,()->open(model.lastOutput));action.add(openFolder);openCharge=button("충·방전 보고서 열기",false,()->open(new File(model.lastOutput,DocxReports.CHARGE_NAME)));action.add(openCharge);openOutage=button("AC 정전 보고서 열기",false,()->open(new File(model.lastOutput,DocxReports.OUTAGE_NAME)));action.add(openOutage);bottom.add(action);
        lastReport.setForeground(MUTED);lastReport.setBorder(new EmptyBorder(3,5,5,5));bottom.add(lastReport);
        progress.setVisible(false);progress.setPreferredSize(new Dimension(600,7));progress.setMaximumSize(new Dimension(Integer.MAX_VALUE,7));bottom.add(progress);
        message.setEditable(false);message.setOpaque(false);message.setLineWrap(true);message.setWrapStyleWord(true);message.setForeground(MUTED);message.setBorder(new EmptyBorder(7,5,0,5));JScrollPane messages=new JScrollPane(message);messages.setBorder(null);messages.setOpaque(false);messages.getViewport().setOpaque(false);messages.setPreferredSize(new Dimension(800,66));bottom.add(messages);root.add(bottom,BorderLayout.SOUTH);
        siteBox.addActionListener(e->{if(!binding)refreshUnits();});
        setMessage("설치장소를 추가하고 ZIP 로그를 선택해 주세요. 보고서 생성 시 저장 폴더를 선택합니다.");refresh();
    }
    private static JLabel label(String s,int size,Color color,boolean bold){JLabel l=new JLabel(s);l.setFont(new Font("Malgun Gothic",bold?Font.BOLD:Font.PLAIN,size));l.setForeground(color);l.setBorder(new EmptyBorder(3,0,5,0));return l;}
    private static JPanel card(String title){JPanel p=new JPanel();p.setAlignmentX(Component.LEFT_ALIGNMENT);p.setBackground(Color.WHITE);p.setBorder(new CompoundBorder(BorderFactory.createLineBorder(new Color(227,234,241)),new EmptyBorder(12,16,12,16)));return p;}
    private static JPanel row(){JPanel p=new JPanel(new FlowLayout(FlowLayout.LEFT,8,5));p.setOpaque(false);p.setAlignmentX(Component.LEFT_ALIGNMENT);return p;}
    private JButton button(String text,boolean primary,Runnable run){JButton b=new JButton(text);b.setFocusPainted(false);b.setFont(new Font("Malgun Gothic",Font.BOLD,13));b.setForeground(primary?Color.WHITE:TEAL);b.setBackground(primary?TEAL:new Color(231,243,244));b.setOpaque(true);b.setBorder(new CompoundBorder(BorderFactory.createLineBorder(primary?TEAL:new Color(212,231,233)),new EmptyBorder(8,13,8,13)));b.addActionListener(e->{if(!busy)run.run();});buttons.add(b);return b;}
    private DesktopModel.Site site(){return (DesktopModel.Site)siteBox.getSelectedItem();}
    private void refresh(){DesktopModel.Site selected=site();binding=true;siteBox.removeAllItems();for(DesktopModel.Site s:model.sites)siteBox.addItem(s);if(selected!=null&&model.sites.contains(selected))siteBox.setSelectedItem(selected);binding=false;refreshUnits();tableModel.setRowCount(0);
        int n=0;for(DesktopModel.Site s:model.sites){n++;for(int i=0;i<s.units.size();i++){DesktopModel.Unit u=s.units.get(i);if(!u.populated())tableModel.addRow(new Object[]{n,s.name,(i+1)+"호","—","아직 등록된 로그가 없습니다.","—","대기"});else for(DesktopModel.Input input:new DesktopModel.Input[]{u.minute,u.uncertain})if(input!=null)tableModel.addRow(new Object[]{n,s.name,(i+1)+"호",input.kind,input.name,DesktopModel.size(input.size),"등록 완료"});}}
        counts.setText(model.sites.size()+"개 장소  ·  "+model.unitCount()+"식  ·  "+model.fileCount()+"개 파일");counts.setForeground(TEAL);enabled();
    }
    private void refreshUnits(){int selected=unitBox.getSelectedIndex();unitBox.removeAllItems();if(site()!=null)for(int i=0;i<site().units.size();i++){DesktopModel.Unit u=site().units.get(i);unitBox.addItem((i+1)+"호 축전지 · "+(u.minute!=null&&u.uncertain!=null?"2개 등록":u.populated()?"1개 등록":"대기"));}if(unitBox.getItemCount()>0)unitBox.setSelectedIndex(Math.max(0,Math.min(selected,unitBox.getItemCount()-1)));enabled();}
    private void enabled(){for(JButton b:buttons)b.setEnabled(!busy);siteBox.setEnabled(!busy);unitBox.setEnabled(!busy&&site()!=null);if(upload!=null)upload.setEnabled(!busy&&site()!=null);if(generate!=null)generate.setEnabled(!busy&&model.fileCount()>0);boolean output=model.lastOutput!=null;if(openFolder!=null){openFolder.setEnabled(!busy&&output);openCharge.setEnabled(!busy&&output);openOutage.setEnabled(!busy&&output);}lastReport.setText(output?(model.changed?"로그 변경됨 · 보고서 생성을 다시 눌러 주세요. 최근 보고서: ":"최근 보고서: ")+model.lastOutput.getName():"두 보고서는 새 폴더에 저장됩니다. 이전 보고서는 덮어쓰지 않습니다.");}
    private void setMessage(String text){message.setText(text);message.setCaretPosition(0);}
    private void fail(Throwable e){setMessage("오류: "+(e.getMessage()==null?e.toString():e.getMessage()));JOptionPane.showMessageDialog(this,message.getText(),"작업 확인",JOptionPane.WARNING_MESSAGE);}
    private void siteDialog(boolean edit){if(edit&&site()==null)return;String name=(String)JOptionPane.showInputDialog(this,"설치장소를 입력해 주세요. 예: 용인외사",edit?"설치장소 이름 변경":"설치장소 추가",JOptionPane.PLAIN_MESSAGE,null,null,edit?site().name:"");if(name==null)return;try{DesktopModel.Site target=edit?site():model.addSite(name);if(edit)model.rename(target,name);refresh();siteBox.setSelectedItem(target);}catch(Exception e){fail(e);}}
    private void addUnit(){if(site()==null)return;try{site().units.add(new DesktopModel.Unit());model.changed=true;model.save();refresh();unitBox.setSelectedIndex(site().units.size()-1);}catch(Exception e){fail(e);}}
    private void clearUnit(){if(site()==null||unitBox.getSelectedIndex()<0)return;if(JOptionPane.showConfirmDialog(this,"선택한 호기의 등록 로그를 삭제할까요?\n이미 생성한 보고서는 유지됩니다.","호기 로그 삭제",JOptionPane.OK_CANCEL_OPTION)!=JOptionPane.OK_OPTION)return;try{model.clearUnit(site(),unitBox.getSelectedIndex());refresh();}catch(Exception e){fail(e);}}
    private void removeSite(){if(site()==null)return;if(JOptionPane.showConfirmDialog(this,"설치장소 '"+site().name+"'의 등록 목록을 삭제할까요?\n원본 ZIP과 생성한 보고서는 유지됩니다.","설치장소 삭제",JOptionPane.OK_CANCEL_OPTION)!=JOptionPane.OK_OPTION)return;try{model.sites.remove(site());model.changed=true;model.save();refresh();}catch(Exception e){fail(e);}}
    private JFileChooser chooser(String title){JFileChooser c=new JFileChooser(chooserDir);c.setDialogTitle(title);return c;}
    private void chooseFiles(){if(site()==null)return;JFileChooser c=chooser("로그파일 업로드 (여러 파일 선택 가능)");c.setMultiSelectionEnabled(true);c.setAcceptAllFileFilterUsed(false);c.setFileFilter(new FileNameExtensionFilter("축전지 로그 ZIP (*.zip)","zip"));if(c.showOpenDialog(this)!=JFileChooser.APPROVE_OPTION)return;File[] files=c.getSelectedFiles();if(files.length==0&&c.getSelectedFile()!=null)files=new File[]{c.getSelectedFile()};if(files.length==0)return;chooserDir=c.getCurrentDirectory();final File[] selected=files;final DesktopModel.Site target=site();final int unit=unitBox.getSelectedIndex();
        work("로그파일을 읽고 확인하는 중입니다…",()->{DesktopModel.ImportResult result=model.importFiles(target,unit,selected);return result.accepted+"개 업로드 완료"+(result.duplicates>0?"\n동일 내용 "+result.duplicates+"개를 별도 호기로 등록했습니다. 실제 장비 구분을 확인해 주세요.":"")+(result.errors.isEmpty()?"":"\n실패 "+result.errors.size()+"개\n"+String.join("\n",result.errors));});
    }
    private void chooseOutput(){JFileChooser c=chooser("보고서 2개를 저장할 폴더 선택");c.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);c.setAcceptAllFileFilterUsed(false);if(c.showSaveDialog(this)!=JFileChooser.APPROVE_OPTION)return;File parent=c.getSelectedFile();chooserDir=parent;work("전체 로그 분석 및 Word 보고서 2개 생성 중입니다…",()->"보고서 2개 생성 완료\n저장 위치: "+model.generate(parent).getAbsolutePath());}
    private void work(String title,Callable<String> action){busy=true;enabled();progress.setVisible(true);progress.setIndeterminate(true);setMessage(title);new SwingWorker<String,Void>(){protected String doInBackground()throws Exception{return action.call();}protected void done(){busy=false;progress.setIndeterminate(false);progress.setVisible(false);refresh();try{setMessage(get());}catch(Exception ex){fail(ex.getCause()==null?ex:ex.getCause());}}}.execute();}
    private void open(File file){if(file==null)return;try{Desktop.getDesktop().open(file);}catch(Exception ex){fail(new IOException("파일을 열 수 없습니다. Word 문서를 열 수 있는 프로그램을 확인해 주세요.\n"+file.getAbsolutePath(),ex));}}
    static BufferedImage icon(){BufferedImage image=new BufferedImage(64,64,BufferedImage.TYPE_INT_ARGB);Graphics2D g=image.createGraphics();g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);g.setColor(TEAL);g.fillRoundRect(1,1,62,62,16,16);g.setColor(Color.WHITE);g.setStroke(new BasicStroke(4));g.drawRoundRect(13,21,35,25,4,4);g.fillRect(49,28,5,11);g.fillRect(19,27,7,13);g.fillRect(30,27,7,13);g.dispose();return image;}
    private static void releaseLock(){try{if(instanceLock!=null)instanceLock.release();if(instanceChannel!=null)instanceChannel.close();}catch(IOException ignored){}}
    public static void main(String[] args)throws Exception{
        if(args.length>0&&args[0].equals("--self-test")){DesktopSelfTest.run(new File(args[1]));return;}
        if(args.length>0&&args[0].equals("--render-ui")){renderForTest(new File(args[1]));return;}
        if(!System.getProperty("os.arch","").contains("64")){JOptionPane.showMessageDialog(null,"이 프로그램은 Windows 64비트 전용입니다.");return;}
        UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName());installFonts();
        String base=System.getenv("LOCALAPPDATA");if(base==null)base=System.getProperty("user.home");File home=new File(System.getProperty("batteryreport.data",new File(base,"BatteryLogReport").getPath()));
        DesktopModel model=new DesktopModel(home);instanceChannel=new RandomAccessFile(new File(home,"app.lock"),"rw").getChannel();instanceLock=instanceChannel.tryLock();if(instanceLock==null){JOptionPane.showMessageDialog(null,"축전지 로그 보고서 프로그램이 이미 실행 중입니다.");instanceChannel.close();return;}
        try{model.load();}catch(Exception e){releaseLock();JOptionPane.showMessageDialog(null,e.getMessage(),"등록 정보 확인",JOptionPane.ERROR_MESSAGE);return;}
        Runtime.getRuntime().addShutdownHook(new Thread(DesktopApp::releaseLock));SwingUtilities.invokeLater(()->new DesktopApp(model).setVisible(true));
    }
    private static void installFonts(){Font f=new Font("Malgun Gothic",Font.PLAIN,13);Enumeration<Object> keys=UIManager.getDefaults().keys();while(keys.hasMoreElements()){Object key=keys.nextElement();if(UIManager.get(key) instanceof javax.swing.plaf.FontUIResource)UIManager.put(key,new javax.swing.plaf.FontUIResource(f));}}
    private static void renderForTest(File project)throws Exception{
        UIManager.setLookAndFeel(UIManager.getCrossPlatformLookAndFeelClassName());installFonts();DesktopModel model=new DesktopModel(new File(project,"qa/windows-ui-session"));model.load();if(model.sites.isEmpty()){DesktopModel.Site s=model.addSite("용인외사");model.importFiles(s,0,new File[]{new File(project,"references/perfmg_minute.zip"),new File(project,"references/perfmg_uncertain.zip")});}
        SwingUtilities.invokeAndWait(()->{try{DesktopApp app=new DesktopApp(model);Container content=app.getContentPane();content.setSize(1100,820);layoutTree(content);BufferedImage image=new BufferedImage(1100,820,BufferedImage.TYPE_INT_RGB);Graphics2D g=image.createGraphics();content.printAll(g);g.dispose();if((image.getRGB(30,30)&0xffffff)==0)throw new IOException("UI render is blank");ImageIO.write(image,"png",new File(project,"qa/windows-ui.png"));app.dispose();}catch(Exception e){throw new RuntimeException(e);}});
    }
    private static void layoutTree(Container c){c.doLayout();for(Component child:c.getComponents())if(child instanceof Container)layoutTree((Container)child);}
}
