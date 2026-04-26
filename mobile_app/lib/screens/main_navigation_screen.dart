import 'package:flutter/material.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_container.dart';
import 'chat_screen.dart';
import 'memory_screen.dart';
import 'personas_screen.dart';

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _selectedIndex = 0;

  final List<Widget> _screens = [
    const ChatScreen(),
    const MemoryScreen(),
    const PersonasScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBody: true, // Allows content to show behind the glass bar
      body: _screens[_selectedIndex],
      bottomNavigationBar: Container(
        margin: const EdgeInsets.fromLTRB(20, 0, 20, 30),
        child: GlassContainer(
          borderRadius: 30,
          blur: 20,
          opacity: 0.1,
          color: AppTheme.surfaceDark,
          child: BottomNavigationBar(
            currentIndex: _selectedIndex,
            onTap: (index) => setState(() => _selectedIndex = index),
            backgroundColor: Colors.transparent,
            elevation: 0,
            selectedItemColor: AppTheme.neonCyan,
            unselectedItemColor: AppTheme.textGrey,
            showSelectedLabels: true,
            showUnselectedLabels: false,
            type: BottomNavigationBarType.fixed,
            items: const [
              BottomNavigationBarItem(
                icon: Icon(FontAwesomeIcons.commentDots),
                label: 'CHAT',
              ),
              BottomNavigationBarItem(
                icon: Icon(FontAwesomeIcons.brain),
                label: 'MEMORY',
              ),
              BottomNavigationBarItem(
                icon: Icon(FontAwesomeIcons.userAstronaut),
                label: 'PERSONAS',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
