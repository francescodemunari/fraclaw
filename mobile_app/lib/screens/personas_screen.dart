import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/socket_service.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_container.dart';
import '../widgets/app_ui.dart';
import '../widgets/aurora_background.dart';

class PersonasScreen extends StatelessWidget {
  const PersonasScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final socketService = context.watch<SocketService>();

    return Scaffold(
      backgroundColor: AppTheme.primaryDark,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Text(
          'NEURAL IDENTITIES',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            letterSpacing: 4,
            shadows: [
              Shadow(
                color: AppTheme.neonCyan.withValues(alpha: 0.5),
                blurRadius: 10,
              ),
            ],
          ),
        ),
      ),
      body: AuroraBackground(
        child: socketService.personas.isEmpty
            ? const Center(
                child: CircularProgressIndicator(color: AppTheme.primaryCyan),
              )
            : ListView.builder(
                padding: const EdgeInsets.fromLTRB(20, 120, 20, 40),
                itemCount: socketService.personas.length,
                itemBuilder: (context, index) {
                  final persona = socketService.personas[index];
                  final personaName = persona['name'] as String;
                  final personaDescription =
                      persona['description'] as String? ?? 'Neural Identity';
                  final isActive = socketService.activePersona == personaName;

                  return Padding(
                    padding: const EdgeInsets.only(bottom: 20),
                    child: GestureDetector(
                      onTap: () async {
                        final success = await socketService.activatePersona(
                          personaName,
                        );
                        if (success && context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            AppUI.snackBar('Switched to $personaName identity'),
                          );
                        }
                      },
                      child: Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(
                            color: isActive
                                ? AppTheme.primaryCyan.withValues(alpha: 0.5)
                                : Colors.white.withValues(alpha: 0.1),
                            width: isActive ? 2 : 1,
                          ),
                          boxShadow: isActive
                              ? [
                                  BoxShadow(
                                    color: AppTheme.primaryCyan.withValues(
                                      alpha: 0.2,
                                    ),
                                    blurRadius: 15,
                                    spreadRadius: 1,
                                  ),
                                ]
                              : [],
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(24),
                          child: GlassContainer(
                            borderRadius: 24,
                            opacity: isActive ? 0.15 : 0.05,
                            blur: 15,
                            child: Padding(
                              padding: const EdgeInsets.all(24),
                              child: Row(
                                children: [
                                  Container(
                                    width: 56,
                                    height: 56,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: isActive
                                          ? AppTheme.primaryCyan.withValues(
                                              alpha: 0.2,
                                            )
                                          : Colors.white.withValues(
                                              alpha: 0.05,
                                            ),
                                      border: Border.all(
                                        color: isActive
                                            ? AppTheme.primaryCyan
                                            : Colors.white12,
                                        width: 1.5,
                                      ),
                                    ),
                                    child: ClipOval(
                                      child: Image.asset(
                                        'assets/${personaName.toLowerCase()}.png',
                                        fit: BoxFit.cover,
                                        errorBuilder:
                                            (context, error, stackTrace) {
                                              return Center(
                                                child: Icon(
                                                  isActive
                                                      ? Icons.psychology
                                                      : Icons
                                                            .psychology_outlined,
                                                  color: isActive
                                                      ? AppTheme.primaryCyan
                                                      : Colors.white38,
                                                  size: 30,
                                                ),
                                              );
                                            },
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 20),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          personaName.toUpperCase(),
                                          style: TextStyle(
                                            color: isActive
                                                ? Colors.white
                                                : Colors.white70,
                                            fontWeight: FontWeight.w900,
                                            letterSpacing: 1.5,
                                            fontSize: 16,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          isActive
                                              ? 'Currently Active'
                                              : personaDescription,
                                          style: TextStyle(
                                            color: isActive
                                                ? AppTheme.neonCyan
                                                : Colors.white30,
                                            fontSize: 12,
                                            fontWeight: FontWeight.w300,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  if (isActive)
                                    const Icon(
                                      Icons.check_circle_rounded,
                                      color: AppTheme.primaryCyan,
                                    ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}
