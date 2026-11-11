#!/usr/bin/env python3
"""从 reports 生成报告目录与 GitHub Pages 发布文件。仅使用标准库。"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

CATEGORIES = {"财报解读", "公司研究", "人物访谈", "行业专题", "生活与训练", "未分类"}


class ReportMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.in_title = False
        self.title_parts = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self.in_head = True
        elif tag == "title" and self.in_head:
            self.in_title = True
        elif tag == "meta" and self.in_head:
            key = attrs.get("name", "").lower()
            if key:
                self.meta[key] = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "head":
            self.in_head = self.in_title = False

    def handle_data(self, text):
        if self.in_title:
            self.title_parts.append(text)

    @property
    def title(self):
        return " ".join("".join(self.title_parts).split())


def report_date(metadata, relative_path):
    explicit = metadata.meta.get("report-date", "").strip()
    if explicit:
        return date.fromisoformat(explicit).isoformat()
    match = re.search(r"(?<!\d)(20\d{2})[-.]?(\d{2})[-.]?(\d{2})(?!\d)", relative_path)
    if match:
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    return ""


def read_report(path, root, overrides):
    relative = path.relative_to(root).as_posix()
    metadata = ReportMetadata()
    metadata.feed(path.read_text(encoding="utf-8-sig"))
    settings = overrides.get(relative, {})
    # 分类以明确元信息、分类文件夹、人工目录为顺序；无明确分类则展示为未分类。
    category = metadata.meta.get("report-category", "").strip()
    if not category:
        category = next((part for part in path.relative_to(root).parts[:-1] if part in CATEGORIES), "")
    category = category or settings.get("category", "未分类")
    if category not in CATEGORIES:
        raise ValueError(f"报告分类不在允许列表中：{relative}（{category}）")
    title = metadata.meta.get("report-title", "").strip() or settings.get("title") or metadata.title or path.stem
    description = metadata.meta.get("description", "").strip() or settings.get("description") or f"{category} · 打开阅读完整报告。"
    cover = metadata.meta.get("report-cover", "").strip() or settings.get("cover") or "RESEARCH"
    tag = metadata.meta.get("report-tags", "").strip() or settings.get("tag") or category
    return {"path": relative, "title": title, "originalTitle": metadata.title,
            "description": description, "category": category, "cover": cover,
            "tag": tag, "date": report_date(metadata, relative)}


def copy_public(source, destination):
    """保留报告和资源的相对路径，不发布工作流、模板、配置或隐藏文件。"""
    for entry in source.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            raise ValueError(f"发布目录不接受符号链接：{entry.name}")
        target = destination / entry.name
        if entry.is_dir():
            target.mkdir()
            copy_public(entry, target)
        elif entry.is_file():
            shutil.copy2(entry, target)


def build(root, output):
    root, output = root.resolve(), output.resolve()
    # 防止输出清理误删输入资料；输出必须是仓库内的专用 _site 目录。
    if output != root / "_site":
        raise ValueError("发布输出必须使用报告仓库内的 _site 目录")
    overrides_path = root / "config/catalog-overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    if not isinstance(overrides, dict):
        raise ValueError("人工目录配置必须是对象")
    if any(path.is_file() and path.suffix.lower() in {".html", ".htm"} for path in root.iterdir()):
        raise ValueError("请将根目录中的网页移入 reports 对应分类；首页请编辑 templates/index.html")
    paths = []
    report_root = root / "reports"
    if report_root.exists():
        paths += [path for path in report_root.rglob("*") if path.is_file() and path.suffix.lower() in {".html", ".htm"} and not any(part.startswith(".") for part in path.relative_to(report_root).parts)]
    paths = sorted(paths, key=lambda path: path.relative_to(root).as_posix())
    reports = [read_report(path, root, overrides) for path in paths]
    reports.sort(key=lambda report: report["date"], reverse=True)
    template = (root / "templates/index.html").read_text(encoding="utf-8")
    if template.count("__REPORT_CATALOG__") != 1 or template.count("__BUILD_DATE__") != 1:
        raise ValueError("首页模板缺少或重复了目录占位符")
    payload = json.dumps(reports, ensure_ascii=False, indent=2).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    updated = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y.%m.%d")
    homepage = template.replace("__REPORT_CATALOG__", payload).replace("__BUILD_DATE__", updated)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    if report_root.exists():
        (output / "reports").mkdir()
        copy_public(report_root, output / "reports")
    (output / "index.html").write_text(homepage, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    for report in reports:
        if not (output / report["path"]).is_file():
            raise ValueError(f"报告没有进入发布目录：{report['path']}")
    print(f"目录生成完成：共 {len(reports)} 份报告。")
    for category in sorted(CATEGORIES):
        count = sum(report["category"] == category for report in reports)
        if count:
            print(f"分类统计：{category}，{count} 份。")
    print("发布文件已生成，原始报告未被修改。")
    return reports


def main():
    parser = argparse.ArgumentParser(description="生成研究书架目录", add_help=False)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        build(args.root, args.root / "_site")
    except Exception as error:
        print(f"目录生成失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
