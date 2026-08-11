import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';

SettingsStore createPlatformSettingsStore() => _MemorySettingsStore();

final class _MemorySettingsStore implements SettingsStore {
  Map<String, Object?> _values = <String, Object?>{};

  @override
  Future<SettingsStoreSnapshot> load() async {
    return SettingsStoreSnapshot(
      values: Map<String, Object?>.unmodifiable(_values),
      storageRecovered: false,
    );
  }

  @override
  Future<void> save(Map<String, Object?> values) async {
    _values = Map<String, Object?>.from(values);
  }
}
