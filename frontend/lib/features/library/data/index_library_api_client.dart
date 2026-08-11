import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';

final class IndexLibraryApiClient implements IndexLibraryService {
  const IndexLibraryApiClient(this._transport);

  final JsonTransport _transport;

  static final RegExp _sourceKeyPattern = RegExp(r'^[0-9a-f]{64}$');

  @override
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  }) async {
    final query = Uri(
      queryParameters: <String, String>{
        'page': '$page',
        'page_size': '$pageSize',
      },
    ).query;
    final response = await _transport.get('/v1/index/files?$query');
    return _parseSuccess(response, _parseFilePage);
  }

  @override
  Future<IndexJob> startIndexing(String directory) async {
    final normalized = directory.trim();
    if (normalized.isEmpty) {
      throw const ApiException(
        ApiErrorKind.invalidResponse,
        'Directory path is empty',
      );
    }
    final response = await _transport.post(
      '/v1/indexing/jobs',
      body: <String, Object?>{
        'paths': <String>[normalized],
        'authorized_roots': <String>[normalized],
        'recursive': true,
      },
    );
    return _parseSuccess(response, _parseJob);
  }

  @override
  Future<IndexJob> fetchJob(String jobId) async {
    final response = await _transport.get(
      '/v1/indexing/jobs/${Uri.encodeComponent(jobId)}',
    );
    return _parseSuccess(response, _parseJob);
  }

  @override
  Future<IndexFailureDetails> fetchFailures(String jobId) async {
    final response = await _transport.get(
      '/v1/indexing/jobs/${Uri.encodeComponent(jobId)}/failures',
    );
    return _parseSuccess(response, _parseFailureDetails);
  }

  @override
  Future<IndexJob> reindex(String sourceKey) async {
    _validateSourceKey(sourceKey);
    final response = await _transport.post(
      '/v1/index/files/$sourceKey/reindex',
      body: const <String, Object?>{},
    );
    return _parseSuccess(response, _parseJob);
  }

  @override
  Future<DeletedIndexedFile> remove(String sourceKey) async {
    _validateSourceKey(sourceKey);
    final response = await _transport.delete('/v1/index/files/$sourceKey');
    return _parseSuccess(response, _parseDeletedFile);
  }

  T _parseSuccess<T>(
    JsonResponse response,
    T Function(Map<String, Object?> root) parser,
  ) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw _rejected(response);
    }
    try {
      return parser(_object(response.body, 'response'));
    } on ApiException {
      rethrow;
    } catch (error) {
      throw ApiException(
        ApiErrorKind.invalidResponse,
        'Index library response is malformed',
        statusCode: response.statusCode,
        cause: error,
      );
    }
  }

  IndexedFilePage _parseFilePage(Map<String, Object?> root) {
    final values = _list(root['items'], 'items');
    return IndexedFilePage(
      items: List<IndexedFile>.unmodifiable(
        values.map((value) => _parseFile(_object(value, 'file'))),
      ),
      page: _int(root['page'], 'page'),
      pageSize: _int(root['page_size'], 'page_size'),
      total: _int(root['total'], 'total'),
      totalPages: _int(root['total_pages'], 'total_pages'),
    );
  }

  IndexedFile _parseFile(Map<String, Object?> root) {
    return IndexedFile(
      sourceKey: _string(root['source_key'], 'source_key'),
      fileId: _string(root['file_id'], 'file_id'),
      path: _string(root['path'], 'path'),
      name: _string(root['name'], 'name'),
      mimeType: _string(root['mime_type'], 'mime_type'),
      modality: _string(root['modality'], 'modality'),
      sizeBytes: _int(root['size_bytes'], 'size_bytes'),
      modifiedAt: DateTime.parse(_string(root['modified_at'], 'modified_at')),
      recordCount: _int(root['record_count'], 'record_count'),
    );
  }

  IndexJob _parseJob(Map<String, Object?> root) {
    final result = root['result'];
    return IndexJob(
      jobId: _string(root['job_id'], 'job_id'),
      status: _status(root['status']),
      result: result == null ? null : _parseResult(_object(result, 'result')),
    );
  }

  IndexingResult _parseResult(Map<String, Object?> root) {
    final failures = _list(root['failures'], 'failures');
    return IndexingResult(
      parsedFiles: _int(root['parsed_files'], 'parsed_files'),
      indexedFiles: _int(root['indexed_files'], 'indexed_files'),
      indexedRecords: _int(root['indexed_records'], 'indexed_records'),
      skippedFiles: _int(root['skipped_files'], 'skipped_files'),
      failedFiles: _int(root['failed_files'], 'failed_files'),
      partialFiles: _int(root['partial_files'], 'partial_files'),
      unchangedFiles: _int(root['unchanged_files'], 'unchanged_files'),
      removedStaleRecords: _int(
        root['removed_stale_records'],
        'removed_stale_records',
      ),
      failures: List<IndexFailure>.unmodifiable(
        failures.map((value) => _parseFailure(_object(value, 'failure'))),
      ),
    );
  }

  IndexFailureDetails _parseFailureDetails(Map<String, Object?> root) {
    final failures = _list(root['failures'], 'failures');
    final error = root['error'];
    return IndexFailureDetails(
      jobId: _string(root['job_id'], 'job_id'),
      status: _status(root['status']),
      total: _int(root['total'], 'total'),
      failures: List<IndexFailure>.unmodifiable(
        failures.map((value) => _parseFailure(_object(value, 'failure'))),
      ),
      error: error == null ? null : _parseJobError(_object(error, 'error')),
    );
  }

  IndexFailure _parseFailure(Map<String, Object?> root) {
    return IndexFailure(
      path: _string(root['path'], 'path'),
      code: _string(root['code'], 'code'),
      message: _string(root['message'], 'message'),
      stage: _string(root['stage'], 'stage'),
      retryable: _bool(root['retryable'], 'retryable'),
      fileId: _nullableString(root['file_id'], 'file_id'),
      sourceId: _nullableString(root['source_id'], 'source_id'),
    );
  }

  IndexJobError _parseJobError(Map<String, Object?> root) {
    return IndexJobError(
      code: _string(root['code'], 'code'),
      message: _string(root['message'], 'message'),
      retryable: _bool(root['retryable'], 'retryable'),
    );
  }

  DeletedIndexedFile _parseDeletedFile(Map<String, Object?> root) {
    return DeletedIndexedFile(
      sourceKey: _string(root['source_key'], 'source_key'),
      deletedRecords: _int(root['deleted_records'], 'deleted_records'),
    );
  }

  IndexJobStatus _status(Object? value) {
    for (final status in IndexJobStatus.values) {
      if (value == status.wireName) return status;
    }
    throw FormatException('Unknown indexing status: $value');
  }

  void _validateSourceKey(String sourceKey) {
    if (!_sourceKeyPattern.hasMatch(sourceKey)) {
      throw const ApiException(
        ApiErrorKind.invalidResponse,
        'Invalid source key',
      );
    }
  }

  ApiException _rejected(JsonResponse response) {
    final root = response.body;
    final detail = root is Map<String, Object?> ? root['detail'] : null;
    final values = detail is Map<String, Object?> ? detail : const {};
    final message = values['message'];
    final code = values['code'];
    return ApiException(
      ApiErrorKind.rejected,
      message is String ? message : 'Index library request failed',
      code: code is String ? code : null,
      statusCode: response.statusCode,
    );
  }

  Map<String, Object?> _object(Object? value, String field) {
    if (value is Map<String, Object?>) return value;
    throw FormatException('$field must be an object');
  }

  List<Object?> _list(Object? value, String field) {
    if (value is List<Object?>) return value;
    throw FormatException('$field must be a list');
  }

  String _string(Object? value, String field) {
    if (value is String) return value;
    throw FormatException('$field must be a string');
  }

  String? _nullableString(Object? value, String field) {
    if (value == null) return null;
    return _string(value, field);
  }

  int _int(Object? value, String field) {
    if (value is int) return value;
    throw FormatException('$field must be an integer');
  }

  bool _bool(Object? value, String field) {
    if (value is bool) return value;
    throw FormatException('$field must be a boolean');
  }
}
