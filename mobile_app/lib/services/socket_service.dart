import 'package:flutter/foundation.dart';
import 'package:socket_io_client/socket_io_client.dart' as socket_io;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';
import '../models/message.dart';
import '../models/session.dart';
import 'notification_service.dart';
import 'dart:async';

class SocketService with ChangeNotifier {
  socket_io.Socket? _socket;
  bool _isConnected = false;
  String _serverUrl = 'http://localhost:8000'; // Default for local dev
  final List<ChatMessage> _messages = [];
  List<ChatSession> _sessions = [];
  List<Map<String, dynamic>> _personas = [];
  String _activePersona = 'Default';
  int? _currentSessionId;
  bool _isTyping = false;
  bool _autoPlayAudio = true;

  bool get isConnected => _isConnected;
  bool get isTyping => _isTyping;
  bool get autoPlayAudio => _autoPlayAudio;
  List<ChatMessage> get messages => List.unmodifiable(_messages);
  List<ChatSession> get sessions => List.unmodifiable(_sessions);
  List<Map<String, dynamic>> get personas => List.unmodifiable(_personas);
  String get activePersona => _activePersona;
  int? get currentSessionId => _currentSessionId;
  String get serverUrl => _serverUrl;
  bool _isLoadingSessions = true;
  bool _hasSuccessfullyFetched = false;
  bool get isLoadingSessions => _isLoadingSessions && !_hasSuccessfullyFetched;

  SocketService() {
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUrl = prefs.getString('server_url');
    if (savedUrl != null) {
      _serverUrl = savedUrl;
    }
    _autoPlayAudio = prefs.getBool('auto_play_audio') ?? true;
    notifyListeners();

    // Reset fetch state
    _hasSuccessfullyFetched = false;

    // Start persistent fetching loop
    _startPersistentFetch();

    fetchPersonas();
    connect();
  }

  Timer? _fetchTimer;
  void _startPersistentFetch() {
    _fetchTimer?.cancel();

    // Initial fetch
    fetchSessions();

    // Retry loop: be more aggressive at first, then settle
    _fetchTimer = Timer.periodic(const Duration(seconds: 3), (timer) {
      if (_hasSuccessfullyFetched) {
        timer.cancel();
        return;
      }
      fetchSessions();
    });

    // Stop after 1 minute regardless to avoid drain
    Future.delayed(const Duration(minutes: 1), () {
      _fetchTimer?.cancel();
      if (!_hasSuccessfullyFetched) {
        _isLoadingSessions = false;
        notifyListeners();
      }
    });
  }

  Future<void> updateServerUrl(String url) async {
    // Sanitize input: backend uses HTTP
    String sanitized = url.trim();
    if (sanitized.startsWith('https://')) {
      sanitized = sanitized.replaceFirst('https://', 'http://');
    }
    if (!sanitized.startsWith('http://') && sanitized.isNotEmpty) {
      sanitized = 'http://$sanitized';
    }

    _serverUrl = sanitized;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', sanitized);

    // Reset and start fetching again for the new URL
    _startPersistentFetch();
    connect();
  }

