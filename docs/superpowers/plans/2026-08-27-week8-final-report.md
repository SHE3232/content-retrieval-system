# Week 8 Final Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-backed, illustrated Chinese final report of 10,000–12,000 Chinese characters (hard gate: at least 8,000正文 characters) plus a Week 8 weekly report, with final numbers, screenshots, diagrams, artifacts, and commit aligned to the frozen delivery candidate.

**Architecture:** Machine-readable evidence and `DELIVERY_MANIFEST.json` feed a deterministic document builder. Report prose is maintained as structured Python data close to the generator, figures are generated/reused from verified sources, and automated OOXML checks enforce text length, fonts, colors, white backgrounds, images, captions, and commit consistency. Microsoft Word exports the final DOCX to PDF, then every page is rendered to PNG for visual inspection.

**Tech Stack:** Python 3.10, python-docx, Pillow, matplotlib or project-provided drawing helpers, Microsoft Word COM, Poppler `pdftoppm`, pytest, OOXML/ZIP inspection, SHA-256.

---

### Task 1: Build the final evidence snapshot before writing prose

**Files:**
- Create: `tools/week8/build_report_evidence.py`
- Create: `tools/week8/tests/test_report_evidence.py`
- Create: `docs/week8/evidence/report/final-report-evidence.json`
- Create: `docs/week8/evidence/report/evidence-map.md`

- [ ] **Step 1: Add failing evidence-consistency tests**

Require the frozen commit; Weeks 1–8 artifact inventory; test suites and counts; parser/retrieval/indexing facts from code; benchmark values from existing JSON; platform and release status; accessibility evidence; compliance inventory; artifact hashes; screenshot paths/hashes; and explicit unknown/blocked states. Reject duplicate metrics with different values.

- [ ] **Step 2: Implement the evidence builder**

Read Git metadata, Week 3/5/6 machine evidence, compliance reports, final delivery manifest, and verified file hashes. Extract facts only from parseable inputs; do not infer PASS from filenames or narrative text.

- [ ] **Step 3: Generate the evidence map**

Map each planned chapter/table/figure to exact JSON keys and source paths. The report body will not display citations, but the map remains auditable in the engineering tree.

- [ ] **Step 4: Verify and commit**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week8/tests/test_report_evidence.py -q
git add -- tools/week8/build_report_evidence.py tools/week8/tests/test_report_evidence.py docs/week8/evidence/report
git commit -m "docs: freeze final report evidence"
```

### Task 2: Generate the report figures from verified sources

**Files:**
- Create: `tools/week8/build_report_figures.py`
- Create: `tools/week8/tests/test_report_figures.py`
- Create: `docs/week8/reports/assets/01_总体架构.png`
- Create: `docs/week8/reports/assets/02_文件摄取时序.png`
- Create: `docs/week8/reports/assets/03_混合检索链路.png`
- Create: `docs/week8/reports/assets/04_八周成果时间线.png`
- Create: `docs/week8/reports/assets/05_三类发行关系.png`
- Create: `docs/week8/reports/assets/06_测试结果汇总.png`
- Create: `docs/week8/reports/assets/07_性能对比.png`
- Create: `docs/week8/reports/assets/08_最终交付结构.png`
- Copy: verified UI/five-format screenshots from `docs/week5/evidence/attachments/` into `docs/week8/reports/assets/screenshots/`

- [ ] **Step 1: Add image-quality tests**

Require PNG, at least 1600 px width for diagrams, white corner/background pixels, black/dark text and strokes, no alpha transparency, descriptive filename, source commit in metadata/sidecar, and exact numeric labels matching final evidence.

- [ ] **Step 2: Generate eight diagrams/charts**

Use white backgrounds, black text/lines, restrained gray fills, no gradients, and legible Chinese/English fonts. The performance chart must use only available benchmark values; if final candidate benchmark is unavailable, show the verified historical baseline and label it by source commit rather than inventing a final value.

- [ ] **Step 3: Curate screenshots**

Use Windows search, filter, library, settings/high-contrast/large-text, keyboard, Linux smoke, and five-format screenshots only where the final UI remains visually identical. Re-capture any screen changed by Week 8 source work. Record original and copied SHA-256 in the evidence snapshot.

- [ ] **Step 4: Run image tests and visually inspect a contact sheet**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week8/tests/test_report_figures.py -q
```

