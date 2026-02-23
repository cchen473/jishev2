import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class MobileHomePage extends StatefulWidget {
  final AuthUser user;
  final ApiClient api;
  final VoidCallback onLogout;

  const MobileHomePage({
    super.key,
    required this.user,
    required this.api,
    required this.onLogout,
  });

  @override
  State<MobileHomePage> createState() => _MobileHomePageState();
}

class _MobileHomePageState extends State<MobileHomePage> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final pages = [
      ReportTab(user: widget.user, api: widget.api),
      ChatTab(user: widget.user, api: widget.api),
      AssistantTab(api: widget.api),
      CheckinTab(user: widget.user, api: widget.api),
      CommunityTab(api: widget.api),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.user.community?.name.isNotEmpty == true
            ? '${widget.user.community!.name} · 社区端'
            : 'NebulaGuard 社区端'),
        actions: [
          IconButton(
            tooltip: '退出登录',
            onPressed: widget.onLogout,
            icon: const Icon(Icons.logout_rounded),
          ),
        ],
      ),
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (v) => setState(() => _index = v),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.campaign_outlined), label: '上报'),
          NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: '群聊'),
          NavigationDestination(icon: Icon(Icons.smart_toy_outlined), label: 'AI助手'),
          NavigationDestination(icon: Icon(Icons.fact_check_outlined), label: '报平安'),
          NavigationDestination(icon: Icon(Icons.apartment_outlined), label: '社区'),
        ],
      ),
    );
  }
}

class ReportTab extends StatefulWidget {
  final AuthUser user;
  final ApiClient api;

  const ReportTab({super.key, required this.user, required this.api});

  @override
  State<ReportTab> createState() => _ReportTabState();
}

class _ReportTabState extends State<ReportTab> {
  bool _submitting = false;
  int _feltLevel = 5;
  String _buildingType = '钢筋混凝土住宅';
  final _latController = TextEditingController();
  final _lngController = TextEditingController();
  final _structureController = TextEditingController();
  final _descriptionController = TextEditingController();
  List<String> _advice = [];

  static const _buildingTypes = [
    '钢筋混凝土住宅',
    '高层住宅',
    '老旧砖混楼',
    '学校或医院建筑',
    '自建房',
    '其他',
  ];

  @override
  void initState() {
    super.initState();
    final lat = widget.user.community?.baseLat ?? 30.5728;
    final lng = widget.user.community?.baseLng ?? 104.0668;
    _latController.text = lat.toStringAsFixed(4);
    _lngController.text = lng.toStringAsFixed(4);
  }

