enum IndexJobStatus {
  queued('queued'),
  running('running'),
  completed('completed'),
  completedWithErrors('completed_with_errors'),
  failed('failed');

  const IndexJobStatus(this.wireName);
  final String wireName;

  bool get isTerminal =>
      this == completed || this == completedWithErrors || this == failed;
}

final class IndexedFile {
  const IndexedFile({
    required this.sourceKey,
    required this.fileId,
    required this.path,
    required this.name,
    required this.mimeType,
    required this.modality,
    required this.sizeBytes,
    required this.modifiedAt,
    required this.recordCount,
  });

  final String sourceKey;
  final String fileId;
  final String path;
  final String name;
  final String mimeType;
  final String modality;
  final int sizeBytes;
  final DateTime modifiedAt;
  final int recordCount;
}

final class IndexedFilePage {
  const IndexedFilePage({
    required this.items,
    required this.page,
    required this.pageSize,
    required this.total,
    required this.totalPages,
  });

  final List<IndexedFile> items;
  final int page;
  final int pageSize;
  final int total;
  final int totalPages;
}

final class IndexFailure {
  const IndexFailure({
    required this.path,
    required this.code,
    required this.message,
    required this.stage,
    required this.retryable,
    required this.fileId,
    required this.sourceId,
  });

  final String path;
  final String code;
  final String message;
  final String stage;
  final bool retryable;
  final String? fileId;
  final String? sourceId;
}

final class IndexingResult {
  const IndexingResult({
    required this.parsedFiles,
    required this.indexedFiles,
    required this.indexedRecords,
    required this.skippedFiles,
    required this.failedFiles,
    required this.partialFiles,
    required this.unchangedFiles,
    required this.removedStaleRecords,
    required this.failures,
  });

  final int parsedFiles;
  final int indexedFiles;
  final int indexedRecords;
  final int skippedFiles;
  final int failedFiles;
  final int partialFiles;
  final int unchangedFiles;
  final int removedStaleRecords;
  final List<IndexFailure> failures;
}

final class IndexJob {
  const IndexJob({
    required this.jobId,
    required this.status,
    required this.result,
  });

  final String jobId;
  final IndexJobStatus status;
  final IndexingResult? result;
}

final class IndexJobError {
  const IndexJobError({
    required this.code,
    required this.message,
    required this.retryable,
  });

  final String code;
  final String message;
  final bool retryable;
}

final class IndexFailureDetails {
  const IndexFailureDetails({
    required this.jobId,
    required this.status,
    required this.total,
    required this.failures,
    required this.error,
  });

  final String jobId;
  final IndexJobStatus status;
  final int total;
  final List<IndexFailure> failures;
  final IndexJobError? error;
}

final class DeletedIndexedFile {
  const DeletedIndexedFile({
    required this.sourceKey,
    required this.deletedRecords,
  });

  final String sourceKey;
  final int deletedRecords;
}

abstract interface class IndexLibraryService {
  Future<IndexedFilePage> fetchFiles({
    required int page,
    required int pageSize,
  });

  Future<IndexJob> startIndexing(String directory);

  Future<IndexJob> fetchJob(String jobId);

  Future<IndexFailureDetails> fetchFailures(String jobId);

  Future<IndexJob> reindex(String sourceKey);

  Future<DeletedIndexedFile> remove(String sourceKey);
}
