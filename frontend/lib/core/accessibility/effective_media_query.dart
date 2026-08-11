import 'package:flutter/widgets.dart';

double effectiveTextScale(MediaQueryData media, double preference) {
  final systemScale = media.textScaler.scale(1);
  return (systemScale * preference).clamp(1, 2).toDouble();
}

MediaQueryData effectiveMediaQuery(
  MediaQueryData media, {
  required double textScalePreference,
  required bool reduceMotionPreference,
}) {
  return media.copyWith(
    textScaler: TextScaler.linear(
      effectiveTextScale(media, textScalePreference),
    ),
    disableAnimations: media.disableAnimations || reduceMotionPreference,
  );
}

Duration accessibleDuration(BuildContext context, Duration normal) {
  return MediaQuery.disableAnimationsOf(context) ? Duration.zero : normal;
}
