class ChatSession {
  final int id;
  final String title;
  final DateTime createdAt;

  ChatSession({
    required this.id,
    required this.title,
    required this.createdAt,
  });

  factory ChatSession.fromJson(Map<String, dynamic> json) {
    return ChatSession(
      id: json['id'],
      title: json['title'] ?? 'Untitled',
      createdAt: DateTime.parse(json['created_at']).toLocal(),
    );
  }
}
