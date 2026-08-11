import 'package:content_retrieval_app/core/platform/file_launcher.dart';

final class UnsupportedFileLauncher implements FileLauncher {
  const UnsupportedFileLauncher();

  @override
  Future<void> open(String path) {
    throw const FileLaunchException(
      FileLaunchErrorKind.unsupportedPlatform,
      '当前系统不支持打开文件',
    );
  }
}

FileLauncher createPlatformFileLauncher() => const UnsupportedFileLauncher();

bool get platformFileActionsSupported => false;
