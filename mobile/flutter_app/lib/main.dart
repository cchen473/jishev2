import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'core/api_client.dart';
import 'core/models.dart';
import 'core/session_store.dart';
import 'ui/auth_page.dart';
import 'ui/home_page.dart';

const apiBaseUrlFromEnv =
    String.fromEnvironment('API_BASE_URL', defaultValue: '');

String resolveApiBaseUrl() {
  final configured = apiBaseUrlFromEnv.trim();
  if (configured.isNotEmpty) {
    return configured;
  }
  if (kIsWeb) {
    return 'http://localhost:8000';
  }
  if (defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8000';
  }
  return 'http://127.0.0.1:8000';
}

void main() {
  runApp(const NebulaGuardApp());
}

class NebulaGuardApp extends StatelessWidget {
  const NebulaGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFFC8A56A);
    return MaterialApp(
      title: 'NebulaGuard 社区端',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme:
            ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.light),
        inputDecorationTheme:
            const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme:
            ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark),
        inputDecorationTheme:
            const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      home: const AppController(),
    );
  }
}

class AppController extends StatefulWidget {
  const AppController({super.key});

  @override
  State<AppController> createState() => _AppControllerState();
}

class _AppControllerState extends State<AppController> {
  final _session = SessionStore();
  late final ApiClient _api;
  WebSocketChannel? _channel;
  StreamSubscription? _channelSub;
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  final Set<String> _seenWarningIds = <String>{};
  bool _warningDialogOpen = false;

