import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';
import 'package:content_retrieval_app/features/settings/data/settings_store_provider_stub.dart'
    if (dart.library.io) 'package:content_retrieval_app/features/settings/data/settings_store_provider_io.dart'
    if (dart.library.html) 'package:content_retrieval_app/features/settings/data/settings_store_provider_web.dart'
    as platform;

SettingsStore createPlatformSettingsStore() {
  return platform.createPlatformSettingsStore();
}
