"""Build a standalone browser file from the dashboard and bundled sample prices."""
import json
from pathlib import Path
from quant_backtest.web import HTML
from quant_backtest.data import load_csv

root = Path(__file__).resolve().parents[1]
prices = load_csv(root / 'data/synthetic.csv')
fixture = json.dumps({'dates': [str(d.date()) for d in prices.index], 'close': prices.tolist()}, separators=(',', ':'))
engine = r'''
const bundled = __DATA__;
function evaluateOffline(config, data=bundled){
 const p=data.close,n=p.length,dates=data.dates;
 if(n<3||n!==dates.length||p.some(v=>!Number.isFinite(v)||v<=0))throw Error('Invalid close prices.');
 const {strategy,fast,slow,window,entry_z,exit_z,cash,commission_bps,slippage_bps,risk_free_rate}=config;
 if(!Number.isFinite(cash)||cash<=0||[commission_bps,slippage_bps].some(v=>!Number.isFinite(v)||v<0)||commission_bps+slippage_bps>=10000)throw Error('Invalid capital or trading costs.');
 if(!Number.isFinite(risk_free_rate)||risk_free_rate<=-1)throw Error('Invalid risk-free rate.');
 const signal=Array(n).fill(0);
 if(strategy==='ma'){
   if(!Number.isInteger(fast)||!Number.isInteger(slow)||fast<1||fast>=slow||n<slow+2)throw Error('Require 1 <= fast < slow and enough prices.');
   const sums=[0];for(const v of p)sums.push(sums.at(-1)+v);
   for(let i=slow-1;i<n;i++)signal[i]=((sums[i+1]-sums[i+1-fast])/fast>(sums[i+1]-sums[i+1-slow])/slow)?1:0;
 }else if(strategy==='mean-reversion'){
   if(!Number.isInteger(window)||window<2||n<window+2||!Number.isFinite(entry_z)||!Number.isFinite(exit_z)||exit_z<0||exit_z>=entry_z)throw Error('Require window >= 2 and 0 <= exit z < entry z.');
   let held=0;
   for(let i=window-1;i<n;i++){
     const slice=p.slice(i+1-window,i+1),mean=slice.reduce((a,b)=>a+b,0)/window;
     const sd=Math.sqrt(slice.reduce((a,v)=>a+(v-mean)**2,0)/(window-1));
     if(sd>0){const z=(p[i]-mean)/sd;if(!held&&z<=-entry_z)held=1;else if(held&&z>=-exit_z)held=0;}
     signal[i]=held;
   }
 }else throw Error('Unknown strategy.');
 function account(benchmark){
   let equity=cash,peak=cash,prior=0;const rows=[],eq=[],dd=[];
   for(let i=1;i<n;i++){
     const position=benchmark?1:(i>=2?signal[i-2]:0),turnover=Math.abs(position-prior);
     const asset_return=p[i]/p[i-1]-1,cost_fraction=turnover*(commission_bps+slippage_bps)/10000;
     const net_return=(1-cost_fraction)*(1+position*asset_return)-1;
     equity*=1+net_return;peak=Math.max(peak,equity);
     const drawdown=equity/peak-1;
     rows.push({Date:dates[i],close:p[i],position,asset_return,turnover,cost_fraction,net_return,equity,drawdown});
     eq.push(equity);dd.push(drawdown);prior=position;
   }
   const returns=rows.map(v=>v.net_return),count=returns.length,rf=(1+risk_free_rate)**(1/252)-1;
   const excess=returns.map(v=>v-rf),avg=excess.reduce((a,b)=>a+b,0)/count;
   const sampleStd=Math.sqrt(excess.reduce((a,v)=>a+(v-avg)**2,0)/(count-1));
   const downside=Math.sqrt(excess.reduce((a,v)=>a+Math.min(0,v)**2,0)/count);
   const total=equity/cash-1,cagr=(1+total)**(252/count)-1,maxDraw=Math.min(...dd);
   const ratio=(num,den)=>den>1e-12?num/den:null;
   return {rows,eq,dd,metrics:{total_return:total,cagr,annualized_volatility:sampleStd*Math.sqrt(252),sharpe_ratio:ratio(avg*Math.sqrt(252),sampleStd),sortino_ratio:ratio(avg*Math.sqrt(252),downside),max_drawdown:maxDraw,calmar_ratio:ratio(cagr,Math.abs(maxDraw)),exposure:rows.reduce((a,v)=>a+v.position,0)/count,one_way_trades:rows.filter(v=>v.turnover>0).length,observations:count}};
 }
 const s=account(false),b=account(true),columns=['Date','close','position','asset_return','turnover','cost_fraction','net_return','equity','drawdown'];
 return {metrics:{strategy:s.metrics,buy_and_hold:b.metrics},dates:dates.slice(1),equity:{strategy:s.eq,buy_and_hold:b.eq},drawdown:{strategy:s.dd,buy_and_hold:b.dd},csv:columns.join(',')+'\n'+s.rows.map(row=>columns.map(key=>row[key]).join(',')).join('\n')+'\n'};
}
'''.replace('__DATA__', fixture)
# Retain the visual dashboard, replacing only the HTTP request with the local engine.
html = HTML.replace('<script>', '<script>\n' + engine, 1)
html = html.replace('Running Python backtest…', 'Running backtest…')
html = html.replace("const response=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});const result=await response.json();if(!response.ok)throw Error(result.error);", 'const result=evaluateOffline(config);')
start = html.index("fetch('/api/info').then(")
end = html.index('\n</script>', start)
html = html[:start] + "$('source').textContent='Bundled synthetic data · '+bundled.close.length+' prices · '+bundled.dates[0]+' to '+bundled.dates.at(-1);run();" + html[end:]
html = html.replace('Use your own adjusted-close CSV through the server\'s --csv option.', 'For actual historical prices and custom CSV, use the Python version in the project.')
html = html.replace('<title>Quant Backtest Lab</title>', '<title>Quant Backtest Lab — offline demo</title>')
(root / 'quant-backtest-demo.html').write_text(html, encoding='utf8')
print(root / 'quant-backtest-demo.html')
