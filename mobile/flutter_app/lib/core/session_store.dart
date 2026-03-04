class SessionStore {
  static String _volatileToken = '';

  Future<void> saveToken(String token) async {
    _volatileToken = token;
  }

  Future<String> readToken() async {
    return _volatileToken;
  }

  Future<void> clearToken() async {
    _volatileToken = '';
  }
}
