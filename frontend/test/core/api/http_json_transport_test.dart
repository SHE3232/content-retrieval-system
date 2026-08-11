import 'dart:async';
import 'dart:convert';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/http_json_transport.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('sends GET POST and DELETE as JSON requests', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.method == 'DELETE') {
        return http.Response('', 204);
      }
      return http.Response(
        request.method == 'GET' ? '{"status":"ok"}' : request.body,
        request.method == 'GET' ? 200 : 202,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final transport = HttpJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:8000'),
      timeout: const Duration(seconds: 2),
      client: client,
    );
    addTearDown(transport.close);

    expect((await transport.get('/health')).body, {'status': 'ok'});
    expect((await transport.post('/search', body: {'query': 'notes'})).body, {
      'query': 'notes',
    });
    expect((await transport.delete('/index/files/abc')).statusCode, 204);

    expect(requests.map((request) => request.method), [
      'GET',
      'POST',
      'DELETE',
    ]);
    expect(requests[1].headers['content-type'], contains('application/json'));
    expect(requests[1].headers['accept'], 'application/json');
    expect(requests[2].body, isEmpty);
  });

  test('maps malformed JSON to invalidResponse with its cause', () async {
    final transport = HttpJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:8000'),
      timeout: const Duration(seconds: 2),
      client: MockClient((_) async => http.Response('not-json', 200)),
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

  test('maps a stalled response body to timeout', () async {
    final client = _StalledClient();
    final transport = HttpJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:8000'),
      timeout: const Duration(milliseconds: 100),
      client: client,
    );
    addTearDown(() {
      client.release();
      transport.close();
    });

    await expectLater(
      transport.get('/stalled'),
      throwsA(
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.timeout)
            .having((error) => error.cause, 'cause', isA<TimeoutException>()),
      ),
    );
  });

  test('close closes the injected client exactly once', () {
    final client = _RecordingClient();
    final transport = HttpJsonTransport(
      baseUri: Uri.parse('http://127.0.0.1:8000'),
      timeout: const Duration(seconds: 2),
      client: client,
    );

    transport.close();
    transport.close();

    expect(client.closeCalls, 1);
  });
}

final class _RecordingClient extends http.BaseClient {
  int closeCalls = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return http.StreamedResponse(
      Stream.value(utf8.encode('{}')),
      200,
      headers: {'content-type': 'application/json'},
    );
  }

  @override
  void close() {
    closeCalls += 1;
  }
}

final class _StalledClient extends http.BaseClient {
  final StreamController<List<int>> _controller = StreamController<List<int>>();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    _controller.add(utf8.encode('{"status":'));
    return http.StreamedResponse(
      _controller.stream,
      200,
      headers: {'content-type': 'application/json'},
    );
  }

  void release() {
    if (!_controller.isClosed) {
      _controller.close();
    }
  }

  @override
  void close() {}
}
