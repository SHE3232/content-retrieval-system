import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/features/search/domain/search_models.dart';
import 'package:flutter/foundation.dart';

enum SearchViewState { initial, loading, success, empty, failure }

final class SearchController extends ChangeNotifier {
  SearchController(this.service);

  final SearchService service;

  String query = '';
  RetrievalMode mode = RetrievalMode.hybrid;
  Set<SearchChannel> channels = SearchChannel.values.toSet();
  Set<SearchContentType> contentTypes = SearchContentType.values.toSet();
  SearchViewState state = SearchViewState.initial;
  SearchResponse? response;
  ApiException? error;
  String? queryError;

  int _requestVersion = 0;
  bool _disposed = false;

  void setQuery(String value) {
    if (_disposed) {
      return;
    }
    final changed = query != value;
    final clearedError = queryError != null;
    if (!changed && !clearedError) {
      return;
    }
    query = value;
    queryError = null;
    notifyListeners();
  }

  void setMode(RetrievalMode value) {
    if (_disposed) {
      return;
    }
    final nextChannels = Set<SearchChannel>.of(value.channels);
    if (mode == value && setEquals(channels, nextChannels)) {
      return;
    }
    mode = value;
    channels = nextChannels;
    notifyListeners();
  }

  bool toggleChannel(SearchChannel channel) {
    if (_disposed) {
      return false;
    }
    if (channels.contains(channel)) {
      if (channels.length == 1) {
        return false;
      }
      channels.remove(channel);
    } else {
      channels.add(channel);
    }
    notifyListeners();
    return true;
  }

  void toggleContentType(SearchContentType contentType) {
    if (_disposed) {
      return;
    }
    if (!contentTypes.remove(contentType)) {
      contentTypes.add(contentType);
    }
    notifyListeners();
  }

  Future<void> submit() async {
    if (_disposed) {
      return;
    }

    final normalizedQuery = query.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (normalizedQuery.isEmpty) {
      const validationMessage = 'Enter a search query';
      if (queryError != validationMessage) {
        queryError = validationMessage;
        notifyListeners();
      }
      return;
    }

    queryError = null;
    error = null;
    final requestVersion = ++_requestVersion;
    state = SearchViewState.loading;
    notifyListeners();

    final criteria = SearchCriteria(
      query: normalizedQuery,
      channels: Set<SearchChannel>.of(channels),
      contentTypes: Set<SearchContentType>.of(contentTypes),
    );

    try {
      final nextResponse = await service.search(criteria);
      if (_disposed || requestVersion != _requestVersion) {
        return;
      }
      response = nextResponse;
      state = nextResponse.hits.isEmpty
          ? SearchViewState.empty
          : SearchViewState.success;
      notifyListeners();
    } on ApiException catch (nextError) {
      if (_disposed || requestVersion != _requestVersion) {
        return;
      }
      error = nextError;
      state = SearchViewState.failure;
      notifyListeners();
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
