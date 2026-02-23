import 'package:flutter/material.dart';

enum AuthMode { login, register }

class AuthPage extends StatefulWidget {
  final bool loading;
  final String errorText;
  final Future<void> Function(String username, String password) onLogin;
  final Future<void> Function(
    String username,
    String displayName,
    String password,
    String communityName,
    String communityDistrict,
  ) onRegister;

  const AuthPage({
    super.key,
    required this.loading,
    required this.errorText,
    required this.onLogin,
    required this.onRegister,
  });

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  AuthMode _mode = AuthMode.login;

  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _displayNameController = TextEditingController();
  final _communityController = TextEditingController(text: '成都高新区社区');
  final _districtController = TextEditingController(text: '成都市');

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _displayNameController.dispose();
    _communityController.dispose();
    _districtController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (username.isEmpty || password.isEmpty) {
      return;
    }

    if (_mode == AuthMode.login) {
      await widget.onLogin(username, password);
      return;
    }

    await widget.onRegister(
      username,
      _displayNameController.text.trim().isEmpty
          ? username
          : _displayNameController.text.trim(),
      password,
      _communityController.text.trim().isEmpty ? '成都高新区社区' : _communityController.text.trim(),
      _districtController.text.trim().isEmpty ? '成都市' : _districtController.text.trim(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF111827), Color(0xFF0F172A)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: Card(
                  elevation: 10,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'NebulaGuard 社区端',
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '登录后可上报、聊天、使用AI助手',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[700]),
                        ),
                        const SizedBox(height: 16),
                        SegmentedButton<AuthMode>(
                          segments: const [
                            ButtonSegment(value: AuthMode.login, label: Text('登录')),
                            ButtonSegment(value: AuthMode.register, label: Text('注册')),
                          ],
                          selected: {_mode},
                          onSelectionChanged: (s) => setState(() => _mode = s.first),
                        ),
                        const SizedBox(height: 16),
                        TextField(
                          controller: _usernameController,
                          decoration: const InputDecoration(
                            labelText: '用户名',
                            hintText: '字母/数字/下划线',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _passwordController,
                          obscureText: true,
                          decoration: const InputDecoration(labelText: '密码'),
                        ),
                        if (_mode == AuthMode.register) ...[
                          const SizedBox(height: 12),
                          TextField(
                            controller: _displayNameController,
                            decoration: const InputDecoration(labelText: '显示名称'),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _communityController,
                            decoration: const InputDecoration(labelText: '社区名称'),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _districtController,
                            decoration: const InputDecoration(labelText: '行政区'),
                          ),
                        ],
                        if (widget.errorText.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: cs.errorContainer,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(widget.errorText, style: TextStyle(color: cs.onErrorContainer)),
                          ),
                        ],
                        const SizedBox(height: 16),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton(
                            onPressed: widget.loading ? null : _submit,
                            child: widget.loading
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : Text(_mode == AuthMode.login ? '登录' : '注册并进入'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
