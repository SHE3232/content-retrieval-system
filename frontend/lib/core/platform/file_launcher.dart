export 'file_launcher_stub.dart' if (dart.library.io) 'file_launcher_io.dart';

enum DesktopPlatform { windows, macos, linux, unsupported }

enum FileLaunchErrorKind { unsupportedPlatform, notFound, launchFailed }

final class FileLaunchException implements Exception {
  const FileLaunchException(this.kind, this.message, {this.cause});

  final FileLaunchErrorKind kind;
  final String message;
  final Object? cause;

  @override
  String toString() => 'FileLaunchException($kind, $message)';
}

abstract interface class FileLauncher {
  Future<void> open(String path);
}
