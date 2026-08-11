import 'package:flutter/services.dart';

final class PathClipboardException implements Exception {
  const PathClipboardException({this.cause});

  final String message = '无法复制路径，请稍后重试';
  final Object? cause;

  @override
  String toString() => 'PathClipboardException($message)';
}

abstract interface class PathClipboard {
  Future<void> copy(String path);
}

final class SystemPathClipboard implements PathClipboard {
  @override
  Future<void> copy(String path) async {
    try {
      await Clipboard.setData(ClipboardData(text: path));
    } on PlatformException catch (error) {
      throw PathClipboardException(cause: error);
    }
  }
}
