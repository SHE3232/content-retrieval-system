import 'dart:async';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:content_retrieval_app/features/search/presentation/search_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fakes.dart';

void main() {
  group('SearchController', () {
    test('starts with the complete default search configuration', () {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);

      expect(controller.query, isEmpty);
      expect(controller.mode, RetrievalMode.hybrid);
      expect(controller.channels, SearchChannel.values.toSet());
      expect(controller.contentTypes, SearchContentType.values.toSet());
      expect(controller.state, SearchViewState.initial);
      expect(controller.response, isNull);
      expect(controller.error, isNull);
      expect(controller.queryError, isNull);
    });

    test('channels cannot be mutated through public state', () {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);
      final initialChannels = Set<SearchChannel>.of(controller.channels);

      expect(controller.channels.clear, throwsUnsupportedError);

      expect(controller.channels, initialChannels);
    });

    test('content types cannot be mutated through public state', () {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);
      final initialContentTypes = Set<SearchContentType>.of(
        controller.contentTypes,
      );

      expect(controller.contentTypes.clear, throwsUnsupportedError);

      expect(controller.contentTypes, initialContentTypes);
    });

    test('public filter views stay stable as internal state changes', () {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);
      final channelsView = controller.channels;
      final contentTypesView = controller.contentTypes;

      controller.setMode(RetrievalMode.semantic);
      controller.toggleContentType(SearchContentType.images);

      expect(identical(controller.channels, channelsView), isTrue);
      expect(channelsView, RetrievalMode.semantic.channels);
      expect(identical(controller.contentTypes, contentTypesView), isTrue);
      expect(contentTypesView, isNot(contains(SearchContentType.images)));
    });

    test(
      'blank submit reports validation without calling the service',
      () async {
        final client = FakeSearchService()
          ..results.add(searchResponse('kept', ['kept.txt']));
        final controller = SearchController(client);
        addTearDown(controller.dispose);
        controller.setQuery('kept');
        await controller.submit();
        final previousResponse = controller.response;
        final previousState = controller.state;

        controller.setQuery(' \t\n ');
        await controller.submit();

        expect(client.calls, hasLength(1));
        expect(controller.queryError, isNotEmpty);
        expect(controller.response, same(previousResponse));
        expect(controller.state, previousState);
      },
    );

    test('submit normalizes whitespace and clears query validation', () async {
      final client = FakeSearchService()
        ..results.add(searchResponse('alpha beta gamma', ['match.txt']));
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('   ');
      await controller.submit();
      expect(controller.queryError, isNotNull);

      controller.setQuery('  alpha\t beta \n gamma  ');
      await controller.submit();

      expect(client.calls.single.query, 'alpha beta gamma');
      expect(controller.queryError, isNull);
    });

    test(
      'submit publishes loading immediately and keeps the last response',
      () async {
        final pendingResponse = Completer<SearchResponse>();
        final client = FakeSearchService()
          ..results.addAll([
            searchResponse('first', ['first.txt']),
            pendingResponse.future,
          ]);
        final controller = SearchController(client);
        addTearDown(controller.dispose);
        controller.setQuery('first');
        await controller.submit();
        final previousResponse = controller.response;
        controller.setQuery('second');
        var notifications = 0;
        controller.addListener(() => notifications += 1);

        final submission = controller.submit();

        expect(controller.state, SearchViewState.loading);
        expect(controller.response, same(previousResponse));
        expect(notifications, 1);
        pendingResponse.complete(searchResponse('second', ['second.txt']));
        await submission;
      },
    );

    test('successful search publishes its response', () async {
      final result = searchResponse('found', ['one.txt']);
      final client = FakeSearchService()..results.add(result);
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('found');

      await controller.submit();

      expect(controller.state, SearchViewState.success);
      expect(controller.response, same(result));
      expect(controller.error, isNull);
    });

    test('response without hits publishes empty state', () async {
      final result = searchResponse('missing', const []);
      final client = FakeSearchService()..results.add(result);
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('missing');

      await controller.submit();

      expect(controller.state, SearchViewState.empty);
      expect(controller.response, same(result));
      expect(controller.error, isNull);
    });

    test('ApiException publishes structured failure', () async {
      const failure = ApiException(
        ApiErrorKind.offline,
        'Backend unavailable',
        code: 'offline',
      );
      final client = FakeSearchService()..results.add(failure);
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('query');

      await controller.submit();

      expect(controller.state, SearchViewState.failure);
      expect(controller.error, same(failure));
      expect(controller.response, isNull);
    });

    test('submit snapshots the current criteria', () async {
      final pendingResponse = Completer<SearchResponse>();
      final client = FakeSearchService()..results.add(pendingResponse.future);
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('snapshot');
      expect(controller.toggleChannel(SearchChannel.keyword), isTrue);
      controller.toggleContentType(SearchContentType.images);
      final expectedChannels = Set<SearchChannel>.of(controller.channels);
      final expectedContentTypes = Set<SearchContentType>.of(
        controller.contentTypes,
      );

      final submission = controller.submit();
      final criteria = client.calls.single;
      expect(criteria.query, 'snapshot');
      expect(criteria.channels, expectedChannels);
      expect(criteria.channels, isNotEmpty);
      expect(criteria.contentTypes, expectedContentTypes);
      expect(identical(criteria.channels, controller.channels), isFalse);
      expect(
        identical(criteria.contentTypes, controller.contentTypes),
        isFalse,
      );

      controller.toggleChannel(SearchChannel.keyword);
      controller.toggleContentType(SearchContentType.images);
      expect(criteria.channels, expectedChannels);
      expect(criteria.contentTypes, expectedContentTypes);

      pendingResponse.complete(searchResponse('snapshot', ['result.txt']));
      await submission;
    });

    test(
      'submit snapshots all criteria before loading listeners run',
      () async {
        final client = FakeSearchService()
          ..results.add(searchResponse('original query', ['result.txt']));
        final controller = SearchController(client);
        addTearDown(controller.dispose);
        controller.setQuery('  original\tquery  ');
        final submittedChannels = Set<SearchChannel>.of(controller.channels);
        final submittedContentTypes = Set<SearchContentType>.of(
          controller.contentTypes,
        );
        var changedDuringLoading = false;
        controller.addListener(() {
          if (controller.state != SearchViewState.loading ||
              changedDuringLoading) {
            return;
          }
          changedDuringLoading = true;
          controller.setQuery('changed query');
          controller.toggleChannel(SearchChannel.keyword);
          controller.toggleContentType(SearchContentType.images);
        });

        await controller.submit();

        final criteria = client.calls.single;
        expect(changedDuringLoading, isTrue);
        expect(criteria.query, 'original query');
        expect(criteria.channels, submittedChannels);
        expect(criteria.contentTypes, submittedContentTypes);
        expect(controller.query, 'changed query');
        expect(controller.channels, isNot(submittedChannels));
        expect(controller.contentTypes, isNot(submittedContentTypes));
      },
    );

    test('semantic mode copies exactly its declared channels', () {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);

      controller.setMode(RetrievalMode.semantic);

      expect(controller.mode, RetrievalMode.semantic);
      expect(controller.channels, RetrievalMode.semantic.channels);
      expect(
        identical(controller.channels, RetrievalMode.semantic.channels),
        isFalse,
      );
      expect(controller.toggleChannel(SearchChannel.textSemantic), isTrue);
      expect(RetrievalMode.semantic.channels, {
        SearchChannel.textSemantic,
        SearchChannel.imageSemantic,
      });
    });

    test('toggleChannel keeps the final channel selected', () {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);
      controller.setMode(RetrievalMode.exact);

      expect(controller.toggleChannel(SearchChannel.keyword), isFalse);
      expect(controller.channels, {SearchChannel.keyword});
      expect(controller.toggleChannel(SearchChannel.textSemantic), isTrue);
      expect(controller.channels, {
        SearchChannel.keyword,
        SearchChannel.textSemantic,
      });
      expect(controller.toggleChannel(SearchChannel.keyword), isTrue);
      expect(controller.channels, {SearchChannel.textSemantic});
    });

    test('toggleContentType permits no format restriction on submit', () async {
      final client = FakeSearchService()
        ..results.add(searchResponse('anything', const []));
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('anything');

      for (final contentType in SearchContentType.values) {
        controller.toggleContentType(contentType);
      }
      expect(controller.contentTypes, isEmpty);

      await controller.submit();

      expect(client.calls.single.contentTypes, isEmpty);
    });

    test('late response cannot replace a newer search', () async {
      final first = Completer<SearchResponse>();
      final second = Completer<SearchResponse>();
      final client = FakeSearchService()
        ..results.addAll([first.future, second.future]);
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('first');
      final firstCall = controller.submit();
      controller.setQuery('second');
      final secondCall = controller.submit();

      second.complete(searchResponse('second', ['new.txt']));
      await secondCall;
      first.complete(searchResponse('first', ['old.txt']));
      await firstCall;

      expect(controller.state, SearchViewState.success);
      expect(controller.response?.query, 'second');
      expect(controller.response?.hits.single.name, 'new.txt');
    });

    test('late failure cannot replace a newer search', () async {
      final first = Completer<SearchResponse>();
      final second = Completer<SearchResponse>();
      final client = FakeSearchService()
        ..results.addAll([first.future, second.future]);
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('first');
      final firstCall = controller.submit();
      controller.setQuery('second');
      final secondCall = controller.submit();

      second.complete(searchResponse('second', ['new.txt']));
      await secondCall;
      first.completeError(
        const ApiException(ApiErrorKind.timeout, 'Old request timed out'),
      );
      await firstCall;

      expect(controller.state, SearchViewState.success);
      expect(controller.response?.query, 'second');
      expect(controller.error, isNull);
    });

    test('dispose invalidates pending success and failure', () async {
      final success = Completer<SearchResponse>();
      final successClient = FakeSearchService()..results.add(success.future);
      final successController = SearchController(successClient);
      successController.setQuery('success');
      var successNotifications = 0;
      successController.addListener(() => successNotifications += 1);
      final successCall = successController.submit();
      successNotifications = 0;
      successController.dispose();
      success.complete(searchResponse('success', ['too-late.txt']));
      await successCall;

      expect(successController.state, SearchViewState.loading);
      expect(successController.response, isNull);
      expect(successController.error, isNull);
      expect(successNotifications, 0);
      expect(successController.dispose, returnsNormally);

      final failure = Completer<SearchResponse>();
      final failureClient = FakeSearchService()..results.add(failure.future);
      final failureController = SearchController(failureClient);
      failureController.setQuery('failure');
      var failureNotifications = 0;
      failureController.addListener(() => failureNotifications += 1);
      final failureCall = failureController.submit();
      failureNotifications = 0;
      failureController.dispose();
      failure.completeError(
        const ApiException(ApiErrorKind.offline, 'Too late'),
      );
      await failureCall;

      expect(failureController.state, SearchViewState.loading);
      expect(failureController.response, isNull);
      expect(failureController.error, isNull);
      expect(failureNotifications, 0);
      expect(failureController.dispose, returnsNormally);
    });

    test('changes notify without publishing no-op notifications', () async {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);
      var notifications = 0;
      controller.addListener(() => notifications += 1);

      controller.setQuery('query');
      expect(notifications, 1);
      controller.setQuery('query');
      expect(notifications, 1);
      controller.setMode(RetrievalMode.hybrid);
      expect(notifications, 1);
      controller.setMode(RetrievalMode.exact);
      expect(notifications, 2);
      expect(controller.toggleChannel(SearchChannel.keyword), isFalse);
      expect(notifications, 2);
      expect(controller.toggleChannel(SearchChannel.textSemantic), isTrue);
      expect(notifications, 3);
      controller.toggleContentType(SearchContentType.images);
      expect(notifications, 4);
    });

    test('user input clears an existing validation error', () async {
      final controller = SearchController(FakeSearchService());
      addTearDown(controller.dispose);
      controller.setQuery(' ');
      await controller.submit();
      var notifications = 0;
      controller.addListener(() => notifications += 1);

      controller.setQuery(' ');

      expect(controller.queryError, isNull);
      expect(notifications, 1);
    });

    test(
      'unexpected error restores initial state and original stack trace',
      () async {
        final failure = StateError('Programming failure');
        final originalStackTrace = StackTrace.fromString(
          'original search stack',
        );
        final controller = SearchController(
          _FailingSearchService(failure, originalStackTrace),
        );
        addTearDown(controller.dispose);
        controller.setQuery('query');
        var notifications = 0;
        controller.addListener(() => notifications += 1);
        Object? thrownError;
        StackTrace? thrownStackTrace;

        try {
          await controller.submit();
        } catch (error, stackTrace) {
          thrownError = error;
          thrownStackTrace = stackTrace;
        }

        expect(thrownError, same(failure));
        expect(thrownStackTrace.toString(), originalStackTrace.toString());
        expect(controller.state, SearchViewState.initial);
        expect(controller.error, isNull);
        expect(notifications, 2);
      },
    );

    test('unexpected error restores retained success state', () async {
      final client = FakeSearchService()
        ..results.add(searchResponse('first', ['first.txt']));
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('first');
      await controller.submit();
      final retainedResponse = controller.response;
      controller.setQuery('second');
      var notifications = 0;
      controller.addListener(() => notifications += 1);

      await expectLater(controller.submit(), throwsStateError);

      expect(controller.state, SearchViewState.success);
      expect(controller.response, same(retainedResponse));
      expect(controller.error, isNull);
      expect(notifications, 2);
    });

    test('unexpected error restores retained empty state', () async {
      final client = FakeSearchService()
        ..results.add(searchResponse('first', const []));
      final controller = SearchController(client);
      addTearDown(controller.dispose);
      controller.setQuery('first');
      await controller.submit();
      final retainedResponse = controller.response;
      controller.setQuery('second');

      await expectLater(controller.submit(), throwsStateError);

      expect(controller.state, SearchViewState.empty);
      expect(controller.response, same(retainedResponse));
      expect(controller.error, isNull);
    });

    test(
      'stale unexpected error propagates without changing newer state',
      () async {
        final first = Completer<SearchResponse>();
        final second = Completer<SearchResponse>();
        final client = FakeSearchService()
          ..results.addAll([first.future, second.future]);
        final controller = SearchController(client);
        addTearDown(controller.dispose);
        controller.setQuery('first');
        final firstCall = controller.submit();
        controller.setQuery('second');
        final secondCall = controller.submit();
        second.complete(searchResponse('second', ['new.txt']));
        await secondCall;
        var notifications = 0;
        controller.addListener(() => notifications += 1);
        final failure = StateError('Old programming failure');
        final expectation = expectLater(firstCall, throwsA(same(failure)));

        first.completeError(failure);
        await expectation;

        expect(controller.state, SearchViewState.success);
        expect(controller.response?.query, 'second');
        expect(controller.error, isNull);
        expect(notifications, 0);
      },
    );

    test(
      'disposed unexpected error propagates without updating state',
      () async {
        final pending = Completer<SearchResponse>();
        final client = FakeSearchService()..results.add(pending.future);
        final controller = SearchController(client);
        controller.setQuery('query');
        var notifications = 0;
        controller.addListener(() => notifications += 1);
        final submission = controller.submit();
        notifications = 0;
        controller.dispose();
        final failure = StateError('Disposed programming failure');
        final expectation = expectLater(submission, throwsA(same(failure)));

        pending.completeError(failure);
        await expectation;

        expect(controller.state, SearchViewState.loading);
        expect(controller.response, isNull);
        expect(controller.error, isNull);
        expect(notifications, 0);
      },
    );

    test('disposed controller ignores later commands', () async {
      final client = FakeSearchService();
      final controller = SearchController(client);
      controller.dispose();

      controller.setQuery('ignored');
      controller.setMode(RetrievalMode.exact);
      expect(controller.toggleChannel(SearchChannel.keyword), isFalse);
      controller.toggleContentType(SearchContentType.images);
      await controller.submit();

      expect(controller.query, isEmpty);
      expect(controller.mode, RetrievalMode.hybrid);
      expect(controller.channels, SearchChannel.values.toSet());
      expect(controller.contentTypes, SearchContentType.values.toSet());
      expect(client.calls, isEmpty);
    });
  });
}

SearchResponse searchResponse(String query, List<String> names) {
  return SearchResponse(
    query: query,
    hits: [
      for (final (index, name) in names.indexed)
        SearchHit(
          fileId: 'file-$index',
          sourceId: 'source-$index',
          path: '/tmp/$name',
          name: name,
          mimeType: 'text/plain',
          modality: 'text',
          score: 1,
          matchReasons: const [SearchChannel.keyword],
          snippet: null,
          pageNumber: null,
          paragraphNumber: null,
        ),
    ],
    totalCandidates: names.length,
    elapsedMs: 1,
    weights: const {'keyword': 1},
  );
}

final class _FailingSearchService implements SearchService {
  const _FailingSearchService(this.failure, this.stackTrace);

  final Object failure;
  final StackTrace stackTrace;

  @override
  Future<SearchResponse> search(SearchCriteria criteria) {
    return Future<SearchResponse>.error(failure, stackTrace);
  }
}
