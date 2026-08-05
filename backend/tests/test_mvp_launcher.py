import ctypes
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from content_retrieval.embeddings.manifest import sha256_path


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="PowerShell MVP launcher is Windows-only",
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPOSITORY_ROOT / "tools" / "start-mvp.ps1"
BACKEND_PYTHON = Path(sys.executable)
TEXT_MODEL_ID = "text-multilingual-v1"
IMAGE_MODEL_ID = "mobileclip-s0-v1"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102


@dataclass(frozen=True)
class LauncherFixture:
    root: Path
    model_root: Path
    manifest: Path
    data_dir: Path
    tika_jar: Path
    checksum_file: Path
    api_port: int


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is not available")
    return executable


def _java() -> str:
    executable = shutil.which("java")
    if executable is None:
        pytest.skip("Java is not available")
    return executable


def _available_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.25)
        return client.connect_ex(("127.0.0.1", port)) == 0


def _write_manifest(
    model_root: Path,
    *,
    include_image: bool = True,
    bad_text_digest: bool = False,
) -> Path:
    text_path = model_root / "text" / TEXT_MODEL_ID
    text_path.mkdir(parents=True)
    (text_path / "config.json").write_text(
        '{"fixture": true}',
        encoding="utf-8",
    )
    image_path = model_root / "mobileclip" / "mobileclip_s0.pt"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"local-mobileclip-fixture")

    entries = [
        {
            "model_id": TEXT_MODEL_ID,
            "space_id": "text-semantic-v1",
            "modality": "text",
            "dimensions": 2,
            "relative_path": f"text/{TEXT_MODEL_ID}",
            "sha256": "0" * 64 if bad_text_digest else sha256_path(text_path),
            "license_name": "Apache-2.0",
            "runtime": "sentence-transformers",
        }
    ]
    if include_image:
        entries.append(
            {
                "model_id": IMAGE_MODEL_ID,
                "space_id": "mobileclip-image-text-v1",
                "modality": "image_text",
                "dimensions": 2,
                "relative_path": "mobileclip/mobileclip_s0.pt",
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "license_name": "Fixture",
                "runtime": "pytorch-mobileclip",
            }
        )

    manifest = model_root / "model-manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": "1", "models": entries}),
        encoding="utf-8",
    )
    return manifest


def _build_fixture(
    tmp_path: Path,
    *,
    checksum: str | None = None,
    include_image: bool = True,
    bad_text_digest: bool = False,
) -> LauncherFixture:
    root = tmp_path / "MVP fixture 路径 with spaces"
    root.mkdir()
    model_root = root / "models"
    model_root.mkdir()
    manifest = _write_manifest(
        model_root,
        include_image=include_image,
        bad_text_digest=bad_text_digest,
    )
    tika_jar = root / "tika fixture.jar"
    tika_jar.write_bytes(b"tika-fixture")
    checksum_file = root / "tika fixture.jar.sha512"
    checksum_file.write_text(
        checksum or hashlib.sha512(b"tika-fixture").hexdigest(),
        encoding="ascii",
    )
    return LauncherFixture(
        root=root,
        model_root=model_root,
        manifest=manifest,
        data_dir=root / "runtime data",
        tika_jar=tika_jar,
        checksum_file=checksum_file,
        api_port=_available_tcp_port(),
    )


