import 'dart:async';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/core/api/json_transport.dart';
import 'package:content_retrieval_app/features/status/backend_status_client.dart';
import 'package:content_retrieval_app/features/status/backend_status_controller.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

void main() {
  group('BackendStatusClient', () {
    test(
      'isReady GETs the readiness path and only accepts status 200',
      () async {
        final transport = FakeJsonTransport()
          ..getResponses.addAll(const <JsonResponse>[
            JsonResponse(statusCode: 200, body: null),
            JsonResponse(statusCode: 204, body: null),
            JsonResponse(statusCode: 503, body: null),
          ]);
        final client = BackendStatusClient(transport);

        expect(await client.isReady(), isTrue);
        expect(await client.isReady(), isFalse);
        expect(await client.isReady(), isFalse);
        expect(transport.gets.map((request) => request.path), [
          '/health/ready',
          '/health/ready',
          '/health/ready',
        ]);
      },
    );

    test('fetchStats GETs and parses every integer count', () async {
      final transport = FakeJsonTransport()
        ..getResponses.add(
          const JsonResponse(
            statusCode: 200,
            body: {
              'record_count': 3,
              'file_count': 2,
              'text_record_count': 2,
              'image_record_count': 1,
            },
          ),
        );
      final client = BackendStatusClient(transport);

      final stats = await client.fetchStats();

      expect(transport.gets.single.path, '/v1/index/stats');
      expect(stats.recordCount, 3);
      expect(stats.fileCount, 2);
      expect(stats.textRecordCount, 2);
      expect(stats.imageRecordCount, 1);
    });

    test('fetchStats rejects fractional count values', () async {
      const validBody = <String, Object?>{
        'record_count': 3,
        'file_count': 2,
        'text_record_count': 2,
        'image_record_count': 1,
      };
      const fractionalFields = <String, double>{
        'record_count': 3.9,
        'file_count': 2.8,
        'text_record_count': 2.5,
        'image_record_count': 1.1,
      };
      final transport = FakeJsonTransport();
      for (final field in fractionalFields.entries) {
        transport.getResponses.add(
          JsonResponse(
            statusCode: 200,
            body: <String, Object?>{...validBody, field.key: field.value},
          ),
        );
      }
      final client = BackendStatusClient(transport);

      for (final fieldName in fractionalFields.keys) {
        await expectLater(
          client.fetchStats(),
          throwsA(
            isA<ApiException>()
                .having(
                  (error) => error.kind,
                  'kind for $fieldName',
                  ApiErrorKind.invalidResponse,
                )
                .having((error) => error.cause, 'cause', isNotNull),
          ),
        );
      }
    });

    test('fetchStats normalizes malformed bodies and fields', () async {
      final transport = FakeJsonTransport()
        ..getResponses.addAll(const <JsonResponse>[
          JsonResponse(statusCode: 200, body: <Object?>['not', 'an', 'object']),
          JsonResponse(
            statusCode: 200,
            body: {
              'record_count': 'three',
              'file_count': 2,
              'text_record_count': 2,
              'image_record_count': 1,
            },
          ),
          JsonResponse(
            statusCode: 200,
            body: {'record_count': 3, 'file_count': 2, 'text_record_count': 2},
          ),
        ]);
      final client = BackendStatusClient(transport);

      for (var index = 0; index < 3; index += 1) {
        await expectLater(
          client.fetchStats(),
          throwsA(
            isA<ApiException>()
                .having(
                  (error) => error.kind,
                  'kind',
                  ApiErrorKind.invalidResponse,
                )
                .having((error) => error.cause, 'cause', isNotNull),
          ),
        );
      }
    });

    test('fetchStats rejects a non-success response', () async {
      final transport = FakeJsonTransport()
        ..getResponses.add(
          const JsonResponse(
            statusCode: 503,
            body: {
              'record_count': 3,
              'file_count': 2,
              'text_record_count': 2,
              'image_record_count': 1,
            },
          ),
        );
      final client = BackendStatusClient(transport);

      await expectLater(client.fetchStats(), throwsA(isA<ApiException>()));
    });
  });

  group('BackendStatusController', () {
    test('starts in checking state without stats', () {
      final controller = BackendStatusController(FakeBackendStatusClient());
      addTearDown(controller.dispose);

      expect(controller.state, BackendConnectionState.checking);
      expect(controller.stats, isNull);
    });

    test('start checks immediately and publishes online stats', () async {
      final client = FakeBackendStatusClient()
        ..readyResults.add(true)
        ..statsResults.add(_stats);
      final controller = BackendStatusController(
        client,
        pollInterval: const Duration(hours: 1),
      );
      addTearDown(controller.dispose);

      await controller.start();

      expect(controller.state, BackendConnectionState.online);
      expect(controller.stats?.fileCount, 2);
      expect(client.readyCalls, 1);
    });

    test('offline refresh keeps last successful stats', () async {
      final client = FakeBackendStatusClient()
        ..readyResults.addAll([true, false])
        ..statsResults.add(_stats);
      final controller = BackendStatusController(
        client,
        pollInterval: const Duration(hours: 1),
      );
      addTearDown(controller.dispose);

      await controller.start();
      await controller.refresh();

      expect(controller.state, BackendConnectionState.offline);
      expect(controller.stats?.fileCount, 2);
    });

    test('overlapping refresh is ignored', () async {
      final readiness = Completer<bool>();
      final client = FakeBackendStatusClient()
        ..readyResults.add(readiness.future)
        ..statsResults.add(_stats);
      final controller = BackendStatusController(client);
      addTearDown(controller.dispose);

      final firstRefresh = controller.refresh();
      await controller.refresh();

      expect(client.readyCalls, 1);
      readiness.complete(true);
      await firstRefresh;
      expect(controller.state, BackendConnectionState.online);
    });

    test('readiness ApiException publishes offline', () async {
      final client = FakeBackendStatusClient()
        ..readyErrors.add(
          const ApiException(ApiErrorKind.offline, 'Backend unavailable'),
        );
      final controller = BackendStatusController(client);
      addTearDown(controller.dispose);

      await controller.refresh();

      expect(controller.state, BackendConnectionState.offline);
      expect(controller.stats, isNull);
    });

    test('stats ApiException keeps online state and last stats', () async {
      final client = FakeBackendStatusClient()
        ..readyResults.addAll([true, true])
        ..statsResults.add(_stats);
      final controller = BackendStatusController(
        client,
        pollInterval: const Duration(hours: 1),
      );
      addTearDown(controller.dispose);

      await controller.start();
      final successfulStats = controller.stats;
      client.statsErrors.add(
        const ApiException(ApiErrorKind.invalidResponse, 'Malformed stats'),
      );
      await controller.refresh();

      expect(controller.state, BackendConnectionState.online);
      expect(controller.stats, same(successfulStats));
    });

    testWidgets('polls once per interval and stops after dispose', (
      tester,
    ) async {
      final client = FakeBackendStatusClient()
        ..readyResults.addAll([true, true])
        ..statsResults.addAll([_stats, _stats]);
      final controller = BackendStatusController(
        client,
        pollInterval: const Duration(seconds: 1),
      );

      await controller.start();
      expect(client.readyCalls, 1);

      await tester.pump(const Duration(seconds: 1));
      expect(client.readyCalls, 2);

      controller.dispose();
      await tester.pump(const Duration(seconds: 2));
      expect(client.readyCalls, 2);
    });

    testWidgets('start does not create multiple polling timers', (
      tester,
    ) async {
      final client = FakeBackendStatusClient()
        ..readyResults.addAll([false, false, false, false]);
      final controller = BackendStatusController(
        client,
        pollInterval: const Duration(seconds: 1),
      );

      await controller.start();
      await controller.start();
      await tester.pump(const Duration(seconds: 1));

      expect(client.readyCalls, 3);
      controller.dispose();
    });

    testWidgets(
      'dispose during start prevents state changes notifications and timer',
      (tester) async {
        final readiness = Completer<bool>();
        final client = FakeBackendStatusClient()
          ..readyResults.add(readiness.future);
        final controller = BackendStatusController(
          client,
          pollInterval: const Duration(seconds: 1),
        );
        var notifications = 0;
        controller.addListener(() => notifications += 1);

        final starting = controller.start();
        controller.dispose();
        readiness.complete(false);
        await starting;
        await tester.pump(const Duration(seconds: 2));

        expect(controller.state, BackendConnectionState.checking);
        expect(notifications, 0);
        expect(client.readyCalls, 1);
      },
    );

    testWidgets(
      'dispose while stats load preserves state and prevents later work',
      (tester) async {
        final pendingStats = Completer<IndexStats>();
        final client = FakeBackendStatusClient()
          ..readyResults.add(true)
          ..statsResults.add(pendingStats.future);
        final controller = BackendStatusController(
          client,
          pollInterval: const Duration(seconds: 1),
        );
        var notifications = 0;
        controller.addListener(() => notifications += 1);

        final starting = controller.start();
        await tester.pump();
        expect(client.statsCalls, 1);
        expect(controller.state, BackendConnectionState.online);

        controller.dispose();
        pendingStats.complete(_stats);
        await starting;
        await tester.pump(const Duration(seconds: 2));

        expect(controller.state, BackendConnectionState.online);
        expect(controller.stats, isNull);
        expect(notifications, 0);
        expect(client.readyCalls, 1);
      },
    );
  });
}

const _stats = IndexStats(
  recordCount: 3,
  fileCount: 2,
  textRecordCount: 2,
  imageRecordCount: 1,
);
