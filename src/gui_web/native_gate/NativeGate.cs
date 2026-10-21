// Disposable visual gate only. No production launcher integration or pipeline commands.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

[assembly: TargetFramework(".NETFramework,Version=v4.8")]

public sealed class NativeGate : Form
{
    [DllImport("user32.dll")] static extern uint GetDpiForWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern IntPtr GetWindowDpiAwarenessContext(IntPtr hwnd);
    [DllImport("user32.dll")] static extern int GetAwarenessFromDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll", SetLastError = true)] static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    readonly WebView2 view = new WebView2();
    readonly Label facts = new Label();
    readonly string output, profile;
    readonly Uri origin;
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    readonly List<object> events = new List<object>();
    readonly List<string> blockedRequests = new List<string>();
    string runtime = "initializing";
    int captureIndex;

    [STAThread]
    public static void Main(string[] args)
    {
        SetProcessDpiAwarenessContext(new IntPtr(-4)); // PMv2, before any HWND exists.
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (args.Length != 3) throw new ArgumentException("Expected loopback URL, owned output and profile directories");
        Uri url = new Uri(args[0]);
        if (url.Scheme != "http" || url.Host != "127.0.0.1") throw new ArgumentException("Loopback HTTP only");
        Application.Run(new NativeGate(url, Path.GetFullPath(args[1]), Path.GetFullPath(args[2])));
    }