  void connect() {
    _socket?.disconnect();
    _socket?.dispose();

    debugPrint('Connecting to $_serverUrl...');

    _socket = socket_io.io(
      _serverUrl,
      socket_io.OptionBuilder()
          .setTransports(['websocket'])
          .enableAutoConnect()
          .build(),
    );

    _socket!.onConnect((_) async {
      debugPrint('Connected to Fraclaw backend');
      _isConnected = true;

      // Force a fresh persistent fetch cycle on connection
      _hasSuccessfullyFetched = false;
      _startPersistentFetch();

      await fetchPersonas();

      // No automatic session restoration
      if (_currentSessionId != null) {
        joinSession(_currentSessionId!);
      }

      notifyListeners();
    });

    _socket!.onDisconnect((_) {
      debugPrint('Disconnected from Fraclaw backend');
      _isConnected = false;
      notifyListeners();
    });

    // Universal Notification handler (Reminders, Watchman, etc)
    _socket!.on('notification', (data) {
      final msg = data['message'] ?? 'New alert from Fraclaw';
      NotificationService.showNotification(
        id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
        title: 'Fraclaw AI',
        body: msg,
      );
      debugPrint('🔔 Notification received and shown: $msg');
    });

    // Listen for History & Personas via Socket (Solution A)
    _socket!.on('history_list', (data) {
      if (data['sessions'] != null) {
        _sessions = (data['sessions'] as List)
            .map((s) => ChatSession.fromJson(s))
            .toList();
        _hasSuccessfullyFetched = true;
        _isLoadingSessions = false;
        notifyListeners();
        debugPrint('History synced via Socket.IO');
      }
    });

    _socket!.on('personas_list', (data) {
      if (data['personas'] != null) {
        _personas = List<Map<String, dynamic>>.from(data['personas']);

        final active = _personas.firstWhere(
          (p) => p['is_active'] == 1,
          orElse: () => {},
        );
        if (active.isNotEmpty) {
          _activePersona = active['name'];
        }
        notifyListeners();
        debugPrint('Personas synced via Socket.IO');
      }
    });

    // Listen for AI replies
    _socket!.on('chat_reply', (data) {
      final text = data['text'] ?? '';
      _isTyping = false;

      // Auto-assign session if it was a new one
      if (data['session_id'] != null && _currentSessionId == null) {
        _currentSessionId = data['session_id'];
        fetchSessions();
      }

      // Handle attachments
      String? imagePath;
      List<String> allFiles = [];
      if (data['files'] != null && (data['files'] as List).isNotEmpty) {
        allFiles = List<String>.from(data['files']);
        // Find first image for the imagePath field (legacy/shorthand support)
        for (var f in allFiles) {
          if (f.toLowerCase().contains(
            RegExp(r'\.(jpg|jpeg|png|webp|gif|bmp)'),
          )) {
            imagePath = f;
            break;
          }
        }
      }

      _addMessage(
        ChatMessage(
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          text: text,
          sender: MessageSender.bot,
          timestamp: DateTime.now(),
          imagePath: imagePath,
          files: allFiles,
          isNew: true,
        ),
      );

      NotificationService.showNotification(
        id: 0,
        title: 'Fraclaw',
        body: text.length > 50 ? '${text.substring(0, 50)}...' : text,
      );
    });

    _socket!.on('new_session_created', (data) {
      debugPrint('NEW SESSION: ${data['id']} - ${data['title']}');
      _currentSessionId = data['id'];
      fetchSessions();
    });

    _socket!.on('typing', (data) {
      _isTyping = data['status'] == true;
      notifyListeners();
    });

    _socket!.onConnectError((err) {
      debugPrint('Connect Error: $err');
      _isConnected = false;
      notifyListeners();
    });
  }

  // --- REST Actions ---

