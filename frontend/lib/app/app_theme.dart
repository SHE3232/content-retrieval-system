import 'package:flutter/material.dart';

abstract final class AppTheme {
  static const _seedColor = Color(0xFF3659AD);
  static const _controlRadius = 12.0;

  static ThemeData light({bool highContrast = false}) =>
      _build(Brightness.light, highContrast: highContrast);

  static ThemeData dark({bool highContrast = false}) =>
      _build(Brightness.dark, highContrast: highContrast);

  static ThemeData _build(Brightness brightness, {required bool highContrast}) {
    final generatedScheme = ColorScheme.fromSeed(
      seedColor: _seedColor,
      brightness: brightness,
      contrastLevel: highContrast ? 1 : 0,
    );
    final scheme = highContrast
        ? _highContrastScheme(generatedScheme, brightness)
        : generatedScheme;
    final inputBorder = OutlineInputBorder(
      borderRadius: BorderRadius.circular(_controlRadius),
      borderSide: BorderSide(color: scheme.outline),
    );
    final controlShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(_controlRadius),
    );
    final inputLabelStyle = WidgetStateTextStyle.resolveWith((states) {
      if (states.contains(WidgetState.error)) {
        return TextStyle(color: scheme.error);
      }
      if (states.contains(WidgetState.disabled)) {
        return TextStyle(color: scheme.onSurface.withValues(alpha: 0.38));
      }
      if (states.contains(WidgetState.focused)) {
        return TextStyle(color: scheme.primary);
      }
      return TextStyle(color: scheme.onSurfaceVariant);
    });

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surfaceContainerLowest,
      cardTheme: CardThemeData(
        elevation: 0,
        color: scheme.surfaceContainerLow,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: WidgetStateColor.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) {
            return scheme.onSurface.withValues(alpha: 0.04);
          }
          return scheme.surfaceContainerHighest;
        }),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: inputBorder,
        enabledBorder: inputBorder,
        disabledBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
        errorBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.error),
        ),
        focusedErrorBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.error, width: 2),
        ),
        labelStyle: inputLabelStyle,
        floatingLabelStyle: inputLabelStyle,
        helperStyle: TextStyle(color: scheme.onSurfaceVariant),
        errorStyle: TextStyle(color: scheme.error),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: scheme.surfaceContainerLow,
        selectedColor: scheme.secondaryContainer,
        disabledColor: scheme.onSurface.withValues(alpha: 0.12),
        labelStyle: WidgetStateTextStyle.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) {
            // RawChip applies the disabled opacity while painting its label.
            return TextStyle(color: scheme.onSurface);
          }
          if (states.contains(WidgetState.selected)) {
            return TextStyle(color: scheme.onSecondaryContainer);
          }
          return TextStyle(color: scheme.onSurfaceVariant);
        }),
        side: WidgetStateBorderSide.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) {
            return BorderSide(color: scheme.onSurface.withValues(alpha: 0.12));
          }
          if (states.contains(WidgetState.selected)) {
            return BorderSide(color: scheme.secondary);
          }
          return BorderSide(color: scheme.outlineVariant);
        }),
        shape: controlShape,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        labelPadding: const EdgeInsets.symmetric(horizontal: 4),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          shape: controlShape,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: controlShape,
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          minimumSize: const Size.square(48),
          shape: controlShape,
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: scheme.surfaceContainerLow,
        indicatorColor: scheme.secondaryContainer,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
        minWidth: 72,
        selectedIconTheme: IconThemeData(color: scheme.onSecondaryContainer),
        unselectedIconTheme: IconThemeData(color: scheme.onSurfaceVariant),
        selectedLabelTextStyle: TextStyle(
          color: scheme.onSurface,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelTextStyle: TextStyle(color: scheme.onSurfaceVariant),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          foregroundColor: scheme.onPrimary,
          backgroundColor: scheme.primary,
          disabledForegroundColor: scheme.onSurface.withValues(alpha: 0.38),
          disabledBackgroundColor: scheme.onSurface.withValues(alpha: 0.12),
          shape: controlShape,
        ),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: scheme.inverseSurface,
          borderRadius: BorderRadius.circular(12),
        ),
        textStyle: TextStyle(color: scheme.onInverseSurface),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        waitDuration: const Duration(milliseconds: 500),
        showDuration: const Duration(seconds: 2),
        preferBelow: true,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(_controlRadius),
        ),
      ),
      popupMenuTheme: PopupMenuThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(_controlRadius),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        space: 1,
        thickness: highContrast ? 2 : 1,
      ),
    );
  }

  static ColorScheme _highContrastScheme(
    ColorScheme generated,
    Brightness brightness,
  ) {
    if (brightness == Brightness.light) {
      return generated.copyWith(
        primary: const Color(0xFF002A78),
        onPrimary: Colors.white,
        secondaryContainer: const Color(0xFFD6E1FF),
        onSecondaryContainer: const Color(0xFF001A42),
        surface: Colors.white,
        onSurface: const Color(0xFF101114),
        outline: const Color(0xFF42474F),
        outlineVariant: const Color(0xFF5F636B),
        error: const Color(0xFF8C0009),
        onError: Colors.white,
      );
    }
    return generated.copyWith(
      primary: const Color(0xFFADC6FF),
      onPrimary: const Color(0xFF001B3F),
      secondaryContainer: const Color(0xFF12315F),
      onSecondaryContainer: Colors.white,
      surface: const Color(0xFF0C0E12),
      onSurface: Colors.white,
      outline: const Color(0xFFC5C6CC),
      outlineVariant: const Color(0xFFAEB0B7),
      error: const Color(0xFFFFB4AB),
      onError: const Color(0xFF690005),
    );
  }
}
