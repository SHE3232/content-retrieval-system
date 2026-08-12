import 'dart:io';

import 'package:content_retrieval_app/features/settings/data/settings_store_provider_io.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Android settings use the application private files directory', () {
    final file = resolveSettingsFile(
      isWindows: false,
      isMacOS: false,
      isAndroid: true,
      environment: const <String, String>{},
      systemTemp: Directory('/data/user/0/example/cache'),
      pathSeparator: '/',
    );

    expect(
      file.path,
      '/data/user/0/example/files/ContentRetrieval/settings.json',
    );
  });
}
