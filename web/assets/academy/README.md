# 法考魔法学院正式场景

学院总览有四季 × 白天/黄昏/黑夜 12 种状态，横屏 3840×2880、竖屏独立构图 2880×3840，各一套共 24 张。春季白天沿用 `scene/academy-day-4k.webp` 与 `scene/academy-portrait-4k.webp`；其余按 `scene/academy-<季节>-<时段>[-portrait]-4k.webp` 命名。八科楼内昼夜背景位于 `../beauty/page/train-<key>[-night].webp`，均为 3840×2880；`rooms/thumb-<key>.webp` 是白天正式图导出的 UI 预览。

| key | 科目 | 楼名 | 场景线索 |
| --- | --- | --- | --- |
| minfa | 民法 | 契约馆 | 花园、平等协商、日常契约与卷轴 |
| xingfa | 刑法 | 审判堡 | 红金审判空间、责任、公平与保护 |
| minsu | 民诉 | 衡序厅 | 浅蓝对称议事厅、调解与程序 |
| xingsu | 刑诉 | 真相塔 | 青蓝证据观察与研究空间 |
| xingzheng | 行政法 | 律令宫 | 公共服务、依法行政与权力约束 |
| shangjing | 商经知 | 创艺坊 | 商贸市场、企业与知识创造 |
| sanguo | 三国法 | 万国馆 | 地球仪、条约及国际交流，非历史三国 |
| lilun | 理论法 | 星穹馆 | 法理、宪法、法律思想与职业伦理 |

> 开发工具：`ACADEMY_ART_PAD=32` 让相邻分块重叠 64 像素并按该宽度羽化；默认每侧 16 像素仍兼容旧工作流。秋季极简新版仍在试绘，现有正式图片及其 provenance 未更换。

每个季节的横竖屏白天母版先分别绘制原生 1024×1536 分块，再用 `tools/academy_art_pack.cjs` 校准低频色调并在 16 像素重叠区合成；低分辨率构图参考未放大充当成品。黄昏、夜晚由 `tools/academy_relight.cjs` 从相应原生 4K 母版合成，生成参考只影响大尺度光色，建筑和笔触的细节来自原生母版。八科夜景同样从各自原生 4K 楼内母版合成。`provenance.json` 列出每块原始尺寸和 SHA-256、光照参考用途及各成品的尺寸与 SHA-256。原始块与参考保存在本轮工作区 `/workspace/generated_images/fakao-4k-source`；运行与分发只需本仓内正式 WebP。

画面本身不含建筑名或点击热区。横屏和竖屏入口都由 `scene_portal.js` 的真实按钮及 `app.js` 坐标绘制；用户原有地点坐标和自定义名称继续有效。楼内文字由阅读卡片承载，保留原卡片、导图与试炼数据。八科正式图已登记在 `beauty/builtin-art.json`，网页加载和「导出程序自带美术」使用同一版本；用户自己的同名美术仍优先。

## 既有学院素材

| 文件 | 用途 |
|---|---|
| portrait/mg-eileen-calm/cheer/explain/concern/proud.webp | 艾琳学姐半身立绘：平静、鼓励、讲解、关切、得意（对话框用，3.4） |
| portrait/mg-eileen-blink.webp | 眼部眨眼叠层（只含眼睛区域，边缘羽化；位置比例写在rpg/themes.py） |
| scene/mg-academy-day.webp | 既有学院全景·白天 |
| scene/mg-academy-night.webp | 既有学院全景·夜晚 |

既有素材由用户于2026-10-15在对话中提供，使用Gemini生成（按《图片需求清单-3.4第一批.md》的提示词）。立绘：纯绿色背景经色键去底、缩放至900×1200；既有全景：1672×941，仅转WebP，不重绘；原PNG不分发。使用与分发的授权以所用生成服务的条款为准，由用户确认。新学院总览只替换页面引用，原文件保留供旧设置与回退使用。
