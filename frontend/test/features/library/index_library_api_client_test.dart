import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/library/data/index_library_api_client.dart';
import 'package:content_retrieval_app/features/library/domain/index_library_models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

const _sourceKey =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

void main() {
  test('fetchFiles maps the complete paged catalog response', () async {
    final transport = FakeJsonTransport()
      ..getResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {
            'items': [
              {
                'source_key': _sourceKey,
                'file_id': 'file-1',
                'path': r'C:\docs\guide.pdf',
                'name': 'guide.pdf',
                'mime_type': 'application/pdf',
                'modality': 'text',
                'size_bytes': 4096,
                'modified_at': '2026-08-10T10:00:00Z',
                'record_count': 4,
              },
            ],
            'page': 2,
            'page_size': 25,
            'total': 51,
            'total_pages': 3,
          },
        ),
      );

    final page = await IndexLibraryApiClient(
      transport,
    ).fetchFiles(page: 2, pageSize: 25);

    expect(transport.gets.single.path, '/v1/index/files?page=2&page_size=25');
    expect(page.page, 2);
    expect(page.pageSize, 25);
    expect(page.total, 51);
    expect(page.totalPages, 3);
    expect(page.items.single.sourceKey, _sourceKey);
    expect(page.items.single.modifiedAt, DateTime.utc(2026, 8, 10, 10));
    expect(page.items.single.recordCount, 4);
  });

  test('startIndexing sends the current backend directory contract', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 202,
          body: {'job_id': 'job-1', 'status': 'queued'},
        ),
      );

    final job = await IndexLibraryApiClient(
      transport,
    ).startIndexing(r'C:\docs');

    expect(transport.posts.single.path, '/v1/indexing/jobs');
    expect(transport.posts.single.body, {
      'paths': [r'C:\docs'],
      'authorized_roots': [r'C:\docs'],
      'recursive': true,
    });
    expect(job.jobId, 'job-1');
    expect(job.status, IndexJobStatus.queued);
    expect(job.result, isNull);
  });

  test('fetchJob maps completed_with_errors and all result counters', () async {
    final transport = FakeJsonTransport()
      ..getResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {
            'job_id': 'job-1',
            'status': 'completed_with_errors',
            'result': {
              'parsed_files': 5,
              'indexed_files': 4,
              'indexed_records': 12,
              'skipped_files': 1,
              'failed_files': 1,
              'partial_files': 1,
              'unchanged_files': 2,
              'removed_stale_records': 3,
              'failures': [],
            },
          },
        ),
      );

    final job = await IndexLibraryApiClient(transport).fetchJob('job/1');

    expect(transport.gets.single.path, '/v1/indexing/jobs/job%2F1');
    expect(job.status, IndexJobStatus.completedWithErrors);
    expect(job.result?.indexedRecords, 12);
    expect(job.result?.removedStaleRecords, 3);
  });

  test('fetchFailures maps file failures and terminal job error', () async {
    final transport = FakeJsonTransport()
      ..getResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {
            'job_id': 'job-1',
            'status': 'failed',
            'total': 1,
            'failures': [
              {
                'path': r'C:\docs\broken.pdf',
                'code': 'PARSE_FAILED',
                'message': 'Could not parse file',
                'stage': 'parse',
                'retryable': false,
                'file_id': 'file-2',
                'source_id': null,
              },
            ],
            'error': {
              'code': 'INDEXING_JOB_FAILED',
              'message': 'Indexing job failed unexpectedly',
              'retryable': true,
            },
          },
        ),
      );

    final details = await IndexLibraryApiClient(
      transport,
    ).fetchFailures('job-1');

    expect(details.status, IndexJobStatus.failed);
    expect(details.total, 1);
    expect(details.failures.single.path, r'C:\docs\broken.pdf');
    expect(details.failures.single.retryable, isFalse);
    expect(details.error?.code, 'INDEXING_JOB_FAILED');
  });

  test('reindex and remove map source-key mutation responses', () async {
    final transport = FakeJsonTransport()
      ..postResponses.add(
        const JsonResponse(
          statusCode: 202,
          body: {'job_id': 'job-2', 'status': 'queued'},
        ),
      )
      ..deleteResponses.add(
        const JsonResponse(
          statusCode: 200,
          body: {'source_key': _sourceKey, 'deleted_records': 7},
        ),
      );
    final client = IndexLibraryApiClient(transport);

    final job = await client.reindex(_sourceKey);
    final deleted = await client.remove(_sourceKey);

    expect(transport.posts.single.path, '/v1/index/files/$_sourceKey/reindex');
    expect(transport.posts.single.body, isEmpty);
    expect(job.jobId, 'job-2');
    expect(transport.deletes.single.path, '/v1/index/files/$_sourceKey');
    expect(deleted.deletedRecords, 7);
  });

  test('preserves structured 409 rejection details', () async {
    final transport = FakeJsonTransport()
      ..deleteResponses.add(
        const JsonResponse(
          statusCode: 409,
          body: {
            'detail': {
              'code': 'INDEX_MUTATION_CONFLICT',
              'message': 'Another index mutation is already running',
            },
          },
        ),
      );

    await expectLater(
      IndexLibraryApiClient(transport).remove(_sourceKey),
      throwsA(
        isA<ApiException>()
            .having((error) => error.kind, 'kind', ApiErrorKind.rejected)
            .having((error) => error.code, 'code', 'INDEX_MUTATION_CONFLICT')
            .having((error) => error.statusCode, 'statusCode', 409),
      ),
    );
  });

  test('rejects invalid source keys before transport side effects', () async {
    final transport = FakeJsonTransport();

    await expectLater(
      IndexLibraryApiClient(transport).reindex('../bad'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.kind,
          'kind',
          ApiErrorKind.invalidResponse,
        ),
      ),
    );
    expect(transport.posts, isEmpty);
  });

  test('normalizes malformed successful payloads to invalidResponse', () async {
    final transport = FakeJsonTransport()
      ..getResponses.add(
        const JsonResponse(statusCode: 200, body: {'items': 'not-a-list'}),
      );

    await expectLater(
      IndexLibraryApiClient(transport).fetchFiles(page: 1, pageSize: 20),
      throwsA(
        isA<ApiException>().having(
          (error) => error.kind,
          'kind',
          ApiErrorKind.invalidResponse,
        ),
      ),
    );
  });
}
