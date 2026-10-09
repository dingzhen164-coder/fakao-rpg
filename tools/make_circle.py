# 生成背景法阵 web/art/circle-dark.svg、circle-light.svg：python tools/make_circle.py web/art
import math, urllib.parse, sys
def circle(c):
    pts=lambda r,off: " ".join(f"{200+r*math.cos(math.radians(a+off)):.1f},{200+r*math.sin(math.radians(a+off)):.1f}" for a in (0,120,240))
    ticks="".join(f'<line x1="{200+178*math.cos(math.radians(a)):.1f}" y1="{200+178*math.sin(math.radians(a)):.1f}" x2="{200+(170 if a%30==0 else 174)*math.cos(math.radians(a)):.1f}" y2="{200+(170 if a%30==0 else 174)*math.sin(math.radians(a)):.1f}"/>' for a in range(0,360,6))
    nodes="".join(f'<circle cx="{200+150*math.cos(math.radians(a-90)):.1f}" cy="{200+150*math.sin(math.radians(a-90)):.1f}" r="9"/>' for a in range(0,360,60))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" fill="none" stroke="{c}" stroke-width="1.2">
<defs><path id="t" d="M200,200 m-160,0 a160,160 0 1,1 320,0 a160,160 0 1,1 -320,0"/></defs>
<circle cx="200" cy="200" r="190"/><circle cx="200" cy="200" r="182" stroke-width=".6"/>{ticks}
<circle cx="200" cy="200" r="150"/><circle cx="200" cy="200" r="170" stroke-width=".5"/>
<text font-family="Georgia,serif" font-size="13" letter-spacing="6" fill="{c}" stroke="none"><textPath href="#t">FIAT IUSTITIA RUAT CAELUM ✦ LEX ✦ IUS ✦ AEQUITAS ✦ VERITAS ✦</textPath></text>
<polygon points="{pts(150,-90)}"/><polygon points="{pts(150,90)}"/>{nodes}
<circle cx="200" cy="200" r="76"/><circle cx="200" cy="200" r="70" stroke-width=".5" stroke-dasharray="2 4"/>
<polygon points="{pts(70,-90)}" stroke-width=".7"/><polygon points="{pts(70,90)}" stroke-width=".7"/><circle cx="200" cy="200" r="22"/>
<path d="M200 178 L204 196 L222 200 L204 204 L200 222 L196 204 L178 200 L196 196Z" fill="{c}" stroke="none"/></svg>'''
for c,n in (("#e0b354","dark"),("#7a4f12","light")):
    open(sys.argv[1]+f"/circle-{n}.svg","w").write(circle(c))
    print(n, len(urllib.parse.quote(circle(c))))
