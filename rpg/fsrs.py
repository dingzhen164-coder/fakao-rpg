"""记忆调度纯计算，复用 xingce-rpg 的 FSRS-5 数学函数；参数含义与测试见 DESIGN.md。"""
import math
W = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925,
     1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621]
DECAY, FACTOR = -0.5, 19 / 81


def _clamp_d(d):
    return min(10.0, max(1.0, d))


def init_s(g):
    return max(W[g - 1], 0.1)


def init_d(g):
    return _clamp_d(W[4] - math.exp(W[5] * (g - 1)) + 1)


def next_d(d, g):
    d2 = d - W[6] * (g - 3) * (10 - d) / 9
    return _clamp_d(W[7] * init_d(4) + (1 - W[7]) * d2)


def retrievability(elapsed, s):
    return (1 + FACTOR * max(0.0, elapsed) / s) ** DECAY


def recall_s(d, s, r, g):
    hard = W[15] if g == 2 else 1.0
    easy = W[16] if g == 4 else 1.0
    return s * (math.exp(W[8]) * (11 - d) * s ** (-W[9]) * (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1)


def forget_s(d, s, r):
    f = W[11] * d ** (-W[12]) * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
    return min(f, s / math.exp(W[17] * W[18]))


def short_s(s, g):
    return s * math.exp(W[17] * (g - 3 + W[18]))


def interval(s, retention, max_ivl):
    ivl = s / FACTOR * (retention ** (1 / DECAY) - 1)
    return int(min(max(1, round(ivl)), max_ivl))


# ================================================================ 时间