  bool _booting = true;
  bool _authLoading = false;
  String _authError = '';
  AuthUser? _user;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(baseUrl: resolveApiBaseUrl());
    _primeLocalNetworkPermission();
    _restoreSession();
  }

  Future<void> _primeLocalNetworkPermission() async {
    try {
      await _api.pingBackend();
    } catch (_) {
      // Ignore here. This request is only used to trigger local network permission prompts.
    }
  }

  Future<T> _retryOnceIfSocketError<T>(Future<T> Function() action) async {
    try {
      return await action();
    } catch (e) {
      final message = '$e';
      final isSocketIssue = message.contains('SocketException') ||
          message.contains('No route to host');
      if (!isSocketIssue) rethrow;
      await Future<void>.delayed(const Duration(milliseconds: 1200));
      return action();
    }
  }

  String _formatAuthError(Object error) {
    final message = '$error';
    if (message.contains('SocketException') ||
        message.contains('No route to host')) {
      return '网络连接失败。请在手机中允许 NebulaGuard 访问本地网络后，再点一次登录/注册。';
    }
    if (message.contains('超时')) {
      return '请求超时。请确认后端已启动且地址可访问后重试。';
    }
    return message;
  }

  Future<void> _restoreSession() async {
    final token = await _session.readToken();
    if (token.isNotEmpty) {
      _api.setToken(token);
      try {
        final me = await _api.fetchMe();
        if (mounted) {
          setState(() {
            _user = me;
          });
        }
        _startRealtime(token);
      } catch (_) {
        await _session.clearToken();
        _api.setToken('');
      }
    }
    if (mounted) {
      setState(() => _booting = false);
    }
  }

  Future<void> _login(String username, String password) async {
    setState(() {
      _authLoading = true;
      _authError = '';
    });
    try {
      final payload = await _retryOnceIfSocketError(
        () => _api.login(username: username, password: password),
      );
      _api.setToken(payload.token);
      await _session.saveToken(payload.token);
      _startRealtime(payload.token);
      if (mounted) {
        setState(() => _user = payload.user);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _authError = _formatAuthError(e));
      }
    } finally {
      if (mounted) {
        setState(() => _authLoading = false);
      }
    }
  }

  Future<void> _register(
    String username,
    String displayName,
    String password,
    String communityName,
    String communityDistrict,
  ) async {
    setState(() {
      _authLoading = true;
      _authError = '';
    });
    try {
      final payload = await _retryOnceIfSocketError(
        () => _api.register(
          username: username,
          displayName: displayName,
          password: password,
          communityName: communityName,
          communityDistrict: communityDistrict,
        ),
      );
      _api.setToken(payload.token);
      await _session.saveToken(payload.token);
      _startRealtime(payload.token);
      if (mounted) {
        setState(() => _user = payload.user);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _authError = _formatAuthError(e));
      }
    } finally {
      if (mounted) {
        setState(() => _authLoading = false);
      }
    }
  }

  Future<void> _logout() async {
    _stopRealtime();
    await _session.clearToken();
    _api.setToken('');
    if (mounted) {
      setState(() {
        _user = null;
      });
    }
  }

  void _showWarningDialog({
    required String title,
    required String content,
  }) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: const Color(0xFF8B1E1E),
        duration: const Duration(seconds: 5),
        content: Text('⚠️ $title'),
      ),
    );
    if (_warningDialogOpen) {
      return;
    }
    _warningDialogOpen = true;
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        title: const Text('地震紧急预警'),
        content: Text(content),
        actions: [
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('已知悉'),
          ),
        ],
      ),
    ).whenComplete(() {
      _warningDialogOpen = false;
    });
  }

  void _handleRealtimeMessage(dynamic raw) {
    if (raw is! String) {
      return;
    }
    Map<String, dynamic> data;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return;
      data = decoded;
    } catch (_) {
      return;
    }
    final type = (data['type'] ?? '').toString();
    if (type != 'community_warning' && type != 'community_alert') {
      return;
    }
    final notification = data['notification'];
    String notificationId = '';
    String content = (data['content'] ?? '').toString().trim();
    String title = (data['title'] ?? '紧急预警').toString().trim();
    bool emergency = type == 'community_warning';
    if (notification is Map<String, dynamic>) {
      notificationId = (notification['id'] ?? '').toString();
      final payload = notification['payload'];
      if (payload is Map<String, dynamic>) {
        emergency = emergency || payload['is_emergency'] == true;
      }
      if (content.isEmpty) {
        content = (notification['content'] ?? '').toString();
      }
      if (title.isEmpty) {
        title = (notification['title'] ?? '紧急预警').toString();
      }
    }
    if (!emergency) {
      return;
    }
    if (notificationId.isNotEmpty && _seenWarningIds.contains(notificationId)) {
      return;
    }
    if (notificationId.isNotEmpty) {
      _seenWarningIds.add(notificationId);
      if (_seenWarningIds.length > 300) {
        _seenWarningIds.remove(_seenWarningIds.first);
      }
    }
    _showWarningDialog(
      title: title.isEmpty ? '地震紧急预警' : title,
      content: content.isEmpty
          ? '请立即执行就近避险，等待社区后续调度。'
          : content,
    );
  }

  void _scheduleReconnect(String token) {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 2), () {
      if (!mounted || _user == null || token.isEmpty) return;
      _startRealtime(token);
    });
  }

  void _startRealtime(String token) {
    if (token.isEmpty) return;
    _stopRealtime();
    try {
      final channel = WebSocketChannel.connect(_api.websocketUri(token: token));
      _channel = channel;
      _channelSub = channel.stream.listen(
        _handleRealtimeMessage,
        onError: (_) => _scheduleReconnect(token),
        onDone: () => _scheduleReconnect(token),
      );
      _pingTimer = Timer.periodic(const Duration(seconds: 20), (_) {
        try {
          _channel?.sink.add(jsonEncode({'type': 'ping'}));
        } catch (_) {
          // ignore ping failure
        }
      });
    } catch (_) {
      _scheduleReconnect(token);
    }
  }

  void _stopRealtime() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _pingTimer?.cancel();
    _pingTimer = null;
    _channelSub?.cancel();
    _channelSub = null;
    try {
      _channel?.sink.close();
    } catch (_) {
      // ignore
    }
    _channel = null;
  }

  @override
  void dispose() {
    _stopRealtime();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_booting) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_user == null) {
      return AuthPage(
        loading: _authLoading,
        errorText: _authError,
        onLogin: _login,
        onRegister: _register,
      );
    }

    return MobileHomePage(user: _user!, api: _api, onLogout: _logout);
  }
}
