# Week 6 Windows 轻量稳定包设计

## 1. 目标

在不覆盖现有完整包的前提下，新增一份 Windows 轻量稳定包。最终 ZIP 必须严格小于 `1,000,000,000` 字节，并保留文本语义检索、图片语义检索、五格式解析、本地向量库和断网运行能力。

当前最终目录中的 `01_Windows完整集成稳定版.zip` 为 1,471,215,685 字节。其中两个必需模型在 ZIP 内约占 612.3 MiB，Python 运行时约占 478.0 MiB，完整 JDK 约占 227.2 MiB，Tika 约占 61.6 MiB。轻量化必须聚焦于生产运行时白名单和 Java 运行时，不能仅调整 ZIP 压缩级别。

## 2. 范围

### 保留

- Flutter Windows release 前端。
- 后端生产源码和启动脚本。
- `text-multilingual-v1` 文本模型和 `mobileclip-s0-v1` 图文模型。
- Python 3.10 及应用真正使用的第三方库。
- ChromaDB、PDFium、Tika 及 Tika 所需的最小 Java 运行时。
- 开源许可证、模型清单、包清单和 SHA-256 信息。

### 可裁剪

- MobileCLIP 评测链：`pycocoevalcap`、`clip_benchmark`、`datasets`、`pandas`、`pyarrow` 及仅由评测链引入的依赖。
- 开发与测试组件：`pytest`、`pytest-cov`、`coverage` 和其元数据。
- Python `__pycache__`、`.pyc`、标准库测试数据、第三方包测试目录。
- PyTorch 编译头文件和 `.lib` 静态链接文件；保留所有推理所需 DLL。
- JDK 中的 `jmods`、`src.zip`、编译器、文档工具、调试工具等非运行时内容。
- MobileCLIP 上游源码中的评测、训练和示例资源；保留运行包与许可证。

### 不在本轮范围

- 更换、量化或下载新模型。
- 将模型拆成首次运行下载项。
- 改变检索算法、嵌入维度、模型空间或数据库格式。

## 3. 实现设计

在 `tools/week6/package_stable_build.ps1` 中增加显式轻量模式，并保持默认模式行为不变。轻量模式仅在完成原有白名单复制后、生成 `PACKAGE_MANIFEST.json` 之前运行可审计的裁剪步骤。

裁剪规则使用静态的精确路径/模式白名单，不使用无边界递归删除。每个删除目标必须先解析为位于当次临时 `app/runtime` 或 `app/third_party` 下的绝对路径。原始 ZIP、源码目录、项目 `.venv` 和用户数据均不是删除目标。

Java 运行时使用当前 JDK 的 `jlink` 生成到当次临时目录。模块集以 `java.base`、`java.desktop`、`java.logging`、`java.management`、`java.naming`、`java.net.http`、`java.sql`、`java.xml`、`jdk.crypto.ec`、`jdk.unsupported` 为初始集，并以 Tika 真实启动与五格式解析验证来确认反射加载的模块是否齐全。不根据 `jdeps` 结果盲目删减模块。

轻量包使用新文件名 `01_Windows轻量集成稳定版.zip`，不覆盖 `01_Windows完整集成稳定版.zip`。打包脚本在 ZIP 生成后立即读取精确字节数；若大于等于 `1,000,000,000`，则删除当次临时 ZIP 并以非零码失败，不将超限包移入最终交付目录。

## 4. 清单与可追溯性

`PACKAGE_MANIFEST.json` 在裁剪后生成，因此只记录最终包中实际存在的文件。清单新增以下字段：

- `package_profile: "lightweight"`
- `archive_size_limit_bytes: 1000000000`
- `pruning_policy_version`
- `excluded_runtime_components`
- `java_runtime_mode: "jlink"`

生成后复算 ZIP SHA-256，并在最终回执中报告精确字节数、MiB 数和哈希。不修改现有三份 DOCX 的内容。

## 5. 测试设计

实现遵循测试驱动顺序：

1. 先为轻量模式、精确裁剪规则、必需文件保留、清单字段和严格字节上限写失败测试。
2. 观察测试因轻量功能尚未存在而按预期失败。
3. 实现最少脚本改动，使新测试通过，再运行现有 Week 6 PowerShell 打包测试确认默认模式无回归。
4. 使用真实模型、Tika 和 Flutter release 生成候选轻量包。
5. 在 F 盘独立短路径临时目录解压，检查 ZIP 条目数、清单文件数与 SHA-256。
6. 在解压副本上执行启动预检、Tika 启动、TXT/PDF/DOCX/JPG/PNG 解析，以及真实文本/图片模型加载和检索冒烟。
7. 禁用外网后重复核心冒烟，确认没有首次运行下载。

最终 ZIP 仅做只读审计；任何会写入缓存、数据库或日志的验证都在单独解压副本中进行。

## 6. 失败处理

- 任一必需库、DLL、Java 模块、模型或许可证缺失时，停止交付。
- 任一真实模型或五格式流程失败时，恢复相应依赖或 Java 模块后重新验证，不放宽测试。
- ZIP 达到或超过 `1,000,000,000` 字节时，打包失败。
- 如果在保留全部核心功能的前提下仍无法达到上限，停止并报告实测最小体积；不擅自删除模型、Tika 或离线能力。

## 7. 验收标准

- 新 ZIP 存在且精确字节数 `< 1,000,000,000`。
- 现有完整 ZIP 的路径、大小和哈希未被本流程改写。
- 新 ZIP 可在短路径空目录完整解压，包内清单与实际文件一致。
- 启动预检、Tika、五格式解析、文本模型、图片模型和检索冒烟全部通过。
- 断网状态下核心冒烟通过，不进行外部下载。
- 默认完整打包模式的现有测试全部通过。
