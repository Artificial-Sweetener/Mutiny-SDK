# Mutiny 文档

Mutiny 面向的是那些正经使用 Midjourney、并且想做出比“打开 Discord 然后碰运气”更靠谱方案的构建者。

Mutiny 只有一个公共客户端、一个配置表面、一个实时事件故事，以及一小组恢复辅助方法，用来处理用户带着已保存输出产物回来时的场景。

> **重要提示：** 在集成 Mutiny 之前，请先阅读 [重要免责声明](../README.zh-CN.md#重要免责声明)。Mutiny 需要真实的 Discord 用户 token 和付费 Midjourney 账号，使用它也可能伴随账号风险。

这套文档按工作类型拆分：

- onboarding 页面，带你从零走到可工作的集成
- 面向高级和恢复密集型流程的工作流指南
- 面向精确表面的参考页

## 从这里开始

- [快速开始](getting-started.md)：最小可用集成，包括启动、事件消费和一次真实提交。
- [配置](configuration.md)：Mutiny 配置项的实用指南，以及什么时候该动哪些设置。
- [门面与生命周期](facade-and-lifecycle.md)：公共客户端模型、生命周期行为、观察辅助方法和恢复辅助方法。

## 如果你想尽快上线

按这个顺序读：

1. [快速开始](getting-started.md)
2. [配置](configuration.md)
3. [任务操作](job-actions.md)
4. [事件](events.md)

这条路径会带你从“我有一个令牌和一个频道”走到“我的应用能提交任务、保持同步，并且暴露后续操作控制，而不是对用户胡说八道”。

## 如果你需要精确的旋钮

- [配置参考](configuration-reference.md)：每个配置分区、默认值、辅助方法和 env 映射字段。
- [API 参考](api-reference.md)：精确的根级导入、门面方法和公共模型。

## 如果你在意已保存输出产物和视频

- [视频与产物工作流](video-and-artifact-workflows.md)：图像/视频解析辅助方法、分块重建、`animate` 路由选择和 `extend` 语义。
- [任务操作](job-actions.md)：操作规则、索引要求和后续操作矩阵。

## 如果你正在排查奇怪问题

- [事件](events.md)：事件流契约、消费建议和公共模型形状。
- [故障排查](troubleshooting.md)：常见故障模式、响应转储、宿主应用的陈旧假设，以及先从哪里查。
- [配置](configuration.md)：尤其是 `websocket.capture_enabled` 和 `cache.response_dump_dir` 相关部分。

## 页面地图

- [快速开始](getting-started.md)：你的第一次有用集成。
- [配置](configuration.md)：哪些设置重要，以及为什么。
- [配置参考](configuration-reference.md)：精确字段、默认值和辅助方法行为。
- [门面与生命周期](facade-and-lifecycle.md)：公共客户端的形状。
- [任务操作](job-actions.md)：你能发什么，以及每种操作需要什么上下文。
- [事件](events.md)：事件流里会出现什么，以及如何理性消费。
- [视频与产物工作流](video-and-artifact-workflows.md)：恢复、分块重建，以及 animate/extend 行为。
- [故障排查](troubleshooting.md)：症状 -> 原因 -> 修复。
- [API 参考](api-reference.md)：紧凑版公共表面索引。
