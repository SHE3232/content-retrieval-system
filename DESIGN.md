---
name: 本地内容检索
description: 让用户凭记得的内容安静、可信地找回本地资料。
colors:
  research-cobalt: "#3659AD"
  hc-light-primary: "#002A78"
  hc-light-primary-text: "#FFFFFF"
  hc-light-selected: "#D6E1FF"
  hc-light-selected-text: "#001A42"
  hc-light-surface: "#FFFFFF"
  hc-light-ink: "#101114"
  hc-light-outline: "#42474F"
  hc-light-outline-strong: "#5F636B"
  hc-light-error: "#8C0009"
  hc-dark-primary: "#ADC6FF"
  hc-dark-primary-text: "#001B3F"
  hc-dark-selected: "#12315F"
  hc-dark-surface: "#0C0E12"
  hc-dark-ink: "#FFFFFF"
  hc-dark-outline: "#C5C6CC"
  hc-dark-outline-strong: "#AEB0B7"
  hc-dark-error: "#FFB4AB"
  hc-dark-error-text: "#690005"
typography:
  headline:
    fontFamily: "system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 400
    lineHeight: 1.29
  title:
    fontFamily: "system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: 1.27
  body:
    fontFamily: "system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.43
  label:
    fontFamily: "system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.43
rounded:
  control: "12px"
  navigation-indicator: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  control-gap: "10px"
  md: "12px"
  lg: "16px"
  section: "20px"
  empty-state: "24px"
components:
  button-primary:
    backgroundColor: "{colors.research-cobalt}"
    textColor: "{colors.hc-light-primary-text}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
    height: "48px"
  input:
    backgroundColor: "{colors.hc-light-selected}"
    textColor: "{colors.hc-light-ink}"
    rounded: "{rounded.control}"
    padding: "14px 16px"
  chip-selected:
    backgroundColor: "{colors.hc-light-selected}"
    textColor: "{colors.hc-light-selected-text}"
    rounded: "{rounded.control}"
    padding: "6px 12px"
  navigation-active:
    backgroundColor: "{colors.hc-light-selected}"
    textColor: "{colors.hc-light-selected-text}"
    rounded: "{rounded.navigation-indicator}"
---

# Design System: 本地内容检索

## Overview

**Creative North Star: "安静的研究案头"**

让搜索像打开桌上的一盏灯：用户只需说出还记得的内容，相关资料和依据便清晰浮现，而系统本身退到背景。界面以搜索为视觉中心，以可信的资料目录语言呈现结果来源、命中片段和命中原因；索引维护与技术状态保持可达，但不主导首屏。

视觉上保持现代 Material 3 产品界面，不把“案头”做成木纹、纸张或台灯插画。层次来自克制的表面明度变化、稳定留白和清晰排版；主色只在当前选择、主要操作与焦点中出现。界面拒绝完全单调的纯色，也拒绝后台管理系统式指标墙和技术炫耀。

**Key Characteristics:**

- 搜索是首屏唯一视觉主角。
- 轻量分层，默认表面安静，聚焦状态清晰。
- 结果同时说明内容、来源与命中依据。
- 系统字体、Material Icons 和一致的组件语法。
- WCAG 2.1 AA、键盘、屏幕阅读器、高对比度、200% 字号与减少动态效果均为基线。

## Colors

冷静的中性色承载大部分界面，研究钴蓝只标记需要用户注意或行动的位置；高对比度主题使用显式色值覆盖运行时生成方案。

### Primary

- **研究钴蓝**：Material 3 种子色，生成亮色与暗色语义色板；用于主要操作、键盘焦点、当前导航和选中筛选。

### Neutral

- **安静表面**：使用 `ColorScheme.surface` 与 `surfaceContainerLow` 区分工作区、状态栏、侧栏和次级区域。
- **正文墨色**：使用 `onSurface`；辅助文字使用 `onSurfaceVariant`，不得用低对比度浅灰换取所谓轻盈感。
- **结构轮廓**：输入边界使用 `outline`，分隔线和低强调边界使用 `outlineVariant`。
- **语义状态**：成功、离线和错误只用于真实状态，并始终伴随图标或文字。

**The One-Lamp Rule.** 研究钴蓝只用于主要操作、当前选择与焦点，不作为大面积装饰背景。

**The Quiet Variation Rule.** 通过相邻表面的明度差和极低色度变化避免纯色单调；禁止用渐变文字、彩色光晕或无意义色块制造层次。

## Typography

**Display Font:** 系统无衬线字体
**Body Font:** 系统无衬线字体

