import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'api_exception.dart';
import 'json_transport.dart';

final class IoJsonTransport implements JsonTransport {
  IoJsonTransport({required this.baseUri, required this.timeout})
    : _client = HttpClient();

  final Uri baseUri;
  final Duration timeout;
  final HttpClient _client;

  @override
  Future<JsonResponse> get(String path) => _send('GET', path);

  @override
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  }) => _send('POST', path, body: body);

  Future<JsonResponse> _send(
    String method,
    String path, {
    Map<String, Object?>? body,
  }) async {
    try {
      final request = await _client.openUrl(method, baseUri.resolve(path));
      request.headers.add(HttpHeaders.acceptHeader, ContentType.json.mimeType);
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(timeout);
      final text = await utf8.decoder.bind(response).join();
      final decoded = text.trim().isEmpty ? null : jsonDecode(text);
      return JsonResponse(statusCode: response.statusCode, body: decoded);
    } on TimeoutException {
      throw const ApiException(ApiErrorKind.timeout, 'Request timed out');
    } on SocketException {
      throw const ApiException(ApiErrorKind.offline, 'Backend is unreachable');
    } on FormatException {
      throw const ApiException(
        ApiErrorKind.invalidResponse,
        'Backend returned invalid JSON',
      );
    }
  }

  @override
  void close() => _client.close(force: true);
}