  Future<void> fetchSessions({int retries = 0}) async {
    // Solution A: Use Socket.IO instead of HTTP for better reliability on mobile
    if (_socket != null && _socket!.connected) {
      _socket!.emit('request_history');
    } else {
      // Fallback to HTTP only if socket isn't ready
      try {
        final timestamp = DateTime.now().millisecondsSinceEpoch;
        final response = await http
            .get(Uri.parse('$_serverUrl/api/sessions?t=$timestamp'))
            .timeout(const Duration(seconds: 5));
        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          _sessions = (data['sessions'] as List)
              .map((s) => ChatSession.fromJson(s))
              .toList();
          _hasSuccessfullyFetched = true;
          _isLoadingSessions = false;
          notifyListeners();
        }
      } catch (e) {
        debugPrint('HTTP History Fallback Error: $e');
      }
    }
  }

  Future<void> fetchPersonas() async {
    // Solution A: Use Socket.IO for personas
    if (_socket != null && _socket!.connected) {
      _socket!.emit('request_personas');
    } else {
      try {
        final response = await http.get(Uri.parse('$_serverUrl/api/personas'));
        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          _personas = List<Map<String, dynamic>>.from(data['personas']);
          notifyListeners();
        }
      } catch (e) {
        debugPrint('HTTP Personas Fallback Error: $e');
      }
    }
  }

  List<Map<String, dynamic>> _memories = [];
  List<Map<String, dynamic>> get memories => _memories;

  Future<void> fetchMemories() async {
    try {
      final response = await http.get(Uri.parse('$_serverUrl/api/memories'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _memories = List<Map<String, dynamic>>.from(data['memories']);
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error fetching memories: $e');
    }
  }

  Future<bool> deleteMemory(String category, String key) async {
    try {
      final response = await http.delete(
        Uri.parse('$_serverUrl/api/memories?category=$category&key=$key'),
      );
      if (response.statusCode == 200) {
        fetchMemories();
        return true;
      }
    } catch (e) {
      debugPrint('Error deleting memory: $e');
    }
    return false;
  }

  Future<bool> activatePersona(String name) async {
    try {
      final response = await http.post(
        Uri.parse('$_serverUrl/api/personas/activate?name=$name'),
      );
      if (response.statusCode == 200) {
        _activePersona = name;
        notifyListeners();
        return true;
      }
    } catch (e) {
      debugPrint('Error activating persona: $e');
    }
    return false;
  }

  Future<bool> purgeSystem() async {
    try {
      final response = await http.post(
        Uri.parse('$_serverUrl/api/system/purge'),
      );
      if (response.statusCode == 200) {
        _currentSessionId = null;
        _messages.clear();
        _sessions.clear();
        notifyListeners();
        return true;
      }
    } catch (e) {
      debugPrint('Error purging system: $e');
    }
    return false;
  }

  Future<void> deleteSession(int id) async {
    try {
      final response = await http.delete(
        Uri.parse('$_serverUrl/api/sessions/$id'),
      );
      if (response.statusCode == 200) {
        if (_currentSessionId == id) {
          _currentSessionId = null;
          _messages.clear();
          final prefs = await SharedPreferences.getInstance();
          prefs.remove('last_session_id');
        }
        await fetchSessions();
        // If we just deleted the current session and there are others, load the first one
        if (_currentSessionId == null && _sessions.isNotEmpty) {
          setSession(_sessions.first.id);
        }
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error deleting session: $e');
    }
  }

  Future<void> setSession(int? id) async {
    _currentSessionId = id;
    _messages.clear();

    if (id != null) {
      joinSession(id);
      fetchMessages(id);
    }
    notifyListeners();
  }

  Future<void> fetchMessages(int sessionId) async {
    try {
      final response = await http.get(
        Uri.parse('$_serverUrl/api/sessions/$sessionId/messages'),
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _messages.clear();
        for (var m in data['messages']) {
          final rawFiles = m['files'] != null
              ? List<String>.from(m['files'])
              : <String>[];

          // Extract first image for the imagePath field
          String? imagePath;
          for (var f in rawFiles) {
            if (f.toLowerCase().contains(
              RegExp(r'\.(jpg|jpeg|png|webp|gif|bmp)'),
            )) {
              imagePath = f;
              break;
            }
          }

          _messages.add(
            ChatMessage(
              id: m['id'].toString(),
              text: m['content'],
              sender: m['role'] == 'user'
                  ? MessageSender.user
                  : MessageSender.bot,
              timestamp: DateTime.parse(m['timestamp']).toLocal(),
              imagePath: imagePath,
              files: rawFiles,
            ),
          );
        }
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error fetching messages: $e');
    }
  }

  Future<String?> uploadFile(File file) async {
    final data = await uploadFileExtended(file);
    return data?['path'];
  }

  Future<Map<String, dynamic>?> uploadFileExtended(File file) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$_serverUrl/api/upload'),
      );
      if (_currentSessionId != null) {
        request.fields['session_id'] = _currentSessionId.toString();
      }
      request.files.add(await http.MultipartFile.fromPath('file', file.path));

      var response = await request.send();
      if (response.statusCode == 200) {
        var responseData = await response.stream.bytesToString();
        var data = json.decode(responseData);
        return data; // Return full response map
      }
    } catch (e) {
      debugPrint('Error uploading file context: $e');
    }
    return null;
  }

  // --- Socket Actions ---

  void joinSession(int id) {
    _socket?.emit('join_session', {'session_id': id});
  }

  void sendMessage(String text, {String? imagePath}) {
    if (!_isConnected) return;

    final userMsg = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      text: text,
      sender: MessageSender.user,
      timestamp: DateTime.now(),
      imagePath: imagePath,
    );

    _addMessage(userMsg);

    final payload = {
      'text': text,
      if (_currentSessionId != null) 'session_id': _currentSessionId,
      if (imagePath != null) 'image_path': imagePath,
    };

    _socket!.emit('chat_message', payload);
  }

  void _addMessage(ChatMessage msg) {
    _messages.add(msg);
    notifyListeners();
  }

  @override
  void dispose() {
    _socket?.disconnect();
    super.dispose();
  }
}
