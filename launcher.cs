using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class TrussLabLauncher {
    [STAThread]
    static void Main() {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        if (!File.Exists(python)) {
            MessageBox.Show("Ejecuta Instalar.ps1 en esta carpeta para preparar el entorno Python.", "TrussLab 3D");
            return;
        }
        try {
            var info = new ProcessStartInfo(python, "\"" + Path.Combine(root, "run.py") + "\"");
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            Process.Start(info);
        } catch(Exception e) { MessageBox.Show(e.Message, "TrussLab 3D"); }
    }
}
