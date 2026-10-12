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
