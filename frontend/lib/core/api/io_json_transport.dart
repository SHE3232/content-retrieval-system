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
    Future<HttpClientRequest>? openingRequest;
    HttpClientRequest? activeRequest;
    try {
      openingRequest = _client.openUrl(method, baseUri.resolve(path));
      final request = activeRequest = await openingRequest.timeout(timeout);
      request.headers.add(HttpHeaders.acceptHeader, ContentType.json.mimeType);
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close().timeout(timeout);
      final text = await utf8.decoder.bind(response.timeout(timeout)).join();
      final decoded = text.trim().isEmpty ? null : jsonDecode(text);
      return JsonResponse(statusCode: response.statusCode, body: decoded);
    } on TimeoutException catch (error) {
      activeRequest?.abort(error);
      if (activeRequest == null && openingRequest != null) {
        unawaited(
          openingRequest.then<void>(
            (request) => request.abort(error),
            onError: (_) {},
          ),
        );
      }
      throw ApiException(
        ApiErrorKind.timeout,
        'Request timed out',
        cause: error,
      );
    } on SocketException catch (error) {
      throw ApiException(
        ApiErrorKind.offline,
        'Backend is unreachable',
        cause: error,
      );
    } on HttpException catch (error) {
      throw ApiException(
        ApiErrorKind.invalidResponse,
        'Backend returned invalid HTTP response',
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
  void close() => _client.close(force: true);
}
