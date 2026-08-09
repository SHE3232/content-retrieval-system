final class JsonResponse {
  const JsonResponse({required this.statusCode, required this.body});

  final int statusCode;
  final Object? body;
}

abstract interface class JsonTransport {
  Future<JsonResponse> get(String path);

  Future<JsonResponse> post(String path, {required Map<String, Object?> body});

  void close();
}
