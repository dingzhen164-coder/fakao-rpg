# 给 AI / 开发者的说明

这是一个本地运行的“法师成长记”法考训练网页（Python 标准库后端 + 原生 JS 前端），配合用户的 Obsidian 法考库使用。
它是行测修仙传 3.3.0 的完整复制改造版：固定西方玄幻风格（法师位阶、艾琳学姐），法考八科（民法、刑法、民诉、刑诉、行政法、商经知、三国法、理论法）。
代码里很多变量名、规则名、注释还是修仙说法（修为、境界、渡劫、灵根、功法、玉简……），界面上显示的是 themes.py 里“玄幻”那一套说法；
对照表见 DESIGN.md 第 0 节。

**开始改代码前先读 [DESIGN.md](DESIGN.md)**（背景、架构、数据结构、游戏规则都在里面）。

## 快速定位

| 想改的东西 | 去哪里 |
|---|---|
| 经验值、等级曲线、分批、复查间隔等数值 | 不用改代码：用户的 `训练/规则.md`；默认值在 `defaults/规则.md` + `rpg/config.py` 的 `DEFAULT_RULES`（两处同步） |
| 游戏规则逻辑（修为、境界、打卡、天道进度、每日功课） | `rpg/engine.py` |
| 训练流程（默写 / 费曼 / 错题 / 渡劫 / 炼丹…的对话步骤） | `rpg/trainer.py` |
| 发给 AI 的提示词、AI 返回的 JSON 字段、世界观设定 | `rpg/prompts.py`（字段名被 trainer.py 读取，改了要一起改） |
| AI 导师什么时候说话、说话依据的学员现状 | `rpg/tutor.py`、`engine.tutor_context()` |
| 风格说法（法师位阶名、天赋名、药剂名、世界观） | `rpg/themes.py` 的“玄幻”（前端通过 dashboard.theme.terms 取；固定玄幻，`DEFAULT_THEME`） |
| 境界、渡劫、灵根、丹药、闭关、顿悟、走火入魔、道心、周常、储物袋 | `rpg/engine.py`（文件顶部有总览） |
| 接口 | `rpg/api.py`（顶部有接口清单） |
| 页面、样式 | `web/app.js`、`web/style.css` |
| 🔮 天机简报（时政，行测底本带来的，法考版顶栏已收起） | `rpg/tianji.py`、`web/tianji.js`（代码保留，顶栏不显示） |
| 🖼 修炼战报（海报）、◎ 专注模式 | 数字 `rpg/poster.py`，画图 `web/poster.js`（canvas）；专注 `web/focus.js`（纯前端，`html.focus` 藏顶栏等） |
| 读各科资料（skill 或 10-科目 笔记文件夹）/ 模考复盘 | `rpg/vault.py`（只读；`skill_dir` 先找 skill，再找库里的笔记文件夹） |
| 听道（网课时间）：计入每日功行 | `engine.add_lecture / lecture_minutes / study_minutes`（`minutes()` = 修炼 + 听道）；首页卡片 `web/app.js lectureCard` |
| 背景 / 语录 / BGM | 后端 `rpg/appearance.py`（存档 state["appearance"]）；前端 `web/ambience.js`（自带背景是 SVG 现画；BGM 只播放 训练/外观/音乐/ 里的文件） |
| 题库、试炼塔（单选 / 多选 / 不定项） | `rpg/question_bank.py`（`### 题型`、`norm_answer`、`is_multi`）；作答按钮在 `rpg/trainer.py`（exam_pick 多选是勾选切换） |
| 📄 PDF 制卡（扫描版讲义 PDF → 知识点卡，全用代码） | `rpg/pdfcards.py`（算法）、`rpg/api.py cards_pdf_*`、`web/cards.js genScreen`；依赖 numpy / opencv，打包要装 |
| 真题导入（txt → 题库，待修、补答案、AI 补知识点） | `rpg/importer.py`（粉笔模考 PDF 拆分是行测专用） |
| 默认人设、台词 | `defaults/角色设定.md`、`defaults/台词库.md`、`defaults/台词库·玄幻.md`（首次运行时复制给用户；改结构要升“配置版本”，见 DESIGN.md） |

## 必须遵守

1. 只用 Python 标准库，兼容 Python 3.8；前端不引入构建工具和外部 CDN（离线也要能用）。
2. 只写库里的 `训练/` 文件夹；各科笔记、skill、复盘文件只读。不要把用户的教材、笔记、存档、API key 提交到仓库。
3. 经验和等级只由程序计算，AI 只做判断。
4. 用户可调的数值放 `规则.md`，不要写死在代码里。
5. 中文注释，风格和现有代码一致；新增模块在文件顶部写清楚“做什么、数据格式、谁调用它”。
6. 改完运行 `python -m unittest discover -s tests -v`；改了规则或数据结构，同步更新 DESIGN.md。
   测试：大部分老用例按行测底本配置跑（`tests/legacy_xingce.py`，守住引擎本身）；法考自己的配置在 `tests/test_fakao.py`。
7. 和行测修仙传能同时装在一台电脑 / 平板上：设置目录 `~/.fakao-rpg`、默认端口 8766、平板包名 `com.fakao.mage`、局域网识别 `"app": "fakao-rpg"`，不要改回行测的。
8. 改完界面在电脑（1280×860）和平板（800×1280）、亮色暗色各看一眼。
