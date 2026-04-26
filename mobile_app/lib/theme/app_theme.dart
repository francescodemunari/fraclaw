import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Fraclaw Aurora Crystal Palette
  static const Color primaryDark = Color(0xFF05070A); // Ultra Dark Blue
  static const Color surfaceDark = Color(0xFF0A0C10);
  static const Color primaryCyan = Color(0xFF8190B2); // Silver Crystal Glow
  static const Color accentPurple = Color(0xFF4A2C5A); // Amethyst Depth
  static const Color neonCyan = Color(0xFF00FFFF);    // Neural High-Frequency
  static const Color textLight = Color(0xFFE1E2E8);
  static const Color textGrey = Color(0xFF8E9099);

  static ThemeData darkTheme = ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: primaryDark,
    primaryColor: primaryCyan,
    colorScheme: const ColorScheme.dark(
      primary: primaryCyan,
      secondary: accentPurple,
      surface: surfaceDark,
      onSurface: textLight,
    ),
    textTheme: GoogleFonts.interTextTheme().apply(
      bodyColor: textLight,
      displayColor: textLight,
    ).copyWith(
      headlineLarge: GoogleFonts.outfit(
        fontSize: 32,
        fontWeight: FontWeight.w900,
        letterSpacing: 8,
        color: textLight,
      ),
      titleLarge: GoogleFonts.outfit(
        fontSize: 20,
        fontWeight: FontWeight.w800,
        letterSpacing: 2,
        color: textLight,
      ),
      bodyLarge: GoogleFonts.inter(
        fontSize: 16,
        color: textLight,
        fontWeight: FontWeight.w400,
        height: 1.5,
      ),
      bodyMedium: GoogleFonts.inter(
        fontSize: 14,
        color: textLight,
        fontWeight: FontWeight.w300,
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: primaryDark,
      elevation: 0,
      centerTitle: true,
      iconTheme: IconThemeData(color: textLight),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white.withValues(alpha: 0.05),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      hintStyle: const TextStyle(color: textGrey, fontSize: 14),
    ),
  );
}
