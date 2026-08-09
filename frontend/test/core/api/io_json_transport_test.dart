import 'dart:async';
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
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.invalidResponse)
            .having((error) => error.cause, 'cause', isA<FormatException>()),
      ),
    );
  });

  test('times out while reading a stalled response body', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final releaseResponse = Completer<void>();
    addTearDown(() async {
      if (!releaseResponse.isCompleted) {
        releaseResponse.complete();
      }
      await server.close(force: true);
    });
    server.listen((request) async {
      request.response
        ..statusCode = 200
        ..headers.contentType = ContentType.json
        ..write('{"status":');
      await request.response.flush();
      await releaseResponse.future;
      await request.response.close();
    });
    final transport = IoJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:${server.port}'),
      timeout: const Duration(milliseconds: 200),
    );
    addTearDown(transport.close);

    final guardedRequest = transport
        .get('/stalled-body')
        .timeout(
          const Duration(seconds: 2),
          onTimeout: () => throw StateError(
            'Test guard expired before the transport timeout',
          ),
        );

    await expectLater(
      guardedRequest,
      throwsA(
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.timeout)
            .having((error) => error.cause, 'cause', isA<TimeoutException>()),
      ),
    );
  });

  test('maps truncated HTTP responses to invalidResponse', () async {
    final server = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    addTearDown(server.close);
    server.listen((socket) async {
      socket.write(
        'HTTP/1.1 200 OK\r\n'
        'Content-Type: application/json\r\n'
        'Content-Length: 64\r\n'
        'Connection: close\r\n'
        '\r\n'
        '{"status":',
      );
      await socket.flush();
      await socket.close();
    });
    final transport = IoJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:${server.port}'),
      timeout: const Duration(seconds: 2),
    );
    addTearDown(transport.close);

    await expectLater(
      transport.get('/truncated'),
      throwsA(
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.invalidResponse)
            .having((error) => error.cause, 'cause', isA<HttpException>()),
      ),
    );
  });
}
