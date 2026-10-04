using System.Text.Json;
using System.Diagnostics;
namespace LecturePipeline.Setup;
internal static class Program
{
    [STAThread] static int Main(string[] argv)
    {
        ApplicationConfiguration.Initialize();
        var args=new Dictionary<string,string>();
        for(int i=0;i<argv.Length;i++) {var key=argv[i];if(!key.StartsWith("--"))return 2;args[key]=i+1<argv.Length&&!argv[i+1].StartsWith("--")?argv[++i]:"true";}
        using var form=new SetupForm(args);Application.Run(form);return form.ExitCode;
    }
}
internal sealed class SetupForm:Form
{
    readonly TextBox install=new(){Dock=DockStyle.Fill},data=new(){Dock=DockStyle.Fill};
    readonly ComboBox mode=new(){DropDownStyle=ComboBoxStyle.DropDownList,Width=160};
    readonly Label stage=new(){AutoSize=true,MaximumSize=new Size(670,0),Text="Готово к установке"};
    readonly ProgressBar progress=new(){Dock=DockStyle.Fill};
    readonly TextBox log=new(){Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,Dock=DockStyle.Fill};
    readonly Button start=new(){Text="Установить",AutoSize=true},cancel=new(){Text="Cancel",Enabled=false,AutoSize=true},advanced=new(){Text="Offline / manual import…",AutoSize=true};
    readonly Dictionary<string,string> args;
    CancellationTokenSource? cancellation;bool running;public int ExitCode{get;private set;}
    public SetupForm(Dictionary<string,string> arguments)
    {
        SuspendLayout();args=arguments;Text="Lecture Pipeline — Setup";ClientSize=new Size(740,540);MinimumSize=new Size(680,540);StartPosition=FormStartPosition.CenterScreen;AutoScaleMode=AutoScaleMode.Dpi;Font=new Font("Segoe UI",10);
        install.Text=args.GetValueOrDefault("--install",Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","LecturePipeline"));
        data.Text=args.GetValueOrDefault("--data",Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),"Lecture Pipeline Data"));
        mode.Items.AddRange(["Auto","CPU","GPU"]);mode.SelectedIndex=Array.IndexOf(new[]{"auto","cpu","gpu"},args.GetValueOrDefault("--mode","auto"));if(mode.SelectedIndex<0)mode.SelectedIndex=0;
        var layout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(20),ColumnCount=1,RowCount=9};layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
        for(int i=0;i<6;i++)layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,30));layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.Controls.Add(new Label{Text="Lecture Pipeline · Windows 11 x64",AutoSize=true,Font=new Font(Font,FontStyle.Bold)});
        layout.Controls.Add(new Label{Text="Приложение и необходимые компоненты загрузятся автоматически.\nМодель и GPU: около 4,4 ГБ загрузки; оставьте 15 ГБ свободного места.",AutoSize=true,MaximumSize=new Size(660,0),Margin=new Padding(3,8,3,12)});
        layout.Controls.Add(LocationRow("Установка",install));layout.Controls.Add(LocationRow("Данные",data));
        var choice=new FlowLayoutPanel{AutoSize=true,Dock=DockStyle.Fill};choice.Controls.Add(new Label{Text="Режим ASR",AutoSize=true,Padding=new Padding(0,5,8,0)});choice.Controls.Add(mode);choice.Controls.Add(new Label{Text="Auto: видеокарта только после проверки",AutoSize=true,Padding=new Padding(8,5,0,0)});layout.Controls.Add(choice);
        layout.Controls.Add(stage);layout.Controls.Add(progress);layout.Controls.Add(log);
        var buttons=new FlowLayoutPanel{AutoSize=true,Dock=DockStyle.Fill,FlowDirection=FlowDirection.RightToLeft};buttons.Controls.Add(start);buttons.Controls.Add(cancel);buttons.Controls.Add(advanced);layout.Controls.Add(buttons);Controls.Add(layout);
        start.Click+=async(_,_)=>await Run();cancel.Click+=(_,_)=>RequestCancel();
        advanced.Click+=(_,_)=>{if(Directory.Exists(install.Text))Process.Start(new ProcessStartInfo("explorer.exe"){ArgumentList={install.Text},UseShellExecute=true});MessageBox.Show(this,"В папке установки доступны ImportPyAV.cmd, ImportCTranslate2.cmd, ImportModel.cmd, ImportCUDA.cmd с проверкой pinned SHA-256. После импорта нажмите Retry.","Offline / advanced");};
        FormClosing+=(_,e)=>{if(running){e.Cancel=true;RequestCancel();}};
        Shown+=async(_,_)=>{if(args.TryGetValue("--startup-report",out var path)){File.WriteAllText(path,JsonSerializer.Serialize(new{framework=System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}));Close();}else if(args.ContainsKey("--run"))await Run();};AutoScaleDimensions=new SizeF(96,96);ResumeLayout(true);
    }
    Control LocationRow(string title,TextBox box)
    {
        var row=new TableLayoutPanel{ColumnCount=3,Dock=DockStyle.Fill,AutoSize=true,Margin=new Padding(0,4,0,4)};row.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,90));row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));row.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));row.Controls.Add(new Label{Text=title,AutoSize=true,Padding=new Padding(0,5,0,0)});row.Controls.Add(box);
        var browse=new Button{Text="Обзор…",AutoSize=true};row.Controls.Add(browse);browse.Click+=(_,_)=>{if(running)return;using var dialog=new FolderBrowserDialog{InitialDirectory=Directory.Exists(box.Text)?box.Text:Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)};if(dialog.ShowDialog(this)==DialogResult.OK)box.Text=dialog.SelectedPath;};return row;
    }
    void RequestCancel(){cancellation?.Cancel();cancel.Enabled=false;stage.Text="Отмена запрошена. Ожидание безопасной границы…";}
    void Display(Update value)
    {
        if(IsDisposed)return;if(InvokeRequired){BeginInvoke(()=>Display(value));return;}stage.Text=value.Message;
        if(value.Total>0){progress.Style=ProgressBarStyle.Continuous;progress.Value=(int)Math.Clamp(value.Done*100/value.Total.Value,0,100);}else progress.Style=ProgressBarStyle.Marquee;
        if(value.Done==0)log.AppendText(value.Message+Environment.NewLine);
    }
    async Task Run()
    {
        if(running)return;running=true;start.Enabled=false;cancel.Enabled=true;advanced.Enabled=false;install.Enabled=data.Enabled=mode.Enabled=false;cancellation=new();ExitCode=1;
        var options=new InstallOptions(install.Text,data.Text,mode.Text.ToLowerInvariant(),args.GetValueOrDefault("--shortcut-directory"),!args.ContainsKey("--no-launch"),args.GetValueOrDefault("--smoke-audio"));
        using var timer=new System.Windows.Forms.Timer();if(args.TryGetValue("--cancel-after-ms",out var delay)){timer.Interval=int.Parse(delay);timer.Tick+=(_,_)=>{timer.Stop();RequestCancel();};timer.Start();}
        object result;
        try{result=await Task.Run(()=>new InstallEngine(Display).Run(options,cancellation.Token));ExitCode=0;start.Text="Готово";}
        catch(OperationCanceledException){ExitCode=130;stage.Text="Отменено. Проверенные файлы сохранены. Нажмите Retry.";log.AppendText(stage.Text+Environment.NewLine);result=new{status="cancelled"};start.Text="Retry";}
        catch(Exception error){var message=error is UnauthorizedAccessException?"Недостаточно прав. Выберите папку своего пользователя; admin автоматически не запрашивается. "+error.Message:error.Message;stage.Text="Установка не завершена";log.AppendText(message+Environment.NewLine);result=new{status="failed",error=message};start.Text="Retry";}
        finally{running=false;timer.Stop();cancellation.Dispose();cancel.Enabled=false;advanced.Enabled=true;install.Enabled=data.Enabled=mode.Enabled=true;progress.Style=ProgressBarStyle.Continuous;}
        if(args.TryGetValue("--report",out var report))File.WriteAllText(report,JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));
        if(args.ContainsKey("--run"))Close();else if(ExitCode!=0)start.Enabled=true;
    }
}

