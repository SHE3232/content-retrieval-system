enum ApiErrorKind { offline, timeout, invalidResponse, rejected }

final class ApiException implements Exception {
  const ApiException(
    this.kind,
    this.message, {
    this.code,
    this.statusCode,
    this.cause,
  });

  final ApiErrorKind kind;
  final String message;
  final String? code;
  final int? statusCode;
  final Object? cause;

  @override
  String toString() => 'ApiException($kind, $message)';
}