- [ ] **Step 5: Commit figures**

```powershell
git add -- tools/week8/build_report_figures.py tools/week8/tests/test_report_figures.py docs/week8/reports/assets
git commit -m "docs: add final report figures"
```

### Task 3: Implement deterministic DOCX generation and style gates

**Files:**
- Create: `tools/week8/build_final_reports.py`
- Create: `tools/week8/tests/test_build_final_reports.py`
- Create: `docs/week8/reports/项目结项报告.docx`
- Create: `docs/week8/reports/第八周工作周报.docx`

- [ ] **Step 1: Add failing document tests**

The final-report test must require at least 8,000 Chinese characters in正文 excluding cover, TOC labels, headers/footers, captions, tables, and appendices; target 10,000–12,000. Require all specified chapters, at least 12 embedded images, numbered captions, at least 8 tables, the full final commit, platform statuses matching the manifest, and no `TBD`/`TODO`/占位符.

Style tests must inspect OOXML for Times New Roman in all styles/runs including East Asian fonts, black text, black table borders, white/no-fill page and cells, A4 page size, consistent margins, page numbers, repeated table headers, non-splitting rows, keep-with-next headings/captions, and no external image links.

- [ ] **Step 2: Implement common document primitives**

Create functions for section geometry, style normalization, paragraph/run formatting, table geometry, white cells/black borders, captions, image insertion, page fields, cover, metadata table, table of contents field, evidence-bound metrics, and safe output-directory checks. Use source commit and generation time from the evidence JSON.

- [ ] **Step 3: Write the final report content**

Use these exact top-level chapters:

1. 项目背景与目标
2. 需求分析与验收口径
3. 总体架构与技术选型
4. 八周实施过程与阶段成果
5. 文件解析与统一内容模型
6. 多模态嵌入与模型工程
7. 向量存储、索引一致性与生命周期
8. 关键词、语义与混合检索
9. Flutter 客户端与交互设计
10. 无障碍设计与验证
11. 系统集成、性能与稳定性
12. 本地数据安全、隐私与开源合规
13. 测试体系、指标与最终验收
14. 关键问题、解决过程与工程反思
15. 最终交付、局限与后续规划

The eight-week section must describe each week’s goal, implementation, artifact, verification, and effect on the next week. Technical chapters must explain parser registry/Tika, chunking, Sentence Transformers/MobileCLIP, manifest/hash verification, Chroma identity and mutation semantics, BM25/vector retrieval/weighted RRF, FastAPI lifecycle, Flutter state/API layers, keyboard/semantics/high contrast/text scale/reduced motion, launchers, packaging, offline recovery, security boundary, compliance inventory, and dual-track distribution.

- [ ] **Step 4: Write the Week 8 weekly report**

Cover planned items, completed local items, test/build counts, clean-engineering decisions, release/manifest results, report/video/portfolio status, external macOS/GitHub gates, risks, and exact next actions. Never call a blocked gate completed.

- [ ] **Step 5: Generate and run structural tests**

```powershell
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' tools/week8/build_final_reports.py --evidence docs/week8/evidence/report/final-report-evidence.json --assets docs/week8/reports/assets --output docs/week8/reports
& 'F:\contentretrivalsystem\backend\.venv\Scripts\python.exe' -m pytest tools/week8/tests/test_build_final_reports.py -q
```

- [ ] **Step 6: Commit generator, tests, and DOCX files**

```powershell
git add -- tools/week8/build_final_reports.py tools/week8/tests/test_build_final_reports.py docs/week8/reports/项目结项报告.docx docs/week8/reports/第八周工作周报.docx
git commit -m "docs: generate Week 8 final reports"
```

### Task 4: Perform Microsoft Word/PDF/PNG visual verification

**Files:**
- Create after execution: `docs/week8/evidence/report/word-validation.json`
- Create after execution: `docs/week8/evidence/report/rendered-final-report/`
- Create after execution: `docs/week8/evidence/report/rendered-week8-report/`
- Modify if required: `tools/week8/build_final_reports.py`

