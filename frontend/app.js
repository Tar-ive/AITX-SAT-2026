const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const API_BASE=$('meta[name="dashboard-api"]').content;
const catalog={
  gpu:{label:"RTX 5090",target:3499,icon:"fa-microchip"},
  macbook:{label:"MacBook",target:699,icon:"fa-laptop"},
  ram:{label:"DDR5 RAM",target:199,icon:"fa-memory"}
};
const state={category:"gpu",market:null,deals:[],dealFilter:"all",improvement:[],operations:null,experiments:null,limit:3};
let marketChart,improvementChart,toastTimer;
const karpathyCharts={};

const money=(n,currency="USD")=>new Intl.NumberFormat("en-US",{style:"currency",currency,maximumFractionDigits:n<1000?2:0}).format(n);
const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const safeUrl=value=>{try{const url=new URL(value);return["http:","https:"].includes(url.protocol)?url.href:"#"}catch{return"#"}};
const relativeTime=value=>{const minutes=Math.max(0,Math.round((Date.now()-new Date(value))/60000));return minutes<1?"just now":minutes<60?`${minutes} min ago`:`${Math.round(minutes/60)}h ago`};
const sourceNote=row=>`${row.source_name} · ${row.collection_method==="scraped"?"scraped via Apify":"official API"}`;
const showToast=message=>{const el=$("#toast");el.textContent=message;el.classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove("show"),2600)};

async function api(path){
  const response=await fetch(`${API_BASE}${path}`,{headers:{"Accept":"application/json"}});
  const payload=await response.json();
  if(!response.ok)throw new Error(payload.error||`API ${response.status}`);
  return payload;
}

function showPage(id){
  const page=$(`#${id}-page`);
  if(!page)return;
  const focusView=["leaderboard","methodology"].includes(id);
  document.body.classList.toggle("focus-view",focusView);
  $$(".method-video video").forEach(video=>id==="methodology"?video.play().catch(()=>{}):video.pause());
  $$(".page").forEach(el=>el.classList.toggle("active",el===page));
  $$(".nav-link[data-page]").forEach(el=>el.classList.toggle("active",el.dataset.page===id));
  $(".rail").classList.remove("open");
  window.scrollTo({top:0,behavior:"smooth"});
  history.replaceState(null,"",`#${id}`);
  if(id==="dashboard")setTimeout(()=>marketChart?.resize(),0);
  if(id==="leaderboard")setTimeout(()=>{
    improvementChart?.resize();
    Object.values(karpathyCharts).forEach(c=>c?.resize());
  },0);
}

function renderListingRows(rows){
  if(!rows.length){
    $("#listing-list").innerHTML='<div class="empty-state"><i class="fa-solid fa-database"></i><strong>No live listings yet</strong><small>Run the marketplace ingester, then refresh.</small></div>';
    return;
  }
  $("#listing-list").innerHTML=rows.slice(0,3).map(row=>`
    <a class="listing" href="${safeUrl(row.listing_url)}" target="_blank" rel="noreferrer">
      ${row.image_url?`<img class="listing-image" src="${safeUrl(row.image_url)}" alt="">`:`<span class="listing-icon"><i class="fa-solid ${catalog[row.category].icon}"></i></span>`}
      <div><strong>${esc(row.title)}</strong><small>${esc(sourceNote(row))}</small></div>
      <div class="listing-price"><b>${money(row.total_price,row.currency)}</b><span class="source-tag">open listing</span></div>
    </a>`).join("");
}

