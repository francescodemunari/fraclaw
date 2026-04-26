import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'dart:io';
import '../services/socket_service.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_container.dart';
import '../widgets/app_ui.dart';
import '../widgets/aurora_background.dart';

class MemoryScreen extends StatefulWidget {
  const MemoryScreen({super.key});

  @override
  State<MemoryScreen> createState() => _MemoryScreenState();
}

class _MemoryScreenState extends State<MemoryScreen> {
  bool _isUploading = false;
  String? _statusMessage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SocketService>().fetchMemories();
    });
  }

  Future<void> _pickAndUpload() async {
    final socketService = context.read<SocketService>();
    
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.any,
      allowMultiple: false,
    );

    if (result != null) {
      setState(() {
        _isUploading = true;
        _statusMessage = 'Uploading ${result.files.first.name}...';
      });

      try {
        var request = http.MultipartRequest('POST', Uri.parse('${socketService.serverUrl}/api/upload'));
        
        if (Platform.isWindows || Platform.isAndroid || Platform.isIOS) {
          request.files.add(await http.MultipartFile.fromPath('file', result.files.first.path!));
        }

        var response = await request.send();

        if (response.statusCode == 200) {
          setState(() => _statusMessage = '✅ File indexed successfully!');
          socketService.fetchMemories(); // Refresh list if upload affects facts
        } else {
          setState(() => _statusMessage = '❌ Upload failed (Error ${response.statusCode})');
        }
      } catch (e) {
        setState(() => _statusMessage = '❌ Error: $e');
      } finally {
        setState(() => _isUploading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final service = context.watch<SocketService>();
    final memories = service.memories;

    return Scaffold(
      backgroundColor: AppTheme.primaryDark,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Text(
          'MEMORY CORE',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            letterSpacing: 4,
            fontWeight: FontWeight.w900,
            shadows: [Shadow(color: AppTheme.neonCyan.withValues(alpha: 0.5), blurRadius: 10)],
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white60),
            onPressed: () => service.fetchMemories(),
          )
        ],
      ),
      body: AuroraBackground(
        child: Column(
          children: [
            const SizedBox(height: 120),
            if (_statusMessage != null) _buildStatusBanner(),
            Expanded(
              child: memories.isEmpty
                  ? _buildEmptyState()
                  : _buildMemoriesList(memories, service),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isUploading ? null : _pickAndUpload,
        backgroundColor: AppTheme.primaryCyan,
        icon: _isUploading 
          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
          : const Icon(Icons.add_to_photos_outlined, color: Colors.white),
        label: Text(_isUploading ? 'INDEXING...' : 'EXPAND KNOWLEDGE', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1)),
      ),
    );
  }

  Widget _buildStatusBanner() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      child: GlassContainer(
        borderRadius: 15,
        opacity: 0.1,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          child: Row(
            children: [
              Expanded(child: Text(_statusMessage!, style: TextStyle(color: _statusMessage!.contains('✅') ? Colors.greenAccent : Colors.redAccent, fontSize: 13))),
              IconButton(icon: const Icon(Icons.close, size: 16, color: Colors.white30), onPressed: () => setState(() => _statusMessage = null))
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.psychology_outlined, size: 80, color: Colors.white.withValues(alpha: 0.05)),
          const SizedBox(height: 20),
          Text('COGNITIVE VOID', style: TextStyle(color: Colors.white.withValues(alpha: 0.2), letterSpacing: 5, fontWeight: FontWeight.w100)),
        ],
      ),
    );
  }

  Widget _buildMemoriesList(List<Map<String, dynamic>> memories, SocketService service) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      itemCount: memories.length,
      itemBuilder: (context, index) {
        final m = memories[index];
        return Padding(
          padding: const EdgeInsets.only(bottom: 15),
          child: GlassContainer(
            borderRadius: 20,
            opacity: 0.05,
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              leading: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: AppTheme.primaryCyan.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)),
                child: Icon(_getIconForCategory(m['category']), color: AppTheme.primaryCyan, size: 20),
              ),
              title: Text(m['key'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 4.0),
                child: Text(m['value'], style: TextStyle(color: Colors.white70.withValues(alpha: 0.5), fontSize: 13)),
              ),
              trailing: IconButton(
                icon: const Icon(Icons.delete_sweep_outlined, color: Colors.redAccent, size: 20),
                onPressed: () => _confirmDelete(m['category'], m['key'], service),
              ),
            ),
          ),
        );
      },
    );
  }

  IconData _getIconForCategory(String? category) {
    switch (category?.toLowerCase()) {
      case 'personal': return Icons.person_outline;
      case 'project': return Icons.work_outline;
      case 'preference': return Icons.settings_suggest_outlined;
      default: return Icons.memory_outlined;
    }
  }

  void _confirmDelete(String category, String key, SocketService service) async {
    final confirm = await AppUI.confirmDialog(
      context,
      title: 'Forget Fact?',
      message: 'Remove "$key" from active knowledge?',
      confirmLabel: 'FORGET',
      destructive: true,
    );
    if (confirm == true) {
      service.deleteMemory(category, key);
    }
  }
}
