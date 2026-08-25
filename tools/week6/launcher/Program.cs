using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

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
            bool headless = false;
            string packageRoot = AppDomain.CurrentDomain.BaseDirectory;
            for (int index = 0; index < args.Length; index++)
            {
                if (string.Equals(args[index], "--check-only", StringComparison.OrdinalIgnoreCase))
                {
                    checkOnly = true;
                }
                else if (string.Equals(args[index], "--headless", StringComparison.OrdinalIgnoreCase))
                {
                    headless = true;
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

            using (Mutex launcherMutex = new Mutex(false, GetLauncherMutexName(packageRoot)))
            {
                bool ownsMutex;
                try
                {
                    ownsMutex = launcherMutex.WaitOne(0, false);
                }
                catch (AbandonedMutexException)
                {
                    ownsMutex = true;
                }
                if (!ownsMutex)
                {
                    if (!headless)
                    {
                        MessageBox.Show(
                            "内容检索系统正在启动或运行，请耐心等待。",
                            "内容检索系统",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Information
                        );
                    }
                    return 0;
                }
                try
                {
                    if (headless)
                    {
                        return RunIntegratedLauncher(packageRoot);
                    }
                    return RunWithStartupWindow(packageRoot);
                }
                finally
                {
                    launcherMutex.ReleaseMutex();
                }
            }
        }

        private static string GetLauncherMutexName(string packageRoot)
        {
            byte[] rootBytes = Encoding.UTF8.GetBytes(Path.GetFullPath(packageRoot).ToUpperInvariant());
            using (SHA256 sha256 = SHA256.Create())
            {
                byte[] hash = sha256.ComputeHash(rootBytes);
                StringBuilder suffix = new StringBuilder(24);
                for (int index = 0; index < 12; index++)
                {
                    suffix.Append(hash[index].ToString("x2"));
                }
                return @"Local\ContentRetrievalSystem-" + suffix;
            }
        }

        private static int RunWithStartupWindow(string packageRoot)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            int exitCode = 1;
            Form startupWindow = new Form
            {
                Text = "内容检索系统",
                StartPosition = FormStartPosition.CenterScreen,
                FormBorderStyle = FormBorderStyle.FixedDialog,
                MaximizeBox = false,
                MinimizeBox = false,
                ControlBox = false,
                ShowInTaskbar = true,
                ClientSize = new Size(440, 150),
                Font = new Font("Microsoft YaHei UI", 9F),
            };
            Label title = new Label
            {
                AutoSize = false,
                Location = new Point(24, 22),
                Size = new Size(392, 28),
                Font = new Font("Microsoft YaHei UI", 12F, FontStyle.Bold),
                Text = "正在启动内容检索系统",
            };
            Label detail = new Label
            {
                AutoSize = false,
                Location = new Point(24, 56),
                Size = new Size(392, 42),
                Text = "正在加载本地模型，首次启动通常需要 2–3 分钟。\r\n请耐心等待，不要重复双击。",
            };
            ProgressBar progress = new ProgressBar
            {
                Location = new Point(24, 110),
                Size = new Size(392, 16),
                Style = ProgressBarStyle.Marquee,
                MarqueeAnimationSpeed = 25,
            };
            startupWindow.Controls.Add(title);
            startupWindow.Controls.Add(detail);
            startupWindow.Controls.Add(progress);

            System.Windows.Forms.Timer frontendTimer = new System.Windows.Forms.Timer { Interval = 250 };
            frontendTimer.Tick += delegate
            {
                if (IsFrontendWindowVisible(packageRoot))
                {
                    frontendTimer.Stop();
                    startupWindow.Hide();
                }
            };
            startupWindow.Shown += delegate
            {
                frontendTimer.Start();
                ThreadPool.QueueUserWorkItem(delegate
                {
                    string failure = null;
                    int launcherExitCode = 1;
                    try
                    {
                        launcherExitCode = RunIntegratedLauncher(packageRoot);
                    }
                    catch (Exception exception)
                    {
                        failure = exception.ToString();
                    }
                    startupWindow.BeginInvoke((MethodInvoker)delegate
                    {
                        exitCode = launcherExitCode;
                        frontendTimer.Stop();
                        if (failure != null || launcherExitCode != 0)
                        {
                            string logPath = Path.Combine(packageRoot, "data", "launcher.log");
                            string message = failure ?? ("启动进程退出，代码：" + launcherExitCode);
                            MessageBox.Show(
                                startupWindow,
                                "内容检索系统启动失败。\r\n\r\n" + message + "\r\n\r\n日志：" + logPath,
                                "内容检索系统",
                                MessageBoxButtons.OK,
                                MessageBoxIcon.Error
                            );
                        }
                        startupWindow.Close();
                    });
                });
            };

            Application.Run(startupWindow);
            frontendTimer.Dispose();
            startupWindow.Dispose();
            return exitCode;
        }

        private static bool IsFrontendWindowVisible(string packageRoot)
        {
            string expectedExecutable = Path.GetFullPath(
                Path.Combine(packageRoot, @"frontend\content_retrieval_app.exe")
            );
            foreach (Process process in Process.GetProcessesByName("content_retrieval_app"))
            {
                using (process)
                {
                    try
                    {
                        if (
                            process.MainWindowHandle != IntPtr.Zero &&
                            string.Equals(process.MainModule.FileName, expectedExecutable, StringComparison.OrdinalIgnoreCase)
                        )
                        {
                            return true;
                        }
                    }
                    catch (Exception)
                    {
                        // A process can exit while it is being inspected.
                    }
                }
            }
            return false;
        }

        private static int RunIntegratedLauncher(string packageRoot)
        {
            string script = Path.Combine(packageRoot, "启动应用.ps1");
            string dataDirectory = Path.Combine(packageRoot, "data");
            Directory.CreateDirectory(dataDirectory);
            string logPath = Path.Combine(dataDirectory, "launcher.log");
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

            using (FileStream logFile = new FileStream(
                logPath,
                FileMode.Create,
                FileAccess.Write,
                FileShare.ReadWrite
            ))
            using (StreamWriter logWriter = new StreamWriter(logFile, new UTF8Encoding(false)))
            using (Process process = new Process { StartInfo = startInfo })
            {
                object logLock = new object();
                Action<string> writeLogLine = delegate(string line)
                {
                    if (line == null) return;
                    lock (logLock)
                    {
                        logWriter.WriteLine(line);
                        logWriter.Flush();
                    }
                };
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs eventArgs)
                {
                    writeLogLine(eventArgs.Data);
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs eventArgs)
                {
                    writeLogLine(eventArgs.Data);
                };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                return process.ExitCode;
            }
        }

        private static string PowerShellLiteral(string value)
        {
            return "'" + value.Replace("'", "''") + "'";
        }
    }
}
