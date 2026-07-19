const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const API_BASE=$('meta[name="dashboard-api"]').content;
const catalog={
  gpu:{label:"RTX 5090",target:3499,icon:"fa-microchip"},
  macbook:{label:"MacBook",target:699,icon:"fa-laptop"},
  ram:{label:"DDR5 RAM",target:199,icon:"fa-memory"}
};
const state={category:"gpu",market:null,deals:[],dealFilter:"all",experiments:null,limit:3};
let marketChart,toastTimer;
const karpathyCharts={};
const EVAL_CACHE_KEY="aitx-evals-summary-v3", EVAL_CACHE_MAX_AGE=15*60*1000;

const money=(n,currency="USD")=>new Intl.NumberFormat("en-US",{style:"currency",currency,maximumFractionDigits:n<1000?2:0}).format(n);
const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const safeUrl=value=>{try{const url=new URL(value);return["http:","https:"].includes(url.protocol)?url.href:"#"}catch{return"#"}};
const relativeTime=value=>{const minutes=Math.max(0,Math.round((Date.now()-new Date(value))/60000));return minutes<1?"just now":minutes<60?`${minutes} min ago`:`${Math.round(minutes/60)}h ago`};
const sourceNote=row=>`${row.source_name} · ${row.collection_method==="scraped"?"scraped via Apify":"official API"}`;
const showToast=message=>{const el=$("#toast");el.textContent=message;el.classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove("show"),2600)};
const readEvalCache=()=>{try{const hit=JSON.parse(localStorage.getItem(EVAL_CACHE_KEY));return hit&&Date.now()-hit.savedAt<EVAL_CACHE_MAX_AGE?hit.payload:null}catch{return null}};
const writeEvalCache=payload=>{try{localStorage.setItem(EVAL_CACHE_KEY,JSON.stringify({savedAt:Date.now(),payload}))}catch{}};

async function api(path){
  const response=await fetch(`${API_BASE}${path}`,{headers:{"Accept":"application/json"}});
  const payload=await response.json();
  if(!response.ok)throw new Error(payload.error||`API ${response.status}`);
  return payload;
}

