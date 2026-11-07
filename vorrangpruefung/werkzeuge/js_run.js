const {chromium}=require('playwright'); const fs=require('fs');
const cases=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const AD0={gj:0,ef:"ja",ssw:0,avB:0,avN:0,uhP:0,sg:0,sgSt:0,schw:false,merkG:false,sb:false,kv:"auto",jb:0,jn:0,rb:0,rn:0,grz:false,so:0};
const base={verh:false,son:{azubi:false,eu:false,asyl:false,stat:false},pa:"0.3",stabil:true,mi:0,hz:0,ww:false,kdz:"normal",hzG:null,mog:null,verm:0,step:1,kzStart:"",kzPrev:"",kzGap:0,kzUsed:null,mpb:false,umgCnt:0,umgAge:8,umgNights:0,umgArt:"temp",ext25:0};
const num=t=>{const m=(t||'').replace(/\s/g,'').match(/-?[\d.]+,\d+/); return m?parseFloat(m[0].replace(/\./g,'').replace(',','.')):0;};
(async()=>{const b=await chromium.launch();const p=await b.newPage();const out=[];const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.goto('file:///home/user/Test/vorrangpruefung/Vorrangpruefung_Wolfsburg.html');
for(const c of cases){
  const S=Object.assign({},base,c.S); S.ad=[0,1].map(i=>Object.assign({},AD0,(c.S.ad||[])[i]||{}));
  S.kids=(c.S.kids||[]).map(k=>Object.assign({uh:0,et:"none",eb:0,en:0},k));
  await p.evaluate(s=>{localStorage.clear();localStorage.setItem("vp-wob-input4",JSON.stringify(s));},S); await p.reload();
  const r=await p.evaluate(()=>{const kp=[...document.querySelectorAll('.kpi')].map(e=>[e.querySelector('span').textContent,e.querySelector('b').textContent]);
    const vr=[...document.querySelectorAll('.vrow')].map(e=>[e.querySelector('.vtop b').textContent,(e.querySelector('.pill')||{}).textContent,e.querySelector('.amt').textContent]);
    return {head:document.querySelector('.verdict b').textContent,kp,vr,bud:[...document.querySelectorAll('#budget .brow b')].map(x=>x.textContent)};});
  const kv=Object.fromEntries(r.kp.map(([a,b])=>[a,b]));
  const am0=(r.vr[0]&&r.vr[0][2])||""; const ki=am0.indexOf("Kinderwohngeld"); const kw=ki>=0?num(am0.slice(ki)):0;
  out.push({id:c.id,head:r.head,s0:num(r.kp[0][1]),kv:num(r.kp[1][1]),wg:num(r.kp[2][1]),kiz:(r.kp[3][0].includes('Kinderzuschlag')?num(r.kp[3][1]):0),kw,
    st:r.vr.slice(1).map(v=>v[1]),bud:r.bud.map(num)});
}
fs.writeFileSync(process.argv[3],JSON.stringify(out,null,1)); console.log('JS fertig',out.length,'Fehler',errs);await b.close();})();
