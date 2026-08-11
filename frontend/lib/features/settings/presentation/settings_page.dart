import 'package:content_retrieval_app/core/accessibility/live_region_message.dart';
import 'package:content_retrieval_app/features/settings/domain/app_settings.dart';
import 'package:content_retrieval_app/features/settings/presentation/settings_controller.dart';
import 'package:flutter/material.dart';

final class SettingsPage extends StatefulWidget {
  const SettingsPage({
    super.key,
    required this.controller,
    this.onSettingsSaved,
  });

  final SettingsController controller;
  final VoidCallback? onSettingsSaved;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

final class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _backendUrlController;
  String? _successMessage;

  @override
  void initState() {
    super.initState();
    _backendUrlController = TextEditingController(
      text: widget.controller.draft.backendBaseUrl,
    );
  }

  @override
  void dispose() {
    _backendUrlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 760),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Semantics(
                      header: true,
                      child: Text(
                        '设置',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '偏好设置保存在本机，不会上传。',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 20),
                    if (controller.recoveryWarning != null)
                      _MessageBanner(
                        message: controller.recoveryWarning!,
                        actionLabel: '知道了',
                        onAction: controller.dismissRecoveryWarning,
                      ),
                    if (controller.saveError != null)
                      _MessageBanner(message: controller.saveError!),
                    if (_successMessage != null)
                      _MessageBanner(
                        message: _successMessage!,
                        actionLabel: '关闭',
                        onAction: () => setState(() => _successMessage = null),
                      ),
                    _SettingsSection(
                      title: '后端连接',
                      children: [
                        TextField(
                          key: const Key('backend-base-url'),
                          controller: _backendUrlController,
                          enabled: !controller.isBusy,
                          keyboardType: TextInputType.url,
                          autocorrect: false,
                          decoration: InputDecoration(
                            labelText: '后端地址',
                            hintText: 'http://127.0.0.1:8000',
                            errorText: controller.backendUrlError,
                            helperText: '仅支持 HTTP 或 HTTPS 根地址。',
                          ),
                          onChanged: (value) {
                            _successMessage = null;
                            controller.setBackendBaseUrl(value);
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    _SettingsSection(
                      title: '外观与无障碍',
                      children: [
                        const Text('主题'),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _themeChoice(
                              label: '跟随系统',
                              value: AppThemePreference.system,
                              controller: controller,
                            ),
                            _themeChoice(
                              label: '浅色',
                              value: AppThemePreference.light,
                              controller: controller,
                            ),
                            _themeChoice(
                              label: '深色',
                              value: AppThemePreference.dark,
                              controller: controller,
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('高对比度'),
                          subtitle: const Text('增强边框和文字与背景的区分度'),
                          value: controller.draft.highContrast,
                          onChanged: controller.isBusy
                              ? null
                              : controller.setHighContrast,
                        ),
                        const Divider(),
                        const Text('文字大小'),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final scale in supportedTextScales)
                              ChoiceChip(
                                label: Text('${(scale * 100).round()}%'),
                                selected: controller.draft.textScale == scale,
                                onSelected: controller.isBusy
                                    ? null
                                    : (_) => controller.setTextScale(scale),
                              ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('减少动态效果'),
                          subtitle: const Text('关闭非必要动画和过渡效果'),
                          value: controller.draft.reduceMotion,
                          onChanged: controller.isBusy
                              ? null
                              : controller.setReduceMotion,
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    Wrap(
                      alignment: WrapAlignment.end,
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        OutlinedButton(
                          onPressed: controller.isBusy ? null : _reset,
                          child: const Text('恢复默认设置'),
                        ),
                        FilledButton(
                          onPressed:
                              controller.isBusy ||
                                  controller.backendUrlError != null
                              ? null
                              : _save,
                          child: Text(controller.isBusy ? '正在保存…' : '保存设置'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _themeChoice({
    required String label,
    required AppThemePreference value,
    required SettingsController controller,
  }) {
    return ChoiceChip(
      label: Text(label),
      selected: controller.draft.themeMode == value,
      onSelected: controller.isBusy
          ? null
          : (_) => controller.setThemeMode(value),
    );
  }

  Future<void> _save() async {
    final saved = await widget.controller.save();
    if (!mounted || !saved) return;
    _backendUrlController.text = widget.controller.settings.backendBaseUrl;
    setState(() => _successMessage = '设置已保存');
    widget.onSettingsSaved?.call();
  }

  Future<void> _reset() async {
    final reset = await widget.controller.reset();
    if (!mounted || !reset) return;
    _backendUrlController.text = widget.controller.settings.backendBaseUrl;
    setState(() => _successMessage = '已恢复默认设置');
    widget.onSettingsSaved?.call();
  }
}

final class _SettingsSection extends StatelessWidget {
  const _SettingsSection({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text(title, style: Theme.of(context).textTheme.titleLarge),
            ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      ),
    );
  }
}

final class _MessageBanner extends StatelessWidget {
  const _MessageBanner({
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: MaterialBanner(
        content: LiveRegionMessage(
          message: message.endsWith('。') ? message : '$message。',
          child: Text(message),
        ),
        actions: [
          if (actionLabel != null && onAction != null)
            TextButton(onPressed: onAction, child: Text(actionLabel!)),
        ],
      ),
    );
  }
}
