import 'dart:io';

import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/io_directory_picker.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'Windows picker runs a static STA dialog script without a shell',
    () async {
      String? executable;
      List<String>? arguments;
      final picker = IoDirectoryPicker(
        platform: DesktopPlatform.windows,
        runProcess: (program, args) async {
          executable = program;
          arguments = args;
          return ProcessResult(1, 0, 'C:\\docs\r\n', '');
        },
      );

      expect(await picker.pickDirectory(), r'C:\docs');
      expect(executable, 'powershell.exe');
      expect(arguments, containsAllInOrder(['-NoProfile', '-STA', '-Command']));
      expect(arguments!.last, contains('FolderBrowserDialog'));
      expect(arguments!.last, contains('选择资料文件夹'));
      expect(picker.isSupported, isTrue);
    },
  );

  test(
    'macOS and Linux use argument arrays and trim the selected path',
    () async {
      final calls = <({String program, List<String> args})>[];
      Future<ProcessResult> runner(String program, List<String> args) async {
        calls.add((program: program, args: args));
        return ProcessResult(1, 0, '/Users/test/Documents\n', '');
      }

      final mac = IoDirectoryPicker(
        platform: DesktopPlatform.macos,
        runProcess: runner,
      );
      final linux = IoDirectoryPicker(
        platform: DesktopPlatform.linux,
        runProcess: runner,
      );

      expect(await mac.pickDirectory(), '/Users/test/Documents');
      expect(await linux.pickDirectory(), '/Users/test/Documents');
      expect(calls[0].program, 'osascript');
      expect(calls[0].args, contains(contains('选择资料文件夹')));
      expect(calls[1].program, 'zenity');
      expect(calls[1].args, contains('--directory'));
      expect(calls[1].args, contains('--title=选择资料文件夹'));
    },
  );

  test('cancel returns null and unexpected process failure is safe', () async {
    final cancelled = IoDirectoryPicker(
      platform: DesktopPlatform.linux,
      runProcess: (_, _) async => ProcessResult(1, 1, '', ''),
    );
    final failed = IoDirectoryPicker(
      platform: DesktopPlatform.linux,
      runProcess: (_, _) async => ProcessResult(1, 2, '', 'raw details'),
    );

    expect(await cancelled.pickDirectory(), isNull);
    await expectLater(
      failed.pickDirectory(),
      throwsA(
        isA<DirectoryPickerException>().having(
          (error) => error.message,
          'message',
          '无法打开资料文件夹选择窗口，请重新尝试。',
        ),
      ),
    );
  });

  test(
    'unsupported platform reports capability without side effects',
    () async {
      var calls = 0;
      final picker = IoDirectoryPicker(
        platform: DesktopPlatform.unsupported,
        runProcess: (_, _) async {
          calls += 1;
          return ProcessResult(1, 0, '', '');
        },
      );

      expect(picker.isSupported, isFalse);
      expect(await picker.pickDirectory(), isNull);
      expect(calls, 0);
    },
  );
}
