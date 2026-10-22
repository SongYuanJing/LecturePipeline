// Local read-only WebView2 shell. Pipeline authority remains in the Python backend.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

[assembly: TargetFramework(".NETFramework,Version=v4.8")]

public sealed class DesktopShell : Form
{
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    readonly Uri origin;
    readonly string profile;
    readonly string statusPath;
    readonly WebView2 view = new WebView2();

    [STAThread]
    public static void Main(string[] args)
    {
        if (args.Length != 2 && args.Length != 3) throw new ArgumentException("Expected dashboard URL and local profile");
        Uri url = new Uri(args[0]);
        if (url.Scheme != "http" || url.Host != "127.0.0.1" || url.Port < 1)
            throw new ArgumentException("Dashboard requires a local 127.0.0.1 URL");
        SetProcessDpiAwarenessContext(new IntPtr(-4));
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new DesktopShell(url, Path.GetFullPath(args[1]), args.Length == 3 ? Path.GetFullPath(args[2]) : null));
    }

    DesktopShell(Uri url, string profileDirectory, string firstLaunchStatus)
    {
        origin = url;
        profile = profileDirectory;
        statusPath = firstLaunchStatus;
        Text = "Lecture Pipeline DEV";
        var selectedIcon = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "LecturePipeline-A-dark.ico");
        if (File.Exists(selectedIcon)) Icon = new System.Drawing.Icon(selectedIcon);
        MinimumSize = new System.Drawing.Size(720, 500);
        StartPosition = FormStartPosition.CenterScreen;
        WindowState = FormWindowState.Maximized;
        view.Dock = DockStyle.Fill;
        Controls.Add(view);
        Shown += async delegate {
            try {
                var environment = await CoreWebView2Environment.CreateAsync(null, profile, null);
                await view.EnsureCoreWebView2Async(environment);
                view.CoreWebView2.Settings.AreDevToolsEnabled = false;
                view.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
                view.CoreWebView2.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e) {
                    if (!Allowed(e.Uri)) e.Cancel = true;
                };
                view.CoreWebView2.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e) {
                    e.Handled = true;
                };
                view.CoreWebView2.PermissionRequested += delegate(object sender, CoreWebView2PermissionRequestedEventArgs e) {
                    e.State = CoreWebView2PermissionState.Deny;
                };
                view.CoreWebView2.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
                view.CoreWebView2.WebResourceRequested += delegate(object sender, CoreWebView2WebResourceRequestedEventArgs e) {
                    if (e.Request.Method != "GET" || !Allowed(e.Request.Uri))
                        e.Response = environment.CreateWebResourceResponse(
                            new MemoryStream(System.Text.Encoding.UTF8.GetBytes("Read-only DEV dashboard")),
                            403, "Blocked", "Content-Type: text/plain");
                };
                view.Source = origin;
                Signal("ready", "");
            } catch (Exception error) {
                Signal("error", error.ToString());
                if (statusPath != null) {
                    Environment.ExitCode = 2;
                    Close();
                    return;
                }
                MessageBox.Show(this, "Новый интерфейс недоступен. Откройте Lecture Pipeline (Tk).\n\n" + error.Message,
                    "Lecture Pipeline DEV", MessageBoxButtons.OK, MessageBoxIcon.Error);
                Environment.ExitCode = 2;
                Close();
            }
        };
        FormClosed += delegate { view.Dispose(); };
    }

    void Signal(string state, string detail)
    {
        if (statusPath == null) return;
        var temporary = statusPath + ".pending";
        File.WriteAllText(temporary, state + "\n" + detail);
        File.Move(temporary, statusPath);
    }

    bool Allowed(string value)
    {
        Uri target;
        return Uri.TryCreate(value, UriKind.Absolute, out target)
            && target.GetLeftPart(UriPartial.Authority) == origin.GetLeftPart(UriPartial.Authority);
    }
}
