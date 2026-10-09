# CLAUDE.md

先读 [AGENTS.md](AGENTS.md) 和 [DESIGN.md](DESIGN.md)。

法师成长记 = 行测修仙传 3.3.0（github.com/dingzhen164-coder/xingce-rpg）完整复制后改成的法考版：
固定西方玄幻风格（王立法学魔法学院、导师艾琳学姐），法考八科，引擎和行测版一致。两边以后各自开发，互不影响；
行测那边的好用改动可以照搬过来（照搬时注意板块名、风格、端口、设置目录这些法考版专有的地方，见 DESIGN.md 第 0 节）。

## 用户与目标

- 法考备考：2026-12-01 开始，每天 180 分钟，目标日暂定 2027-09-10（客观题），都在 规则.md 里改。
- 设备：Windows、M 系列 Mac、安卓平板（App）、iPad（浏览器）；Obsidian + 坚果云同步。
- AI 用用户自己的 DeepSeek key，按需调用；法条、构成要件必须严谨，拿不准要提示以现行法和教材为准。
- 全程中文；用户定产品方向，大功能先说方案再做。

## 版本号

改 rpg/version.py 时按这个规则（用户定的）：
- 第三位 z：小更新（修 bug、调界面、给已有功能加个按钮 / 选项）；
- 第二位 y：较大的更新（一个板块里加一个新功能）；
- 第一位 x：增加大板块（顶栏多一个新板块），或整体大改。
同时在 rpg/data/changelog.md 最上面加一节（tests/test_device.py 会检查）。
推到 main 且 rpg/version.py 变了，GitHub Actions 自动打包 exe / Mac / APK 发 Release。
