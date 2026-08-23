export 'directory_picker_stub.dart'
    if (dart.library.io) 'io_directory_picker.dart';

final class DirectoryPickerException implements Exception {
  const DirectoryPickerException(this.message, {this.cause});

  final String message;
  final Object? cause;

  @override
  String toString() => 'DirectoryPickerException($message)';
}

abstract interface class DirectoryPicker {
  bool get isSupported;

  Future<String?> pickDirectory();
}

final class UnsupportedDirectoryPicker implements DirectoryPicker {
  const UnsupportedDirectoryPicker();

  @override
  bool get isSupported => false;

  @override
  Future<String?> pickDirectory() async => null;
}