- [ ] **Step 1: Open each DOCX read-only in Microsoft Word**

Use Word COM with alerts disabled and read-only open. Update fields and TOC, repaginate, save the final DOCX, then export PDF. Record Word version, page count, and export exit status.

- [ ] **Step 2: Render every PDF page to PNG**

Use `pdftoppm -png -r 150`. Verify rendered page count equals Word/PDF page count and create a numbered contact sheet without omitting pages.

- [ ] **Step 3: Inspect every page**

Check cover, TOC, headings, Chinese/English glyphs, captions, image sharpness, table overflow, row splits, blank pages, widows/orphans, headers/footers, page numbers, black-only text/lines, white backgrounds, and final appendix/hash readability. Record every issue by document/page and fix the generator, never hand-edit only the output DOCX.

- [ ] **Step 4: Rebuild and repeat until zero visual defects**

After any generator change, rebuild both DOCX files, rerun structural tests, Word export, full-page render, and full inspection. `word-validation.json` may say PASS only with zero open issues.

- [ ] **Step 5: Commit final verified documents and compact visual evidence**

Commit the two DOCX files, generator changes, validation JSON, and contact sheets. Keep individual high-volume page renders out of the public source ZIP but retain them in the Week 8 evidence delivery directory.

### Task 5: Cross-check report, portfolio, video, and artifacts

**Files:**
- Create: `tools/week8/validate_cross_deliverables.py`
- Create: `tools/week8/tests/test_cross_deliverables.py`
- Create: `docs/week8/evidence/final-cross-check.json`

- [ ] **Step 1: Add failing cross-deliverable tests**

Extract text/metadata from DOCX, portfolio Markdown, release notes, demo/video JSON, `SOURCE_VERSION.txt`, archives, and `DELIVERY_MANIFEST.json`. Require one identical full commit; identical test counts/platform statuses; matching artifact names/sizes/hashes; matching public/research license language; and no claim that a blocked external gate passed.

- [ ] **Step 2: Implement and run the validator**

The validator returns non-zero for any mismatch and lists the exact file/key/value pair. It must not silently normalize contradictory facts.

- [ ] **Step 3: Copy verified reports into final delivery**

Copy `项目结项报告.docx`, `第八周工作周报.docx`, their PDFs, and the validation summary to `output/week8/第八周最终交付/06_结项文档/`, then regenerate top-level hashes and manifest.

- [ ] **Step 4: Commit the validator and evidence**

```powershell
git add -- tools/week8/validate_cross_deliverables.py tools/week8/tests/test_cross_deliverables.py docs/week8/evidence/final-cross-check.json
git commit -m "test: cross-check Week 8 final deliverables"
```

### Task 6: Final report acceptance gate

**Files:**
- Read: `docs/week8/reports/项目结项报告.docx`
- Read: `docs/week8/reports/第八周工作周报.docx`
- Read: `docs/week8/evidence/report/word-validation.json`
- Read: `docs/week8/evidence/final-cross-check.json`

- [ ] **Step 1: Run fresh structural, visual, and cross-deliverable checks**

All commands must run after the final candidate commit and final artifact rebuild. Quote exact character count, image count, table count, page count, source commit, and validator results from the fresh outputs.

- [ ] **Step 2: Verify final hashes after copy**

Recompute SHA-256 for both DOCX/PDF files in source and final delivery, require byte-for-byte equality, and update `DELIVERY_MANIFEST.json` and `SHA256SUMS.txt` once.

- [ ] **Step 3: Preserve honest blocked statuses**

If macOS, GitHub publication, or real video is still blocked, the report and Week 8 weekly report must state that exact status. The documents can be structurally final, but the overall Week 8 goal remains incomplete.

- [ ] **Step 4: Mark the report accepted only after every report-specific gate passes**

Acceptance requires >=8,000正文 Chinese characters, all required chapters, all figures/tables, Times New Roman/black/white style, Word/PDF/PNG inspection with zero open issues, final-candidate fact consistency, and final-delivery hash equality.