function renderMarketChart(rows){
  const shown=rows.slice(0,state.limit), target=+$("#target-price").value, product=catalog[state.category];
  marketChart?.destroy();
  marketChart=new Chart($("#price-chart"),{type:"line",data:{
    labels:shown.map((row,index)=>`${row.source_name} ${index+1}`),
    datasets:[
      {label:"Live listing",data:shown.map(row=>row.total_price),borderColor:"#171711",backgroundColor:"#28754c",borderWidth:2,pointRadius:4,pointHoverRadius:6,tension:.2},
      {label:"Your target",data:shown.map(()=>target),borderColor:"#a64c3c",borderDash:[4,4],borderWidth:1,pointRadius:0}
    ]
  },options:{animation:false,responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:"index"},plugins:{
    legend:{display:false},
    tooltip:{backgroundColor:"#171711",titleFont:{family:"DM Mono"},bodyFont:{family:"DM Sans"},callbacks:{
      title:items=>shown[items[0].dataIndex]?.title||product.label,
      label:context=>`${context.dataset.label}: ${money(context.parsed.y)}`
    }}
  },scales:{
    x:{grid:{display:false},ticks:{font:{family:"DM Mono",size:9},color:"#77736a"}},
    y:{grid:{color:"#ded8cc"},ticks:{callback:value=>money(value),font:{family:"DM Mono",size:9},color:"#77736a"}}
  }}});
}

function renderMarket(payload){
  state.market=payload;
  const rows=payload.listings, meta=payload.meta, product=catalog[state.category], target=+$("#target-price").value;
  const prices=rows.map(row=>row.total_price), best=prices.length?Math.min(...prices):null, max=prices.length?Math.max(...prices):null;
  $("#data-badge").innerHTML='<i class="fa-solid fa-database"></i> Live Supabase';
  $("#sync-status").innerHTML=`<span class="live-dot"></span> Hosted Supabase refreshed <strong>${relativeTime(meta.last_synced_at)}</strong>`;
  $("#chart-title").textContent=`${product.label} current price spread`;
  $("#best-price").textContent=best==null?"—":money(best);
  $("#target-display").textContent=money(target);
  $("#range-display").textContent=best==null?"—":`${money(best)}–${money(max)}`;
  $("#live-listing-count").textContent=String(rows.length);
  $("#metric-listings").textContent=String(rows.length);
  $("#metric-sources").textContent=String(meta.source_count);
  $("#metric-source-names").textContent=meta.sources.join(", ")||"No live sources";
  $("#metric-syncs").textContent=String(meta.successful_syncs);
  $("#metric-last-sync").textContent=`Last sync ${relativeTime(meta.last_synced_at)}`;
  const buy=best!=null&&best<=target, difference=best==null?0:Math.abs(best-target);
  $("#decision-status").textContent=best==null?"NO DATA":buy?"BUY":"WAIT";
  $("#decision-status").className=`status ${buy?"buy":"wait"}`;
  $("#decision-copy").textContent=best==null?"No verified live price":buy?`${money(best)} is within target`:`Best price is ${money(difference)} above target`;
  renderListingRows(rows);
  renderMarketChart(rows);
}

async function loadMarket(category=state.category){
  state.category=category;
  $("#data-badge").innerHTML='<i class="fa-solid fa-spinner fa-spin"></i> Loading Supabase';
  try{
    const payload=await api(`/api/marketplace?category=${encodeURIComponent(category)}`);
    renderMarket(payload);
  }catch(error){
    $("#data-badge").innerHTML='<i class="fa-solid fa-triangle-exclamation"></i> API unavailable';
    $("#sync-status").innerHTML='<span class="error-dot"></span> Hosted Supabase connection failed';
    renderMarket({listings:[],meta:{last_synced_at:new Date().toISOString(),source_count:0,sources:[],successful_syncs:0}});
    showToast(error.message);
  }
}

function renderDeals(filter=state.dealFilter){
  state.dealFilter=filter;
  const rows=filter==="all"?state.deals:state.deals.filter(row=>row.category===filter);
  $("#deal-grid").innerHTML=rows.length?rows.map(row=>`
    <article class="deal-card">
      ${row.image_url?`<img class="deal-image" src="${safeUrl(row.image_url)}" alt="">`:`<i class="fa-solid ${catalog[row.category].icon}"></i>`}
      <div class="deal-meta"><span>${esc(row.category)}</span><span>${esc(row.source_name)}</span></div>
      <h2>${esc(row.title)}</h2>
      <footer><div><b>${money(row.total_price,row.currency)}</b><small>${esc(row.condition||"Condition unknown")} · ${esc(row.collection_method)}</small></div><a href="${safeUrl(row.listing_url)}" target="_blank" rel="noreferrer">Check listing <i class="fa-solid fa-arrow-right"></i></a></footer>
    </article>`).join(""):'<div class="empty-state wide"><strong>No live listings in this category.</strong></div>';
}

