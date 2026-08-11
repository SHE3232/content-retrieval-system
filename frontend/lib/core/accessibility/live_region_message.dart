import 'package:flutter/widgets.dart';

final class LiveRegionMessage extends StatelessWidget {
  const LiveRegionMessage({
    super.key,
    required this.message,
    this.child,
    this.excludeChildSemantics = true,
  });

  final String message;
  final Widget? child;
  final bool excludeChildSemantics;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      liveRegion: true,
      label: message,
      explicitChildNodes: !excludeChildSemantics,
      child: excludeChildSemantics
          ? ExcludeSemantics(child: child ?? Text(message))
          : (child ?? Text(message)),
    );
  }
}
