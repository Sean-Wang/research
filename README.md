# 研究书架

所有报告统一保存在 `reports/分类/`，根目录不再存放 HTML。

```text
.github/workflows/       自动发布
config/                  书架目录配置
reports/                 所有报告与附件
  财报解读/
  公司研究/
  人物访谈/
  行业专题/
  生活与训练/
scripts/                 目录生成程序
templates/index.html     首页设计模板
README.md
```

以后打开 reports 中的对应分类，上传报告并提交到 main，GitHub Actions 自动生成书架与发布。
报告标题读取 HTML 的 title，日期读取文件名中的 YYYYMMDD，分类读取分类文件夹。
如需自定义，可在 head 内使用 report-title、report-date、report-category、description、report-cover、report-tags 元信息。
现有报告的精简标题等配置位于 config/catalog-overrides.json，新报告无需手动登记。

修改书架外观请编辑 templates/index.html；线上 index.html 仅在发布时生成到 _site，不提交生成结果。
报告附属资源放在报告所在文件夹中并保持相对路径。仅将准备公开的报告与资源放进 reports。

本次统一分类会改变原有报告地址；从书架重新打开即可。以前的直链、收藏与最近阅读记录不会自动迁移。