    NativeGate(Uri url, string outputDirectory, string profileDirectory)
    {
        origin = url; output = outputDirectory; profile = profileDirectory;
        Directory.CreateDirectory(output);
        Text = "VIC-28 Preview 2 | WebView2 DEV gate";
        Font = new Font("Segoe UI", 10F);
        AutoScaleMode = AutoScaleMode.Dpi;
        AutoScaleDimensions = new SizeF(96F, 96F);
        MinimumSize = new Size(700, 480);
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(1400, 920);
        WindowState = FormWindowState.Maximized;
        var tools = new FlowLayoutPanel { Dock = DockStyle.Top, AutoSize = true, Padding = new Padding(8), WrapContents = true };
        var zoom = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 150, AccessibleName = "Масштаб содержимого" };
        zoom.Items.AddRange(new object[] { "Контент 100%", "Контент 125%", "Контент 150%", "Контент 200%" });
        zoom.SelectedIndex = 0;
        zoom.SelectedIndexChanged += delegate { if (view.CoreWebView2 != null) { view.ZoomFactor = new double[] { 1, 1.25, 1.5, 2 }[zoom.SelectedIndex]; Record("content_zoom", view.ZoomFactor); UpdateFacts(); } };
        var language = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 185, AccessibleName = "Язык ввода" };
        foreach (InputLanguage item in InputLanguage.InstalledInputLanguages) language.Items.Add(item.Culture.Name + " | " + item.LayoutName);
        language.SelectedIndexChanged += delegate {
            InputLanguage.CurrentInputLanguage = InputLanguage.InstalledInputLanguages[language.SelectedIndex];
            Record("input_language", InputLanguage.CurrentInputLanguage.Culture.Name);
            view.Focus(); UpdateFacts();
        };
        var capture = new Button { Text = "Снимок и отчёт", AutoSize = true, AccessibleName = "Снимок и отчёт" };
        capture.Click += async delegate {
            if (view.CoreWebView2 == null) return;
            string stem = "capture-" + (++captureIndex).ToString("00");
            using (var file = File.Create(Path.Combine(output, stem + ".png")))
                await view.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, file);
            string layout = await view.CoreWebView2.ExecuteScriptAsync(@"JSON.stringify({title:document.title,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,search:document.querySelector('#global-search')?.value,body:document.body.innerText,overflow:document.documentElement.scrollWidth-innerWidth,mainOverflow:document.querySelector('main').scrollWidth-document.querySelector('main').clientWidth})");
            File.WriteAllText(Path.Combine(output, stem + ".json"), layout, Encoding.UTF8);
            Record("capture", stem); SaveFacts();
        };
        facts.AutoSize = true; facts.Margin = new Padding(12, 7, 0, 0);
        tools.Controls.Add(zoom); tools.Controls.Add(language); tools.Controls.Add(capture); tools.Controls.Add(facts);
        view.Dock = DockStyle.Fill;
        Controls.Add(view); Controls.Add(tools);
        Shown += async delegate {
            try {
                // Controls added after the form's initial DPI pass need explicit device bounds.
                int dpi = (int)GetDpiForWindow(Handle);
                zoom.Width = 150 * dpi / 96; zoom.DropDownWidth = 180 * dpi / 96;
                language.Width = 220 * dpi / 96; language.DropDownWidth = 350 * dpi / 96;
                var environment = await CoreWebView2Environment.CreateAsync(null, profile, null);
                await view.EnsureCoreWebView2Async(environment);
                runtime = environment.BrowserVersionString;
                view.CoreWebView2.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e) {
                    Uri target; if (!Uri.TryCreate(e.Uri, UriKind.Absolute, out target) || target.GetLeftPart(UriPartial.Authority) != origin.GetLeftPart(UriPartial.Authority)) { e.Cancel = true; Record("navigation_blocked", e.Uri); }
                };
                view.CoreWebView2.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e) { e.Handled = true; };
                view.CoreWebView2.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
                view.CoreWebView2.WebResourceRequested += delegate(object sender, CoreWebView2WebResourceRequestedEventArgs e) {
                    Uri target;
                    if (e.Request.Method != "GET" || !Uri.TryCreate(e.Request.Uri, UriKind.Absolute, out target) || target.GetLeftPart(UriPartial.Authority) != origin.GetLeftPart(UriPartial.Authority)) {
                        blockedRequests.Add(e.Request.Method + " " + e.Request.Uri);
                        e.Response = environment.CreateWebResourceResponse(new MemoryStream(Encoding.UTF8.GetBytes("DEV read-only gate")), 403, "Blocked", "Content-Type: text/plain"); SaveFacts();
                    }
                };
                view.CoreWebView2.WebMessageReceived += delegate(object sender, CoreWebView2WebMessageReceivedEventArgs e) {
                    if (new Uri(e.Source).GetLeftPart(UriPartial.Authority) == origin.GetLeftPart(UriPartial.Authority)) Record("page", json.DeserializeObject(e.WebMessageAsJson));
                };
                await view.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(@"
                  for(const name of ['focusin','compositionstart','compositionupdate','compositionend','input']) document.addEventListener(name,e=>{
                    if(e.target.id==='global-search') chrome.webview.postMessage({event:name,data:e.data??null,isComposing:e.isComposing??null,value:e.target.value,connected:e.target.isConnected});
                  },true);
                  window.addEventListener('error',e=>chrome.webview.postMessage({event:'error',message:e.message}));
                  window.addEventListener('unhandledrejection',e=>chrome.webview.postMessage({event:'unhandledrejection',message:String(e.reason)}));
                  document.addEventListener('DOMContentLoaded',()=>chrome.webview.postMessage({event:'document_ready',dpr:devicePixelRatio,viewport:[innerWidth,innerHeight]}));
                ");
                view.CoreWebView2.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e) { Record("navigation", new { success = e.IsSuccess, status = e.WebErrorStatus.ToString() }); UpdateFacts(); };
                view.Source = origin;
                Record("initialized", runtime); UpdateFacts();
            } catch (Exception error) { runtime = "FAILED"; Record("initialization_error", error.ToString()); UpdateFacts(); }
        };
        ResizeEnd += delegate { Record("resize", new { Width, Height }); UpdateFacts(); };
        FormClosed += delegate { Record("closed", true); view.Dispose(); };
    }

    protected override void WndProc(ref Message message)
    {
        base.WndProc(ref message);
        if (message.Msg == 0x02E0 && IsHandleCreated) { Record("WM_DPICHANGED", GetDpiForWindow(Handle)); UpdateFacts(); }
    }
    void Record(string name, object value)
    {
        events.Add(new { at = DateTime.UtcNow.ToString("o"), name, value });
        SaveFacts();
    }
    void UpdateFacts()
    {
        if (!IsHandleCreated) return;
        facts.Text = "Windows DPI " + GetDpiForWindow(Handle) + " | WebView2 " + runtime + " | " + InputLanguage.CurrentInputLanguage.Culture.Name;
        SaveFacts();
    }
    void SaveFacts()
    {
        if (output == null || !IsHandleCreated) return;
        File.WriteAllText(Path.Combine(output, "native-gate.json"), json.Serialize(new {
            role = "isolated DEV gate, not a production shell", url = origin.ToString(), runtime,
            dpi = GetDpiForWindow(Handle), awareness = GetAwarenessFromDpiAwarenessContext(GetWindowDpiAwarenessContext(Handle)),
            contentZoom = view.ZoomFactor, client = new { ClientSize.Width, ClientSize.Height },
            profile, inputLanguage = InputLanguage.CurrentInputLanguage.Culture.Name,
            blockedPageRequests = blockedRequests, events
        }), Encoding.UTF8);
    }
}
