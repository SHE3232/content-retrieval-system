import 'dart:math' as math;

import 'package:content_retrieval_app/app/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  for (final theme in <ThemeData>[
    AppTheme.light(highContrast: true),
    AppTheme.dark(highContrast: true),
  ]) {
    test('${theme.brightness.name} high contrast tokens meet WCAG ratios', () {
      final scheme = theme.colorScheme;

      _expectRatio(scheme.onSurface, scheme.surface, 4.5, 'surface text');
      _expectRatio(scheme.onPrimary, scheme.primary, 4.5, 'primary text');
      _expectRatio(scheme.onError, scheme.error, 4.5, 'error text');
      _expectRatio(
        scheme.onErrorContainer,
        scheme.errorContainer,
        4.5,
        'persistent error notice text',
      );
      _expectRatio(
        scheme.onTertiaryContainer,
        scheme.tertiaryContainer,
        4.5,
        'persistent warning notice text',
      );
      _expectRatio(
        scheme.onSurface,
        scheme.surfaceContainerHigh,
        4.5,
        'persistent information notice text',
      );
      _expectRatio(
        scheme.onSecondaryContainer,
        scheme.secondaryContainer,
        4.5,
        'selected control text',
      );
      _expectRatio(scheme.outline, scheme.surface, 3, 'control boundary');
      _expectRatio(scheme.primary, scheme.surface, 3, 'focus indicator');
    });
  }

  test('high contrast variants use stronger boundaries than defaults', () {
    final normal = AppTheme.light();
    final highContrast = AppTheme.light(highContrast: true);

    expect(
      _contrastRatio(
        highContrast.colorScheme.outline,
        highContrast.colorScheme.surface,
      ),
      greaterThan(
        _contrastRatio(normal.colorScheme.outline, normal.colorScheme.surface),
      ),
    );
    expect(
      highContrast.dividerTheme.thickness,
      greaterThan(normal.dividerTheme.thickness!),
    );
  });
}

void _expectRatio(
  Color foreground,
  Color background,
  double minimum,
  String label,
) {
  expect(
    _contrastRatio(foreground, background),
    greaterThanOrEqualTo(minimum),
    reason: label,
  );
}

double _contrastRatio(Color foreground, Color background) {
  final lighter = math.max(
    foreground.computeLuminance(),
    background.computeLuminance(),
  );
  final darker = math.min(
    foreground.computeLuminance(),
    background.computeLuminance(),
  );
  return (lighter + 0.05) / (darker + 0.05);
}
