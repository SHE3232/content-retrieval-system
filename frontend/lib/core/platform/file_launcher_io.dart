import 'dart:io';

import 'package:content_retrieval_app/core/platform/file_launcher.dart';

final class IoFileLauncher implements FileLauncher {
  IoFileLauncher({
    required this.platform,
    Future<bool> Function(String path)? fileExists,
    Future<void> Function(String executable, List<String> arguments)?
    startProcess,
  }) : _fileExists = fileExists ?? _defaultFileExists,
       _startProcess = startProcess ?? _defaultStart;

  final DesktopPlatform platform;
  final Future<bool> Function(String path) _fileExists;
  final Future<void> Function(String executable, List<String> arguments)
  _startProcess;

  @override
  Future<void> open(String path) async {
    if (path.trim().isEmpty) {
      throw const FileLaunchException(
        FileLaunchErrorKind.notFound,
        '文件不存在或已被移动',
      );
    }
    final executable = switch (platform) {
      DesktopPlatform.windows => 'explorer.exe',
      DesktopPlatform.macos => 'open',
      DesktopPlatform.linux => 'xdg-open',
      DesktopPlatform.unsupported => throw const FileLaunchException(
        FileLaunchErrorKind.unsupportedPlatform,
        '当前系统不支持打开文件',
      ),
    };
    final bool exists;
    try {
      exists = await _fileExists(path);
    } on FileSystemException catch (error) {
      throw FileLaunchException(
        FileLaunchErrorKind.launchFailed,
        '无法打开文件，请检查系统关联设置',
        cause: error,
      );
    }
    if (!exists) {
      throw const FileLaunchException(
        FileLaunchErrorKind.notFound,
        '文件不存在或已被移动',
      );
    }
    try {
      await _startProcess(executable, <String>[path]);
    } on ProcessException catch (error) {
      throw FileLaunchException(
        FileLaunchErrorKind.launchFailed,
        '无法打开文件，请检查系统关联设置',
        cause: error,
      );
    }
  }
}

FileLauncher createPlatformFileLauncher() {
  return IoFileLauncher(platform: currentDesktopPlatform());
}

bool get platformFileActionsSupported =>
    currentDesktopPlatform() != DesktopPlatform.unsupported;

DesktopPlatform currentDesktopPlatform() {
  if (Platform.isWindows) return DesktopPlatform.windows;
  if (Platform.isMacOS) return DesktopPlatform.macos;
  if (Platform.isLinux) return DesktopPlatform.linux;
  return DesktopPlatform.unsupported;
}

Future<bool> _defaultFileExists(String path) => File(path).exists();

Future<void> _defaultStart(String executable, List<String> arguments) async {
  await Process.start(
    executable,
    arguments,
    mode: ProcessStartMode.detached,
    runInShell: false,
  );
}
