// No browser binary needed: exercise the standalone page's click handlers and DOM writes.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('quant-backtest-demo.html','utf8');
const script=html.split('<script>')[1].split('</script>')[0];
const elements=new Map();
function element(id){if(!elements.has(id)){const e={id,value:'',textContent:'',hidden:false,disabled:false,children:[],listeners:{},labels:[{textContent:id}],validity:{valueMissing:false},style:{},addEventListener(kind,fn){(this.listeners[kind]??=[]).push(fn)},checkValidity(){return this.value!==''},focus(){},replaceChildren(){this.children=[]},append(node){this.children.push(node)},setAttribute(){}};elements.set(id,e);}return elements.get(id)}
for(const [id,value] of Object.entries({strategy:'ma',fast:'20',slow:'100',window:'20',entry_z:'1.5',exit_z:'0',cash:'100000',commission_bps:'1',slippage_bps:'4',risk_free_rate:'0'}))element(id).value=value;
const document={getElementById:element,createElement:()=>({children:[],append(n){this.children.push(n)},set textContent(v){this._text=v}}),createElementNS:()=>({setAttribute(){}})};
const ctx=vm.createContext({document,console,setTimeout,URL,Blob});vm.runInContext(script,ctx);
const click=()=>element('run').listeners.click[0]({preventDefault(){}});
(async()=>{const start=element('total').textContent;assert.equal(start,'16.46%');
 element('fast').value='10';element('slow').value='40';await click();assert.equal(element('total').textContent,'19.29%');assert.equal(element('equity-chart').children.length,12);
 element('strategy').value='mean-reversion';element('strategy').listeners.change.forEach(fn=>fn());assert.equal(element('fast').disabled,true);assert.equal(element('window').disabled,false);await click();assert.equal(element('total').textContent,'-20.44%');
 element('risk_free_rate').value='5';const unchanged=element('total').textContent,sharpe=element('sharpe').textContent;await click();assert.equal(element('total').textContent,unchanged);assert.notEqual(element('sharpe').textContent,sharpe);
 element('window').value='';await click();assert.equal(element('error').hidden,false);assert.match(element('error').textContent,/Check window/);
 console.log('PASS click updates moving average, switches strategies, updates risk ratios, and reports invalid inputs.');
})().catch(e=>{console.error(e);process.exitCode=1});
