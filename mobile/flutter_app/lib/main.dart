import 'package:flutter/material.dart';

import 'core/api_client.dart';
import 'core/models.dart';
import 'core/session_store.dart';
import 'ui/auth_page.dart';
import 'ui/home_page.dart';

const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

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

  bool _booting = true;
  bool _authLoading = false;
  String _authError = '';
  AuthUser? _user;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(baseUrl: apiBaseUrl);
    _primeLocalNetworkPermission();
    _restoreSession();
  }

  Future<void> _primeLocalNetworkPermission() async {
    try {
      await _api.pingHealth();
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
    await _session.clearToken();
    _api.setToken('');
    if (mounted) {
      setState(() {
        _user = null;
      });
    }
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
