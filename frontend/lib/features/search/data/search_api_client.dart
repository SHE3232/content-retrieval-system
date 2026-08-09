import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';

final class SearchApiClient implements SearchService {
  const SearchApiClient(this._transport);

  final JsonTransport _transport;

  @override
  Future<SearchResponse> search(SearchCriteria criteria) async {
    final response = await _transport.post(
      '/v1/search',
      body: _serialize(criteria),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw _rejected(response);
    }

    try {
      final root = response.body;
      if (root is! Map<String, Object?>) {
        throw const FormatException('Search response body must be an object');
      }
      return _parseResponse(root);
    } on ApiException {
      rethrow;
    } catch (error) {
      throw ApiException(
        ApiErrorKind.invalidResponse,
        'Search response is malformed',
        statusCode: response.statusCode,
        cause: error,
      );
    }
  }

  Map<String, Object?> _serialize(SearchCriteria criteria) {
    final mimeTypes = <String>[];
    final modalities = <String>[];

    for (final contentType in SearchContentType.values) {
      if (!criteria.contentTypes.contains(contentType)) {
        continue;
      }
      mimeTypes.addAll(contentTypeMimeTypes[contentType]!);
      final modality = contentTypeModalities[contentType]!;
      if (!modalities.contains(modality)) {
        modalities.add(modality);
      }
    }

    return <String, Object?>{
      'query': criteria.query,
      'top_k': criteria.topK,
      'channels': <String>[
        for (final channel in SearchChannel.values)
          if (criteria.channels.contains(channel)) channel.wireName,
      ],
      'filters': <String, Object?>{
        'mime_types': mimeTypes,
        'modalities': modalities,
      },
      'weights': null,
    };
  }

  SearchResponse _parseResponse(Map<String, Object?> root) {
    final hitValues = root['hits'] as List<Object?>;
    final weightValues = root['weights'] as Map<String, Object?>;

    return SearchResponse(
      query: root['query'] as String,
      hits: List<SearchHit>.unmodifiable(hitValues.map(_parseHit)),
      totalCandidates: (root['total_candidates'] as num).toInt(),
      elapsedMs: (root['elapsed_ms'] as num).toDouble(),
      weights: Map<String, double>.unmodifiable(
        weightValues.map(
          (key, value) =>
              MapEntry<String, double>(key, (value as num).toDouble()),
        ),
      ),
    );
  }

  SearchHit _parseHit(Object? value) {
    if (value is! Map<String, Object?>) {
      throw const FormatException('Search hit must be an object');
    }

    final matchReasonValues = value['match_reasons'] as List<Object?>;
    return SearchHit(
      fileId: value['file_id'] as String,
      sourceId: value['source_id'] as String,
      path: value['path'] as String,
      name: value['name'] as String,
      mimeType: value['mime_type'] as String,
      modality: value['modality'] as String,
      score: (value['score'] as num).toDouble(),
      matchReasons: List<SearchChannel>.unmodifiable(
        matchReasonValues.map(_parseChannel),
      ),
      snippet: value['snippet'] as String?,
      pageNumber: (value['page_number'] as num?)?.toInt(),
      paragraphNumber: (value['paragraph_number'] as num?)?.toInt(),
    );
  }

  SearchChannel _parseChannel(Object? value) {
    for (final channel in SearchChannel.values) {
      if (value == channel.wireName) {
        return channel;
      }
    }
    throw ApiException(
      ApiErrorKind.invalidResponse,
      'Unknown search match reason: $value',
    );
  }

  ApiException _rejected(JsonResponse response) {
    final root = response.body;
    final detail = root is Map<String, Object?> ? root['detail'] : null;
    final values = detail is Map<String, Object?> ? detail : const {};
    final message = values['message'];
    final code = values['code'];
    return ApiException(
      ApiErrorKind.rejected,
      message is String ? message : 'Search request failed',
      code: code is String ? code : null,
      statusCode: response.statusCode,
    );
  }
}
