# 数据来源与许可说明

## 本地烟测内容

- `datasets/smoke/text/` 下文本由本项目创建，仅用于软件测试。
- 项目根目录的 PDF 和 DOCX 为用户提供的项目材料，仅用于本地开发和验证；在未确认传播权限前不得随公开仓库发布。
- Flutter 默认应用图标来自 `flutter create` 生成的项目资产，其再分发应遵循 Flutter 项目及相关模板许可。

## 外部候选数据集

### Google Natural Questions

- 官方来源：`https://ai.google.com/research/NaturalQuestions/download`
- 官方页面标注：Creative Commons Share-Alike 3.0。
- 旧样本路径：`gs://bert-nq/tiny-dev` 与
  `gs://natural_questions/v1.0/sample/nq-dev-sample.jsonl.gz`。
- 2026-07-14 实测状态：已登录 Google 账号仍对两个路径返回 HTTP 403，
  缺少 `storage.objects.get`；不再声称官方 tiny-dev 已成功下载。
- 当前本地替代来源：
  `https://huggingface.co/datasets/sentence-transformers/NQ-retrieval`，使用其
  `dev.jsonl.gz` 并固定选取 200 个有长答案、文档 URL 唯一的检索样本。
- 本地文件 SHA-256：
  `ad23b7e4f50b0f02c9395a4f8fe39946e3e1242edea7c826aaf7ac378f3e8779`。
- 许可管理：这是 NQ 衍生数据，按原始 NQ CC BY-SA 3.0 的署名与同方式共享要求保守处理；
  Sentence Transformers 仓库来源记录不代替原始数据许可。对外重新分发前需再次复核两级来源条款。

### COCO

- 官方来源：`https://cocodataset.org/`
- 标注包：`http://images.cocodataset.org/annotations/annotations_trainval2017.zip`
- 标注包 SHA-256：`113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268`。
- captions JSON SHA-256：`afe3b30e403dd7f228e2373023abbd60042a6e10ec6874d3652df034d289ebb9`。
- instances JSON SHA-256：`e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`。
- 当前状态：已固定 200 张 val2017 图片，其中 validation 160 张、冻结 benchmark 40 张。
- 图片来自 Flickr，不存在覆盖全部图片的单一许可。本子集逐图保留 Flickr URL、COCO URL、
  许可证 ID/URL 和文件 SHA-256；其中包含非商业、相同方式共享和禁止演绎等不同限制。
- 公开代码包不包含图片二进制；如需重建，应运行准备脚本从官方源下载，并按
  `datasets/processed/coco/*/items.jsonl` 的单图许可记录使用。

### RVL-CDIP

- 原计划来源：`https://www.cs.cmu.edu/~aharley/rvl-cdip/`
- 当前状态：原链接已重定向，未下载。
- 注意：在找到可靠来源并确认数据许可、隐私和再分发条件前，不纳入正式验证集。

### Wikipedia Dumps

- 官方来源：`https://dumps.wikimedia.org/`
- 许可说明：`https://dumps.wikimedia.org/legal.html`
- 官方说明指出文本通常采用 CC BY-SA 4.0 和 GFDL；图片及例外内容需要逐项核查。
- 当前状态：未下载。

## 模型与数据分离

MobileCLIP 代码、预训练模型和训练数据具有不同许可。下载任何预训练权重前，应单独保存对应模型卡和许可文本，不能仅依据代码仓库的开源许可证判断模型权重可否再分发。
