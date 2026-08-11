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
