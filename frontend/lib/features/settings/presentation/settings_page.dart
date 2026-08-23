import 'package:content_retrieval_app/core/presentation/workspace_header.dart';
import 'package:content_retrieval_app/core/presentation/workspace_notice.dart';
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
  late final FocusNode _resetFocusNode;
  late final FocusNode _saveFocusNode;
  bool _isPageActive = true;

  @override
  void initState() {
    super.initState();
    _backendUrlController = TextEditingController(
      text: widget.controller.draft.backendBaseUrl,
    );
    _resetFocusNode = FocusNode(debugLabel: 'settings-reset-action');
    _saveFocusNode = FocusNode(debugLabel: 'settings-save-action');
  }

  @override
  void dispose() {
    _backendUrlController.dispose();
    _resetFocusNode.dispose();
    _saveFocusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    _isPageActive = Visibility.of(context);
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
                    const WorkspaceHeader(
                      title: '设置',
                      description: '这些偏好只保存在当前设备上',
                    ),
                    const SizedBox(height: 20),
                    if (controller.recoveryWarning != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: WorkspaceNotice(
                          tone: WorkspaceNoticeTone.warning,
                          message: controller.recoveryWarning!,
                          actionLabel: '知道了',
                          onAction: controller.dismissRecoveryWarning,
                          announce: true,
                        ),
                      ),
                    if (controller.saveError != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: WorkspaceNotice(
                          tone: WorkspaceNoticeTone.error,
                          message: controller.saveError!,
                          announce: true,
                        ),
                      ),
                    _SettingsSection(
                      sectionKey: const Key('settings-connection-section'),
                      title: '连接',
                      children: [
                        TextField(
                          key: const Key('backend-base-url'),
                          controller: _backendUrlController,
                          enabled: !controller.isBusy,
                          keyboardType: TextInputType.url,
                          autocorrect: false,
                          decoration: InputDecoration(
                            labelText: '服务地址',
                            hintText: 'http://127.0.0.1:8000',
                            errorText: controller.backendUrlError,
                            helperText: '用于连接这台设备上的本地检索服务。',
                          ),
                          onChanged: controller.setBackendBaseUrl,
                        ),
                      ],
                    ),
                    _SettingsSection(
                      sectionKey: const Key('settings-appearance-section'),
                      title: '外观',
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
                        const SizedBox(height: 16),
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
                      ],
                    ),
                    _SettingsSection(
                      sectionKey: const Key('settings-accessibility-section'),
                      title: '无障碍',
                      children: [
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('高对比度'),
                          subtitle: const Text('增强文字、边框与背景的区分'),
                          value: controller.draft.highContrast,
                          onChanged: controller.isBusy
                              ? null
                              : controller.setHighContrast,
                        ),
                        const Divider(),
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('减少动态效果'),
                          subtitle: const Text('减少非必要的动画和过渡'),
                          value: controller.draft.reduceMotion,
                          onChanged: controller.isBusy
                              ? null
                              : controller.setReduceMotion,
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    Wrap(
                      alignment: WrapAlignment.spaceBetween,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        Text(controller.hasUnsavedChanges ? '尚未保存更改' : '已保存'),
                        Wrap(
                          spacing: 12,
                          runSpacing: 12,
                          children: [
                            OutlinedButton(
                              focusNode: _resetFocusNode,
                              onPressed: controller.isBusy
                                  ? null
                                  : _confirmReset,
                              child: const Text('恢复默认设置'),
                            ),
                            FilledButton(
                              focusNode: _saveFocusNode,
                              onPressed:
                                  controller.isBusy ||
                                      controller.backendUrlError != null ||
                                      !controller.hasUnsavedChanges
                                  ? null
                                  : _save,
                              child: Text(controller.isBusy ? '正在保存…' : '保存设置'),
                            ),
                          ],
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
    if (!mounted) return;
    _restoreActionFocus(_saveFocusNode);
    if (!saved) return;
    _backendUrlController.text = widget.controller.settings.backendBaseUrl;
    _showConfirmation('设置已保存');
    widget.onSettingsSaved?.call();
  }

  Future<void> _confirmReset() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('恢复默认设置？'),
        content: const Text('当前未保存的更改将被替换。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('恢复默认设置'),
          ),
        ],
      ),
    );
    if (confirmed == true) await _reset();
  }

  Future<void> _reset() async {
    final reset = await widget.controller.reset();
    if (!mounted) return;
    _restoreActionFocus(_resetFocusNode);
    if (!reset) return;
    _backendUrlController.text = widget.controller.settings.backendBaseUrl;
    _showConfirmation('已恢复默认设置');
    widget.onSettingsSaved?.call();
  }

  void _showConfirmation(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  void _restoreActionFocus(FocusNode focusNode) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted &&
          _isPageActive &&
          !widget.controller.isBusy &&
          focusNode.canRequestFocus) {
        focusNode.requestFocus();
      }
    });
  }
}

final class _SettingsSection extends StatelessWidget {
  const _SettingsSection({
    required this.sectionKey,
    required this.title,
    required this.children,
  });

  final Key sectionKey;
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: sectionKey,
      padding: const EdgeInsets.symmetric(vertical: 20),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
      ),
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
    );
  }
}
