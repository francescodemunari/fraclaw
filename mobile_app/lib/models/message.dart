enum MessageSender { user, bot, system }

class ChatMessage {
  final String id;
  final String text;
  final MessageSender sender;
  final DateTime timestamp;
  final String? imagePath;
  final String? filePath;
  final List<String>? files;
  final bool isTyping;
  final bool isNew;

  ChatMessage({
    required this.id,
    required this.text,
    required this.sender,
    required this.timestamp,
    this.imagePath,
    this.filePath,
    this.files,
    this.isTyping = false,
    this.isNew = false,
  });

  // Convert to Map for potential local storage (database/json)
  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'text': text,
      'sender': sender.toString(),
      'timestamp': timestamp.toIso8601String(),
      'imagePath': imagePath,
      'filePath': filePath,
      'files': files,
      'isNew': isNew,
    };
  }

  // Create from Map
  factory ChatMessage.fromMap(Map<String, dynamic> map) {
    return ChatMessage(
      id: map['id'],
      text: map['text'],
      sender: MessageSender.values.firstWhere(
        (e) => e.toString() == map['sender'],
        orElse: () => MessageSender.system,
      ),
      timestamp: DateTime.parse(map['timestamp']).toLocal(),
      imagePath: map['imagePath'],
      filePath: map['filePath'],
      files: map['files'] != null ? List<String>.from(map['files']) : null,
      isNew: map['isNew'] ?? false,
    );
  }
}
