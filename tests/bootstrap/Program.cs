using LecturePipeline.Setup;
using System.Text.Json.Nodes;

var folder=Path.Combine(Path.GetTempPath(),"lp-bootstrap-tests-"+Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(folder);int tests=0;
void Check(bool result) {if(!result)throw new Exception("Assertion failed");tests++;}
async Task Reject(Func<Task> action)
{try{await action();}catch(IOException){tests++;return;}throw new Exception("Expected rejection");}
try
{
    foreach(var name in new[]{"../escape","/absolute","C:/absolute","folder/../../escape",@"folder\escape"})
        await Reject(()=>{InstallEngine.ZipTarget(folder,name);return Task.CompletedTask;});
    Check(InstallEngine.ZipTarget(folder,"目录/a file")==Path.Combine(folder,"目录","a file"));
    Check(InstallEngine.Normalize(Path.Combine(folder,"Программа 课程"))==Path.Combine(folder,"Программа 课程"));
    await Reject(()=>{InstallEngine.Normalize("relative");return Task.CompletedTask;});
    var engine=new InstallEngine(_=>{});
    await Reject(()=>engine.Run(new(folder,Path.Combine(folder,"data"),"auto"),CancellationToken.None));
    var old=Path.Combine(folder,"existing");Directory.CreateDirectory(old);File.WriteAllText(Path.Combine(old,"keep"),"untouched");
    await Reject(()=>engine.Run(new(old,Path.Combine(folder,"data"),"auto"),CancellationToken.None));
    Check(File.ReadAllText(Path.Combine(old,"keep"))=="untouched");
    var fresh=Path.Combine(folder,"cancel");var cancel=new CancellationTokenSource();cancel.Cancel();
    try{await engine.Run(new(fresh,Path.Combine(folder,"fresh-data"),"auto"),cancel.Token);throw new Exception("Expected cancel");}catch(OperationCanceledException){tests++;}
    Check(JsonNode.Parse(File.ReadAllText(Path.Combine(fresh,"bootstrap-state.json")))!["status"]!.GetValue<string>()=="cancelled");
    Check(!File.Exists(Path.Combine(fresh,"current.json")));
    Check(!Directory.EnumerateFiles(fresh,"*.part",SearchOption.AllDirectories).Any());
    var statePath=Path.Combine(fresh,"bootstrap-state.json");var state=JsonNode.Parse(File.ReadAllText(statePath))!;state["status"]="ready";File.WriteAllText(statePath,state.ToJsonString());
    try{await engine.Run(new(fresh,Path.Combine(folder,"fresh-data"),"auto"),cancel.Token);throw new Exception("Expected cancel");}catch(OperationCanceledException){tests++;}
    Check(JsonNode.Parse(File.ReadAllText(statePath))!["status"]!.GetValue<string>()=="ready");
    Console.WriteLine($"{tests} bootstrap assertions passed");
    if(args.Length==2 && args[0]=="--screenshot")
    {
        var thread=new Thread(()=>{
            Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
            Application.EnableVisualStyles();
            using var form=new SetupForm(new Dictionary<string,string>{["--install"]=Path.Combine(folder,"Программа 课程"),["--data"]=Path.Combine(folder,"Данные 课程")});
            form.Shown+=(_,_)=>{using var bitmap=new System.Drawing.Bitmap(form.Width,form.Height);form.DrawToBitmap(bitmap,form.ClientRectangle with { Width=form.Width,Height=form.Height });bitmap.Save(args[1]);form.Close();};
            Application.Run(form);
        });
        thread.SetApartmentState(ApartmentState.STA);thread.Start();thread.Join();
    }
}
finally
{
    // Only the exact new temporary directory created above, never an input path.
    if(Path.GetDirectoryName(folder)==Path.TrimEndingDirectorySeparator(Path.GetTempPath()))Directory.Delete(folder,true);
}
