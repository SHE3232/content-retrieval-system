enum SearchChannel {
  keyword('keyword'),
  textSemantic('text_semantic'),
  imageSemantic('image_semantic');

  const SearchChannel(this.wireName);

  final String wireName;
}

enum RetrievalMode {
  exact({SearchChannel.keyword}),
  hybrid({
    SearchChannel.keyword,
    SearchChannel.textSemantic,
    SearchChannel.imageSemantic,
  }),
  semantic({SearchChannel.textSemantic, SearchChannel.imageSemantic});

  const RetrievalMode(this.channels);

  final Set<SearchChannel> channels;
}

enum SearchContentType { documents, textFiles, images }

const contentTypeMimeTypes = <SearchContentType, List<String>>{
  SearchContentType.documents: [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ],
  SearchContentType.textFiles: ['text/plain'],
  SearchContentType.images: ['image/png', 'image/jpeg', 'image/webp'],
};

const contentTypeModalities = <SearchContentType, String>{
  SearchContentType.documents: 'text',
  SearchContentType.textFiles: 'text',
  SearchContentType.images: 'image',
};

final class SearchCriteria {
  const SearchCriteria({
    required this.query,
    required this.channels,
    required this.contentTypes,
    this.topK = 20,
  });

  final String query;
  final Set<SearchChannel> channels;
  final Set<SearchContentType> contentTypes;
  final int topK;
}

final class SearchHit {
  const SearchHit({
    required this.fileId,
    required this.sourceId,
    required this.path,
    required this.name,
    required this.mimeType,
    required this.modality,
    required this.score,
    required this.matchReasons,
    required this.snippet,
    required this.pageNumber,
    required this.paragraphNumber,
  });

  final String fileId;
  final String sourceId;
  final String path;
  final String name;
  final String mimeType;
  final String modality;
  final double score;
  final List<SearchChannel> matchReasons;
  final String? snippet;
  final int? pageNumber;
  final int? paragraphNumber;
}

final class SearchResponse {
  const SearchResponse({
    required this.query,
    required this.hits,
    required this.totalCandidates,
    required this.elapsedMs,
    required this.weights,
  });

  final String query;
  final List<SearchHit> hits;
  final int totalCandidates;
  final double elapsedMs;
  final Map<String, double> weights;
}

abstract interface class SearchService {
  Future<SearchResponse> search(SearchCriteria criteria);
}
