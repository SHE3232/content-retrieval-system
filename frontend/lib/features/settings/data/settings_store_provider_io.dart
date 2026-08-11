import 'dart:io';

import 'package:content_retrieval_app/features/settings/data/json_file_settings_store.dart';
import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';

SettingsStore createPlatformSettingsStore() {
  final environment = Platform.environment;
  late final String directory;
  if (Platform.isWindows) {
    directory = environment['APPDATA'] ?? environment['LOCALAPPDATA'] ?? '.';
    return JsonFileSettingsStore(
      File(
        '$directory${Platform.pathSeparator}ContentRetrieval${Platform.pathSeparator}settings.json',
      ),
    );
  }
  if (Platform.isMacOS) {
    final home = environment['HOME'] ?? '.';
    return JsonFileSettingsStore(
      File('$home/Library/Application Support/ContentRetrieval/settings.json'),
    );
  }
  final config = environment['XDG_CONFIG_HOME'];
  final home = environment['HOME'] ?? '.';
  directory = config == null || config.isEmpty ? '$home/.config' : config;
  return JsonFileSettingsStore(
    File('$directory/content-retrieval/settings.json'),
  );
}
