using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace ContentRetrievalLauncher
{
    internal static class Program
    {
        private static readonly string[] RequiredPaths =
        {
            @"frontend\content_retrieval_app.exe",
            @"runtime\python\python.exe",
            @"runtime\java\bin\java.exe",
            @"models\model-manifest.json",
            @"tools\tika\tika-server-standard-3.3.1.jar",
            @"tools\tika\tika-server-standard-3.3.1.jar.sha512",
            @"tools\start-mvp.ps1",
            "启动应用.ps1",
        };

        [STAThread]
        private static int Main(string[] args)
        {
            bool checkOnly = false;
            string packageRoot = AppDomain.CurrentDomain.BaseDirectory;
            for (int index = 0; index < args.Length; index++)
            {
                if (string.Equals(args[index], "--check-only", StringComparison.OrdinalIgnoreCase))
                {
                    checkOnly = true;
                }
                else if (string.Equals(args[index], "--headless", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                else if (string.Equals(args[index], "--package-root", StringComparison.OrdinalIgnoreCase) && index + 1 < args.Length)
                {
                    packageRoot = args[++index];
                }
            }

            packageRoot = Path.GetFullPath(packageRoot);
            List<string> missing = new List<string>();
            foreach (string relativePath in RequiredPaths)
            {
                if (!File.Exists(Path.Combine(packageRoot, relativePath)))
                {
                    missing.Add(relativePath);
                }
            }

            if (missing.Count > 0)
            {
                Console.Error.WriteLine("Missing package resources: " + string.Join(", ", missing.ToArray()));
                return 2;
            }

            if (checkOnly)
            {
                Console.WriteLine("One-click launcher preflight passed");
                return 0;
            }

            return RunIntegratedLauncher(packageRoot);
        }

        private static int RunIntegratedLauncher(string packageRoot)
        {
            string script = Path.Combine(packageRoot, "启动应用.ps1");
            string dataDirectory = Path.Combine(packageRoot, "data");
            Directory.CreateDirectory(dataDirectory);
            string logPath = Path.Combine(dataDirectory, "launcher.log");
            StringBuilder log = new StringBuilder();
            string command = "& " + PowerShellLiteral(script) + " -PackageRoot " + PowerShellLiteral(packageRoot);
            string encodedCommand = Convert.ToBase64String(Encoding.Unicode.GetBytes(command));
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand " + encodedCommand,
                WorkingDirectory = packageRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };

            using (Process process = new Process { StartInfo = startInfo })
            {
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs eventArgs)
                {
                    if (eventArgs.Data != null) log.AppendLine(eventArgs.Data);
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs eventArgs)
                {
                    if (eventArgs.Data != null) log.AppendLine(eventArgs.Data);
                };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                File.WriteAllText(logPath, log.ToString(), new UTF8Encoding(false));
                return process.ExitCode;
            }
        }

        private static string PowerShellLiteral(string value)
        {
            return "'" + value.Replace("'", "''") + "'";
        }
    }
}
