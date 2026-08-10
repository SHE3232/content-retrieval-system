import 'dart:collection';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:flutter/foundation.dart';

enum SearchViewState { initial, loading, success, empty, failure }

final class SearchController extends ChangeNotifier {
  SearchController(this.service);

  final SearchService service;

  String _query = '';
  RetrievalMode _mode = RetrievalMode.hybrid;
  final Set<SearchChannel> _channels = SearchChannel.values.toSet();
  final Set<SearchContentType> _contentTypes = SearchContentType.values.toSet();
  late final Set<SearchChannel> _channelsView = UnmodifiableSetView(_channels);
  late final Set<SearchContentType> _contentTypesView = UnmodifiableSetView(
    _contentTypes,
  );
  SearchViewState _state = SearchViewState.initial;
  SearchResponse? _response;
  ApiException? _error;
  String? _queryError;

  int _requestVersion = 0;
  bool _disposed = false;

  String get query => _query;
  RetrievalMode get mode => _mode;
  Set<SearchChannel> get channels => _channelsView;
  Set<SearchContentType> get contentTypes => _contentTypesView;
  SearchViewState get state => _state;
  SearchResponse? get response => _response;
  ApiException? get error => _error;
  String? get queryError => _queryError;

  void setQuery(String value) {
    if (_disposed) {
      return;
    }
    final changed = _query != value;
    final clearedError = _queryError != null;
    if (!changed && !clearedError) {
      return;
    }
    _query = value;
    _queryError = null;
    notifyListeners();
  }

  void setMode(RetrievalMode value) {
    if (_disposed) {
      return;
    }
    final nextChannels = Set<SearchChannel>.of(value.channels);
    if (_mode == value && setEquals(_channels, nextChannels)) {
      return;
    }
    _mode = value;
    _channels
      ..clear()
      ..addAll(nextChannels);
    notifyListeners();
  }

  bool toggleChannel(SearchChannel channel) {
    if (_disposed) {
      return false;
    }
    if (_channels.contains(channel)) {
      if (_channels.length == 1) {
        return false;
      }
      _channels.remove(channel);
    } else {
      _channels.add(channel);
    }
    notifyListeners();
    return true;
  }

  void toggleContentType(SearchContentType contentType) {
    if (_disposed) {
      return;
    }
    if (!_contentTypes.remove(contentType)) {
      _contentTypes.add(contentType);
    }
    notifyListeners();
  }

  Future<void> submit() async {
    if (_disposed) {
      return;
    }

    final normalizedQuery = _query.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (normalizedQuery.isEmpty) {
      const validationMessage = 'Enter a search query';
      if (_queryError != validationMessage) {
        _queryError = validationMessage;
        notifyListeners();
      }
      return;
    }

    final criteria = SearchCriteria(
      query: normalizedQuery,
      channels: Set<SearchChannel>.of(_channels),
      contentTypes: Set<SearchContentType>.of(_contentTypes),
    );
    _queryError = null;
    _error = null;
    final requestVersion = ++_requestVersion;
    _state = SearchViewState.loading;
    notifyListeners();

    try {
      final nextResponse = await service.search(criteria);
      if (_disposed || requestVersion != _requestVersion) {
        return;
      }
      _response = nextResponse;
      _state = nextResponse.hits.isEmpty
          ? SearchViewState.empty
          : SearchViewState.success;
      notifyListeners();
    } on ApiException catch (nextError) {
      if (_disposed || requestVersion != _requestVersion) {
        return;
      }
      _error = nextError;
      _state = SearchViewState.failure;
      notifyListeners();
    } catch (unexpectedError, stackTrace) {
      if (!_disposed && requestVersion == _requestVersion) {
        final retainedResponse = _response;
        _state = retainedResponse == null
            ? SearchViewState.initial
            : retainedResponse.hits.isEmpty
            ? SearchViewState.empty
            : SearchViewState.success;
        _error = null;
        notifyListeners();
      }
      Error.throwWithStackTrace(unexpectedError, stackTrace);
    }
  }

  @override
  void dispose() {
    if (_disposed) {
      return;
    }
    _disposed = true;
    _requestVersion += 1;
    super.dispose();
  }
}
