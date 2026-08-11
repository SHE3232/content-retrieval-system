import 'dart:convert';
import 'dart:io';

import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';

final class JsonFileSettingsStore implements SettingsStore {
  const JsonFileSettingsStore(this.file);

  final File file;

  @override
  Future<SettingsStoreSnapshot> load() async {
    if (!await file.exists()) {
      return const SettingsStoreSnapshot(
        values: <String, Object?>{},
        storageRecovered: false,
      );
    }

    try {
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! Map<String, dynamic>) {
        return _recoveredSnapshot;
      }
      return SettingsStoreSnapshot(
        values: Map<String, Object?>.unmodifiable(decoded),
        storageRecovered: false,
      );
    } on FormatException {
      return _recoveredSnapshot;
    }
  }

  @override
  Future<void> save(Map<String, Object?> values) async {
    final parent = file.parent;
    if (!await parent.exists()) await parent.create(recursive: true);

    final temporary = File('${file.path}.tmp');
    final backup = File('${file.path}.bak');
    try {
      await temporary.writeAsString(jsonEncode(values), flush: true);
      if (await backup.exists()) await backup.delete();
      if (await file.exists()) await file.rename(backup.path);
      try {
        await temporary.rename(file.path);
      } catch (_) {
        if (await backup.exists() && !await file.exists()) {
          await backup.rename(file.path);
        }
        rethrow;
      }
      if (await backup.exists()) await backup.delete();
    } finally {
      if (await temporary.exists()) await temporary.delete();
    }
  }

  static const _recoveredSnapshot = SettingsStoreSnapshot(
    values: <String, Object?>{},
    storageRecovered: true,
  );
}