function showPage(requestedId){
  const id=requestedId==="leaderboard"?"evals":requestedId;
  const page=$(`#${id}-page`);
  if(!page)return;
  const focusView=["evals","methodology"].includes(id);
  document.body.classList.toggle("focus-view",focusView);
  $$(".method-video video").forEach(video=>id==="methodology"?video.play().catch(()=>{}):video.pause());
  $$(".page").forEach(el=>el.classList.toggle("active",el===page));
  $$(".nav-link[data-page]").forEach(el=>el.classList.toggle("active",el.dataset.page===id));
  $(".rail").classList.remove("open");
  window.scrollTo({top:0,behavior:"smooth"});
  history.replaceState(null,"",`#${id}`);
  if(id==="dashboard")setTimeout(()=>marketChart?.resize(),0);
  if(id==="evals")setTimeout(()=>Object.values(karpathyCharts).forEach(c=>c?.resize()),0);
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

const metricMeta={
  accuracy:{label:"Decision quality",format:value=>Number(value).toFixed(3)},
  retrieval_s:{label:"Seconds per answer",format:value=>`${Number(value).toFixed(2)}s`},
  prompt_injection_risk:{label:"Prompt injection risk",format:value=>`${Number(value).toFixed(1)}%`},
  episodic_diff_lines:{label:"Hermes episodic memory diff lines",format:value=>`${Number(value).toFixed(0)} lines`},
  knowledge_regression:{label:"Agent knowledge regression",format:value=>Number(value).toFixed(4)}
};
const measured=value=>value!==null&&value!==undefined&&Number.isFinite(Number(value));
const evalStatus=exp=>exp.kept||exp.accepted?"PROMOTED":exp.rolled_back?"ROLLED BACK":"EVALUATED";
const evalTime=value=>{
  const date=new Date(value);
  return Number.isNaN(date.valueOf())?String(value||"Unknown time"):new Intl.DateTimeFormat("en-US",{
    month:"short",day:"numeric",hour:"numeric",minute:"2-digit"
  }).format(date);
};

function renderResearchDetail(exp,metric="accuracy",previous=null){
  if(!exp)return;
  const evidence=exp.evidence||{};
  const meta=metricMeta[metric]||metricMeta.accuracy;
  const value=measured(exp[metric])?Number(exp[metric]):null;
  const prior=measured(previous?.[metric])?Number(previous[metric]):null;
  const delta=value!==null&&prior!==null?value-prior:null;
  $("#research-detail-title").textContent=`#${exp.experiment} · ${exp.description||exp.version}`;
  $("#research-detail-decision").textContent=[
    evalStatus(exp),
    `${meta.label}: ${value===null?"not measured":meta.format(value)}`,
    `Δ ${delta===null?"—":`${delta>=0?"+":""}${meta.format(delta)}`}`
  ].join(" · ");
  $("#research-detail-source").textContent=[evidence.source,evidence.source_detail,evidence.git_hash&&`git ${evidence.git_hash}`].filter(Boolean).join(" · ")||"Live EC2 experiment";
  $("#research-detail-change").textContent=evidence.improvement||exp.description||"No harness change recorded.";
  $("#research-detail-preference").textContent=evidence.preference||"No explicit preference attached to this trial.";
  const coverage=exp.episodes_tried||exp.rollouts||exp.stored_samples
    ?`${exp.episodes_tried||0} episodes · ${exp.rollouts||0} rollouts · ${exp.stored_samples||0} stored samples`
    :"Episode and rollout counts were not persisted for this cycle";
  $("#research-detail-test").textContent=[
    coverage,
    evidence.memory_change,
    evidence.tested_by
  ].filter(Boolean).join(" · ");
}

/** Connect every measured run; color communicates promotion or rollback. */
function renderKarpathyChart(canvasId, experiments, metric, opts={}){
  const canvas=$(`#${canvasId}`);
  if(!canvas||!window.Chart)return;
  const values=experiments.map(exp=>measured(exp[metric])?Number(exp[metric]):null);
  let champion=null;
  const championValues=experiments.map((exp,index)=>{
    if(values[index]!==null&&(exp.kept||exp.accepted))champion=values[index];
    return champion;
  });
  karpathyCharts[canvasId]?.destroy();
  karpathyCharts[canvasId]=new Chart(canvas,{
    type:"line",
    data:{
      labels:experiments.map(exp=>evalTime(exp.ts)),
      datasets:[{
        label:"Evaluated",
        data:values,
        showLine:false,
        pointRadius:3,
        pointHoverRadius:7,
        pointBackgroundColor:experiments.map(exp=>exp.rolled_back?"#a64c3c":"#c9c5ba"),
        pointBorderColor:experiments.map(exp=>exp.rolled_back?"#a64c3c":"#c9c5ba")
      },{
        label:"Promoted champion",
        data:championValues,
        borderColor:"#28754c",
        borderWidth:2.5,
        pointRadius:experiments.map(exp=>exp.kept||exp.accepted?5:0),
        pointHoverRadius:experiments.map(exp=>exp.kept||exp.accepted?7:0),
        pointBackgroundColor:"#fffdf7",
        pointBorderColor:"#28754c",
        pointBorderWidth:2,
        stepped:"after",
        spanGaps:true
      }]
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
              return exp?`#${exp.experiment} · ${evalTime(exp.ts)}`:"";
            },
            afterBody:items=>{
              const exp=experiments[items[0]?.dataIndex ?? 0];
              const evidence=exp?.evidence||{};
              return exp?[
                `${evalStatus(exp)}: ${exp.description}`,
                `Evidence: ${evidence.source||"live EC2 research"}`,
                `Preference: ${(evidence.preference||"none attached").slice(0,90)}`,
                `Test: ${(evidence.tested_by||"Verifiers golden set").slice(0,90)}`
              ]:[];
            }
          }
        }
      },
      onHover:(_event,elements)=>{
        const index=elements[0]?.index;
        if(index!=null)renderResearchDetail(experiments[index],metric,experiments[index-1]);
      },
      scales:{
        x:{
          title:{display:true,text:"Evaluated at",font:{family:"DM Mono",size:10}},
          grid:{display:false},
          ticks:{font:{family:"DM Mono",size:9},color:"#77736a",maxTicks:10}
        },
        y:{
          title:{display:true,text:opts.yLabel||metric,font:{family:"DM Mono",size:10}},
          grid:{color:"#ded8cc"},
          ticks:{font:{family:"DM Mono",size:9},color:"#77736a"}
        }
      }
    }
  });
}

