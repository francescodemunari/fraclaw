import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class AuroraBackground extends StatelessWidget {
  final Widget? child;
  const AuroraBackground({super.key, this.child});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _AuroraPainter(),
      child: child,
    );
  }
}

class _AuroraPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint();
    final rect = Rect.fromLTWH(0, 0, size.width, size.height);

    // Global clear background
    canvas.drawRect(rect, paint..color = AppTheme.primaryDark);

    // Aurora Blob 1: Amethyst Top Left
    final offset1 = Offset(size.width * 0.2, size.height * 0.2);
    paint.shader = RadialGradient(
      colors: [
        AppTheme.accentPurple.withValues(alpha: 0.12),
        AppTheme.accentPurple.withValues(alpha: 0.0),
      ],
      stops: const [0.0, 1.0],
    ).createShader(Rect.fromCircle(center: offset1, radius: size.width * 0.8));
    canvas.drawCircle(offset1, size.width * 0.8, paint);

    // Aurora Blob 2: Silver Crystal Bottom Right
    final offset2 = Offset(size.width * 0.8, size.height * 0.8);
    paint.shader = RadialGradient(
      colors: [
        AppTheme.primaryCyan.withValues(alpha: 0.08),
        AppTheme.primaryCyan.withValues(alpha: 0.0),
      ],
      stops: const [0.0, 1.0],
    ).createShader(Rect.fromCircle(center: offset2, radius: size.width * 0.6));
    canvas.drawCircle(offset2, size.width * 0.6, paint);

    // Aurora Blob 3: Accent Cyan Center
    final offset3 = Offset(size.width * 0.5, size.height * 0.6);
    paint.shader = RadialGradient(
      colors: [
        AppTheme.neonCyan.withValues(alpha: 0.03),
        AppTheme.neonCyan.withValues(alpha: 0.0),
      ],
      stops: const [0.0, 1.0],
    ).createShader(Rect.fromCircle(center: offset3, radius: size.width * 0.5));
    canvas.drawCircle(offset3, size.width * 0.5, paint);
  }

  @override
  bool shouldRepaint(covariant _AuroraPainter oldDelegate) => false;
}
