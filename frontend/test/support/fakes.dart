import 'package:content_retrieval_app/core/api/json_transport.dart';

final class CapturedGet {
  const CapturedGet(this.path);

  final String path;
}

final class CapturedPost {
  const CapturedPost(this.path, this.body);

  final String path;
  final Map<String, Object?> body;
}

final class FakeJsonTransport implements JsonTransport {
  final List<JsonResponse> getResponses = <JsonResponse>[];
  final List<JsonResponse> postResponses = <JsonResponse>[];
  final List<CapturedGet> gets = <CapturedGet>[];
  final List<CapturedPost> posts = <CapturedPost>[];

  bool isClosed = false;

  @override
  Future<JsonResponse> get(String path) async {
    gets.add(CapturedGet(path));
    if (getResponses.isEmpty) {
      throw StateError('No queued GET response for $path');
    }
    return getResponses.removeAt(0);
  }

  @override
  Future<JsonResponse> post(
    String path, {
    required Map<String, Object?> body,
  }) async {
    posts.add(CapturedPost(path, Map<String, Object?>.unmodifiable(body)));
    if (postResponses.isEmpty) {
      throw StateError('No queued POST response for $path');
    }
    return postResponses.removeAt(0);
  }

  @override
  void close() {
    isClosed = true;
  }
}
