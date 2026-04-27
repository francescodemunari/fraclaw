import 'dart:io';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:desktop_drop/desktop_drop.dart';
import 'package:file_picker/file_picker.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:image_picker/image_picker.dart';
import '../services/socket_service.dart';
import '../models/message.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_background.dart';
import 'memory_screen.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';

import '../widgets/app_ui.dart';
import 'personas_screen.dart';

import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_highlighter/flutter_highlighter.dart';
import 'package:flutter_highlighter/themes/atom-one-dark.dart';
import 'package:markdown/markdown.dart' as md;

class CodeElementBuilder extends MarkdownElementBuilder {
  @override
  Widget? visitElementAfter(md.Element element, TextStyle? preferredStyle) {
    var language = '';
    if (element.attributes['class'] != null) {
      String lg = element.attributes['class'] as String;
      if (lg.startsWith('language-')) {
        language = lg.substring(9);
      }
    }
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: HighlightView(
          element.textContent,
          language: language.isEmpty ? 'plaintext' : language,
          theme: atomOneDarkTheme,
          padding: const EdgeInsets.all(12),
          textStyle: const TextStyle(fontFamily: 'monospace', fontSize: 12),
        ),
      ),
    );
  }
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  final TextEditingController _controller = TextEditingController();
  final TextEditingController _historySearchController =
      TextEditingController();
  final ScrollController _scrollController = ScrollController();
  String _historySearchQuery = '';
  final AudioRecorder _audioRecorder = AudioRecorder();
  final AudioPlayer _audioPlayer = AudioPlayer();

  late final AnimationController _pulseController;
  late final PageController _pageController;
  bool _isRecording = false;
  bool _isDragging = false;
  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: 1);
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );

    // Add observer for lifecycle events
    WidgetsBinding.instance.addObserver(this);

    // Auto-fetch sessions on start and connect
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SocketService>().fetchSessions();
      context.read<SocketService>().fetchPersonas();
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Refresh sessions when returning to the app
    if (state == AppLifecycleState.resumed) {
      context.read<SocketService>().fetchSessions();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pulseController.dispose();
    _pageController.dispose();
    _audioRecorder.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _startRecording() async {
    try {
      if (await _audioRecorder.hasPermission()) {
        final directory = await getTemporaryDirectory();
        final path = '${directory.path}/audit_record.m4a';

        const config = RecordConfig();
        await _audioRecorder.start(config, path: path);
        setState(() => _isRecording = true);
        _pulseController.repeat(reverse: true);

        ScaffoldMessenger.of(context).showSnackBar(AppUI.recordingSnackBar());
      } else {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(AppUI.errorSnackBar('Microphone permission denied.'));
      }
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(AppUI.errorSnackBar('Audio Recording Error: $e'));
    }
  }

  Future<void> _stopRecording(SocketService service) async {
    ScaffoldMessenger.of(context).clearSnackBars();
    try {
      final path = await _audioRecorder.stop();
      setState(() => _isRecording = false);
      _pulseController.stop();
      _pulseController.reset();

      if (path != null) {
        debugPrint("MESSAGING: Recording stopped. Path: $path");
        final file = File(path);

        final uploadData = await service.uploadFileExtended(file);
        if (uploadData != null) {
          final transcription = uploadData['transcription'] as String?;
          final remotePath = uploadData['path'] as String?;

          if (transcription != null && transcription.isNotEmpty) {
            service.sendMessage(transcription, imagePath: remotePath);
          } else {
            service.sendMessage(
              "🎤 Voice Message Received",
              imagePath: remotePath,
            );
          }

          _scrollToBottom();
        }
      }
    } catch (e) {
      debugPrint("MESSAGING: Stop recording error: $e");
    }
  }

  void _showSettingsDialog(SocketService service) {
    final ipController = TextEditingController(text: service.serverUrl);

    AppUI.infoDialog(
      context,
      title: 'Server Settings',
      content: TextField(
        controller: ipController,
        style: const TextStyle(color: Colors.white),
        decoration: const InputDecoration(
          labelText: 'Tailscale IP / Server URL',
          labelStyle: TextStyle(color: Colors.white54),
          enabledBorder: UnderlineInputBorder(
            borderSide: BorderSide(color: Colors.white10),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          style: TextButton.styleFrom(foregroundColor: Colors.white38),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () {
            service.updateServerUrl(ipController.text.trim());
            Navigator.pop(context);
          },
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.accentPurple.withValues(alpha: 0.2),
            foregroundColor: AppTheme.primaryCyan,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: BorderSide(
                color: AppTheme.primaryCyan.withValues(alpha: 0.5),
              ),
            ),
          ),
          child: const Text('Save & Connect'),
        ),
      ],
    );
  }

  int _lastMessageCount = 0;

  @override
  Widget build(BuildContext context) {
    // Only watch specific fields to avoid full-screen rebuilds
    final isTyping = context.select<SocketService, bool>((s) => s.isTyping);
    final messages = context.select<SocketService, List<ChatMessage>>(
      (s) => s.messages,
    );
    final socketService = context.read<SocketService>();

    if (isTyping) {
      if (!_pulseController.isAnimating) _pulseController.repeat(reverse: true);
    } else {
      if (!_isRecording && _pulseController.isAnimating) {
        _pulseController.stop();
      }
    }
    // Scroll only when a new message is added, not every frame
    if (messages.length != _lastMessageCount) {
      _lastMessageCount = messages.length;
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }

    return DropTarget(
      onDragDone: (detail) => _handleDrop(socketService, detail.files),
      onDragEntered: (detail) => setState(() => _isDragging = true),
      onDragExited: (detail) => setState(() => _isDragging = false),
      child: Scaffold(
        backgroundColor: AppTheme.primaryDark,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          toolbarHeight: 70,
          leading: IconButton(
            icon: const Icon(Icons.menu_rounded, color: Colors.white70),
            onPressed: () => _pageController.animateToPage(
              0,
              duration: const Duration(milliseconds: 400),
              curve: Curves.easeOutCubic,
            ),
          ),
          title: GestureDetector(
            onTap: () => _pageController.animateToPage(
              1,
              duration: const Duration(milliseconds: 400),
              curve: Curves.easeOutCubic,
            ),
            child: Text(
              'FRACLAW',
              style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                fontSize: 22,
                shadows: [
                  Shadow(
                    color: AppTheme.neonCyan.withValues(alpha: 0.5),
                    blurRadius: 10,
                  ),
                ],
              ),
            ),
          ),
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Center(
                child: IconButton(
                  icon: const Icon(
                    Icons.settings_input_component_outlined,
                    color: Colors.white70,
                    size: 22,
                  ),
                  onPressed: () => _pageController.animateToPage(
                    2,
                    duration: const Duration(milliseconds: 400),
                    curve: Curves.easeOutCubic,
                  ),
                ),
              ),
            ),
          ],
        ),
        body: PageView(
          controller: _pageController,
          children: [
            _buildHistoryPanel(socketService),
            _buildChatBody(socketService, messages, isTyping),
            _buildSystemPanel(context, socketService),
          ],
        ),
      ),
    );
  }

  Widget _buildChatBody(
    SocketService socketService,
    List<ChatMessage> messages,
    bool isTyping,
  ) {
    return AuroraBackground(
      child: Stack(
        children: [
          if (_isDragging) _buildDropOverlay(),
          Column(
            children: [
              Expanded(
                child: SelectionArea(
                  child: messages.isEmpty && !isTyping
                      ? _buildAnimatedEmptyState()
                      : ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 20,
                          ),
                          itemCount: messages.length + (isTyping ? 1 : 0),
                          itemBuilder: (context, index) {
                            if (isTyping && index == messages.length) {
                              return _buildInlineThinkingBubble(
                                socketService.activePersona.toLowerCase(),
                              );
                            }
                            final msg = messages[index];
                            return _MessageBubble(
                              key: ValueKey(msg.id),
                              message: msg,
                              serverUrl: socketService.serverUrl,
                              audioPlayer: _audioPlayer,
                            );
                          },
                        ),
                ),
              ),
              _buildPremiumInputBar(socketService),
              const SizedBox(height: 24),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAnimatedEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 180,
            height: 180,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Colors.white.withValues(alpha: 0.02),
                  blurRadius: 100,
                ),
              ],
            ),
            child: Image.asset(
              'assets/logo.png',
              fit: BoxFit.contain,
              errorBuilder: (c, e, s) =>
                  const Icon(Icons.blur_on, size: 80, color: Colors.white10),
            ),
          ),
          const SizedBox(height: 50),
          const Text(
            'Welcome to Fraclaw.',
            style: TextStyle(
              color: Colors.white,
              fontSize: 22,
              fontWeight: FontWeight.w200,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'How can I assist you today?',
            style: TextStyle(
              color: Colors.white30,
              fontSize: 14,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPremiumInputBar(SocketService service) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            height: 64,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(32),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.accentPurple.withValues(alpha: 0.2),
                  blurRadius: 40,
                  spreadRadius: -10,
                ),
                BoxShadow(
                  color: AppTheme.neonCyan.withValues(alpha: 0.1),
                  blurRadius: 50,
                  spreadRadius: -20,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
          ),
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(32),
              color: const Color(0xFF101018).withValues(alpha: 0.8),
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.08),
                width: 1.5,
              ),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.white.withValues(alpha: 0.05),
                  Colors.transparent,
                  AppTheme.accentPurple.withValues(alpha: 0.02),
                ],
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: _buildInputIconButton(
                      Icons.add_circle_outline_rounded,
                      () async {
                        final res = await FilePicker.platform.pickFiles();
                        if (res != null) {
                          _handleDrop(service, [XFile(res.files.single.path!)]);
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      minLines: 1,
                      maxLines: 6,
                      keyboardType: TextInputType.multiline,
                      textInputAction: TextInputAction.newline,
                      style: Theme.of(
                        context,
                      ).textTheme.bodyLarge?.copyWith(fontSize: 16),
                      decoration: const InputDecoration(
                        hintText: 'Neural Input...',
                        hintStyle: TextStyle(
                          color: Colors.white24,
                          fontWeight: FontWeight.w200,
                        ),
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        filled: false,
                        contentPadding: EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: _buildMicButton(service),
                  ),
                  const SizedBox(width: 12),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: _buildSendButton(service),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputIconButton(IconData icon, VoidCallback onTap) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.all(8),
          child: Icon(icon, color: Colors.white60, size: 24),
        ),
      ),
    );
  }

  Widget _buildMicButton(SocketService service) {
    return GestureDetector(
      onTap: () {
        if (_isRecording) {
          _stopRecording(service);
        } else {
          _startRecording();
        }
      },
      child: AnimatedBuilder(
        animation: _pulseController,
        builder: (context, child) {
          return AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _isRecording
                  ? Colors.red.withValues(
                      alpha: 0.1 + (0.2 * _pulseController.value),
                    )
                  : Colors.white.withValues(alpha: 0.05),
              boxShadow: _isRecording
                  ? [
                      BoxShadow(
                        color: Colors.redAccent.withOpacity(
                          0.4 * _pulseController.value,
                        ),
                        blurRadius: 15 * _pulseController.value,
                        spreadRadius: 2 * _pulseController.value,
                      ),
                    ]
                  : [],
            ),
            child: Icon(
              _isRecording ? Icons.mic_rounded : Icons.mic_none_rounded,
              color: _isRecording ? Colors.redAccent : Colors.white54,
              size: 22,
            ),
          );
        },
      ),
    );
  }

  Widget _buildSendButton(SocketService service) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _send(service),
        borderRadius: BorderRadius.circular(25),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: const LinearGradient(
              colors: [AppTheme.accentPurple, Colors.deepPurpleAccent],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            boxShadow: [
              BoxShadow(
                color: AppTheme.accentPurple.withValues(alpha: 0.4),
                blurRadius: 15,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
        ),
      ),
    );
  }

  Widget _buildDropOverlay() => Container(
    color: Colors.purple.withValues(alpha: 0.1),
    child: Center(
      child: Icon(
        Icons.upload_file_rounded,
        size: 80,
        color: Colors.white.withValues(alpha: 0.5),
      ),
    ),
  );

  Future<void> _handleDrop(SocketService service, List<dynamic> files) async {
    setState(() => _isDragging = false);
    for (var f in files) {
      final file = File(f.path);
      final uploadedPath = await service.uploadFile(file);
      if (uploadedPath != null) {
        service.sendMessage(
          "📁 Attached file: ${f.name}",
          imagePath: uploadedPath,
        );
      }
    }
  }

  Widget _buildInlineThinkingBubble(String activePersona) {
    return Padding(
      padding: const EdgeInsets.only(top: 12, bottom: 4, right: 50),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Container(
            width: 36,
            height: 36,
            margin: const EdgeInsets.only(right: 8, bottom: 4),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.accentPurple.withValues(alpha: 0.15),
              border: Border.all(
                color: AppTheme.accentPurple.withValues(alpha: 0.4),
                width: 1.5,
              ),
            ),
            child: ClipOval(
              child: Image.asset(
                'assets/${activePersona.toLowerCase()}.png',
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return const Center(
                    child: Icon(
                      Icons.smart_toy_rounded,
                      color: AppTheme.accentPurple,
                      size: 20,
                    ),
                  );
                },
              ),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: Colors.white10),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildPulseDot(0),
                _buildPulseDot(1),
                _buildPulseDot(2),
                const SizedBox(width: 12),
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) => Opacity(
                    opacity: 0.4 + (0.6 * _pulseController.value),
                    child: const Text(
                      'THINKING...',
                      style: TextStyle(
                        color: Colors.white38,
                        fontSize: 9,
                        letterSpacing: 4,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPulseDot(int index) {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final double delay = index * 0.2;
        final double value =
            (sin((_pulseController.value * 2 * pi) + (delay * 2 * pi)) + 1) / 2;
        return Container(
          width: 4,
          height: 4,
          margin: const EdgeInsets.symmetric(horizontal: 2.5),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppTheme.neonCyan.withValues(alpha: 0.2 + (0.8 * value)),
            boxShadow: [
              BoxShadow(
                color: AppTheme.neonCyan.withValues(alpha: 0.4 * value),
                blurRadius: 4 * value,
              ),
            ],
          ),
        );
      },
    );
  }

  void _send(SocketService service) {
    if (_controller.text.trim().isNotEmpty) {
      service.sendMessage(_controller.text.trim());
      _controller.clear();
      _scrollToBottom();
    }
  }

  Widget _buildHistoryPanel(SocketService service) {
    return Consumer<SocketService>(
      builder: (context, service, child) {
        return Container(
          color: const Color(0xFF030303),
          child: Column(
            children: [
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 40, 24, 20),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.history,
                        color: AppTheme.accentPurple,
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'HISTORY',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 4,
                        ),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.add, color: Colors.white54),
                        onPressed: () {
                          service.setSession(null);
                          _pageController.animateToPage(
                            1,
                            duration: const Duration(milliseconds: 400),
                            curve: Curves.easeOutCubic,
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),

              // Search Bar
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 8,
                ),
                child: Container(
                  height: 44,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: Colors.white.withValues(alpha: 0.1),
                    ),
                  ),
                  child: TextField(
                    controller: _historySearchController,
                    onChanged: (val) =>
                        setState(() => _historySearchQuery = val.toLowerCase()),
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: 'Search conversations...',
                      hintStyle: const TextStyle(
                        color: Colors.white24,
                        fontSize: 13,
                      ),
                      prefixIcon: const Icon(
                        Icons.search,
                        color: Colors.white54,
                        size: 18,
                      ),
                      suffixIcon: _historySearchQuery.isNotEmpty
                          ? IconButton(
                              icon: const Icon(
                                Icons.close,
                                color: Colors.white54,
                                size: 16,
                              ),
                              onPressed: () {
                                _historySearchController.clear();
                                setState(() => _historySearchQuery = '');
                              },
                            )
                          : null,
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              Expanded(
                child: () {
                  final filteredSessions = service.sessions
                      .where(
                        (s) =>
                            s.title.toLowerCase().contains(_historySearchQuery),
                      )
                      .toList();

                  return RefreshIndicator(
                    onRefresh: () => service.fetchSessions(),
                    color: AppTheme.accentPurple,
                    backgroundColor: const Color(0xFF1A1A1A),
                    child: service.isLoadingSessions
                        ? const Center(
                            child: CircularProgressIndicator(
                              color: AppTheme.accentPurple,
                            ),
                          )
                        : filteredSessions.isEmpty
                        ? ListView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            children: [
                              const SizedBox(height: 100),
                              Center(
                                child: Column(
                                  children: [
                                    Icon(
                                      _historySearchQuery.isEmpty
                                          ? Icons.history_toggle_off
                                          : Icons.search_off,
                                      color: Colors.white10,
                                      size: 40,
                                    ),
                                    const SizedBox(height: 16),
                                    Text(
                                      _historySearchQuery.isEmpty
                                          ? 'No sessions recorded'
                                          : 'No matches found',
                                      style: const TextStyle(
                                        color: Colors.white24,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemCount: filteredSessions.length,
                            itemBuilder: (context, index) {
                              final session = filteredSessions[index];
                              final isActive =
                                  service.currentSessionId == session.id;
                              return Container(
                                margin: const EdgeInsets.only(bottom: 8),
                                decoration: BoxDecoration(
                                  color: isActive
                                      ? AppTheme.accentPurple.withValues(
                                          alpha: 0.1,
                                        )
                                      : Colors.transparent,
                                  borderRadius: BorderRadius.circular(15),
                                  border: Border.all(
                                    color: isActive
                                        ? AppTheme.accentPurple.withValues(
                                            alpha: 0.3,
                                          )
                                        : Colors.transparent,
                                  ),
                                ),
                                child: ListTile(
                                  title: Text(
                                    session.title,
                                    style: TextStyle(
                                      color: isActive
                                          ? Colors.white
                                          : Colors.white70,
                                      fontSize: 14,
                                      fontWeight: isActive
                                          ? FontWeight.bold
                                          : FontWeight.normal,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  subtitle: Text(
                                    "${session.createdAt.day.toString().padLeft(2, '0')}/${session.createdAt.month.toString().padLeft(2, '0')} ${session.createdAt.hour.toString().padLeft(2, '0')}:${session.createdAt.minute.toString().padLeft(2, '0')}",
                                    style: const TextStyle(
                                      color: Colors.white24,
                                      fontSize: 11,
                                    ),
                                  ),
                                  onTap: () {
                                    service.setSession(session.id);
                                    _pageController.animateToPage(
                                      1,
                                      duration: const Duration(
                                        milliseconds: 400,
                                      ),
                                      curve: Curves.easeOutCubic,
                                    );
                                  },
                                  trailing: IconButton(
                                    icon: const Icon(
                                      Icons.delete_outline,
                                      color: Colors.white24,
                                      size: 18,
                                    ),
                                    tooltip: 'Delete chat',
                                    onPressed: () async {
                                      final confirm = await AppUI.confirmDialog(
                                        context,
                                        title: 'Delete Chat',
                                        message: 'Delete "${session.title}"?',
                                        confirmLabel: 'Delete',
                                        destructive: true,
                                      );
                                      if (confirm == true) {
                                        await service.deleteSession(session.id);
                                        if (service.sessions.isEmpty) {
                                          _pageController.animateToPage(
                                            1,
                                            duration: const Duration(
                                              milliseconds: 400,
                                            ),
                                            curve: Curves.easeOutCubic,
                                          );
                                        }
                                      }
                                    },
                                  ),
                                ),
                              );
                            },
                          ),
                  );
                }(),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSystemPanel(BuildContext context, SocketService service) {
    return Consumer<SocketService>(
      builder: (context, service, child) {
        return Container(
          color: const Color(0xFF030303),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(32, 40, 32, 0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'SYSTEM',
                        style: TextStyle(
                          fontSize: 40,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -2,
                        ),
                      ),
                      Text(
                        'CORE INTERFACE',
                        style: TextStyle(
                          color: AppTheme.primaryCyan.withValues(alpha: 0.5),
                          fontSize: 11,
                          letterSpacing: 3,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 60),
              _buildDrawerItem(Icons.hub_outlined, 'Neural Identities', () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const PersonasScreen()),
                );
              }),
              _buildDrawerItem(
                Icons.router_rounded,
                'Network Config',
                () => _showSettingsDialog(service),
              ),
              _buildDrawerItem(
                Icons.folder_copy_outlined,
                'Memory Index',
                () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const MemoryScreen()),
                ),
              ),
              const Spacer(),
              Padding(
                padding: const EdgeInsets.all(32),
                child: OutlinedButton(
                  onPressed: () => _confirmHardReset(context, service),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Colors.redAccent, width: 0.2),
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  child: const Center(
                    child: Text(
                      'HARD RESET SYSTEM',
                      style: TextStyle(
                        color: Colors.redAccent,
                        fontSize: 11,
                        letterSpacing: 3,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _confirmHardReset(BuildContext context, SocketService service) async {
    final confirm = await AppUI.confirmDialog(
      context,
      title: 'CRITICAL ACTION',
      message:
          'This will purge all conversations, memories, and vector databases. This action is IRREVERSIBLE.',
      confirmLabel: 'PURGE EVERYTHING',
      destructive: true,
    );

    if (confirm == true && context.mounted) {
      final success = await service.purgeSystem();
      if (success && context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          AppUI.snackBar(
            'System wiped successfully.',
            icon: Icons.check_circle_outline,
          ),
        );
      }
    }
  }

  Widget _buildDrawerItem(IconData icon, String title, VoidCallback onTap) =>
      ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 32, vertical: 8),
        leading: Icon(icon, color: Colors.white60, size: 22),
        title: Text(
          title,
          style: const TextStyle(
            color: Colors.white70,
            fontSize: 15,
            fontWeight: FontWeight.w300,
          ),
        ),
        onTap: onTap,
      );
}

// ─── Premium Audio Player Card ────────────────────────────────────────────────
class _AudioPlayerCard extends StatefulWidget {
  final String fileName;
  final String fileUrl;
  final bool autoPlay;

  const _AudioPlayerCard({
    required this.fileName,
    required this.fileUrl,
    this.autoPlay = false,
  });

  @override
  State<_AudioPlayerCard> createState() => _AudioPlayerCardState();
}

class _AudioPlayerCardState extends State<_AudioPlayerCard> {
  static final Set<String> _autoPlayedUrls = {};
  late final AudioPlayer _player;
  bool _isPlaying = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  @override
  void initState() {
    super.initState();
    _player = AudioPlayer();
    _player.onPlayerStateChanged.listen((state) {
      if (mounted) setState(() => _isPlaying = state == PlayerState.playing);
    });
    _player.onPositionChanged.listen((pos) {
      if (mounted) setState(() => _position = pos);
    });
    _player.onDurationChanged.listen((dur) {
      if (mounted) setState(() => _duration = dur);
    });
    _player.onPlayerComplete.listen((_) {
      if (mounted) {
        setState(() {
          _isPlaying = false;
          _position = Duration.zero;
        });
      }
    });

    if (widget.autoPlay && !_autoPlayedUrls.contains(widget.fileUrl)) {
      _autoPlayedUrls.add(widget.fileUrl);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _player.play(UrlSource(widget.fileUrl));
        }
      });
    }
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  String _fmt(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Future<void> _toggle() async {
    if (_isPlaying) {
      await _player.pause();
    } else {
      if (_position == Duration.zero || _position >= _duration) {
        await _player.play(UrlSource(widget.fileUrl));
      } else {
        await _player.resume();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = _duration.inMilliseconds > 0
        ? _position.inMilliseconds / _duration.inMilliseconds
        : 0.0;

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF0E0E0E),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryCyan.withValues(alpha: 0.05),
            blurRadius: 20,
            spreadRadius: 2,
          ),
        ],
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header row ──────────────────────────────────────
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppTheme.primaryCyan.withValues(alpha: 0.12),
                  border: Border.all(
                    color: AppTheme.primaryCyan.withValues(alpha: 0.3),
                  ),
                ),
                child: const Icon(
                  Icons.mic,
                  color: AppTheme.primaryCyan,
                  size: 16,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.fileName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                    const Text(
                      'VOICE MESSAGE',
                      style: TextStyle(
                        color: Colors.white38,
                        fontSize: 9,
                        letterSpacing: 2,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.download_outlined,
                color: Colors.white24,
                size: 18,
              ),
            ],
          ),
          const SizedBox(height: 12),
          // ── Player row ──────────────────────────────────────
          Row(
            children: [
              // Play/Pause
              GestureDetector(
                onTap: _toggle,
                child: Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: _isPlaying
                          ? [AppTheme.accentPurple, AppTheme.primaryCyan]
                          : [Colors.white12, Colors.white10],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: Icon(
                    _isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              // Progress bar
              Expanded(
                child: Column(
                  children: [
                    SliderTheme(
                      data: SliderThemeData(
                        trackHeight: 3,
                        thumbShape: const RoundSliderThumbShape(
                          enabledThumbRadius: 5,
                        ),
                        overlayShape: const RoundSliderOverlayShape(
                          overlayRadius: 12,
                        ),
                        activeTrackColor: AppTheme.primaryCyan,
                        inactiveTrackColor: Colors.white10,
                        thumbColor: Colors.white,
                        overlayColor: AppTheme.primaryCyan.withValues(
                          alpha: 0.2,
                        ),
                      ),
                      child: Slider(
                        value: progress.clamp(0.0, 1.0),
                        onChanged: (v) async {
                          final seek = Duration(
                            milliseconds: (v * _duration.inMilliseconds)
                                .round(),
                          );
                          await _player.seek(seek);
                        },
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            _fmt(_position),
                            style: const TextStyle(
                              color: Colors.white38,
                              fontSize: 9,
                            ),
                          ),
                          Text(
                            _fmt(_duration),
                            style: const TextStyle(
                              color: Colors.white38,
                              fontSize: 9,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              const Icon(
                Icons.volume_up_outlined,
                color: Colors.white24,
                size: 16,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ─── Optimised Message Bubble ─────────────────────────────────────────────────
// Separate StatefulWidget so Flutter's element tree can skip re-rendering
// unchanged messages when new ones are added to the bottom of the list.
class _MessageBubble extends StatefulWidget {
  final ChatMessage message;
  final String serverUrl;
  final AudioPlayer audioPlayer;

  const _MessageBubble({
    super.key,
    required this.message,
    required this.serverUrl,
    required this.audioPlayer,
  });

  @override
  State<_MessageBubble> createState() => _MessageBubbleState();
}

class _MessageBubbleState extends State<_MessageBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anim;
  late final Animation<double> _opacity;
  late final Animation<Offset> _slide;
  bool _showTranscript = false;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );
    _opacity = CurvedAnimation(parent: _anim, curve: Curves.easeOut);
    _slide = Tween<Offset>(
      begin: const Offset(0, 0.08),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _anim, curve: Curves.easeOut));
    _anim.forward();
  }

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  String _resolveFolder(String path) {
    if (path.contains('workspace')) return 'workspace';
    if (path.contains('output')) return 'outputs';
    if (path.contains('generated_images')) return 'generated_images';
    return 'uploads';
  }

  @override
  Widget build(BuildContext context) {
    final msg = widget.message;
    final bool isUser = msg.sender == MessageSender.user;

    // Build image attachment widget if present
    Widget? imageWidget;
    if (msg.imagePath != null) {
      final normalized = msg.imagePath!.replaceAll('\\', '/');
      final fileName = normalized.split('/').last;
      final folder = _resolveFolder(msg.imagePath!);
      final imageUrl = '${widget.serverUrl}/$folder/$fileName';

      if (fileName.toLowerCase().contains(
        RegExp(r'\.(jpg|jpeg|png|webp|gif|bmp)'),
      )) {
        imageWidget = Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: GestureDetector(
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (ctx) => _ImagePreviewScreen(
                    imageUrl: imageUrl,
                    fileName: fileName,
                  ),
                ),
              );
            },
            child: Hero(
              tag: imageUrl,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Image.network(
                  imageUrl,
                  fit: BoxFit.cover,
                  cacheWidth: 800, // Limit decode size for memory
                  errorBuilder: (c, e, s) => Container(
                    padding: const EdgeInsets.all(10),
                    color: Colors.white12,
                    child: const Icon(
                      Icons.image_not_supported_outlined,
                      color: Colors.white24,
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      }
    }

    // Efficient bubble decoration — no BackdropFilter per bubble
    final bubbleDecoration = BoxDecoration(
      color: isUser
          ? AppTheme.accentPurple.withValues(alpha: 0.18)
          : Colors.white.withValues(alpha: 0.05),
      borderRadius: BorderRadius.circular(22),
      border: Border.all(
        color: isUser
            ? AppTheme.accentPurple.withValues(alpha: 0.35)
            : Colors.white.withValues(alpha: 0.08),
        width: 1,
      ),
    );

    final hasAudio =
        !isUser &&
        msg.files != null &&
        msg.files!.any(
          (f) => f.toLowerCase().contains(RegExp(r'\.(wav|mp3|m4a|ogg)')),
        );

    // Build text element based on transcript expansion state
    Widget textContent;
    if (hasAudio && !_showTranscript) {
      textContent = GestureDetector(
        onTap: () => setState(() => _showTranscript = true),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.translate_rounded,
              color: AppTheme.primaryCyan,
              size: 16,
            ),
            const SizedBox(width: 8),
            Text(
              'Show Transcript',
              style: TextStyle(
                color: AppTheme.primaryCyan.withValues(alpha: 0.9),
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      );
    } else {
      textContent = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MarkdownBody(
            data: msg.text,
            selectable: true,
            styleSheet: MarkdownStyleSheet(
              p: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: isUser
                    ? Colors.white
                    : Colors.white.withValues(alpha: 0.88),
                fontWeight: isUser ? FontWeight.w500 : FontWeight.w300,
                height: 1.5,
              ),
              code: const TextStyle(
                fontFamily: 'monospace',
                backgroundColor: Colors.transparent,
                color: AppTheme.primaryCyan,
              ),
              codeblockDecoration: BoxDecoration(
                color: Colors.black26,
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            builders: {'code': CodeElementBuilder()},
          ),
          if (hasAudio && _showTranscript)
            Padding(
              padding: const EdgeInsets.only(top: 8.0),
              child: GestureDetector(
                onTap: () => setState(() => _showTranscript = false),
                child: const Text(
                  'Hide Transcript',
                  style: TextStyle(color: Colors.white38, fontSize: 11),
                ),
              ),
            ),
        ],
      );
    }

    final activePersona = context
        .select<SocketService, String>((s) => s.activePersona)
        .toLowerCase();

    return FadeTransition(
      opacity: _opacity,
      child: SlideTransition(
        position: _slide,
        child: Padding(
          padding: EdgeInsets.only(
            top: 10,
            bottom: 4,
            left: isUser ? 52 : 0,
            right: isUser ? 0 : 52,
          ),
          child: Row(
            mainAxisAlignment: isUser
                ? MainAxisAlignment.end
                : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (!isUser)
                Container(
                  width: 36,
                  height: 36,
                  margin: const EdgeInsets.only(right: 12, bottom: 4),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.accentPurple.withValues(alpha: 0.15),
                    border: Border.all(
                      color: AppTheme.accentPurple.withValues(alpha: 0.4),
                      width: 1.5,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.accentPurple.withValues(alpha: 0.2),
                        blurRadius: 8,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                  child: ClipOval(
                    child: Image.asset(
                      'assets/$activePersona.png',
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) {
                        return const Center(
                          child: Icon(
                            Icons.smart_toy_rounded,
                            color: AppTheme.accentPurple,
                            size: 20,
                          ),
                        );
                      },
                    ),
                  ),
                ),
              Flexible(
                child: Column(
                  crossAxisAlignment: isUser
                      ? CrossAxisAlignment.end
                      : CrossAxisAlignment.start,
                  children: [
                    if (imageWidget != null) imageWidget,
                    Container(
                      decoration: bubbleDecoration,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 14,
                      ),
                      child: textContent,
                    ),
                    if (msg.files != null && msg.files!.isNotEmpty)
                      _FileListSection(
                        files: msg.files!,
                        serverUrl: widget.serverUrl,
                        autoPlayAudio: !isUser && msg.isNew,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── File List Section (stateless wrapper) ────────────────────────────────────
class _FileListSection extends StatelessWidget {
  final List<String> files;
  final String serverUrl;
  final bool autoPlayAudio;

  const _FileListSection({
    required this.files,
    required this.serverUrl,
    this.autoPlayAudio = false,
  });

  String _resolveFolder(String path) {
    if (path.contains('workspace')) return 'workspace';
    if (path.contains('output')) return 'outputs';
    if (path.contains('generated_images')) return 'generated_images';
    return 'uploads';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: files.map((f) {
        final normalized = f.replaceAll('\\', '/');
        final fileName = normalized.split('/').last;
        final isImage = fileName.toLowerCase().contains(
          RegExp(r'\.(jpg|jpeg|png|webp|gif|bmp)'),
        );
        if (isImage) return const SizedBox.shrink();

        final folder = _resolveFolder(f);
        final fileUrl = '$serverUrl/$folder/$fileName';

        final isAudio = fileName.toLowerCase().contains(
          RegExp(r'\.(wav|mp3|m4a|ogg)'),
        );

        if (isAudio) {
          return Padding(
            padding: const EdgeInsets.only(top: 10),
            child: _AudioPlayerCard(
              fileName: fileName,
              fileUrl: fileUrl,
              autoPlay: autoPlayAudio,
            ),
          );
        }

        return _DownloadableFileItem(fileName: fileName, fileUrl: fileUrl);
      }).toList(),
    );
  }
}

class _DownloadableFileItem extends StatefulWidget {
  final String fileName;
  final String fileUrl;

  const _DownloadableFileItem({required this.fileName, required this.fileUrl});

  @override
  State<_DownloadableFileItem> createState() => _DownloadableFileItemState();
}

class _DownloadableFileItemState extends State<_DownloadableFileItem> {
  bool _isDownloading = false;
  String? _localPath;

  @override
  void initState() {
    super.initState();
    _checkIfDownloaded();
  }

  Future<void> _checkIfDownloaded() async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File('${dir.path}/${widget.fileName}');
    if (await file.exists()) {
      setState(() {
        _localPath = file.path;
      });
    }
  }

  Future<void> _handleTap() async {
    if (_localPath != null) {
      // Already downloaded, open it!
      OpenFilex.open(_localPath!);
      return;
    }

    // Need to download
    setState(() => _isDownloading = true);

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(AppUI.downloadingSnackBar(widget.fileName));

    try {
      final response = await http.get(Uri.parse(widget.fileUrl));
      if (response.statusCode == 200) {
        final dir = await getApplicationDocumentsDirectory();
        final file = File('${dir.path}/${widget.fileName}');
        await file.writeAsBytes(response.bodyBytes);

        setState(() {
          _localPath = file.path;
          _isDownloading = false;
        });

        // Auto open when finished
        OpenFilex.open(_localPath!);
      } else {
        setState(() => _isDownloading = false);
      }
    } catch (e) {
      debugPrint("Download error: $e");
      setState(() => _isDownloading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bool isDownloaded = _localPath != null;

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isDownloaded
                ? AppTheme.accentPurple.withValues(alpha: 0.4)
                : Colors.white.withValues(alpha: 0.1),
          ),
        ),
        child: ListTile(
          dense: true,
          leading: Icon(
            isDownloaded
                ? Icons.file_present_rounded
                : Icons.description_outlined,
            color: isDownloaded ? AppTheme.accentPurple : Colors.white70,
            size: 20,
          ),
          title: Text(
            widget.fileName,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.bold,
            ),
          ),
          trailing: _isDownloading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppTheme.primaryCyan,
                  ),
                )
              : Icon(
                  isDownloaded
                      ? Icons.open_in_new_rounded
                      : Icons.download_for_offline_outlined,
                  color: AppTheme.primaryCyan,
                  size: 20,
                ),
          onTap: _isDownloading ? null : _handleTap,
        ),
      ),
    );
  }
}

class _ImagePreviewScreen extends StatefulWidget {
  final String imageUrl;
  final String fileName;

  const _ImagePreviewScreen({required this.imageUrl, required this.fileName});

  @override
  _ImagePreviewScreenState createState() => _ImagePreviewScreenState();
}

class _ImagePreviewScreenState extends State<_ImagePreviewScreen> {
  bool _isDownloading = false;

  Future<void> _downloadImage() async {
    setState(() {
      _isDownloading = true;
    });

    try {
      final response = await http.get(Uri.parse(widget.imageUrl));
      if (response.statusCode == 200) {
        Directory? dir;
        if (Platform.isAndroid) {
          dir = Directory('/storage/emulated/0/Download');
          if (!await dir.exists()) {
            dir = await getExternalStorageDirectory();
          }
        } else {
          dir =
              await getDownloadsDirectory() ??
              await getApplicationDocumentsDirectory();
        }

        final savePath = '${dir!.path}/${widget.fileName}';
        final file = File(savePath);
        await file.writeAsBytes(response.bodyBytes);

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Image downloaded to $savePath'),
              backgroundColor: AppTheme.accentPurple,
            ),
          );
        }
      } else {
        throw Exception('Server returned ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to download: $e'),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isDownloading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Zoomable image viewer
          Center(
            child: InteractiveViewer(
              minScale: 0.5,
              maxScale: 4.0,
              child: Hero(
                tag: widget.imageUrl,
                child: Image.network(
                  widget.imageUrl,
                  fit: BoxFit.contain,
                  errorBuilder: (c, e, s) => const Icon(
                    Icons.broken_image,
                    color: Colors.white54,
                    size: 64,
                  ),
                ),
              ),
            ),
          ),

          // Top Bar Overlay
          SafeArea(
            child: Align(
              alignment: Alignment.topCenter,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16.0,
                  vertical: 8.0,
                ),
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    colors: [Colors.black87, Colors.transparent],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white),
                      onPressed: () => Navigator.of(context).pop(),
                    ),
                    _isDownloading
                        ? const Padding(
                            padding: EdgeInsets.all(12.0),
                            child: SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppTheme.primaryCyan,
                              ),
                            ),
                          )
                        : IconButton(
                            icon: const Icon(
                              Icons.download,
                              color: Colors.white,
                            ),
                            onPressed: _downloadImage,
                          ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