async function loadDeals(){
  try{
    const payload=await api("/api/marketplace?category=all");
    state.deals=payload.listings;
    renderDeals();
    $(".primary-nav [data-page='deals'] b").textContent=String(payload.listings.length);
  }catch(error){
    state.deals=[];
    renderDeals();
  }
}

const metricCell=(value,ci,format,trend)=>value==null
  ?'<td class="unavailable"><b>—</b><small>not measured</small></td>'
  :`<td class="${trend}"><b>${format(value)}</b><small>${ci==null?"":`±${format(ci)}`}</small></td>`;
function trendClass(value,baseline,higherIsBetter){
  if(value==null||baseline==null)return"same";
  const delta=value-baseline;
  if(Math.abs(delta)<.0001)return"same";
  return(higherIsBetter?delta>0:delta<0)?"better":"worse";
}

function renderImprovement(payload){
  state.improvement=payload.runs;
  const runs=payload.runs, baseline=runs.find(run=>run.baseline)||runs.at(-1);
  const candidates=[...payload.candidates].sort((a,b)=>a.step-b.step);
  $("#improvement-evidence").textContent=payload.evidence_status==="illustrative"?"Prototype evaluation history":`${candidates.length} measured runs`;
  $("#benchmark-note").textContent=`95% confidence intervals · ${payload.evidence_status}`;
  $("#improvement-table").innerHTML=runs.map((run,index)=>{
    const movement=index===0?'<span class="movement up">↑ 1</span>':index===1?'<span class="movement down">↓ 1</span>':'<span class="movement">–</span>';
    return`<tr class="${run.current?"champion":""}">
      <td><span class="rank">${index+1}</span>${movement}</td>
      <td><strong>${esc(run.version)}${run.current?" (current)":""}</strong><small>${esc(run.label)}</small></td>
      ${metricCell(run.decision_quality,run.decision_ci,v=>v.toFixed(3),trendClass(run.decision_quality,baseline.decision_quality,true))}
      ${metricCell(run.landed_price_error,run.landed_ci,v=>`${v.toFixed(1)}%`,trendClass(run.landed_price_error,baseline.landed_price_error,false))}
      ${metricCell(run.latency,run.latency_ci,v=>`${v.toFixed(2)}s`,trendClass(run.latency,baseline.latency,false))}
      ${metricCell(run.valid_url_rate,run.url_ci,v=>`${v.toFixed(1)}%`,trendClass(run.valid_url_rate,baseline.valid_url_rate,true))}
      ${metricCell(run.unsupported_claims,run.claims_ci,v=>`${v.toFixed(2)}%`,trendClass(run.unsupported_claims,baseline.unsupported_claims,false))}
      ${metricCell(run.forecast_regret,run.regret_ci,v=>money(v),trendClass(run.forecast_regret,baseline.forecast_regret,false))}
    </tr>`;
  }).join("");

  const current=runs.find(run=>run.current)||runs[0], latest=candidates.at(-1);
  if(candidates.length===1){
    $("#improvement-summary").innerHTML=`
      <p class="eyebrow">Measured baseline established</p>
      <strong>${current.decision_quality.toFixed(3)}</strong><span>decision quality · ±${current.decision_ci.toFixed(3)}</span>
      <dl><div><dt>Rollouts</dt><dd>${current.sample_size}</dd></div><div><dt>Median latency</dt><dd>${current.latency.toFixed(2)}s</dd></div><div><dt>Teacher</dt><dd>${esc(current.teacher_model)}</dd></div></dl>
      <small>Memory is off. Run the first lessons-informed challenger to begin the trend.</small>`;
  }else{
    const decisionGain=(latest.decision_quality-current.decision_quality)/current.decision_quality*100;
    $("#improvement-summary").innerHTML=`
      <p class="eyebrow">${latest.accepted?"Promoted":"Challenger held"}</p>
      <strong>${decisionGain>=0?"+":""}${decisionGain.toFixed(1)}%</strong><span>decision quality</span>
      <dl><div><dt>Candidate</dt><dd>${esc(latest.version)}</dd></div><div><dt>Champion</dt><dd>${esc(current.version)}</dd></div><div><dt>Decision</dt><dd>${latest.accepted?"Promoted":"No change"}</dd></div></dl>
      <small>${esc(latest.policy_change)}</small>`;
  }
  renderImprovementChart(runs,payload.candidates);
}