function renderEvalResults(experiments){
  const host=$("#eval-results");
  if(!host)return;
  host.innerHTML=experiments.map((exp,index)=>{
    const episodes=exp.sample_episodes||[];
    const status=evalStatus(exp);
    const episodeRows=episodes.map(episode=>`
      <details class="episode-result">
        <summary>
          <span>Episode ${Number(episode.episode_index)+1}</span>
          <b>${measured(episode.decision_quality)?Number(episode.decision_quality).toFixed(3):"—"} quality</b>
          <b>${measured(episode.median_seconds)?`${Number(episode.median_seconds).toFixed(2)}s`:"—"}</b>
          <i class="fa-solid fa-chevron-down"></i>
        </summary>
        <p class="episode-prompt">${esc(episode.prompt)}</p>
        <div class="rollout-list">
          ${(episode.rollouts||[]).map(run=>`
            <div class="rollout-row">
              <strong>R${esc(run.rollout_number??"—")}</strong>
              <span>Quality <b>${measured(run.decision_quality)?Number(run.decision_quality).toFixed(3):"—"}</b></span>
              <span>Time <b>${measured(run.seconds_per_answer)?`${Number(run.seconds_per_answer).toFixed(2)}s`:"—"}</b></span>
              <span>Platform <b>${esc(run.platform)}</b></span>
              <span>${esc(run.condition||"condition —")}${run.lead_time_days!=null?` · ${esc(run.lead_time_days)}d`:""}</span>
            </div>`).join("")}
        </div>
      </details>`).join("");
    const empty=`<p class="eval-results-empty">No raw samples persisted${exp.failed_rollouts?` · ${esc(exp.failed_rollouts)} provider calls failed`:""}.</p>`;
    return `
      <details class="eval-result-card" ${index===experiments.length-1?"open":""}>
        <summary>
          <span class="eval-result-index">${String(index+1).padStart(2,"0")}</span>
          <span class="eval-result-name"><strong>${esc(exp.description||exp.version)}</strong><small>${esc(evalTime(exp.ts))}</small></span>
          <span class="eval-result-count"><b>${esc(exp.episodes_tried||episodes.length)}</b> episodes</span>
          <span class="eval-result-count"><b>${esc(exp.stored_samples||0)}</b> samples</span>
          <span class="eval-result-status ${status.toLowerCase().replace(" ","-")}">${status}</span>
          <i class="fa-solid fa-chevron-down"></i>
        </summary>
        <div class="episode-list">${episodeRows||empty}</div>
      </details>`;
  }).join("")||'<p class="eval-results-empty">No evaluation evidence stored yet.</p>';
}

function renderExperiments(payload){
  state.experiments=payload;
  const exps=(payload.experiments||[]).map(exp=>({
    ...exp,
    retrieval_s:measured(exp.retrieval_s)?Number(exp.retrieval_s):null,
    prompt_injection_risk:measured(exp.prompt_injection_risk)?Number(exp.prompt_injection_risk):null,
    episodic_diff_lines:Number(exp.episodic_diff_lines??0),
    knowledge_regression:Number(exp.knowledge_regression??exp.agent_regression??0)
  }));
  const s=payload.summary||{};
  const loops=payload.loops||{};
  const sourceLabel=payload.source||"live Supabase evaluations";
  $("#improvement-evidence").textContent=`${s.experiments||exps.length} evals · ${loops.sources?.length||0} loop sources · ${sourceLabel}`;
  $("#seed-value").textContent=sourceLabel;
  $("#seed-eval-count").textContent=String(s.experiments??exps.length);
  $("#seed-kept-count").textContent=String(s.kept??exps.filter(exp=>exp.kept).length);
  $("#seed-loop-count").textContent=String(loops.sources?.length??0);
  const note=payload.seed_justification?.supabase_note||"";
  $("#seed-note").textContent=[
    note||"Measured evaluation history from Supabase.",
    loops.latest_experiment_id&&`latest ${loops.latest_experiment_id} · ${relativeTime(loops.latest_experiment_at)}`,
    s.episodes_tried||s.rollouts?`${s.episodes_tried||0} episodes · ${s.rollouts||0} rollouts`:"older cycle coverage was not persisted",
    "45s server/CDN cache · instant browser cache"
  ].filter(Boolean).join(" · ");
  $("#acc-delta").textContent=`${(s.accuracy_start??0).toFixed(3)} → ${(s.accuracy_now??0).toFixed(3)}`;
  $("#ret-delta").textContent=measured(s.retrieval_start)&&measured(s.retrieval_now)?`${Number(s.retrieval_start).toFixed(1)}s → ${Number(s.retrieval_now).toFixed(1)}s`:"not measured";
  $("#injection-delta").textContent=measured(s.prompt_injection_risk_start)&&measured(s.prompt_injection_risk_now)?`${Number(s.prompt_injection_risk_start).toFixed(1)} → ${Number(s.prompt_injection_risk_now).toFixed(1)}`:"not measured";
  $("#injection-empty").hidden=exps.some(exp=>measured(exp.prompt_injection_risk));
  $("#memory-delta").textContent=`${Number(s.episodic_diff_now??exps.at(-1)?.episodic_diff_lines??0).toFixed(0)} lines`;
  $("#knowledge-delta").textContent=`${Number(s.knowledge_regression_start??0).toFixed(3)} → ${Number(s.knowledge_regression_now??exps.at(-1)?.knowledge_regression??0).toFixed(3)}`;

  renderKarpathyChart("chart-accuracy", exps, "accuracy", {yLabel:"Decision quality"});
  renderKarpathyChart("chart-retrieval", exps, "retrieval_s", {yLabel:"Seconds per answer"});
  renderKarpathyChart("chart-injection", exps, "prompt_injection_risk", {yLabel:"Prompt injection risk"});
  renderKarpathyChart("chart-memory", exps, "episodic_diff_lines", {yLabel:"Hermes memory diff lines"});
  renderKarpathyChart("chart-knowledge", exps, "knowledge_regression", {yLabel:"Agent knowledge regression"});
  renderResearchDetail(exps.at(-1),"accuracy",exps.at(-2));
  updateMethodologyEvidence(payload);
}