  @override
  void dispose() {
    _latController.dispose();
    _lngController.dispose();
    _structureController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final lat = double.tryParse(_latController.text.trim());
    final lng = double.tryParse(_lngController.text.trim());
    if (lat == null || lng == null) {
      _toast('坐标格式不正确');
      return;
    }

    setState(() => _submitting = true);
    try {
      final advice = await widget.api.submitEarthquakeReport(
        lat: lat,
        lng: lng,
        feltLevel: _feltLevel,
        buildingType: _buildingType,
        structureNotes: _structureController.text.trim(),
        description: _descriptionController.text.trim(),
      );
      setState(() {
        _advice = advice;
      });
      _toast('上报成功，社区已收到通知');
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  void _toast(String text) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('地震上报', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text('上报后会同步社区通知并生成躲避建议', style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _latController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                        decoration: const InputDecoration(labelText: '纬度'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: TextField(
                        controller: _lngController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                        decoration: const InputDecoration(labelText: '经度'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text('震感等级：$_feltLevel'),
                Slider(
                  value: _feltLevel.toDouble(),
                  min: 1,
                  max: 12,
                  divisions: 11,
                  label: '$_feltLevel',
                  onChanged: (v) => setState(() => _feltLevel = v.round()),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  value: _buildingType,
                  items: _buildingTypes
                      .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                      .toList(),
                  onChanged: (v) => setState(() => _buildingType = v ?? _buildingType),
                  decoration: const InputDecoration(labelText: '建筑/房屋结构'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _structureController,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: '周边建筑/构造补充',
                    hintText: '例如：楼道杂物多、外墙开裂、玻璃幕墙较多等',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _descriptionController,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: '现场描述（可选）',
                    hintText: '描述震感、人群状态、异常情况',
                  ),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _submitting ? null : _submit,
                    icon: _submitting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send_rounded),
                    label: Text(_submitting ? '上报中...' : '提交地震上报'),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (_advice.isNotEmpty) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('躲避建议', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  ..._advice.asMap().entries.map(
                        (e) => Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Text('${e.key + 1}. ${e.value}'),
                        ),
                      ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class ChatTab extends StatefulWidget {
  final AuthUser user;
  final ApiClient api;

  const ChatTab({super.key, required this.user, required this.api});

  @override
  State<ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<ChatTab> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  List<ChatMessage> _messages = [];
  bool _loading = true;
  bool _sending = false;
  bool _askAi = true;
  Timer? _timer;
  static const _quickPrompts = [
    '本楼已巡查完成，老人已联系',
    '请确认集合点是否变更',
    '道路受阻，请改派路线',
    '志愿者到位，可接收任务',
  ];

  @override
  void initState() {
    super.initState();
    _loadMessages();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _loadMessages(silent: true));
  }

  @override
  void dispose() {
    _timer?.cancel();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadMessages({bool silent = false}) async {
    if (!silent && mounted) {
      setState(() => _loading = true);
    }
    try {
      final list = await widget.api.fetchChatMessages(limit: 120);
      if (!mounted) return;
      setState(() => _messages = list);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 180),
            curve: Curves.easeOut,
          );
        }
      });
    } catch (_) {
      // no-op for polling errors
    } finally {
      if (mounted && !silent) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _send() async {
    final content = _controller.text.trim();
    if (content.isEmpty || _sending) return;

    setState(() => _sending = true);
    try {
      await widget.api.sendChatMessage(content: content, askAi: _askAi);
      _controller.clear();
      await _loadMessages(silent: true);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  void _insertPrompt(String text) {
    _controller.text = text;
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: _controller.text.length),
    );
  }

  bool _isMine(ChatMessage message) {
    if (message.senderUserId != null && message.senderUserId == widget.user.id) {
      return true;
    }
    return message.role == 'user' && message.senderName == widget.user.displayName;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(14, 8, 14, 8),
          child: Row(
            children: [
              Text('社区群聊', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                tooltip: '刷新',
                onPressed: () => _loadMessages(),
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _messages.isEmpty
                  ? const Center(child: Text('暂无聊天消息，先发一条吧'))
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      itemCount: _messages.length,
                      itemBuilder: (context, i) {
                        final msg = _messages[i];
                        final mine = _isMine(msg);
                        final bubbleColor = mine
                            ? Theme.of(context).colorScheme.primaryContainer
                            : (msg.role == 'assistant'
                                ? const Color(0xFFFFF5E1)
                                : Theme.of(context).colorScheme.surfaceContainerHighest);
                        final align = mine ? Alignment.centerRight : Alignment.centerLeft;
                        return Align(
                          alignment: align,
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 320),
                            child: Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                              decoration: BoxDecoration(
                                color: bubbleColor,
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Column(
                                crossAxisAlignment:
                                    mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    msg.role == 'assistant' ? '社区AI助手' : msg.senderName,
                                    style: Theme.of(context).textTheme.labelSmall,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    msg.content,
                                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.35),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    msg.createdAt.length >= 16
                                        ? msg.createdAt.replaceFirst('T', ' ').substring(0, 16)
                                        : msg.createdAt,
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelSmall
                                        ?.copyWith(color: Colors.grey[600]),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
        ),
        SafeArea(
          top: false,
          child: Container(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(top: BorderSide(color: Colors.grey.withOpacity(0.2))),
            ),
            child: Column(
              children: [
                SizedBox(
                  height: 34,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _quickPrompts.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 6),
                    itemBuilder: (context, i) => OutlinedButton(
                      onPressed: () => _insertPrompt(_quickPrompts[i]),
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(color: Colors.grey.withOpacity(0.35)),
                        visualDensity: VisualDensity.compact,
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                      ),
                      child: Text(_quickPrompts[i], style: Theme.of(context).textTheme.labelSmall),
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Switch(
                      value: _askAi,
                      onChanged: (v) => setState(() => _askAi = v),
                    ),
                    const SizedBox(width: 4),
                    Text('发送后让 AI 跟进', style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        minLines: 1,
                        maxLines: 4,
                        decoration: const InputDecoration(hintText: '输入消息并发送给社区'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                      onPressed: _sending ? null : _send,
                      child: _sending
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.send_rounded),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class AssistantTab extends StatefulWidget {
  final ApiClient api;

  const AssistantTab({super.key, required this.api});

  @override
  State<AssistantTab> createState() => _AssistantTabState();
}

class _AssistantTabState extends State<AssistantTab> {
  final _questionController = TextEditingController();
  final List<AssistantAskResult> _history = [];
  bool _loading = false;

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  Future<void> _ask() async {
    final q = _questionController.text.trim();
    if (q.isEmpty || _loading) return;

    setState(() => _loading = true);
    try {
      final result = await widget.api.askAssistant(q);
      if (!mounted) return;
      setState(() {
        _history.insert(0, result);
        _questionController.clear();
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('社区 AI 管理助手', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 6),
                Text(
                  '用于楼栋协同、通知模板、应急分工策略，回答会同步写入社区聊天。',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _questionController,
                  minLines: 2,
                  maxLines: 5,
                  decoration: const InputDecoration(
                    labelText: '输入问题',
                    hintText: '例如：今晚余震预警下，如何组织楼栋长分批巡查？',
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _loading ? null : _ask,
                    icon: _loading
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.auto_awesome_rounded),
                    label: Text(_loading ? '生成中...' : '提问 AI 助手'),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (_history.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text('暂无提问记录，先问一个社区管理问题。'),
            ),
          )
        else
          ..._history.map(
            (item) => Card(
              margin: const EdgeInsets.only(bottom: 10),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('你问：', style: Theme.of(context).textTheme.labelMedium),
                    const SizedBox(height: 4),
                    Text(item.userMessage.content),
                    const Divider(height: 18),
                    Text('AI 建议：', style: Theme.of(context).textTheme.labelMedium),
                    const SizedBox(height: 4),
                    Text(item.assistantMessage.content),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class CheckinTab extends StatefulWidget {
  final AuthUser user;
  final ApiClient api;

  const CheckinTab({super.key, required this.user, required this.api});

  @override
  State<CheckinTab> createState() => _CheckinTabState();
}

class _CheckinTabState extends State<CheckinTab> {
  final _subjectController = TextEditingController();
  final _notesController = TextEditingController();
  String _relation = 'self';
  String _status = 'safe';
  bool _submitting = false;
  CheckinSummary? _summary;

  @override
  void initState() {
    super.initState();
    _subjectController.text = widget.user.displayName;
    _loadSummary();
  }

  @override
  void dispose() {
    _subjectController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _loadSummary() async {
    try {
      final summary = await widget.api.fetchCheckinSummary();
      if (!mounted) return;
      setState(() => _summary = summary);
    } catch (_) {
      // no-op
    }
  }

  Future<void> _submit() async {
    if (_subjectController.text.trim().isEmpty || _submitting) return;
    setState(() => _submitting = true);
    try {
      await widget.api.submitResidentCheckin(
        subjectName: _subjectController.text.trim(),
        relation: _relation,
        status: _status,
        notes: _notesController.text.trim(),
        lat: widget.user.community?.baseLat,
        lng: widget.user.community?.baseLng,
      );
      if (!mounted) return;
      _notesController.clear();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('报平安状态已提交')));
      await _loadSummary();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final byStatus = _summary?.byStatus ?? <String, int>{};
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('一键报平安', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 6),
                Text('用于社区统计安全状态，管理端会实时看到回执变化。', style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 12),
                TextField(
                  controller: _subjectController,
                  decoration: const InputDecoration(labelText: '上报对象'),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  value: _relation,
                  decoration: const InputDecoration(labelText: '关系'),
                  items: const [
                    DropdownMenuItem(value: 'self', child: Text('本人')),
                    DropdownMenuItem(value: 'family', child: Text('家人代报')),
                    DropdownMenuItem(value: 'neighbor', child: Text('邻里代报')),
                    DropdownMenuItem(value: 'other', child: Text('其他')),
                  ],
                  onChanged: (v) => setState(() => _relation = v ?? 'self'),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  value: _status,
                  decoration: const InputDecoration(labelText: '当前状态'),
                  items: const [
                    DropdownMenuItem(value: 'safe', child: Text('平安')),
                    DropdownMenuItem(value: 'need_help', child: Text('需要救援')),
                    DropdownMenuItem(value: 'missing_proxy', child: Text('失联代报')),
                  ],
                  onChanged: (v) => setState(() => _status = v ?? 'safe'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _notesController,
                  minLines: 2,
                  maxLines: 4,
                  decoration: const InputDecoration(labelText: '备注（可选）'),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _submitting ? null : _submit,
                    icon: _submitting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.fact_check_rounded),
                    label: Text(_submitting ? '提交中...' : '提交报平安'),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('社区回执概览', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _SummaryChip(label: '总回执', value: '${_summary?.total ?? 0}'),
                    _SummaryChip(label: '平安', value: '${byStatus['safe'] ?? 0}'),
                    _SummaryChip(label: '需救援', value: '${byStatus['need_help'] ?? 0}'),
                    _SummaryChip(label: '失联代报', value: '${byStatus['missing_proxy'] ?? 0}'),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class CommunityTab extends StatefulWidget {
  final ApiClient api;

  const CommunityTab({super.key, required this.api});

  @override
  State<CommunityTab> createState() => _CommunityTabState();
}

class _CommunityTabState extends State<CommunityTab> {
  bool _loading = true;
  List<IncidentItem> _incidents = [];
  List<ShelterItem> _shelters = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final incidents = await widget.api.fetchIncidents(limit: 60);
      final shelters = await widget.api.fetchShelters(limit: 60);
      if (!mounted) return;
      setState(() {
        _incidents = incidents;
        _shelters = shelters;
      });
    } catch (_) {
      // ignore
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('社区事件看板', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (_incidents.isEmpty)
                    const Text('暂无事件')
                  else
                    ..._incidents.take(8).map(
                          (item) => ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            title: Text(item.title, style: Theme.of(context).textTheme.bodyMedium),
                            subtitle: Text('${item.status} · ${item.priority}'),
                          ),
                        ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('避难点容量', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (_shelters.isEmpty)
                    const Text('暂无避难点数据')
                  else
                    ..._shelters.take(8).map((item) {
                      final ratio = item.capacity <= 0 ? 0.0 : item.currentOccupancy / item.capacity;
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(item.name),
                            const SizedBox(height: 2),
                            Text(
                              '${item.currentOccupancy}/${item.capacity} · ${item.status}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            const SizedBox(height: 4),
                            LinearProgressIndicator(value: ratio.clamp(0, 1)),
                          ],
                        ),
                      );
                    }),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  final String label;
  final String value;

  const _SummaryChip({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.withOpacity(0.35)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 3),
          Text(value, style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}