function renderImprovementChart(runs,candidates=[]){
  const ordered=[...candidates].sort((a,b)=>a.step-b.step);
  let champion=null;
  const championLine=ordered.map(candidate=>{if(candidate.accepted)champion=candidate.decision_quality;return champion});
  improvementChart?.destroy();
  improvementChart=new Chart($("#improvement-chart"),{type:"line",data:{labels:ordered.map(run=>run.version),datasets:[
    {label:"Champion",data:championLine,stepped:"after",borderColor:"#e84c6a",backgroundColor:"#e84c6a",pointRadius:4,borderWidth:3},
    {label:"Evaluated candidate",data:ordered.map(run=>run.decision_quality),showLine:false,pointBackgroundColor:ordered.map(run=>run.accepted?"#28754c":"#aaa69b"),pointBorderColor:"#fffdf7",pointRadius:6}
  ]},options:{animation:false,responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{boxWidth:14,font:{family:"DM Sans",size:11}}}},scales:{
    x:{grid:{display:false},ticks:{font:{family:"DM Mono",size:10}}},
    y:{suggestedMin:.45,suggestedMax:.80,title:{display:true,text:"Decision quality"},ticks:{font:{family:"DM Mono",size:9}},grid:{color:"#ded8cc"}}
  }}});
}

/** Karpathy-style keep/discard staircase for one metric. */
function renderKarpathyChart(canvasId, experiments, metric, opts={}){
  const canvas=$(`#${canvasId}`);
  if(!canvas||!window.Chart)return;
  let best=null;
  const running=[], discarded=[], keptPts=[];
  experiments.forEach((e,i)=>{
    if(e.kept||e.accepted){
      best=e[metric];
      keptPts.push(e[metric]);
      discarded.push(null);
    }else{
      keptPts.push(null);
      discarded.push(e[metric]);
    }
    running.push(best);
  });
  const labels=experiments.map(e=>e.experiment);
  karpathyCharts[canvasId]?.destroy();
  const showLabels=!!opts.annotate;
  karpathyCharts[canvasId]=new Chart(canvas,{
    type:"line",
    data:{
      labels,
      datasets:[
        {
          label:"Discarded",
          data:discarded,
          showLine:false,
          pointRadius:3,
          pointHoverRadius:5,
          pointBackgroundColor:"#c8c4ba",
          pointBorderWidth:0,
          order:1
        },
        {
          label:"Kept",
          data:keptPts,
          showLine:false,
          pointRadius:5.5,
          pointHoverRadius:7,
          pointBackgroundColor:"#fffdf7",
          pointBorderColor:"#28754c",
          pointBorderWidth:2,
          order:3
        },
        {
          label:"Running best",
          data:running,
          stepped:"after",
          borderColor:"#28754c",
          borderWidth:2.4,
          pointRadius:0,
          spanGaps:true,
          order:2
        }
      ]
    },
    options:{
      animation:false,
      responsive:true,
      maintainAspectRatio:false,
      interaction:{mode:"index",intersect:false},
      plugins:{
        legend:{position:"bottom",labels:{boxWidth:12,font:{family:"DM Sans",size:11}}},
        tooltip:{
          backgroundColor:"#171711",
          titleFont:{family:"DM Mono"},
          bodyFont:{family:"DM Sans"},
          filter:item=>item.raw!=null,
          callbacks:{
            title:items=>{
              const exp=experiments[items[0]?.dataIndex ?? 0];
              return exp?`#${exp.experiment} · ${exp.ts?.slice(5,16)||exp.version}`:"";
            },
            afterBody:items=>{
              const exp=experiments[items[0]?.dataIndex ?? 0];
              return exp?.description?[`${exp.kept||exp.accepted?"KEPT":"discarded"}: ${exp.description}`]:[];
            }
          }
        }
      },
      scales:{
        x:{
          title:{display:true,text:"Experiment #",font:{family:"DM Mono",size:10}},
          grid:{display:false},
          ticks:{font:{family:"DM Mono",size:9},color:"#77736a",maxTicks:10}
        },
        y:{
          title:{display:true,text:opts.yLabel||metric,font:{family:"DM Mono",size:10}},
          grid:{color:"#ded8cc"},
          ticks:{font:{family:"DM Mono",size:9},color:"#77736a"}
        }
      }
    },
    plugins: showLabels?[{
      id:"keptLabels",
      afterDatasetsDraw(chart){
        const meta=chart.getDatasetMeta(1);
        const ctx=chart.ctx;
        ctx.save();
        ctx.font="9px DM Mono, monospace";
        ctx.fillStyle="#3d3a32";
        experiments.forEach((e,i)=>{
          if(!(e.kept||e.accepted))return;
          const pt=meta.data[i];
          if(!pt||pt.skip)return;
          ctx.save();
          ctx.translate(pt.x+4, pt.y-4);
          ctx.rotate(-Math.PI/7);
          ctx.fillText((e.description||"").slice(0,34),0,0);
          ctx.restore();
        });
        ctx.restore();
      }
    }]:[]
  });
}

