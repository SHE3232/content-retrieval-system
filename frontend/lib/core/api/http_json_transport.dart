import 'dart:async';
import 'dart:convert';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:http/http.dart' as http;

final class HttpJsonTransport implements JsonTransport {
  HttpJsonTransport({
    required this.baseUri,
    required this.timeout,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final Uri baseUri;
  final Duration timeout;
  final http.Client _client;
  bool _closed = false;

  @override
  Future<JsonResponse> get(String path) => _send('GET', path);

  @override
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  }) => _send('POST', path, body: body);

  @override
  Future<JsonResponse> delete(String path) => _send('DELETE', path);

  Future<JsonResponse> _send(
    String method,
    String path, {
    Map<String, Object?>? body,
  }) async {
    if (_closed) {
      throw const ApiException(ApiErrorKind.offline, 'Transport is closed');
    }

    final request = http.Request(method, baseUri.resolve(path))
      ..headers['accept'] = 'application/json';
    if (body != null) {
      request
        ..headers['content-type'] = 'application/json; charset=utf-8'
        ..body = jsonEncode(body);
    }

    try {
      final response = await _client.send(request).timeout(timeout);
      final bytes = await response.stream
          .timeout(timeout)
          .fold<List<int>>(<int>[], (buffer, chunk) => buffer..addAll(chunk));
      final text = utf8.decode(bytes);
      final Object? decoded = text.trim().isEmpty ? null : jsonDecode(text);
      return JsonResponse(statusCode: response.statusCode, body: decoded);
    } on TimeoutException catch (error) {
      throw ApiException(
        ApiErrorKind.timeout,
        'Request timed out',
        cause: error,
      );
    } on http.ClientException catch (error) {
      throw ApiException(
        ApiErrorKind.offline,
        'Backend is unreachable',
        cause: error,
      );
    } on FormatException catch (error) {
      throw ApiException(
        ApiErrorKind.invalidResponse,
        'Backend returned invalid JSON',
        cause: error,
      );
    }
  }

  @override
  void close() {
    if (_closed) return;
    _closed = true;
    _client.close();
  }
}
