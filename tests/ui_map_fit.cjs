/* 法考首页地图（config.fit）：4:3 居中、名牌按图片坐标、旧版横屏位置被丢弃、新版保存位置保留；Win/Mac/iPad/安卓平板横屏多种比例。
   用 page.route 把全景换成 4:3 占位图，不依赖正式素材。 */
const { chromium } = require('playwright'); const { spawn } = require('node:child_process'); const assert = require('node:assert/strict');
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
(async () => {
  const srv = spawn(process.env.PYTHON || 'python3', ['tests/ui_layout_server.py'], { env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  const base = await new Promise((res, rej) => { let t = ''; const timer = setTimeout(() => rej(Error('服务没起来')), 25000);
    srv.stdout.on('data', (b) => { t += b; const m = t.match(/UI-READY (\S+)/); if (m) { clearTimeout(timer); res(m[1]); } }); });
  const browser = await chromium.launch();
  try {
    for (const [name, w, h] of [['1280x860', 1280, 860], ['1920x1080', 1920, 1080], ['ipad 1180x820', 1180, 820], ['16:10 1280x800', 1280, 800], ['ipad 1366x1024', 1366, 1024]]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h } });
      const page = await ctx.newPage(); const errors = []; page.on('pageerror', (e) => errors.push(e.message));
      await page.route(/academy\/scene\/academy-(day|spring-dusk|spring-night)-4k\.webp/, (r) => r.fulfill({ status: 200, contentType: 'image/png', body: PNG }));
      await page.addInitScript(() => { try { localStorage.setItem('scene-layout:mage:saved', JSON.stringify({ desktop: { dwelling: { x: 5, y: 5 } }, narrow: {}, names: {} })); } catch (e) {} });  // 旧版本（无版本号）保存的位置
      await page.goto(base); await page.waitForTimeout(1500);
      await page.evaluate(() => document.querySelectorAll('.cer-ok').forEach((b) => b.click())); await page.waitForTimeout(500);
      const info = await page.evaluate(() => {
        const f = document.querySelector('.portal-frame'); if (!f) return null;
        const fr = f.getBoundingClientRect(), st = f.parentElement.getBoundingClientRect();
        const d = document.querySelector('[data-portal-go="dwelling"]').getBoundingClientRect();
        const places = [...document.querySelectorAll('[data-portal-go]')].map((e) => { const q = e.getBoundingClientRect(); return { id: e.dataset.portalGo, in: q.left >= fr.left - 1 && q.right <= fr.right + 1 && q.top >= fr.top - 1 && q.bottom <= fr.bottom + 1 }; });
        return { ratio: fr.width / fr.height, fits: fr.width <= st.width + 1 && fr.height <= st.height + 1, dx: (d.left + d.width / 2 - fr.left) / fr.width * 100, dy: (d.top + d.height / 2 - fr.top) / fr.height * 100, n: places.length, outside: places.filter((p) => !p.in).map((p) => p.id) };
      });
      assert(info, `${name} 没有 .portal-frame`);
      assert(Math.abs(info.ratio - 4 / 3) < 0.02 && info.fits, `${name} 地图框应保持 4:3 且不超出舞台`);
      assert.equal(info.n, 12, `${name} 应有 12 个地点`);
      assert(Math.abs(info.dx - 15.9) < 1 && Math.abs(info.dy - 78.4) < 1.5, `${name} 旧版保存的横屏位置应被丢弃，营地按新默认 (15.9,78.4)，实际 (${info.dx.toFixed(1)},${info.dy.toFixed(1)})`);
      assert.deepEqual(info.outside, [], `${name} 名牌不能伸出地图框`);
      assert.deepEqual(errors, [], `${name} 脚本报错`);
      await ctx.close();
    }
    // 带当前版本号保存的位置要保留
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } }); const page = await ctx.newPage();
    await page.route(/academy\/scene\/academy-(day|spring-dusk|spring-night)-4k\.webp/, (r) => r.fulfill({ status: 200, contentType: 'image/png', body: PNG }));
    await page.addInitScript(() => { try { localStorage.setItem('scene-layout:mage:saved', JSON.stringify({ desktop: { dwelling: { x: 30, y: 40 } }, narrow: {}, names: {}, desktopVersion: 'fit-v1' })); } catch (e) {} });
    await page.goto(base); await page.waitForTimeout(1500); await page.evaluate(() => document.querySelectorAll('.cer-ok').forEach((b) => b.click())); await page.waitForTimeout(500);
    const kept = await page.evaluate(() => { const f = document.querySelector('.portal-frame').getBoundingClientRect(), d = document.querySelector('[data-portal-go="dwelling"]').getBoundingClientRect(); return [(d.left + d.width / 2 - f.left) / f.width * 100, (d.top + d.height / 2 - f.top) / f.height * 100]; });
    assert(Math.abs(kept[0] - 30) < 1 && Math.abs(kept[1] - 40) < 1.5, '当前版本号保存的自定义位置应保留');
    console.log('法考首页地图：4:3 居中、名牌按图片坐标、旧版位置丢弃/新版保留、5 种横屏比例通过');
  } finally { await browser.close(); srv.kill(); }
})().catch((e) => { console.error(e); process.exit(1); });