function fmtDelta(start, now, digits=3, invert=false){
  const d=now-start;
  const good=invert?d<0:d>0;
  const arrow=d>0?"▲":d<0?"▼":"–";
  return `${arrow} ${Math.abs(d).toFixed(digits)}`;
}

function renderExperiments(payload){
  state.experiments=payload;
  const exps=payload.experiments||[];
  const s=payload.summary||{};
  $("#improvement-evidence").textContent=`${s.experiments||exps.length} experiments · ${s.kept||0} kept · ${payload.seed}`;
  $("#seed-value").textContent=String(payload.seed??"—");
  $("#seed-exp-count").textContent=String(s.experiments??exps.length);
  $("#seed-kept-count").textContent=String(s.kept??0);
  const note=payload.seed_justification?.supabase_note||"";
  $("#seed-note").textContent=note||"Measured experiment history from the live EC2 loop.";
  const methodSeed=$("#method-seed");
  if(methodSeed)methodSeed.textContent=String(payload.seed??"—");

  $("#acc-delta").textContent=`${(s.accuracy_start??0).toFixed(3)} → ${(s.accuracy_now??0).toFixed(3)}`;
  $("#ret-delta").textContent=`${(s.retrieval_start??0).toFixed(1)}s → ${(s.retrieval_now??0).toFixed(1)}s`;
  $("#price-delta").textContent=`${(s.price_regression_start??0).toFixed(1)} → ${(s.price_regression_now??0).toFixed(1)}`;
  $("#agent-delta").textContent=`${(s.agent_regression_start??0).toFixed(3)} → ${(s.agent_regression_now??0).toFixed(3)}`;

  renderKarpathyChart("chart-accuracy", exps, "accuracy", {yLabel:"Accuracy (↑ better)"});
  renderKarpathyChart("chart-retrieval", exps, "retrieval_s", {yLabel:"Seconds (↓ better)", lowerIsBetter:false});
  renderKarpathyChart("chart-price", exps, "price_regression", {yLabel:"Price regression (↓ better)"});
  renderKarpathyChart("chart-agent", exps, "agent_regression", {yLabel:"Agent regression (↓ better)"});
  renderKarpathyChart("chart-overview", exps, "accuracy", {yLabel:"Accuracy", annotate:true});

  const kept=exps.filter(e=>e.kept||e.accepted);
  $("#kept-log").innerHTML=kept.map(e=>`
    <li><b>#${e.experiment}</b> <span>${esc(e.ts?.slice(0,16)||"")}</span>
    <strong>${e.accuracy.toFixed(4)}</strong> · ${e.retrieval_s.toFixed(2)}s
    <em>${esc(e.description)}</em></li>`).join("");
}

