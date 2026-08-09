import 'dart:async';

import 'package:content_retrieval_app/core/api/api_exception.dart';
import 'package:content_retrieval_app/features/status/backend_status_models.dart';
import 'package:flutter/foundation.dart';

final class BackendStatusController extends ChangeNotifier {
  BackendStatusController(
    this.api, {
    this.pollInterval = const Duration(seconds: 10),
  });

  final BackendStatusApi api;
  final Duration pollInterval;

  BackendConnectionState state = BackendConnectionState.checking;
  IndexStats? stats;

  bool _refreshing = false;
  bool _disposed = false;
  Timer? _timer;

  Future<void> start() async {
    if (_disposed) {
      return;
    }
    state = BackendConnectionState.checking;
    await refresh();
    if (_disposed) {
      return;
    }
    _timer ??= Timer.periodic(pollInterval, (_) => unawaited(refresh()));
  }

  Future<void> refresh() async {
    if (_refreshing || _disposed) {
      return;
    }
    _refreshing = true;
    try {
      final ready = await api.isReady();
      if (_disposed) {
        return;
      }
      state = ready
          ? BackendConnectionState.online
          : BackendConnectionState.offline;
      if (ready) {
        try {
          final nextStats = await api.fetchStats();
          if (_disposed) {
            return;
          }
          stats = nextStats;
        } on ApiException {
          // Search remains available when stats alone fail.
        }
      }
    } on ApiException {
      if (!_disposed) {
        state = BackendConnectionState.offline;
      }
    } finally {
      _refreshing = false;
      if (!_disposed) {
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    if (_disposed) {
      return;
    }
    _disposed = true;
    _timer?.cancel();
    super.dispose();
  }
}
