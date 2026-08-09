enum BackendConnectionState { checking, online, offline }

final class IndexStats {
  const IndexStats({
    required this.recordCount,
    required this.fileCount,
    required this.textRecordCount,
    required this.imageRecordCount,
  });

  final int recordCount;
  final int fileCount;
  final int textRecordCount;
  final int imageRecordCount;
}

abstract interface class BackendStatusApi {
  Future<bool> isReady();

  Future<IndexStats> fetchStats();
}
