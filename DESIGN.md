# 法官成长记设计说明

本项目是自用法考学习程序，Python标准库后端与原生JS前端，Windows与M系列Mac运行本机服务器，安卓和iPad通过局域网访问。目标是把考点资料、体系回忆、卡片、客观题与主观题表达连在一起。用户已确认1.0.0设计并授权开始开发。

## 文件与架构

server.py提供HTTP与本机/局域网鉴权；rpg/service.py处理学习业务；storage.py保存存档；materials.py只读扫描与OCR结构整理；fsrs.py复用参考项目的记忆数学函数；ai.py集中提示词与缓存；web/app.js提供页面。安装包仅在CI用PyInstaller构建，无Python运行依赖。

## 存储边界

原资料只读，读取10-科目、20-错题、30-案例、40-法条与年度变动、50-复习管理、60-真题库、99-讲义PDF、99-知识点库。用户数据只写训练/，拒绝目录穿越和软链接。路径与key保存在~/.fakao-rpg/settings.json；教学资料不进公开仓库。

训练/资料整理/包含整理稿与原文快照，训练/卡片/保存可在Obsidian查看的问答，训练/笔记/保存文字，训练/AI结果/保存处理结果，训练/存档/存档.json保存所有状态。先写临时文件fsync再replace。每天首次写入前备份旧存档，保留30天。坚果云不提供分布式锁，界面提醒勿同时运行两台电脑，退出并完成同步后切换。

## schema_version 1

- config: start_date、target_date、subjective_date、daily_minutes、new_per_day、reviews_per_day。
- materials: source稳定摘要ID→{original,cleaned,meta,subject,title,chapter,teacher,edition,fingerprint,status:draft或verified,warnings,pages,question_draft,practice,history}。同来源更新稳定ID，旧整理稿记录版本；题目草稿不自动入库。
- cards: 随机ID→{front,back,subject,material_id,source_version,reps,due,s,d,last}。due为UNIX秒；调度数学为参考项目FSRS-5，首版复习评分四档，重来1分钟后重学；其他分档按默认90%保留率排期，不声称完整兼容Anki的学习步进或参数训练。每日上限可调；同日同卡奖励最多一次。
- questions: 随机ID→{stem,options,answer数组,type:single/multiple/indefinite,subject,point,explanation,source}。答案精确集合匹配；首版不采用特殊部分得分规则，不宣称正式整卷计分。questions读取与作答前响应不含答案、解析。
- attempts: {qid,question完整快照,answer,correct,repeat,date,request_id,assessment:program}。原题修改后历史快照不变，重复request_id幂等，首次与复练分开。
- exams: {material,questions:[{prompt,reference,points:[{id,text,score}]}],answers,started,minutes,mode,submitted,revision,strokes,assessment,grading}。交卷前移除reference和points；模拟机考服务端截止校验，日常练习不强制截止；逐次版本号防旧页面覆盖；交卷不可修改。没有可信采分点不评分。
- notes: {title,text,strokes,revision}。笔迹每点为0～1归一化坐标；笔与鼠标写字，触摸滚动；增量绘制当前笔，保存与写字重叠时继续保存新内容。
- activity: 日期→有效秒；可见且最近操作的学习页心跳计时，上限30秒，同主机多标签不重复累计；属于行为校验，不是考试防作弊系统。
- events、xp: 奖励幂等。成长是游戏反馈，不换算考试预测分数。五级至一级法官助理，再初任/资深/高级法官、大法官、首席大法官；高级阶段需要跨科题目表现与主观题AI参考评分，未AI评分不冒充能力认证。具体名称是游戏等级，不对应正式人事职级。

## OCR与AI

元信息可直接读取；本地整理标题、空行、明确选项与页码。多栏图表无法可靠恢复时警告、保留原文，不推断法律规则。用户核对后确认verified，允许体系训练和制卡。AI整理输出草稿，仍需人工核对。多老师材料不自动合并；来源版本独立。

AI只做主动触发的整理、制卡、答疑、采分点判定。缓存key含API地址、模型、提示词版本、任务和完整payload摘要。调用输出JSON；截断拒收；采分点要求唯一齐全、hit布尔、命中证据必须在作答原文中；程序累计score。离线或无key仍可学习、自评、作答并保存，联网后手动补评。首版串行存档锁保证一致性，长AI调用时其他写操作会等待；未来可改为快照+版本校验异步任务。

## 界面和发布

深蓝与金色、浅色深色，直观中文导航。桌面1280×860、平板800×1280各两种主题真实Chrome截图；客观题真实点击、机考保存恢复与笔/手指分别验证。当前容器无Chrome，CI利用runner已有Chrome+Node标准库CDP，避免本机新增依赖。CI全部测试和三平台包成功后才发布完整Release。安卓自用调试签名存在CI cache，cache丢失需卸载重装；电脑保留学习数据。Mac采用临时签名，无Apple开发者公证。

## 首版边界

支持单篇导入和已核对题目人工录入，主观题试卷以JSON输入问题与采分点。没有预装法考题库，未把用户教材打包。PDF原资料可扫描，但自动提取和OCR另行讨论依赖；首版体系按科目章节考点列表与主动回忆呈现，图形导图编辑、整卷客观机考、正式电子法条查阅和程序内自动替换更新尚待后续迭代。更新使用Release下载后替换程序，训练数据独立。
