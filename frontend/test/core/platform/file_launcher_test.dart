import 'dart:io';

import 'package:content_retrieval_app/core/platform/file_launcher.dart';
import 'package:content_retrieval_app/core/platform/path_clipboard.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('IoFileLauncher', () {
    test('uses explorer arguments without a shell on Windows', () async {
      String? executable;
      List<String>? arguments;
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.windows,
        fileExists: (_) async => true,
        startProcess: (program, args) async {
          executable = program;
          arguments = args;
        },
      );

      await launcher.open(r'C:\notes\project plan.pdf');

      expect(executable, 'explorer.exe');
      expect(arguments, [r'C:\notes\project plan.pdf']);
    });

    test('uses open with one path argument on macOS', () async {
      String? executable;
      List<String>? arguments;
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.macos,
        fileExists: (_) async => true,
        startProcess: (program, args) async {
          executable = program;
          arguments = args;
        },
      );

      await launcher.open('/Users/ada/project plan.pdf');

      expect(executable, 'open');
      expect(arguments, ['/Users/ada/project plan.pdf']);
    });

    test('uses xdg-open with one path argument on Linux', () async {
      String? executable;
      List<String>? arguments;
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.linux,
        fileExists: (_) async => true,
        startProcess: (program, args) async {
          executable = program;
          arguments = args;
        },
      );

      await launcher.open('/home/ada/project plan.pdf');

      expect(executable, 'xdg-open');
      expect(arguments, ['/home/ada/project plan.pdf']);
    });

    test('passes a path with shell metacharacters unchanged', () async {
      const path = r' C:\资料\project plan & "draft".pdf ';
      String? checkedPath;
      String? executable;
      List<String>? arguments;
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.windows,
        fileExists: (candidate) async {
          checkedPath = candidate;
          return true;
        },
        startProcess: (program, args) async {
          executable = program;
          arguments = args;
        },
      );

      await launcher.open(path);

      expect(checkedPath, path);
      expect(executable, 'explorer.exe');
      expect(arguments, hasLength(1));
      expect(arguments, [path]);
    });

    for (final emptyPath in ['', '   ']) {
      test(
        'rejects empty path ${emptyPath.length} before side effects',
        () async {
          var existenceChecked = false;
          final launcher = IoFileLauncher(
            platform: DesktopPlatform.windows,
            fileExists: (_) async {
              existenceChecked = true;
              return true;
            },
            startProcess: (_, _) async => fail('must not start'),
          );

          await expectLater(
            launcher.open(emptyPath),
            throwsA(
              isA<FileLaunchException>()
                  .having(
                    (error) => error.kind,
                    'kind',
                    FileLaunchErrorKind.notFound,
                  )
                  .having((error) => error.message, 'message', '文件不存在或已被移动'),
            ),
          );
          expect(existenceChecked, isFalse);
        },
      );
    }

    test('rejects a missing result path before starting a process', () async {
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.windows,
        fileExists: (_) async => false,
        startProcess: (_, _) async => fail('must not start'),
      );

      await expectLater(
        launcher.open(r'C:\missing.pdf'),
        throwsA(
          isA<FileLaunchException>()
              .having(
                (error) => error.kind,
                'kind',
                FileLaunchErrorKind.notFound,
              )
              .having((error) => error.message, 'message', '文件不存在或已被移动'),
        ),
      );
    });

    test(
      'rejects an unsupported platform without starting a process',
      () async {
        var existenceChecks = 0;
        var processStarts = 0;
        final launcher = IoFileLauncher(
          platform: DesktopPlatform.unsupported,
          fileExists: (_) async {
            existenceChecks += 1;
            return true;
          },
          startProcess: (_, _) async {
            processStarts += 1;
          },
        );

        await expectLater(
          launcher.open('/tmp/report.pdf'),
          throwsA(
            isA<FileLaunchException>()
                .having(
                  (error) => error.kind,
                  'kind',
                  FileLaunchErrorKind.unsupportedPlatform,
                )
                .having((error) => error.message, 'message', '当前系统不支持打开文件')
                .having((error) => error.cause, 'cause', isNull),
          ),
        );
        expect(existenceChecks, 0);
        expect(processStarts, 0);
      },
    );

    test('maps ProcessException to launchFailed and preserves cause', () async {
      final cause = ProcessException(
        'explorer.exe',
        const [r'C:\notes\report.pdf'],
        'Access denied',
        5,
      );
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.windows,
        fileExists: (_) async => true,
        startProcess: (_, _) async => throw cause,
      );

      await expectLater(
        launcher.open(r'C:\notes\report.pdf'),
        throwsA(
          isA<FileLaunchException>()
              .having(
                (error) => error.kind,
                'kind',
                FileLaunchErrorKind.launchFailed,
              )
              .having((error) => error.message, 'message', '无法打开文件，请检查系统关联设置')
              .having((error) => error.cause, 'cause', same(cause)),
        ),
      );
    });

    test('preserves unexpected process start errors', () async {
      final cause = StateError('process start failed');
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.linux,
        fileExists: (_) async => true,
        startProcess: (_, _) async => throw cause,
      );

      await expectLater(launcher.open('/tmp/report.pdf'), throwsA(same(cause)));
    });

    test('preserves unexpected file existence errors', () async {
      final cause = StateError('existence check failed');
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.linux,
        fileExists: (_) async => throw cause,
        startProcess: (_, _) async => fail('must not start'),
      );

      await expectLater(launcher.open('/tmp/report.pdf'), throwsA(same(cause)));
    });

    test('maps file existence errors to launchFailed', () async {
      const cause = FileSystemException('permission denied');
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.macos,
        fileExists: (_) async => throw cause,
        startProcess: (_, _) async => fail('must not start'),
      );

      await expectLater(
        launcher.open('/Users/ada/report.pdf'),
        throwsA(
          isA<FileLaunchException>()
              .having(
                (error) => error.kind,
                'kind',
                FileLaunchErrorKind.launchFailed,
              )
              .having((error) => error.message, 'message', '无法打开文件，请检查系统关联设置')
              .having((error) => error.cause, 'cause', same(cause)),
        ),
      );
    });

    test('does not rewrap an injected FileLaunchException', () async {
      const cause = FileLaunchException(
        FileLaunchErrorKind.unsupportedPlatform,
        '自定义错误',
      );
      final launcher = IoFileLauncher(
        platform: DesktopPlatform.windows,
        fileExists: (_) async => true,
        startProcess: (_, _) async => throw cause,
      );

      await expectLater(
        launcher.open(r'C:\notes\report.pdf'),
        throwsA(same(cause)),
      );
    });
  });

  test('FileLaunchException exposes stable fields and toString', () {
    final cause = StateError('failure');
    final error = FileLaunchException(
      FileLaunchErrorKind.launchFailed,
      '无法打开文件，请检查系统关联设置',
      cause: cause,
    );

    expect(error.kind, FileLaunchErrorKind.launchFailed);
    expect(error.message, '无法打开文件，请检查系统关联设置');
    expect(error.cause, same(cause));
    expect(
      error.toString(),
      'FileLaunchException(FileLaunchErrorKind.launchFailed, '
      '无法打开文件，请检查系统关联设置)',
    );
  });

  test('currentDesktopPlatform reports the dart:io desktop platform', () {
    final expected = switch ((
      Platform.isWindows,
      Platform.isMacOS,
      Platform.isLinux,
    )) {
      (true, _, _) => DesktopPlatform.windows,
      (_, true, _) => DesktopPlatform.macos,
      (_, _, true) => DesktopPlatform.linux,
      _ => DesktopPlatform.unsupported,
    };

    expect(currentDesktopPlatform(), expected);
  });

  test('SystemPathClipboard copies the original path as text', () async {
    const path = r'C:\资料\project plan & "draft".pdf';
    MethodCall? clipboardCall;
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      clipboardCall = call;
      return null;
    });
    addTearDown(
      () => messenger.setMockMethodCallHandler(SystemChannels.platform, null),
    );
    final PathClipboard clipboard = SystemPathClipboard();

    await clipboard.copy(path);

    expect(clipboardCall?.method, 'Clipboard.setData');
    expect(clipboardCall?.arguments, {'text': path});
  });
}
