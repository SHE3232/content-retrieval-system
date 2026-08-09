import 'dart:convert';
import 'dart:io';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/io_json_transport.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('sends JSON requests and decodes JSON responses', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    server.listen((request) async {
      if (request.uri.path == '/get') {
        request.response
          ..statusCode = 200
          ..headers.contentType = ContentType.json
          ..write(jsonEncode({'status': 'ok'}));
      } else {
        final body = await utf8.decoder.bind(request).join();
        request.response
          ..statusCode = 202
          ..headers.contentType = ContentType.json
          ..write(body);
      }
      await request.response.close();
    });
    final transport = IoJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:${server.port}'),
      timeout: const Duration(seconds: 2),
    );
    addTearDown(transport.close);

    expect((await transport.get('/get')).body, {'status': 'ok'});
    final posted = await transport.post('/post', body: {'query': 'notes'});
    expect(posted.statusCode, 202);
    expect(posted.body, {'query': 'notes'});
  });

  test('maps malformed JSON to invalidResponse', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(() => server.close(force: true));
    server.listen((request) async {
      request.response
        ..statusCode = 200
        ..write('not-json');
      await request.response.close();
    });
    final transport = IoJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:${server.port}'),
      timeout: const Duration(seconds: 2),
    );
    addTearDown(transport.close);

    await expectLater(
      transport.get('/broken'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.kind,
          'kind',
          ApiErrorKind.invalidResponse,
        ),
      ),
    );
  });
}