async function loadExperiments(){
  // Prefer API; fall back to static JSON committed in the repo.
  try{
    renderExperiments(await api("/api/autoresearch-experiments"));
    return;
  }catch(_){}
  try{
    const paths=[`data/autoresearch_experiments.json?t=${Date.now()}`,`../data/autoresearch_experiments.json?t=${Date.now()}`];
    let res=null;
    for(const path of paths){res=await fetch(path);if(res.ok)break;}
    if(!res||!res.ok)throw new Error("offline experiment history missing");
    renderExperiments(await res.json());
  }catch(error){
    $("#improvement-evidence").textContent="Experiment history unavailable";
    $("#seed-note").textContent=error.message;
  }
}

async function loadImprovement(){
  try{renderImprovement(await api("/api/improvement"))}
  catch(error){
    $("#improvement-table").innerHTML=`<tr><td colspan="8">Evaluation API unavailable: ${esc(error.message)}</td></tr>`;
    $("#improvement-summary").innerHTML="<strong>No evaluation history</strong><p>Start the dashboard API and refresh.</p>";
  }
}

function renderOperations(payload){
  state.operations=payload;
  const {lessons,latest_eval:latest}=payload;
  $("#lessons-status").innerHTML=lessons.status==="synced"&&lessons.lesson_count>0
    ?`<i class="fa-solid fa-circle-check"></i> ${lessons.lesson_count} lessons synced · ${esc(relativeTime(lessons.updated_at))}`
    :lessons.status==="synced"
    ?'<i class="fa-solid fa-circle-check"></i> No cloud lesson promotion yet'
    :'<i class="fa-solid fa-cloud-arrow-down"></i> Lessons file awaiting cloud sandbox sync';
  $("#fresh-run-strip").innerHTML=latest?`
    <span><small>Latest measured run</small><strong>${esc(latest.model.split("/").at(-1))}</strong></span>
    <span><small>Decision quality</small><strong>${latest.avg_reward.toFixed(3)}</strong></span>
    <span><small>Valid JSON</small><strong>${latest.avg_metrics.valid_json_rate_pct.toFixed(1)}%</strong></span>
    <span><small>Rollouts</small><strong>${latest.rollout_count}</strong></span>
    <span><small>Evaluation time</small><strong>${latest.eval_seconds.toFixed(1)}s</strong></span>
  `:'<span><small>Latest measured run</small><strong>Awaiting first evaluation</strong></span>';
}

async function loadOperations(){
  try{renderOperations(await api("/api/rsi-operations"))}
  catch(error){
    $("#lessons-status").innerHTML='<i class="fa-solid fa-triangle-exclamation"></i> RSI operations unavailable';
  }
}

async function loadRsiIdeas(){
  try{
    const payload=await api("/api/rsi-ideas");
    const count=Number(payload.promoted_count||0);
    $("#loop-history-count").textContent=count?`${count} promoted idea${count===1?"":"s"} recalled`:"No promoted ideas yet";
    $("#loop-history-idea").textContent=payload.ideas?.[0]?.lesson||"AutoResearch will store the first successful strategy here.";
    $(".rsi-loop-center").title=$("#loop-history-idea").textContent;
  }catch{
    $("#loop-history-count").textContent="Supabase history ready";
    $("#loop-history-idea").textContent="AutoResearch checks prior successful lessons before creating challengers.";
    $(".rsi-loop-center").title=$("#loop-history-idea").textContent;
  }
}

