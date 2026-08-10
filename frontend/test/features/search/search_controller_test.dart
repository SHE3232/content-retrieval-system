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
      'unexpected service errors propagate instead of becoming failure',
      () async {
        final controller = SearchController(FakeSearchService());
        addTearDown(controller.dispose);
        controller.setQuery('query');

        await expectLater(controller.submit(), throwsStateError);

        expect(controller.state, SearchViewState.loading);
        expect(controller.error, isNull);
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
