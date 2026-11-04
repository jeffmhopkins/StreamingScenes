// Screenshots the JStream web UI a running daemon serves on 127.0.0.1:4455, at 1440 × 900
// and scale 3, with the Monitors item selected: node capture-ui.js <token file> <out.png>
const { chromium } = require('playwright');
(async () => {
  const [token, out] = [require('fs').readFileSync(process.argv[2], 'utf8').trim(), process.argv[3]];
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 3, httpCredentials: { username: 'jstream', password: token } });
  const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:4455/');
  await p.getByRole('button', { name: 'Connect' }).click();
  await p.locator('header.app-header').waitFor();
  await p.waitForTimeout(2000);
  const mons = p.getByText('Monitors', { exact: true }).first();
  if (await mons.count()) await mons.click();
  await p.waitForTimeout(3000);
  await p.screenshot({ path: out });
  await b.close();
})();