def _run_launcher(
    fixture: LauncherFixture,
    *,
    java: str | Path,
    python: str | Path = BACKEND_PYTHON,
    model_root: str | Path | None = None,
    check_only: bool = True,
    env: dict[str, str] | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    command = [
        _powershell(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(LAUNCHER),
    ]
    if check_only:
        command.append("-CheckOnly")
    command.extend(
        [
            "-PythonExecutable",
            str(python),
            "-JavaExecutable",
            str(java),
            "-ModelRoot",
            str(model_root if model_root is not None else fixture.model_root),
            "-ManifestPath",
            str(fixture.manifest),
            "-DataDir",
            str(fixture.data_dir),
            "-TikaJar",
            str(fixture.tika_jar),
            "-TikaChecksumFile",
            str(fixture.checksum_file),
            "-Port",
            str(fixture.api_port),
        ]
    )
    return subprocess.run(
        command,
        cwd=fixture.root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )


def _compile_console_application(source: str, output: Path) -> None:
    csc = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
    if not csc.is_file():
        pytest.skip(".NET Framework C# compiler is not available")
    compile_output = (
        Path(tempfile.gettempdir()) / f"mvp-fake-{uuid.uuid4().hex}.exe"
    )
    source_path = (
        Path(tempfile.gettempdir()) / f"mvp-fake-{uuid.uuid4().hex}.cs"
    )
    source_path.write_text(textwrap.dedent(source), encoding="utf-8")
    try:
        result = subprocess.run(
            [
                str(csc),
                "/nologo",
                "/target:exe",
                f"/out:{compile_output}",
                str(source_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert compile_output.is_file(), result.stdout + result.stderr
    finally:
        source_path.unlink(missing_ok=True)
    shutil.move(compile_output, output)
    assert output.is_file()


@pytest.fixture(scope="module")
def fake_java(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("Fake Java 路径 with spaces")
    executable = root / "fake-java.exe"
    _compile_console_application(
        r"""
        using System;
        using System.Diagnostics;
        using System.IO;
        using System.Net;
        using System.Net.Sockets;
        using System.Text;
        using System.Threading;

        public static class Program
        {
            private static int Serve(string pidFile)
            {
                if (!String.IsNullOrEmpty(pidFile))
                {
                    File.WriteAllText(pidFile, Process.GetCurrentProcess().Id.ToString());
                }

                TcpListener listener = new TcpListener(IPAddress.Loopback, 9998);
                listener.Start();
                byte[] response = Encoding.ASCII.GetBytes(
                    "HTTP/1.1 200 OK\r\nContent-Length: 16\r\nConnection: close\r\n\r\nApache Tika fake"
                );
                while (true)
                {
                    using (TcpClient client = listener.AcceptTcpClient())
                    using (NetworkStream stream = client.GetStream())
                    {
                        byte[] request = new byte[4096];
                        stream.Read(request, 0, request.Length);
                        stream.Write(response, 0, response.Length);
                    }
                }
            }

            public static int Main(string[] args)
            {
                string invocationLog = Environment.GetEnvironmentVariable("FAKE_JAVA_LOG");
                if (!String.IsNullOrEmpty(invocationLog))
                {
                    File.AppendAllText(invocationLog, String.Join(" ", args) + Environment.NewLine);
                }
                if (args.Length > 0 && args[0] == "-version")
                {
                    Console.Error.WriteLine("fake java version 1");
                    return 0;
                }

                string pidFile = Environment.GetEnvironmentVariable("FAKE_JAVA_PID_FILE");
                if (
                    args.Length == 3 &&
                    args[0] == "-cp" &&
                    args[2] == "--child"
                )
                {
                    return Serve(pidFile);
                }

                string argumentsFile = Environment.GetEnvironmentVariable("FAKE_JAVA_ARGUMENTS_FILE");
                if (!String.IsNullOrEmpty(argumentsFile))
                {
                    using (StreamWriter writer = new StreamWriter(
                        argumentsFile,
                        false,
                        new UTF8Encoding(false)
                    ))
                    {
                        writer.WriteLine(args.Length);
                        foreach (string argument in args)
                        {
                            writer.WriteLine(argument.Length + ":" + argument);
                        }
                    }
                }

                string expectedJar = Environment.GetEnvironmentVariable("FAKE_JAVA_EXPECTED_JAR");
                if (
                    args.Length != 4 ||
                    args[0] != "-jar" ||
                    args[1] != expectedJar ||
                    args[2] != "-p" ||
                    args[3] != "9998"
                )
                {
                    return 23;
                }

                if (!String.IsNullOrEmpty(pidFile))
                {
                    File.WriteAllText(pidFile, Process.GetCurrentProcess().Id.ToString());
                }
                if (Environment.GetEnvironmentVariable("FAKE_JAVA_MODE") == "exit")
                {
                    return 17;
                }

                if (Environment.GetEnvironmentVariable("FAKE_JAVA_MODE") == "wrapper")
                {
                    ProcessStartInfo startInfo = new ProcessStartInfo();
                    startInfo.FileName = Process.GetCurrentProcess().MainModule.FileName;
                    startInfo.Arguments = "-cp \"" + expectedJar.Replace("\"", "\\\"") + "\" --child";
                    startInfo.UseShellExecute = false;
                    startInfo.CreateNoWindow = true;
                    startInfo.EnvironmentVariables["FAKE_JAVA_MODE"] = "child";
                    Process.Start(startInfo);
                    Thread.Sleep(750);
                    return 0;
                }

                return Serve(pidFile);
            }
        }
        """,
        executable,
    )
    return executable


@pytest.fixture(scope="module")
def fake_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("Fake Python 路径 with spaces")
    executable = root / "fake-python.exe"
    _compile_console_application(
        r"""
        using System;
        using System.IO;

        public static class Program
        {
            public static int Main(string[] args)
            {
                string log = Environment.GetEnvironmentVariable("FAKE_PYTHON_LOG");
                if (!String.IsNullOrEmpty(log))
                {
                    File.AppendAllText(log, String.Join(" ", args) + Environment.NewLine);
                }
                if (args.Length > 1 && args[0] == "-c")
                {
                    if (args[1].Contains("version_info"))
                    {
                        Console.WriteLine("3.10");
                    }
                    return 0;
                }
                return 91;
            }
        }
        """,
        executable,
    )
    return executable


def _process_is_alive(pid: int) -> bool:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
        False,
        pid,
    )
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _terminate_pid(pid: int) -> None:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x0001 | SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        kernel32.TerminateProcess(handle, 1)
        kernel32.WaitForSingleObject(handle, 5000)
    finally:
        kernel32.CloseHandle(handle)


def _wait_for_pid_file(path: Path, timeout: float = 10) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return int(path.read_text(encoding="utf-8").strip())
        time.sleep(0.05)
    raise AssertionError(f"PID file was not created: {path}")


def _wait_for_process_exit(pid: int, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_is_alive(pid):
            return
        time.sleep(0.05)
    raise AssertionError(f"process did not exit: {pid}")


def _read_recorded_arguments(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    count = int(lines[0])
    arguments: list[str] = []
    for line in lines[1:]:
        length_text, argument = line.split(":", 1)
        assert int(length_text) == len(argument)
        arguments.append(argument)
    assert count == len(arguments)
    return arguments


def test_check_only_verifies_real_runtimes_and_manifest(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)

    result = _run_launcher(fixture, java=_java())

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MVP preflight passed" in result.stdout
    assert not fixture.data_dir.exists()


def test_check_only_quotes_trailing_separator_model_root(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    model_root_with_trailing_separator = str(fixture.model_root) + os.sep

    result = _run_launcher(
        fixture,
        java=_java(),
        model_root=model_root_with_trailing_separator,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MVP preflight passed" in result.stdout
    assert not fixture.data_dir.exists()


def test_check_only_rejects_java_that_fails_version_check(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    bad_java = fixture.root / "bad-java.cmd"
    bad_java.write_text("@exit /b 7\n", encoding="ascii")

    result = _run_launcher(fixture, java=bad_java)

    assert result.returncode != 0
    assert "Java runtime check failed" in result.stdout + result.stderr


def test_check_only_reports_missing_required_model_id(tmp_path: Path) -> None:
    fixture = _build_fixture(
        tmp_path,
        include_image=False,
    )

    result = _run_launcher(fixture, java=_java())

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert (
        "Model manifest verification failed: ModelManifestError: "
        f"unknown model_id: {IMAGE_MODEL_ID}"
    ) in output
    assert "Traceback" not in output
    assert not fixture.data_dir.exists()


def test_check_only_reports_model_digest_mismatch(tmp_path: Path) -> None:
    fixture = _build_fixture(
        tmp_path,
        bad_text_digest=True,
    )
    text_path = fixture.model_root / "text" / TEXT_MODEL_ID
    actual_digest = sha256_path(text_path)

    result = _run_launcher(fixture, java=_java())

    assert result.returncode != 0
    output = result.stdout + result.stderr
    expected_diagnostic = (
        "Model manifest verification failed: ModelManifestError: "
        f"model SHA-256 mismatch for {TEXT_MODEL_ID}: "
        f"expected {'0' * 64}, got {actual_digest}"
    )
    assert "".join(expected_diagnostic.split()) in "".join(output.split())
    assert "Traceback" not in output
    assert not fixture.data_dir.exists()


def test_check_only_rejects_mismatched_tika_checksum(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path, checksum="0" * 128)

    result = _run_launcher(fixture, java=_java())

    assert result.returncode != 0
    assert "Tika server JAR SHA-512 mismatch" in result.stdout + result.stderr


def test_check_only_preserves_preexisting_data_directory(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    fixture.data_dir.mkdir()
    sentinel = fixture.data_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    result = _run_launcher(fixture, java=_java())

    assert result.returncode == 0, result.stdout + result.stderr
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_check_only_does_not_start_tika_or_uvicorn(
    tmp_path: Path,
    fake_java: Path,
    fake_python: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    python_log = fixture.root / "python invocations.log"
    java_log = fixture.root / "java invocations.log"
    pid_file = fixture.root / "java pid.txt"
    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(python_log)
    env["FAKE_JAVA_LOG"] = str(java_log)
    env["FAKE_JAVA_PID_FILE"] = str(pid_file)

    result = _run_launcher(
        fixture,
        java=fake_java,
        python=fake_python,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not pid_file.exists()
    assert java_log.is_file()
    assert java_log.read_text(encoding="utf-8").splitlines() == ["-version"]
    assert python_log.is_file()
    assert "-m uvicorn" not in python_log.read_text(encoding="utf-8")
    assert not _port_is_open(fixture.api_port)


def test_fake_java_rejects_incorrect_tika_arguments(
    tmp_path: Path,
    fake_java: Path,
) -> None:
    if _port_is_open(9998):
        pytest.skip("port 9998 is already occupied")
    fixture = _build_fixture(tmp_path)
    arguments_file = fixture.root / "rejected arguments.txt"
    env = os.environ.copy()
    env["FAKE_JAVA_ARGUMENTS_FILE"] = str(arguments_file)
    env["FAKE_JAVA_EXPECTED_JAR"] = str(fixture.tika_jar)

    result = subprocess.run(
        [str(fake_java), "-jar", str(fixture.tika_jar), "-p", "9999"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
        env=env,
    )

    assert result.returncode == 23
    assert _read_recorded_arguments(arguments_file) == [
        "-jar",
        str(fixture.tika_jar),
        "-p",
        "9999",
    ]
    assert not _port_is_open(9998)


TIKA_SERVER_CODE = r"""
import http.server
import os
import pathlib
import sys

pathlib.Path(sys.argv[1]).write_text(str(os.getpid()), encoding="utf-8")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Apache Tika existing"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

http.server.ThreadingHTTPServer(("127.0.0.1", 9998), Handler).serve_forever()
"""


def _wait_for_tika(timeout: float = 10) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with opener.open("http://127.0.0.1:9998/version", timeout=0.5) as response:
                if response.status == 200 and b"Apache Tika" in response.read():
                    return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("Tika fixture did not become ready")


def test_existing_tika_is_reused_and_left_running(
    tmp_path: Path,
    fake_python: Path,
) -> None:
    if _port_is_open(9998):
        pytest.skip("port 9998 is already occupied")
    fixture = _build_fixture(tmp_path)
    pid_file = fixture.root / "existing tika pid.txt"
    service = subprocess.Popen(
        [str(BACKEND_PYTHON), "-c", TIKA_SERVER_CODE, str(pid_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_tika()
        result = _run_launcher(
            fixture,
            java=_java(),
            python=fake_python,
            check_only=False,
            timeout=30,
        )

        assert result.returncode != 0
        assert "MVP API exited with code" in result.stdout + result.stderr
        assert service.poll() is None
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait(timeout=5)


def test_started_tika_is_stopped_after_uvicorn_failure(
    tmp_path: Path,
    fake_java: Path,
    fake_python: Path,
) -> None:
    if _port_is_open(9998):
        pytest.skip("port 9998 is already occupied")
    fixture = _build_fixture(tmp_path)
    pid_file = fixture.root / "started tika pid.txt"
    arguments_file = fixture.root / "started tika arguments.txt"
    env = os.environ.copy()
    env["FAKE_JAVA_PID_FILE"] = str(pid_file)
    env["FAKE_JAVA_ARGUMENTS_FILE"] = str(arguments_file)
    env["FAKE_JAVA_EXPECTED_JAR"] = str(fixture.tika_jar)
    pid: int | None = None
    try:
        result = _run_launcher(
            fixture,
            java=fake_java,
            python=fake_python,
            check_only=False,
            env=env,
            timeout=30,
        )
        pid = _wait_for_pid_file(pid_file)

        assert result.returncode != 0
        assert "MVP API exited with code" in result.stdout + result.stderr
        assert _read_recorded_arguments(arguments_file) == [
            "-jar",
            str(fixture.tika_jar),
            "-p",
            "9998",
        ]
        _wait_for_process_exit(pid)
    finally:
        if pid is None and pid_file.is_file():
            pid = int(pid_file.read_text(encoding="utf-8"))
        if pid is not None and _process_is_alive(pid):
            _terminate_pid(pid)


def test_started_tika_wrapper_descendant_is_stopped_after_wrapper_exits(
    tmp_path: Path,
    fake_java: Path,
    fake_python: Path,
) -> None:
    if _port_is_open(9998):
        pytest.skip("port 9998 is already occupied")
    fixture = _build_fixture(tmp_path)
    pid_file = fixture.root / "wrapper descendant tika pid.txt"
    arguments_file = fixture.root / "wrapper descendant arguments.txt"
    env = os.environ.copy()
    env["FAKE_JAVA_PID_FILE"] = str(pid_file)
    env["FAKE_JAVA_ARGUMENTS_FILE"] = str(arguments_file)
    env["FAKE_JAVA_EXPECTED_JAR"] = str(fixture.tika_jar)
    env["FAKE_JAVA_MODE"] = "wrapper"
    descendant_pid: int | None = None
    try:
        result = _run_launcher(
            fixture,
            java=fake_java,
            python=fake_python,
            check_only=False,
            env=env,
            timeout=30,
        )
        descendant_pid = _wait_for_pid_file(pid_file)

        assert result.returncode != 0
        assert "MVP API exited with code" in result.stdout + result.stderr
        assert "Tika server exited before becoming ready" not in result.stdout + result.stderr
        assert _read_recorded_arguments(arguments_file) == [
            "-jar",
            str(fixture.tika_jar),
            "-p",
            "9998",
        ]
        _wait_for_process_exit(descendant_pid)
        assert not _port_is_open(9998)
    finally:
        if descendant_pid is None and pid_file.is_file():
            descendant_pid = int(pid_file.read_text(encoding="utf-8"))
        if descendant_pid is not None and _process_is_alive(descendant_pid):
            _terminate_pid(descendant_pid)


def test_tika_early_exit_is_reported_without_process_leak(
    tmp_path: Path,
    fake_java: Path,
    fake_python: Path,
) -> None:
    if _port_is_open(9998):
        pytest.skip("port 9998 is already occupied")
    fixture = _build_fixture(tmp_path)
    pid_file = fixture.root / "early exit tika pid.txt"
    arguments_file = fixture.root / "early exit tika arguments.txt"
    env = os.environ.copy()
    env["FAKE_JAVA_PID_FILE"] = str(pid_file)
    env["FAKE_JAVA_ARGUMENTS_FILE"] = str(arguments_file)
    env["FAKE_JAVA_EXPECTED_JAR"] = str(fixture.tika_jar)
    env["FAKE_JAVA_MODE"] = "exit"

    result = _run_launcher(
        fixture,
        java=fake_java,
        python=fake_python,
        check_only=False,
        env=env,
        timeout=30,
    )
    pid = _wait_for_pid_file(pid_file)

    assert result.returncode != 0
    assert "Tika server exited before becoming ready" in result.stdout + result.stderr
    assert _read_recorded_arguments(arguments_file) == [
        "-jar",
        str(fixture.tika_jar),
        "-p",
        "9998",
    ]
    _wait_for_process_exit(pid)
