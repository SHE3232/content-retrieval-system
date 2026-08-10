import 'package:flutter/services.dart';

abstract interface class PathClipboard {
  Future<void> copy(String path);
}

final class SystemPathClipboard implements PathClipboard {
  @override
  Future<void> copy(String path) =>
      Clipboard.setData(ClipboardData(text: path));
}
