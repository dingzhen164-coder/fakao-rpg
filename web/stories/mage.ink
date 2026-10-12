// 原创剧情，生成自rpg/data/narrative.json；修改该源后重新编译。
VAR learned = false
VAR tower = false
VAR boss = false
-> END
=== prologue_start ===
学院钟楼敲响。艾琳学姐站在法典长廊，朝你挥了挥手。
欢迎来到王立法学魔法学院，小法师。法典的力量来自理解与论证。你想先了解什么？
+ [我想先梳理方法] # choice:understand
  -> prologue_understand
+ [我想先试着作答] # choice:practice
  -> prologue_practice
+ {learned} [聊聊已有的学习记录] # choice:recorded
  -> prologue_recorded
=== prologue_understand ===
艾琳翻开法典：“先理清构成要件、例外与法律效果。咒文书馆保留八科资料，冒险大厅仍按原课程安排训练。”
+ [记下这个方向] # choice:continue
  -> prologue_end
=== prologue_practice ===
艾琳合拢法典：“已核验题按原规则判分；未核验卷轴只留练习记录，不当成标准答案。遇到疑点，先核对教材与法源。”
+ [带着问题去练习] # choice:continue
  -> prologue_end
=== prologue_recorded ===
你的学习记录已经留在法典中。先弄清规则与适用条件，再用题目检验自己的理解。
+ [继续前行] # choice:continue
  -> prologue_end
=== prologue_end ===
学院的灯火亮起。艾琳为你留下一页书签：“准备好了，就从眼前的一门课程开始。”学院纪事可以随时重读。
-> END
=== study_echo_start ===
你的学习记录已经留在法典中。先弄清规则与适用条件，再用题目检验自己的理解。
这段对话因已有学习记录开放；阅读与选项不会改变成绩或学习时长。
+ [我想先梳理方法] # choice:understand
  -> study_echo_understand
+ [我想先试着作答] # choice:practice
  -> study_echo_practice
+ {learned} [聊聊已有的学习记录] # choice:recorded
  -> study_echo_recorded
=== study_echo_understand ===
艾琳翻开法典：“先理清构成要件、例外与法律效果。咒文书馆保留八科资料，冒险大厅仍按原课程安排训练。”
+ [记下这个方向] # choice:continue
  -> study_echo_end
=== study_echo_practice ===
艾琳合拢法典：“已核验题按原规则判分；未核验卷轴只留练习记录，不当成标准答案。遇到疑点，先核对教材与法源。”
+ [带着问题去练习] # choice:continue
  -> study_echo_end
=== study_echo_recorded ===
你的学习记录已经留在法典中。先弄清规则与适用条件，再用题目检验自己的理解。
+ [继续前行] # choice:continue
  -> study_echo_end
=== study_echo_end ===
学院的灯火亮起。艾琳为你留下一页书签：“准备好了，就从眼前的一门课程开始。”学院纪事可以随时重读。
-> END
=== peer_method_start ===
法典页边还空着。你想先画出规则脉络，还是用一个问题检验边界？
这是内置同伴对话，选择只影响后续台词与纪念；正式学习仍使用原功能。
+ [先梳理与回忆] # choice:method
  -> peer_method_method
+ [先独立练习] # choice:practice
  -> peer_method_practice
=== peer_method_method ===
莉娅留下几条空白索引：“按要件、例外、效果分开整理；不确定的内容留待核对。”
+ [记下这个方向] # choice:continue
  -> peer_method_end
=== peer_method_practice ===
莉娅递来一页练习纸：“先独立作答，再核对可靠答案与法源。”
+ [带着问题去学习] # choice:continue
  -> peer_method_end
=== peer_method_end ===
这次交谈已经记下。学习入口随时开放；交付首段真实学习成果后，已读支线可留下同伴纪念。
-> END
=== peer_review_start ===
学过的内容还值得回看。你想温习一张符文，还是复练一道题？
这是内置同伴对话，选择只影响后续台词与纪念；正式学习仍使用原功能。
+ [先梳理与回忆] # choice:method
  -> peer_review_method
+ [先独立练习] # choice:practice
  -> peer_review_practice
=== peer_review_method ===
诺亚在灯下留出一张空白书签：“先说出答案，再翻看背面，按真实表现评分。”
+ [记下这个方向] # choice:continue
  -> peer_review_end
=== peer_review_practice ===
诺亚指向试炼塔：“复练保留原规则，弄清判断依据比多点一次领奖更有用。”
+ [带着问题去学习] # choice:continue
  -> peer_review_end
=== peer_review_end ===
这次交谈已经记下。学习入口随时开放；交付首段真实学习成果后，已读支线可留下同伴纪念。
-> END
