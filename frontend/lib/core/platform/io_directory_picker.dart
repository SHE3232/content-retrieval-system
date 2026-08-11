import 'dart:io';

import 'package:content_retrieval_app/core/platform/directory_picker.dart';
import 'package:content_retrieval_app/core/platform/file_launcher.dart';

typedef RunDirectoryPickerProcess =
    Future<ProcessResult> Function(String executable, List<String> arguments);

final class DirectoryPickerException implements Exception {
  const DirectoryPickerException(this.message, {this.cause});

  final String message;
  final Object? cause;

  @override
  String toString() => 'DirectoryPickerException($message)';
}

final class IoDirectoryPicker implements DirectoryPicker {
  IoDirectoryPicker({
    required this.platform,
    RunDirectoryPickerProcess? runProcess,
  }) : _runProcess = runProcess ?? _defaultRunProcess;

  final DesktopPlatform platform;
  final RunDirectoryPickerProcess _runProcess;

  @override
  bool get isSupported => platform != DesktopPlatform.unsupported;

  @override
  Future<String?> pickDirectory() async {
    if (!isSupported) return null;
    final (executable, arguments) = _command();
    try {
      final result = await _runProcess(executable, arguments);
      if (result.exitCode == 1) return null;
      if (result.exitCode != 0) {
        throw DirectoryPickerException(
          '无法打开文件夹选择器，请重试。',
          cause: ProcessException(
            executable,
            arguments,
            '${result.stderr}',
            result.exitCode,
          ),
        );
      }
      final selected = '${result.stdout}'.trim();
      return selected.isEmpty ? null : selected;
    } on DirectoryPickerException {
      rethrow;
    } on ProcessException catch (error) {
      throw DirectoryPickerException('无法打开文件夹选择器，请重试。', cause: error);
    }
  }

  (String, List<String>) _command() {
    return switch (platform) {
      DesktopPlatform.windows => (
        'powershell.exe',
        <String>[
          '-NoProfile',
          '-STA',
          '-NonInteractive',
          '-Command',
          r'''Add-Type -AssemblyName System.Windows.Forms; $dialog = New-Object System.Windows.Forms.FolderBrowserDialog; $dialog.Description = '选择索引文件夹'; if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.SelectedPath) }''',
        ],
      ),
      DesktopPlatform.macos => (
        'osascript',
        <String>['-e', 'POSIX path of (choose folder with prompt "选择索引文件夹")'],
      ),
      DesktopPlatform.linux => (
        'zenity',
        <String>['--file-selection', '--directory', '--title=选择索引文件夹'],
      ),
      DesktopPlatform.unsupported => throw const DirectoryPickerException(
        '当前平台不支持选择桌面文件夹。',
      ),
    };
  }

  static Future<ProcessResult> _defaultRunProcess(
    String executable,
    List<String> arguments,
  ) {
    return Process.run(executable, arguments, runInShell: false);
  }
}