async function loadExperiments(){
  const cached=readEvalCache();
  if(cached)renderExperiments(cached);
  try{
    const payload=await api("/api/autoresearch-experiments?detail=summary");
    writeEvalCache(payload);
    renderExperiments(payload);
  }catch(error){
    if(!cached){
      $("#improvement-evidence").textContent="Supabase evaluation history unavailable";
      $("#seed-note").textContent=error.message;
    }
  }
}

async function loadExperimentDetails(){
  if(state.experimentsDetailLoaded)return;
  $("#eval-results").innerHTML='<p class="eval-results-empty"><i class="fa-solid fa-spinner fa-spin"></i> Loading detailed Supabase evidence…</p>';
  try{
    const payload=await api("/api/autoresearch-experiments?detail=full");
    renderEvalResults(payload.experiments||[]);
    state.experimentsDetailLoaded=true;
  }catch(error){
    $("#eval-results").innerHTML=`<p class="eval-results-empty">${esc(error.message)}</p>`;
  }
}

function updateMethodologyEvidence(payload){
  const loops=payload.loops||{}, promotion=payload.promotion||{}, soul=loops.latest_soul||{};
  const details={
    0:`${payload.summary?.experiments||0} persisted experiments across ${loops.sources?.length||0} live sources. Latest: ${loops.latest_experiment_id||"waiting"} from ${loops.latest_source||"EC2"} (${relativeTime(loops.latest_experiment_at)}).`,
    2:`Hermes SOUL v${soul.version??"—"} wrote ${soul.diff_lines??0} diff lines. Latest promoted memory provenance: ${loops.git_hash?`git ${loops.git_hash}`:"hash pending"} · ${soul.summary||"Supabase versioned memory"}.`,
    8:`${promotion.pareto||"Only measured improvements advance."} ${promotion.nightly||"The prior champion remains available for rollback."}`,
    9:promotion.discord||"Evaluation summaries are posted as titled threads in the Discord #eval forum."
  };
  Object.entries(details).forEach(([index,detail])=>{
    const card=$(`.loop-card[data-loop-index="${index}"]`);
    if(card)card.dataset.loopDetail=detail;
  });
  if($("#loop-step-label")?.textContent.startsWith("Step 01"))$("#loop-step-detail").textContent=details[0];
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
  const stepLabel=$("#loop-step-label"), stepTitle=$("#loop-step-title"), stepDetail=$("#loop-step-detail");
  const showStep=card=>{
    const index=Number(card.dataset.loopIndex), title=$("h3",card)?.textContent||"Research Loop";
    stepLabel.textContent=`Step ${String(index+1).padStart(2,"0")} · live`;
    stepTitle.innerHTML=title.replace(" ","<br>");
    stepDetail.textContent=card.dataset.loopDetail||"Measured evidence moves through the recursive loop.";
  };
  cards.forEach(card=>{
    card.addEventListener("mouseenter",()=>showStep(card));
    card.addEventListener("focusin",()=>showStep(card));
  });
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
$("#eval-results-shell").addEventListener("toggle",event=>{if(event.currentTarget.open)loadExperimentDetails()});
window.addEventListener("hashchange",()=>showPage(location.hash.slice(1)||"dashboard"));

initRsiLoop();
Promise.allSettled([loadMarket(),loadDeals(),loadRsiIdeas(),loadExperiments()]);
showPage(location.hash.slice(1)||"dashboard");
