import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';

final class BackendStatusClient implements BackendStatusApi {
  const BackendStatusClient(this._transport);

  final JsonTransport _transport;

  @override
  Future<bool> isReady() async {
    final response = await _transport.get('/health/ready');
    return response.statusCode == 200;
  }

  @override
  Future<IndexStats> fetchStats() async {
    final response = await _transport.get('/v1/index/stats');
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        ApiErrorKind.rejected,
        'Index stats request failed',
        statusCode: response.statusCode,
      );
    }

    try {
      final root = response.body;
      if (root is! Map<String, Object?>) {
        throw const FormatException('Index stats body must be an object');
      }
      return IndexStats(
        recordCount: (root['record_count'] as num).toInt(),
        fileCount: (root['file_count'] as num).toInt(),
        textRecordCount: (root['text_record_count'] as num).toInt(),
        imageRecordCount: (root['image_record_count'] as num).toInt(),
      );
    } catch (error) {
      throw ApiException(
        ApiErrorKind.invalidResponse,
        'Index stats response is malformed',
        statusCode: response.statusCode,
        cause: error,
      );
    }
  }
}
