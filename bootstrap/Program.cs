using System.Diagnostics;
using System.Text.Json;

namespace LecturePipeline.Setup;

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        var timer = Stopwatch.StartNew();
        ApplicationConfiguration.Initialize();
        var form = new Form { Text = "Lecture Pipeline — Setup", Width = 700, Height = 320,
            StartPosition = FormStartPosition.CenterScreen, AutoScaleMode = AutoScaleMode.Dpi };
        form.Controls.Add(new Label { Text = "Lecture Pipeline\nWindows 11 x64\nПодготовка установки…",
            Dock = DockStyle.Fill, Padding = new Padding(24), Font = new Font("Segoe UI", 14) });
        if (args.Length == 2 && args[0] == "--startup-report")
            form.Shown += (_, _) => {
                File.WriteAllText(args[1], JsonSerializer.Serialize(new { shown_ms = timer.Elapsed.TotalMilliseconds,
                    framework = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription }));
                form.BeginInvoke(form.Close);
            };
        Application.Run(form);
    }
}
