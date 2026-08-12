import 'dart:io';

import 'package:content_retrieval_app/features/settings/data/json_file_settings_store.dart';
import 'package:content_retrieval_app/features/settings/data/settings_repository.dart';

SettingsStore createPlatformSettingsStore() {
  return JsonFileSettingsStore(
    resolveSettingsFile(
      isWindows: Platform.isWindows,
      isMacOS: Platform.isMacOS,
      isAndroid: Platform.isAndroid,
      environment: Platform.environment,
      systemTemp: Directory.systemTemp,
      pathSeparator: Platform.pathSeparator,
    ),
  );
}

File resolveSettingsFile({
  required bool isWindows,
  required bool isMacOS,
  required bool isAndroid,
  required Map<String, String> environment,
  required Directory systemTemp,
  required String pathSeparator,
}) {
  late final String directory;
  if (isWindows) {
    directory = environment['APPDATA'] ?? environment['LOCALAPPDATA'] ?? '.';
    return File(
      '$directory${pathSeparator}ContentRetrieval${pathSeparator}settings.json',
    );
  }
  if (isMacOS) {
    final home = environment['HOME'] ?? '.';
    return File(
      '$home/Library/Application Support/ContentRetrieval/settings.json',
    );
  }
  if (isAndroid) {
    return File(
      '${systemTemp.parent.path}${pathSeparator}files'
      '${pathSeparator}ContentRetrieval'
      '${pathSeparator}settings.json',
    );
  }
  final config = environment['XDG_CONFIG_HOME'];
  final home = environment['HOME'] ?? '.';
  directory = config == null || config.isEmpty ? '$home/.config' : config;
  return File('$directory/content-retrieval/settings.json');
}
