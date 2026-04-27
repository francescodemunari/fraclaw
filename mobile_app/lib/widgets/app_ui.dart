import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Centralized UI utilities — styled dark glass popups and dialogs.
/// Use these everywhere instead of raw SnackBar/AlertDialog.
class AppUI {
  // ─── Snackbars ──────────────────────────────────────────────────────────────

  /// Standard dark glass info snackbar
  static SnackBar snackBar(
    String message, {
    IconData icon = Icons.info_outline_rounded,
    Color iconColor = AppTheme.primaryCyan,
    Duration duration = const Duration(seconds: 3),
    Widget? trailing,
  }) {
    return SnackBar(
      content: Row(
        children: [
          Icon(icon, color: iconColor, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.w400,
              ),
            ),
          ),
          if (trailing != null) trailing,
        ],
      ),
      backgroundColor: const Color(0xFF0F0F18),
      behavior: SnackBarBehavior.floating,
      duration: duration,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 24, left: 20, right: 20),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: iconColor.withAlpha(60), width: 1),
      ),
    );
  }

  /// Error variant — red border
  static SnackBar errorSnackBar(String message) {
    return snackBar(
      message,
      icon: Icons.error_outline_rounded,
      iconColor: Colors.redAccent,
    );
  }

  /// Recording in-progress snackbar
  static SnackBar recordingSnackBar() {
    return SnackBar(
      content: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: Colors.redAccent,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          const Text(
            'Recording... Tap again to send',
            style: TextStyle(color: Colors.white, fontSize: 13),
          ),
        ],
      ),
      backgroundColor: const Color(0xFF0F0F18),
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 30),
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 24, left: 20, right: 20),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.redAccent.withAlpha(80), width: 1),
      ),
    );
  }

  /// Downloading spinner snackbar
  static SnackBar downloadingSnackBar(String fileName) {
    return SnackBar(
      content: Row(
        children: [
          const SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppTheme.neonCyan,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Downloading $fileName…',
              style: const TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
        ],
      ),
      backgroundColor: const Color(0xFF0F0F18),
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 2),
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 24, left: 20, right: 20),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: AppTheme.neonCyan.withAlpha(60), width: 1),
      ),
    );
  }

  // ─── Dialogs ─────────────────────────────────────────────────────────────────

  /// Standard dark glass confirmation dialog
  static Future<bool?> confirmDialog(
    BuildContext context, {
    required String title,
    required String message,
    String confirmLabel = 'Confirm',
    String cancelLabel = 'Cancel',
    Color confirmColor = AppTheme.primaryCyan,
    bool destructive = false,
  }) {
    return showDialog<bool>(
      context: context,
      barrierColor: Colors.black54,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        child: Container(
          padding: const EdgeInsets.all(28),
          decoration: BoxDecoration(
            color: const Color(0xFF0D0D1A),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: (destructive ? Colors.redAccent : confirmColor).withAlpha(
                50,
              ),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withAlpha(120),
                blurRadius: 40,
                spreadRadius: -4,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    destructive
                        ? Icons.warning_amber_rounded
                        : Icons.help_outline_rounded,
                    color: destructive ? Colors.redAccent : confirmColor,
                    size: 20,
                  ),
                  const SizedBox(width: 10),
                  Text(
                    title,
                    style: TextStyle(
                      color: destructive ? Colors.redAccent : Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.5,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                message,
                style: const TextStyle(
                  color: Colors.white54,
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 28),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(ctx, false),
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.white38,
                    ),
                    child: Text(
                      cancelLabel,
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: () => Navigator.pop(ctx, true),
                    style: TextButton.styleFrom(
                      foregroundColor: destructive
                          ? Colors.redAccent
                          : confirmColor,
                      backgroundColor:
                          (destructive ? Colors.redAccent : confirmColor)
                              .withAlpha(20),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                        side: BorderSide(
                          color: (destructive ? Colors.redAccent : confirmColor)
                              .withAlpha(80),
                        ),
                      ),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 10,
                      ),
                    ),
                    child: Text(
                      confirmLabel,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// General-purpose info/content dialog
  static Future<void> infoDialog(
    BuildContext context, {
    required String title,
    required Widget content,
    List<Widget>? actions,
  }) {
    return showDialog<void>(
      context: context,
      barrierColor: Colors.black54,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        child: Container(
          padding: const EdgeInsets.all(28),
          decoration: BoxDecoration(
            color: const Color(0xFF0D0D1A),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: AppTheme.primaryCyan.withAlpha(40),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withAlpha(120),
                blurRadius: 40,
                spreadRadius: -4,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 20),
              content,
              if (actions != null) ...[
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: actions,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