function initRsiLoop(){
  const stage=$("#rsi-loop-stage"), canvas=$("#rsi-loop-canvas"), cards=$$(".loop-card",stage);
  if(!stage||!canvas||!window.THREE||!cards.length){stage?.classList.add("three-unavailable");return}
  const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera(38,1,.1,100);
  camera.position.set(0,0,11.8);
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  const orbit=new THREE.Group();
  scene.add(orbit);
  const count=cards.length, rx=4.5, ry=4;
  const points=Array.from({length:64},(_,i)=>{
    const angle=i/64*Math.PI*2;
    return new THREE.Vector3(Math.cos(angle)*rx,Math.sin(angle)*ry,0);
  });
  const loopLine=new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineDashedMaterial({color:0x383838,dashSize:.09,gapSize:.11,transparent:true,opacity:.85})
  );
  loopLine.computeLineDistances();
  orbit.add(loopLine);
  orbit.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points.slice(19,34)),
    new THREE.LineBasicMaterial({color:0x76bd68,transparent:true,opacity:.9})
  ));
  const up=new THREE.Vector3(0,1,0);
  for(let i=0;i<count;i++){
    const angle=(i+.55)/count*Math.PI*2, arrow=new THREE.Mesh(
      new THREE.ConeGeometry(.075,.24,12),
      new THREE.MeshBasicMaterial({color:0x76bd68})
    );
    arrow.position.set(Math.cos(angle)*rx,Math.sin(angle)*ry,0);
    arrow.quaternion.setFromUnitVectors(
      up,
      new THREE.Vector3(-Math.sin(angle)*rx,Math.cos(angle)*ry,0).normalize()
    );
    orbit.add(arrow);
  }
  const particles=Array.from({length:14},(_,i)=>{
    const dot=new THREE.Mesh(
      new THREE.SphereGeometry(i%5===0?.045:.022,8,8),
      new THREE.MeshBasicMaterial({color:i%5===0?0x8ee879:0x4c7646})
    );
    orbit.add(dot);
    return{dot,offset:i/14};
  });
  let paused=matchMedia("(prefers-reduced-motion: reduce)").matches, last=performance.now(), phase=0;
  const motion=$("#loop-motion-toggle");
  const syncMotion=()=>{
    motion.innerHTML=`<i class="fa-solid fa-${paused?"play":"pause"}"></i>`;
    motion.setAttribute("aria-label",paused?"Play loop":"Pause loop");
    motion.setAttribute("aria-pressed",String(paused));
  };
  syncMotion();
  motion.addEventListener("click",()=>{paused=!paused;syncMotion()});
  const resize=()=>{
    const width=stage.clientWidth||1000, height=stage.clientHeight||1100;
    renderer.setSize(width,height,false);
    camera.aspect=width/height;
    orbit.scale.setScalar(width<600?.54:1);
    camera.position.z=width<600?20:16.2;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(stage);
  resize();
  function frame(now){
    const delta=Math.min((now-last)/1000,.05);
    last=now;
    if(!paused)phase+=delta*.11;
    particles.forEach(({dot,offset})=>{
      const angle=(offset+phase*.08)%1*Math.PI*2;
      dot.position.set(Math.cos(angle)*rx,Math.sin(angle)*ry,0);
    });
    orbit.updateMatrixWorld(true);
    const width=stage.clientWidth||1000, height=stage.clientHeight||1100;
    cards.forEach((card,i)=>{
      const angle=i/count*Math.PI*2-Math.PI/2+phase;
      const world=new THREE.Vector3(Math.cos(angle)*rx,Math.sin(angle)*ry,0)
        .applyMatrix4(orbit.matrixWorld);
      const projected=world.clone().project(camera);
      card.style.left=`${(projected.x*.5+.5)*width}px`;
      card.style.top=`${(-projected.y*.5+.5)*height}px`;
      card.style.transform="translate(-50%,-50%)";
      card.style.opacity="1";
      card.style.zIndex="10";
    });
    renderer.render(scene,camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

$$("[data-page]").forEach(el=>el.addEventListener("click",()=>showPage(el.dataset.page)));
$("#mobile-menu").addEventListener("click",()=>$(".rail").classList.toggle("open"));
$("#theme-button").addEventListener("click",()=>document.body.classList.toggle("high-contrast"));
$("#alerts-button").addEventListener("click",()=>showToast("3 local target alerts are configured."));
$("#product-select").addEventListener("change",event=>{$("#target-price").value=catalog[event.target.value].target;loadMarket(event.target.value)});
$("#watch-form").addEventListener("submit",event=>{event.preventDefault();renderMarket(state.market);showToast("Target updated locally. Sign-in is required before saving a Supabase watchlist.")});
$$(".segmented button").forEach(el=>el.addEventListener("click",()=>{$$(".segmented button").forEach(button=>button.classList.toggle("active",button===el));state.limit=+el.dataset.range;renderMarketChart(state.market?.listings||[])}));
$$(".filter-chip").forEach(el=>el.addEventListener("click",()=>{$$(".filter-chip").forEach(button=>button.classList.toggle("active",button===el));renderDeals(el.dataset.filter)}));
$("#benchmark-select").addEventListener("change",event=>$("#benchmark-label").textContent=event.target.value);
$("#run-evaluation").addEventListener("click",async event=>{event.currentTarget.innerHTML='<i class="fa-solid fa-spinner fa-spin"></i> Refreshing';await Promise.all([loadImprovement(),loadOperations(),loadExperiments()]);event.currentTarget.innerHTML='<i class="fa-solid fa-check"></i> History refreshed';showToast("Evidence refreshed. Promotion remains a human decision.")});
$(".toggle").addEventListener("click",event=>event.currentTarget.classList.toggle("active"));
const enterFullscreen=async element=>{
  const video=$("video",element);
  if(element.requestFullscreen)return element.requestFullscreen();
  if(video?.webkitEnterFullscreen)return video.webkitEnterFullscreen();
};
const zoom=$("#video-zoom"), zoomStage=$("#video-zoom-stage");
function openVideoZoom(container){
  const card=container.closest(".method-video-card");
  $("#video-zoom-title").textContent=$("h3",card)?.textContent||container.dataset.placeholderLabel||"Workflow recording";
  zoomStage.replaceChildren();
  const video=$("video",container);
  if(video){
    const clone=video.cloneNode(true);
    clone.controls=true;
    clone.autoplay=true;
    clone.muted=true;
    zoomStage.append(clone);
    clone.play().catch(()=>{});
  }else{
    const placeholder=$(".method-video-placeholder",container).cloneNode(true);
    const label=container.dataset.placeholderLabel;
    if(label)$("span",placeholder).textContent=label;
    zoomStage.append(placeholder);
  }
  zoom.showModal();
}
$$(".method-video").forEach(container=>{
  const video=$("video",container), toggle=$(".method-video-play",container);
  if(video&&toggle){
    const togglePlayback=async()=>{
      const play=video.paused;
      $$(".method-video video").forEach(other=>{if(other!==video)other.pause()});
      if(play)await video.play();else video.pause();
    };
    toggle.addEventListener("click",togglePlayback);
    video.addEventListener("click",togglePlayback);
    video.addEventListener("play",()=>{container.classList.add("playing");toggle.setAttribute("aria-pressed","true");$("i",toggle).className="fa-solid fa-pause"});
    video.addEventListener("pause",()=>{container.classList.remove("playing");toggle.setAttribute("aria-pressed","false");$("i",toggle).className="fa-solid fa-play"});
    if(!video.paused){container.classList.add("playing");toggle.setAttribute("aria-pressed","true");$("i",toggle).className="fa-solid fa-pause"}
  }
  $("[data-video-expand]",container)?.addEventListener("click",()=>openVideoZoom(container));
  $("[data-video-fullscreen]",container)?.addEventListener("click",()=>enterFullscreen(container));
});
$("#video-zoom-close").addEventListener("click",()=>zoom.close());
$("#video-zoom-fullscreen").addEventListener("click",()=>enterFullscreen(zoomStage));
zoom.addEventListener("click",event=>{if(event.target===zoom)zoom.close()});
zoom.addEventListener("close",()=>{const video=$("video",zoomStage);video?.pause();zoomStage.replaceChildren()});
window.addEventListener("hashchange",()=>showPage(location.hash.slice(1)||"dashboard"));

initRsiLoop();
Promise.allSettled([loadMarket(),loadDeals(),loadImprovement(),loadOperations(),loadRsiIdeas(),loadExperiments()]);
showPage(location.hash.slice(1)||"dashboard");
