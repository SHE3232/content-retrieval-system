import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/search/data/search_api_client.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

void main() {
  test('serializes query channels formats and topK', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {
            'query': 'local notes',
            'hits': <Object?>[],
            'total_candidates': 0,
            'elapsed_ms': 4.5,
            'weights': {'keyword': 1.0},
          },
        ),
      );
    final client = SearchApiClient(transport);

    await client.search(
      const SearchCriteria(
        query: 'local notes',
        channels: {SearchChannel.keyword, SearchChannel.textSemantic},
        contentTypes: {SearchContentType.documents},
      ),
    );

    expect(transport.posts.single.path, '/v1/search');
    expect(transport.posts.single.body, {
      'query': 'local notes',
      'top_k': 20,
      'channels': ['keyword', 'text_semantic'],
      'filters': {
        'mime_types': [
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ],
        'modalities': ['text'],
      },
      'weights': null,
    });
  });

  test('serializes channels MIME types and modalities in enum order', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(_emptyResponse('ordered'));
    final client = SearchApiClient(transport);

    await client.search(
      const SearchCriteria(
        query: 'ordered',
        channels: {
          SearchChannel.imageSemantic,
          SearchChannel.keyword,
          SearchChannel.textSemantic,
        },
        contentTypes: {
          SearchContentType.images,
          SearchContentType.textFiles,
          SearchContentType.documents,
        },
        topK: 7,
      ),
    );

    expect(transport.posts.single.body, {
      'query': 'ordered',
      'top_k': 7,
      'channels': ['keyword', 'text_semantic', 'image_semantic'],
      'filters': {
        'mime_types': [
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/plain',
          'image/png',
          'image/jpeg',
          'image/webp',
        ],
        'modalities': ['text', 'image'],
      },
      'weights': null,
    });
  });

  test('serializes empty content types as empty filter lists', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(_emptyResponse('anything'));
    final client = SearchApiClient(transport);

    await client.search(
      const SearchCriteria(
        query: 'anything',
        channels: {SearchChannel.keyword},
        contentTypes: <SearchContentType>{},
      ),
    );

    expect(transport.posts.single.body['filters'], {
      'mime_types': <String>[],
      'modalities': <String>[],
    });
  });

  test('parses every response and hit field without scaling score', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {
            'query': 'project plan',
            'hits': <Object?>[
              {
                'file_id': 'file-123',
                'source_id': 'source-456',
                'path': r'C:\notes\project-plan.pdf',
                'name': 'project-plan.pdf',
                'mime_type': 'application/pdf',
                'modality': 'text',
                'score': 0.73125,
                'match_reasons': <Object?>['keyword', 'text_semantic'],
                'snippet': 'The local project plan',
                'page_number': 7,
                'paragraph_number': 3,
              },
            ],
            'total_candidates': 18,
            'elapsed_ms': 12.75,
            'weights': {'keyword': 0.35, 'text_semantic': 1},
          },
        ),
      );
    final client = SearchApiClient(transport);

    final response = await client.search(
      const SearchCriteria(
        query: 'project plan',
        channels: {SearchChannel.keyword},
        contentTypes: {SearchContentType.documents},
      ),
    );

    expect(response.query, 'project plan');
    expect(response.totalCandidates, 18);
    expect(response.elapsedMs, 12.75);
    expect(response.weights, {'keyword': 0.35, 'text_semantic': 1.0});
    expect(response.hits, hasLength(1));

    final hit = response.hits.single;
    expect(hit.fileId, 'file-123');
    expect(hit.sourceId, 'source-456');
    expect(hit.path, r'C:\notes\project-plan.pdf');
    expect(hit.name, 'project-plan.pdf');
    expect(hit.mimeType, 'application/pdf');
    expect(hit.modality, 'text');
    expect(hit.score, 0.73125);
    expect(hit.matchReasons, [
      SearchChannel.keyword,
      SearchChannel.textSemantic,
    ]);
    expect(hit.snippet, 'The local project plan');
    expect(hit.pageNumber, 7);
    expect(hit.paragraphNumber, 3);
  });

  test('maps a 422 backend detail to a rejected ApiException', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 422,
          body: {
            'detail': {
              'code': 'invalid_search_request',
              'message': 'Select at least one channel',
            },
          },
        ),
      );
    final client = SearchApiClient(transport);

    await expectLater(
      client.search(_criteria),
      throwsA(
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.rejected)
            .having((error) => error.code, 'code', 'invalid_search_request')
            .having(
              (error) => error.message,
              'message',
              'Select at least one channel',
            )
            .having((error) => error.statusCode, 'statusCode', 422),
      ),
    );
  });

  test('maps a 503 backend detail to a rejected ApiException', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 503,
          body: {
            'detail': {
              'code': 'search_unavailable',
              'message': 'The local index is unavailable',
            },
          },
        ),
      );
    final client = SearchApiClient(transport);

    await expectLater(
      client.search(_criteria),
      throwsA(
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.rejected)
            .having((error) => error.code, 'code', 'search_unavailable')
            .having(
              (error) => error.message,
              'message',
              'The local index is unavailable',
            )
            .having((error) => error.statusCode, 'statusCode', 503),
      ),
    );
  });

  test('normalizes malformed rejection detail fields', () async {
    final transport = FakeJsonTransport()
      ..postResponses.addAll(const <JsonResponse>[
        JsonResponse(
          statusCode: 422,
          body: {
            'detail': {'code': 17, 'message': 42},
          },
        ),
        JsonResponse(
          statusCode: 503,
          body: {
            'detail': {
              'code': <Object?>['not', 'a', 'string'],
              'message': <Object?>['temporarily', 'unavailable'],
            },
          },
        ),
      ]);
    final client = SearchApiClient(transport);

    for (final statusCode in <int>[422, 503]) {
      await expectLater(
        client.search(_criteria),
        throwsA(
          isA<ApiException>()
              .having((error) => error.kind, 'kind', ApiErrorKind.rejected)
              .having((error) => error.statusCode, 'statusCode', statusCode)
              .having(
                (error) => error.message,
                'message',
                'Search request failed',
              )
              .having((error) => error.code, 'code', isNull),
        ),
      );
    }
  });

  test('normalizes an unknown match reason to invalidResponse', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {
            'query': 'notes',
            'hits': <Object?>[
              {
                'file_id': 'file-123',
                'source_id': 'source-456',
                'path': 'notes.txt',
                'name': 'notes.txt',
                'mime_type': 'text/plain',
                'modality': 'text',
                'score': 0.4,
                'match_reasons': <Object?>['future_channel'],
                'snippet': null,
                'page_number': null,
                'paragraph_number': null,
              },
            ],
            'total_candidates': 1,
            'elapsed_ms': 1,
            'weights': {'future_channel': 1},
          },
        ),
      );
    final client = SearchApiClient(transport);

    await expectLater(
      client.search(_criteria),
      throwsA(
        isA<ApiException>().having(
          (error) => error.kind,
          'kind',
          ApiErrorKind.invalidResponse,
        ),
      ),
    );
  });

  test('normalizes malformed successful response structures', () async {
    final transport = FakeJsonTransport()
      ..postResponses.addAll(const <JsonResponse>[
        JsonResponse(statusCode: 200, body: <Object?>['not', 'a', 'map']),
        JsonResponse(
          statusCode: 200,
          body: {
            'query': 'notes',
            'hits': 'not a list',
            'total_candidates': 0,
            'elapsed_ms': 1,
            'weights': <String, Object?>{},
          },
        ),
      ]);
    final client = SearchApiClient(transport);

    for (var index = 0; index < 2; index++) {
      await expectLater(
        client.search(_criteria),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiErrorKind.invalidResponse,
          ),
        ),
      );
    }
  });
}

const _criteria = SearchCriteria(
  query: 'notes',
  channels: {SearchChannel.keyword},
  contentTypes: {SearchContentType.textFiles},
);

JsonResponse _emptyResponse(String query) => JsonResponse(
  statusCode: 200,
  body: {
    'query': query,
    'hits': <Object?>[],
    'total_candidates': 0,
    'elapsed_ms': 1,
    'weights': <String, Object?>{},
  },
);