**Character:** 单一系统字体保证跨平台清晰度和辅助技术兼容性。层级依靠字号、字重、留白和语义结构建立，不使用展示字体或全大写标签增加噪声。

### Hierarchy

- **Headline**（400，28px，1.29）：页面一级标题，如“设置”和“索引库”。
- **Title**（400，22px，1.27）：主要区块标题和重要状态标题。
- **Body**（400，14px，1.43）：说明、命中片段和辅助信息；连续说明文字限制在约 65–75ch。
- **Label**（600，14px，1.43）：按钮、筛选组、导航选择与状态标签。

**The Read-First Rule.** 字体缩放到 200% 时允许布局重排，不允许截断关键操作、状态或命中说明。

## Elevation

系统采用轻量分层。默认界面主要依靠 Material 3 tonal surfaces、边界和留白表达深度；阴影只属于聚焦搜索、临时浮层、对话框和确实离开基础平面的交互状态。结果列表与设置区块不通过宽而软的装饰阴影堆叠成卡片墙。

**The Flat-at-Rest Rule.** 静止内容默认无装饰阴影；只有焦点、悬停或临时浮层可以短暂抬升。

**The One Separator Rule.** 同一元素使用边界或阴影表达层级，不同时叠加一像素边界与宽模糊阴影。

## Components

### Buttons

- **Shape:** 精炼的圆角矩形（12px），主要按钮最小高度 48px。
- **Primary:** 研究钴蓝背景、对比文本、水平 20px 与垂直 12px 内边距；标签使用动作加对象。
- **Hover / Focus:** 使用 Material 状态层与清晰焦点轮廓；减少动态效果启用时立即切换状态。
- **Secondary:** 轮廓按钮或 tonal button，不通过额外阴影与主按钮竞争。

### Chips

- **Style:** 12px 圆角，水平紧凑，使用低强调表面和结构边界。
- **State:** 选中态使用次级容器色与明确前景色；选中不能只靠颜色，保留语义和可见状态差异。

### Cards / Containers

- **Corner Style:** 沿用 Material 3 的克制圆角，主要内容容器不超过 12–16px。
- **Background:** 相邻语义表面形成轻量分层。
- **Shadow Strategy:** 默认无装饰阴影，遵循 Elevation 规则。
- **Border:** 只在需要区分边界或高对比度模式下使用。
- **Internal Padding:** 常规 16px，区块 20px，空状态 24px。

### Inputs / Fields

- **Style:** 填充式 Material 输入，12px 圆角，14px 垂直和 16px 水平内边距。
- **Focus:** 研究钴蓝双倍描边，搜索框作为页面主焦点可获得轻微表面抬升。
- **Error / Disabled:** 错误使用语义错误色与文字；禁用态仍需保持可读，不以过低透明度隐藏重要标签。

### Navigation

- **Style:** 宽屏使用可展开 NavigationRail，窄屏收为图标轨道；当前项使用 14px 圆角的 selected container。导航保持“搜索、索引库、设置”的任务顺序，搜索始终为默认入口。

### Search Results

- **Style:** 文件名、命中片段、来源位置与命中原因构成稳定阅读顺序。操作位于结果尾部，路径允许截断但必须可完整读取或复制。
- **Trust:** 不显示伪精确的相关度百分比。优先解释“命中了什么”和“来自哪里”。

## Do's and Don'ts

### Do:

- **Do** 让搜索输入在启动后的阅读顺序、焦点顺序和视觉层级中都处于首位。
- **Do** 使用 `surface` 与 `surfaceContainerLow` 的轻量差异形成工作区层次。
- **Do** 在结果中同时展示文件名、命中片段、来源位置和命中原因。
- **Do** 保持 48px 触控目标、可见焦点、屏幕阅读器语义和完整键盘路径。
- **Do** 在高对比度、200% 字号与减少动态效果下重新验证所有页面状态。

### Don't:

- **Don't** 做成完全单调的纯色界面；必须用克制的表面层次区分搜索、结果与次级工具。
- **Don't** 把产品塑造成需要用户理解技术基础设施的后台管理系统。
- **Don't** 以装饰或技术炫耀压过搜索任务。
- **Don't** 在首页堆叠数据库体积、模型状态、延迟、CPU 等开发者指标。
- **Don't** 使用嵌套卡片、大面积高饱和色、渐变文字、玻璃拟态或无意义动效。
- **Don't** 以单独的颜色、相似度百分比或技术术语作为结果可信度的唯一解释。
