using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

namespace LecturePipeline.Setup;

// IShellLinkW preserves paths outside the current ANSI code page.
// https://learn.microsoft.com/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw
internal sealed class ShellShortcut : IDisposable
{
    readonly IShellLinkW link=(IShellLinkW)new ShellLink();
    public ShellShortcut(string? path=null) { if(path!=null)((IPersistFile)link).Load(path,0); }
    public string Target { get {var b=new StringBuilder(32768);link.GetPath(b,b.Capacity,IntPtr.Zero,4);return b.ToString();} set=>link.SetPath(value); }
    public string Arguments { get {var b=new StringBuilder(32768);link.GetArguments(b,b.Capacity);return b.ToString();} set=>link.SetArguments(value); }
    public string Directory { get {var b=new StringBuilder(32768);link.GetWorkingDirectory(b,b.Capacity);return b.ToString();} set=>link.SetWorkingDirectory(value); }
    public void Save(string path) {link.SetDescription("Lecture Pipeline");((IPersistFile)link).Save(path,true);}
    public void Dispose()=>Marshal.FinalReleaseComObject(link);

    [ComImport,Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink { }
    [ComImport,Guid("000214F9-0000-0000-C000-000000000046"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellLinkW
    {
        void GetPath([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int capacity,IntPtr data,uint flags);
        void GetIDList(out IntPtr pidl);
        void SetIDList(IntPtr pidl);
        void GetDescription([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int capacity);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetWorkingDirectory([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int capacity);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetArguments([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder text,int capacity);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetHotkey(out short key);
        void SetHotkey(short key);
        void GetShowCmd(out int command);
        void SetShowCmd(int command);
        void GetIconLocation([Out,MarshalAs(UnmanagedType.LPWStr)] StringBuilder path,int capacity,out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path,int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path,uint reserved);
        void Resolve(IntPtr window,uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }
}
