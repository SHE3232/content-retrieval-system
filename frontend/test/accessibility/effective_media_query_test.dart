import 'package:content_retrieval_app/core/accessibility/effective_media_query.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('composes system and user text scale and clamps at 200 percent', () {
    const system150 = MediaQueryData(textScaler: TextScaler.linear(1.5));

    expect(effectiveTextScale(system150, 1), 1.5);
    expect(effectiveTextScale(system150, 1.25), 1.875);
    expect(effectiveTextScale(system150, 2), 2);
    expect(effectiveTextScale(const MediaQueryData(), 0.5), 1);
  });

  test('preserves platform reduced motion when user preference is false', () {
    const media = MediaQueryData(
      textScaler: TextScaler.linear(1.25),
      disableAnimations: true,
      highContrast: true,
      accessibleNavigation: true,
    );

    final effective = effectiveMediaQuery(
      media,
      textScalePreference: 1.5,
      reduceMotionPreference: false,
    );

    expect(effective.textScaler.scale(1), 1.875);
    expect(effective.disableAnimations, isTrue);
    expect(effective.highContrast, isTrue);
    expect(effective.accessibleNavigation, isTrue);
  });
}
