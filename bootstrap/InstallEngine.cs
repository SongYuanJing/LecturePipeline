using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace LecturePipeline.Setup;

internal record InstallOptions(string Install, string Data, string Mode, string? ShortcutDirectory = null,
    bool Launch = true, string? SmokeAudio = null);
internal record Update(string Stage, string Message, long Done = 0, long? Total = null);

internal sealed class InstallEngine(Action<Update> report)
{
    static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    public static Stream Resource(string name) => Assembly.GetExecutingAssembly().GetManifestResourceStream(name)
        ?? throw new InvalidOperationException("Missing embedded resource: " + name);
    static string Hash(Stream stream) => Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    static string HashFile(string path) { using var stream = File.OpenRead(path); return Hash(stream); }
    static JsonObject ReadObject(string path) => JsonNode.Parse(File.ReadAllText(path))!.AsObject();
    static void Write(string path, object value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path + ".pending", JsonSerializer.Serialize(value, JsonOptions), new UTF8Encoding(false));
        File.Move(path + ".pending", path, true);
    }
    static bool Within(string path, string parent) => path.Equals(parent, StringComparison.OrdinalIgnoreCase)
        || path.StartsWith(parent + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    internal static string Normalize(string value)
    {
        if (!Path.IsPathFullyQualified(value) || value.StartsWith(@"\\"))
            throw new IOException("Выберите абсолютный путь на локальном диске.");
        var result = Path.TrimEndingDirectorySeparator(Path.GetFullPath(value));
        if (result == Path.GetPathRoot(result)) throw new IOException("Выберите отдельную папку, не корень диска.");
        for (var dir = new DirectoryInfo(result); dir != null; dir = dir.Parent)
            if (dir.Exists && (dir.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Путь через junction/symlink не поддерживается: " + dir.FullName);
        return result;
    }
    internal static string ZipTarget(string root, string entry)
    {
        if (entry.Contains(':') || entry.Contains('\\') || entry.StartsWith('/') || entry.Split('/').Contains(".."))
            throw new IOException("Небезопасное имя в архиве: " + entry);
        var target = Path.GetFullPath(Path.Combine(root, entry.Replace('/', Path.DirectorySeparatorChar)));
        if (!Within(target, root) || target == root) throw new IOException("Путь выходит из staging.");
        return target;
    }
    static Dictionary<string,string> Files(JsonObject manifest) => manifest["files"]!.AsObject()
        .ToDictionary(p => p.Key, p => p.Value!.GetValue<string>(), StringComparer.OrdinalIgnoreCase);
    void Verify(string root, Dictionary<string,string> files, CancellationToken cancel)
    {
        foreach (var (name, hash) in files)
        {
            cancel.ThrowIfCancellationRequested();
            var path = ZipTarget(root, name);
            if (!File.Exists(path) || HashFile(path) != hash) throw new IOException("SHA-256 не совпал: " + name);
        }
    }
    void Extract(Stream stream, string root, CancellationToken cancel)
    {
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
        foreach (var entry in archive.Entries)
        {
            cancel.ThrowIfCancellationRequested();
            if (entry.FullName.EndsWith('/')) continue;
            var path = ZipTarget(root, entry.FullName);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            using var source = entry.Open();
            using var target = File.Create(path);
            source.CopyTo(target);
        }
    }
    async Task<string> DownloadBase(string root, CancellationToken cancel)
    {
        using var resource = Resource("base.json");
        var pin = JsonNode.Parse(resource)!;
        string hash = pin["sha256"]!.GetValue<string>();
        long size = pin["bytes"]!.GetValue<long>();
        var cache = Path.Combine(root, "cache", "bootstrap"); Directory.CreateDirectory(cache);
        var path = Path.Combine(cache, hash + ".zip");
        if (File.Exists(path) && HashFile(path) == hash)
        { report(new("base", "Verified cache: base application/private runtime")); return path; }
        string temporary = path + ".part";
        try
        {
            using var client = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
            client.DefaultRequestHeaders.UserAgent.ParseAdd("LecturePipeline-Setup/1");
            using var headerTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancel);
            headerTimeout.CancelAfter(TimeSpan.FromSeconds(60));
            using var response = await client.GetAsync(pin["url"]!.GetValue<string>(), HttpCompletionOption.ResponseHeadersRead, headerTimeout.Token);
            headerTimeout.CancelAfter(Timeout.InfiniteTimeSpan);
            response.EnsureSuccessStatusCode();
            if (response.RequestMessage!.RequestUri!.Scheme != "https") throw new IOException("Требуется HTTPS.");
            await using var input = await response.Content.ReadAsStreamAsync(cancel);
            await using (var output = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None, 1048576, true))
            {
                var buffer = new byte[1048576]; long done = 0;
                while (true)
                {
                    using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancel);
                    timeout.CancelAfter(TimeSpan.FromSeconds(60));
                    int count = await input.ReadAsync(buffer, timeout.Token);
                    if (count == 0) break;
                    done += count;
                    if (done > size) throw new IOException("Base archive превышает pinned size.");
                    await output.WriteAsync(buffer.AsMemory(0,count), cancel);
                    report(new("base", "Загрузка приложения и private runtime", done, size));
                }
                if (done != size) throw new IOException("Base archive загружен не полностью.");
                await output.FlushAsync(cancel);
            }
            cancel.ThrowIfCancellationRequested();
            if (HashFile(temporary) != hash) throw new IOException("SHA-256 base archive не совпал.");
            File.Move(temporary, path, true);
            report(new("base", "Base archive: SHA-256 verified"));
            return path;
        }
        catch (OperationCanceledException) when (!cancel.IsCancellationRequested)
        { throw new IOException("Сетевой таймаут при загрузке base. Проверенные файлы сохранены; нажмите Retry."); }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }
    async Task Prepare(string root, CancellationToken cancel)
    {
        if (File.Exists(Path.Combine(root,"bootstrap-base-ready.json")))
        {
            report(new("base", "Проверка установленного base runtime…"));
            Verify(root, Files(ReadObject(Path.Combine(root,"package-manifest.json"))), cancel);
            report(new("base", "Base application/private runtime already verified")); return;
        }
        var archive = await DownloadBase(root, cancel);
        var stage = Path.Combine(root,".stage");
        // Only this owned installer root can reach here. Never delete another root.
        if (Directory.Exists(stage)) { Normalize(stage); Directory.Delete(stage,true); }
        Directory.CreateDirectory(stage);
        report(new("extract", "Распаковка и проверка private runtime…"));
        using (var stream = File.OpenRead(archive)) Extract(stream,stage,cancel);
        var manifest = ReadObject(Path.Combine(stage,"package-manifest.json"));
        var files = Files(manifest); Verify(stage,files,cancel);
        using var payloadManifest = Resource("application.json");
        var payload = JsonNode.Parse(payloadManifest)!.AsObject();
        // Remove old application entries from the staged base only. Runtime is unchanged.
        foreach (var name in files.Keys.Where(n => n.StartsWith("versions/") || n.StartsWith("launcher/")).ToArray())
        { File.Delete(ZipTarget(stage,name)); files.Remove(name); }
        using (var source = Resource("application.zip")) Extract(source,stage,cancel);
        foreach (var pair in Files(payload)) files[pair.Key] = pair.Value;
        Verify(stage,files,cancel);
        Write(Path.Combine(stage,"package-manifest.json"),new { manifest_schema_version=1,
            app_version=payload["app_version"]!.GetValue<string>(),files });
        cancel.ThrowIfCancellationRequested();
        report(new("publish", "Публикация проверенного base. Отмена после этого этапа…"));
        // Uninterruptible short boundary. Retry accepts only matching already copied bytes.
        foreach (var name in files.Keys.Append("package-manifest.json"))
        {
            var source = ZipTarget(stage,name); var target = ZipTarget(root,name);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            if (File.Exists(target))
            { if (HashFile(target) != HashFile(source)) throw new IOException("Существующий файл сохранён: " + name); }
            else File.Move(source,target);
        }
        Write(Path.Combine(root,"bootstrap-base-ready.json"),new { verified=true });
        Directory.Delete(stage,true);
    }
    async Task Python(InstallOptions options, string root, string data, CancellationToken cancel)
    {
        var cancelFile = Path.Combine(root,"bootstrap-cancel");
        File.Delete(cancelFile);
        using var registration = cancel.Register(() => File.WriteAllText(cancelFile,"cancel"));
        var start = new ProcessStartInfo(Path.Combine(root,"runtime/asr/python.exe")) {
            UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,
            StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8,WorkingDirectory=root };
        foreach (var arg in new[] { "-B","-X","utf8",Path.Combine(root,"launcher/bootstrap_flow.py"),
            "--data",data,"--mode",options.Mode,"--cancel",cancelFile }) start.ArgumentList.Add(arg);
        if (options.SmokeAudio != null) { start.ArgumentList.Add("--smoke-audio"); start.ArgumentList.Add(options.SmokeAudio); }
        using var process = Process.Start(start) ?? throw new IOException("Не удалось запустить private Python.");
        Directory.CreateDirectory(Path.Combine(root,"logs"));
        using var log = new StreamWriter(Path.Combine(root,"logs/bootstrap-python.log"),true,Encoding.UTF8) { AutoFlush=true };
        var errors = process.StandardError.ReadToEndAsync();
        while (await process.StandardOutput.ReadLineAsync() is string line)
        {
            log.WriteLine(line);
            try
            {
                var item=JsonNode.Parse(line)!;
                report(new(item["stage"]!.GetValue<string>(),item["message"]!.GetValue<string>(),
                    item["downloaded"]?.GetValue<long>() ?? 0,item["total"]?.GetValue<long>()));
            }
            catch (JsonException) { report(new("setup",line)); }
        }
        await process.WaitForExitAsync();
        var error = await errors; log.WriteLine(error);
        if (process.ExitCode == 130 || cancel.IsCancellationRequested) throw new OperationCanceledException(cancel);
        if (process.ExitCode != 0) throw new IOException("Python setup не завершён. См. сообщение выше и logs/bootstrap-python.log. " + error);
    }
    internal static string Shortcut(string root, string? customDirectory)
    {
        var folder = customDirectory ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"Lecture Pipeline");
        Directory.CreateDirectory(folder);
        var id = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(root.ToUpperInvariant())))[..8];
        string path = Path.Combine(folder,"Lecture Pipeline — " + id + ".lnk");
        string target = Path.Combine(root,"runtime","asr","pythonw.exe");
        string arguments = "-B -X utf8 \"" + Path.Combine(root,"launcher/launch.py") + "\" gui";
        if (File.Exists(path))
        {
            using var existing=new ShellShortcut(path);
            if(!string.Equals(existing.Target,target,StringComparison.OrdinalIgnoreCase)
                || existing.Arguments!=arguments || !string.Equals(existing.Directory,root,StringComparison.OrdinalIgnoreCase))
                throw new IOException("Конфликт ярлыка; существующий ярлык сохранён: " + path);
            return path;
        }
        using var link=new ShellShortcut {Target=target,Arguments=arguments,Directory=root};
        string temporary=path+".pending";
        try {link.Save(temporary);File.Move(temporary,path);}
        finally {if(File.Exists(temporary))File.Delete(temporary);}
        return path;
    }
    public async Task<object> Run(InstallOptions options, CancellationToken cancel)
    {
        if (!OperatingSystem.IsWindowsVersionAtLeast(10,0,22000) || System.Runtime.InteropServices.RuntimeInformation.OSArchitecture != System.Runtime.InteropServices.Architecture.X64)
            throw new IOException("Поддерживается Windows 11 x64.");
        string root=Normalize(options.Install),data=Normalize(options.Data);
        if (root.Length > 110) throw new IOException("Выберите более короткий install path (до 110 символов): private Python/model paths имеют ограничение Windows.");
        if (Within(root,data) || Within(data,root)) throw new IOException("Папки установки и данных не должны пересекаться.");
        var stateFile=Path.Combine(root,"bootstrap-state.json");
        using var resource=Resource("application.zip"); string bundle=Hash(resource);
        bool wasReady=false;
        if (Directory.Exists(root) && Directory.EnumerateFileSystemEntries(root).Any())
        {
            if (!File.Exists(stateFile)) throw new IOException("Папка установки не пустая. Выберите новую папку; существующая копия сохранена.");
            var state=ReadObject(stateFile);
            wasReady=state["status"]?.GetValue<string>()=="ready";
            if (state["bundle"]!.GetValue<string>() != bundle || state["data"]!.GetValue<string>() != data)
                throw new IOException("Другая версия или папка данных. Этот Setup не выполняет обновление/миграцию.");
        }
        else if (Directory.Exists(data) && Directory.EnumerateFileSystemEntries(data).Any())
            throw new IOException("Выберите новую пустую папку данных.");
        Directory.CreateDirectory(root); Directory.CreateDirectory(Path.GetDirectoryName(data)!);
        using var installLock=new FileStream(Path.Combine(root,"bootstrap.lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None);
        void State(string status) => Write(stateFile,new { schema_version=1,bundle,data,status });
        State("installing");
        try
        {
            cancel.ThrowIfCancellationRequested();
            await Prepare(root,cancel);
            cancel.ThrowIfCancellationRequested();
            await Python(options,root,data,cancel);
            cancel.ThrowIfCancellationRequested();
            report(new("shortcut","Создание пользовательского ярлыка…"));
            string shortcut=Shortcut(root,options.ShortcutDirectory);
            State("ready");
            int? pid=null;
            if (options.Launch)
            {
                var start=new ProcessStartInfo(Path.Combine(root,"runtime/asr/pythonw.exe")) { UseShellExecute=false,WorkingDirectory=root };
                foreach(var arg in new[]{"-B","-X","utf8",Path.Combine(root,"launcher/launch.py"),"gui"}) start.ArgumentList.Add(arg);
                using var app=Process.Start(start) ?? throw new IOException("Не удалось запустить приложение.");
                pid=app.Id;
                // Confirm a real top-level application window, not merely a created process.
                var timer=Stopwatch.StartNew();
                string expectedTitle="Lecture Pipeline · "+ReadObject(Path.Combine(root,"current.json"))["app_version"]!.GetValue<string>();
                while(timer.Elapsed < TimeSpan.FromSeconds(45))
                { await Task.Delay(250); app.Refresh(); if(app.HasExited) throw new IOException("Приложение завершилось при запуске; см. logs/launch-error.txt."); if(app.MainWindowHandle != IntPtr.Zero && app.MainWindowTitle==expectedTitle) break; }
                if(app.MainWindowHandle==IntPtr.Zero || app.MainWindowTitle!=expectedTitle) throw new IOException("Окно приложения не появилось за 45 секунд; см. logs/launch-error.txt.");
            }
            report(new("ready","Установка завершена. Приложение готово."));
            return new { status="ready",install=root,data,shortcut,application_pid=pid };
        }
        catch(OperationCanceledException) { State(wasReady ? "ready" : "cancelled"); throw; }
        catch { State("failed"); throw; }
    }
}
