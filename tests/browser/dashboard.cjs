// Optional end-to-end tests: start the Python web server before running this file.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
  const page = await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  let count=0;
  const check=(label)=>{count++; console.log('PASS '+label);};
  try {
    await page.goto(process.env.BACKTEST_URL || 'http://127.0.0.1:8000');
    await page.getByRole('status').filter({hasText:'Updated'}).waitFor();
    assert.match(await page.locator('#source').textContent(), /synthetic.csv.*1000 prices/);
    assert.equal(await page.locator('#total').textContent(),'16.46%');
    assert.equal(await page.locator('#sharpe').textContent(),'0.537');
    assert.equal(await page.locator('#metrics tr').count(),10);
    assert.equal(await page.locator('#equity-chart path').count(),2);
    check('default Python-backed run, metrics, and equity chart');

    const initial=await page.locator('#total').textContent();
    await page.locator('#commission_bps').fill('100');
    await page.getByRole('button',{name:'Run backtest',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Updated'}).waitFor();
    assert(parseFloat(await page.locator('#total').textContent()) < parseFloat(initial));
    check('higher trading costs reduce displayed net returns');

    await page.locator('#strategy').selectOption('mean-reversion');
    assert(await page.locator('#mr-fields').isVisible());
    assert(!(await page.locator('#ma-fields').isVisible()));
    await page.locator('#commission_bps').fill('1');
    await page.getByRole('button',{name:'Run backtest',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Updated · 44 entries or exits · 999 return observations · Mean reversion'}).waitFor();
    assert.notEqual(await page.locator('#total').textContent(),initial);
    check('mean-reversion selection and Python execution');

    const downloadReady=page.waitForEvent('download');
    await page.getByRole('button',{name:'Download backtest CSV'}).click();
    const download=await downloadReady;
    const fs=require('node:fs/promises');
    const csv=await fs.readFile(await download.path(),'utf8');
    assert(csv.startsWith('Date,close,position,asset_return,turnover,cost_fraction,net_return,equity,drawdown'));
    assert.equal(csv.trim().split('\n').length,1000);
    check('CSV download contains all 999 interval records');

    await page.locator('#strategy').selectOption('ma');
    await page.locator('#fast').fill('200');
    await page.locator('#slow').fill('100');
    await page.getByRole('button',{name:'Run backtest',exact:true}).click();
    await page.getByRole('alert').waitFor();
    assert.match(await page.getByRole('alert').textContent(),/fast < slow/);
    assert(await page.getByRole('button',{name:'Download backtest CSV'}).isDisabled());
    check('invalid parameters show backend validation and disable stale download');

    await page.locator('#fast').fill('20');
    await page.getByRole('button',{name:'Run backtest',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Updated'}).waitFor();
    assert(!(await page.getByRole('alert').isVisible()));
    assert.equal(await page.locator('#total').textContent(),initial);
    check('recovery after an invalid run');

    if(process.env.BACKTEST_SCREENSHOT)await page.screenshot({path:process.env.BACKTEST_SCREENSHOT,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole('button',{name:'Run backtest',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Updated'}).waitFor();
    check('mobile layout fits the viewport and remains functional');

    assert.deepEqual(errors,[]);
    check('no uncaught browser JavaScript errors');
    console.log(`${count} browser checks passed.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
