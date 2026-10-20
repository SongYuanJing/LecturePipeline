'use strict';
// Visual shell and SVG icons retained from the 00.03S Liquid Glass prototype.
// VIC-28 reads versioned host snapshots; no pipeline commands are implemented.
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const paths = {
  wave:'M4 14v-4m4 8V6m4 15V3m4 15V6m4 8v-4',
  home:'M3 10 12 3l9 7M5 9v11h5v-6h4v6h5V9',
  library:'M4 4h4v16H4zM10 4h4v16h-4zM16 5l4-1 3 15-4 1z',
  inbox:'M4 4h16l2 11v5H2v-5L4 4zm-2 11h6l2 3h4l2-3h6',
  courses:'M3 5c4-2 7-2 9 0 2-2 5-2 9 0v15c-4-2-7-2-9 0-2-2-5-2-9 0V5zm9 0v15',
  spark:'m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3zm7-1v4m-2-2h4',
  check:'m5 12 4 4L19 6',
  checkCircle:'M22 11.1V12a10 10 0 1 1-5.9-9.1M22 4l-10 10-3-3',
  alert:'m10.3 3.9-8.5 15A1.4 1.4 0 0 0 3 21h18a1.4 1.4 0 0 0 1.2-2.1l-8.5-15a2 2 0 0 0-3.4 0zM12 9v4m0 4h.01',
  error:'M12 8v5m0 4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  settings:'m9 3-1 3-3 1-2 4 2 2v4l4 3 3-1 3 1 4-3v-4l2-2-2-4-3-1-1-3H9zm6.5 9a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0',
  chevron:'m9 5 7 7-7 7',down:'m6 9 6 6 6-6',close:'m6 6 12 12M6 18 18 6',
  plus:'M12 5v14M5 12h14',search:'M21 21l-5-5m2-6a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  arrow:'M5 12h14m-5-5 5 5-5 5',arrowUp:'M7 17 17 7H7m10 0v10',
  folder:'M3 6V4h6l2 3h10v14H3V6z',file:'M14 2H4v20h16V8l-6-6zm0 0v6h6M8 13h8m-8 4h6',
  cpu:'M6 6h12v12H6zM9 9h6v6H9zM9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4',
  play:'m8 4 13 8-13 8V4z',pause:'M7 4h3v16H7zM14 4h3v16h-3z',stop:'M5 5h14v14H5z',
  refresh:'M21 3v6h-6M3 21v-6h6M20 9A8 8 0 0 0 6 5L3 9m18 6-3 4a8 8 0 0 1-14-4',
  clock:'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0M12 6v6l4 2',
  upload:'M12 16V3M7 8l5-5 5 5M4 16v5h16v-5',download:'M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5',
  layers:'m12 3 10 6-10 6L2 9l10-6zm-10 12 10 6 10-6M2 12l10 6 10-6',
  shield:'m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6l9-4zm-4 10 3 3 5-6',
  eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  dialogue:'M21 11a9 9 0 0 1-9 9H3l1-5a9 9 0 1 1 17-4M8 10h8m-8 4h5',
  calendar:'M4 5h16v16H4zM8 3v4m8-4v4M4 10h16',
  tune:'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6M9 15v6',
  info:'M12 11v6m0-10h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  palette:'M12 3a9 9 0 1 0 0 18h2a2 2 0 0 0 0-4 2 2 0 0 1 0-4h3a4 4 0 0 0 4-4c0-3-4-6-9-6zm-5 7h.01M9 6h.01m5 1h.01M6 15h.01',
  up:'m6 15 6-6 6 6',link:'M10 13a5 5 0 0 0 7 0l4-4a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-4 4a5 5 0 0 0 7 7l2-2'
};
const icon = (name, cls='') => `<svg class="svg-icon ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
const button = (label, action, cls='', ico='') => `<button type="button" class="button ${cls}" data-action="${action}">${ico?icon(ico):''}${label}</button>`;
const iconButton = (label, action, ico) => `<button type="button" class="icon-button" data-action="${action}" aria-label="${label}" title="${label}">${icon(ico)}</button>`;
const tag = (label, color='', ico='') => `<span class="badge ${color}">${ico?icon(ico):''}${label}</span>`;

// No mock records or commands in this frontend. Source kind always comes from the host.
const ui={view:'home',filter:'all',course:'all',search:'',selected:null,glass:true,inspectorClosed:false};
let snapshot=null, transportError='', inFlight=false, timer=null, returnFocus=null;
const statusMeta={ready:['В очереди','clock',''],asr:['Распознавание','wave','purple'],publishing:['Публикация Raw','file','blue'],
  waiting_ai:['Ожидает ручной AI','spark','amber'],raw:['Raw готов','file','blue'],word:['Формирование Word','file','blue'],
  ai_ready:['AI принят · ожидает Word','check','purple'],vocabulary:['Словарь ожидает завершения','courses','amber'],
  done:['Готово','checkCircle','green'],waiting:['Ожидание','clock',''],error:['Ошибка','alert','red'],
  review:['Требует проверки','alert','amber'],problem:['Несогласованное состояние','alert','red']};
const rowList=()=>snapshot?.catalog||[];
const courseList=()=>snapshot?.courses||[];
const count=name=>snapshot?.counts?.[name]??'—';
const frozen=()=>snapshot?.source?.frozen===true;
const live=row=>!transportError&&snapshot?.available&&row?.progress?row.progress:null;
const chosen=()=>rowList().find(row=>row.id===ui.selected);
const known=number=>typeof number==='number'&&Number.isFinite(number);
const sourceName=()=>frozen()?'Синтетический пример':'Реальная DEV-установка';
const prettyTime=stamp=>stamp?new Date(stamp).toLocaleString('ru-RU',{hour12:false}):'нет данных';
const prettyDay=day=>day?new Date(day+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'short'}):'Дата неизвестна';
const sizeParts=n=>n===1?'1 часть':`${n??'—'} частей`;
const stageLabel=value=>({available:'Есть',missing:'Нет',unknown:'Неизвестно',completed:'Завершено',merged:'Обновлён',batch_pending:'Ожидается',legacy:'Старые данные',waiting_ai:'Ожидание',ai_result_ready:'AI принят',building:'Создаётся',vocabulary_pending:'Ожидается',problem:'Проверка',failed:'Ошибка'}[value]||value||'—');
const metaFor=row=>statusMeta[row.status]||[row.status_text||'Неизвестное состояние','info','amber'];
const rowBadge=row=>{const [name,ico,color]=metaFor(row);return tag(esc(name),color,ico);};
const identity=row=>`${row.course_display_name} · ${row.lecture_key}`;
const symbol=row=>{const index=Math.max(0,courseList().findIndex(c=>c.id===row.course_id));const colors=['#c7b0ed','#91c8bd','#a5bee4','#d8bb95'];return `<span class="course-icon" style="--course-color:${colors[index%colors.length]}" aria-hidden="true">${esc((row.course_display_name||row.course_id||'?').slice(0,1))}</span>`;};
const titleBlock=(title,subtitle,actions='')=>`<div class="page-title"><div><h1>${title}</h1><p>${subtitle}</p></div><div class="page-title-actions">${actions||button('Обновить снимок','refresh','','refresh')}</div></div>`;
const empty=(title,text,ico='library')=>`<div class="empty-state"><span class="empty-symbol">${icon(ico)}</span><h2>${title}</h2><p>${text}</p></div>`;
function navItem(label,ico,view,filter='all',n=null){const active=ui.view===view&&(view!=='catalog'||ui.filter===filter);return `<button type="button" class="nav-item ${active?'active':''}" data-nav="${view}" data-filter="${filter}" title="${label}" ${active?'aria-current="page"':''}>${icon(ico)}<span class="label">${label}</span>${n!==null?`<span class="count">${n}</span>`:''}</button>`;}
function renderShell(){
  $('#sidebar').innerHTML=`<div class="brand"><span class="brandmark">${icon('wave')}</span><div class="brand-name">Lecture Pipeline<span>VIC-28 · Work S</span></div></div><div class="workspace-button"><span class="workspace-tile">${icon('layers')}</span><span class="workspace-label">${esc(snapshot?.workspace?.name||'DEV')}<small>Только чтение</small></span></div><p class="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</p><nav class="nav-group">${navItem('Обзор','home','home')}${navItem('Все лекции','library','catalog','all',count('total'))}${navItem('Входящие','inbox','inbox','all',count('pending'))}${navItem('Курсы','courses','courses','all',snapshot?courseList().length:'—')}</nav><p class="nav-label">ПОДБОРКИ</p><nav class="nav-group">${navItem('Ожидают AI','spark','catalog','waiting_ai',count('waiting_ai'))}${navItem('Готовые','checkCircle','catalog','done',count('done'))}${navItem('Требуют внимания','alert','catalog','problems',count('problems'))}</nav><div class="side-bottom">${navItem('Источник и диагностика','settings','diagnostics')}<button class="nav-item" data-action="glass" title="Уменьшить прозрачность">${icon('palette')}<span class="label">${ui.glass?'Уменьшить прозрачность':'Вернуть Liquid Glass'}</span></button><div class="side-note"><strong>${icon('shield')}Read-only DEV</strong>Pipeline, updater и Tk GUI не изменяются.</div><div class="side-version"><span>VIC-28 · preview 1</span><button data-action="fallback" title="Штатный Tk GUI" aria-label="Штатный Tk GUI">${icon('layers')}</button></div></div>`;
  $('#topbar').innerHTML=`<div class="breadcrumbs"><span>${esc(snapshot?.workspace?.id||'DEV')}</span>${icon('chevron')}<span class="current">${{home:'Обзор',catalog:'Лекции',inbox:'Входящие',courses:'Курсы',diagnostics:'Диагностика'}[ui.view]}</span></div><div class="top-actions"><label class="global-search">${icon('search')}<input id="global-search" type="search" value="${esc(ui.search)}" placeholder="Название, курс, дата…" aria-label="Поиск по лекциям"><kbd>Ctrl K</kbd></label><span class="demo-control source-pill ${frozen()?'fixture-source':''}">${icon(frozen()?'eye':'shield')}<span>${frozen()?'СИНТЕТИЧЕСКИЙ ПРИМЕР':'DEV · ТОЛЬКО ЧТЕНИЕ'}</span></span>${iconButton('Обновить снимок','refresh','refresh')}</div>`;
  $('#statusbar').innerHTML=`<span class="status-source">${icon('shield')}GET-only · локально</span><span class="separator"></span><span>${transportError?'Связь потеряна':frozen()?'Зафиксированный пример':snapshot?.available?'Чтение DEV подключено':'Источник недоступен'}</span><span class="spacer"></span><button data-action="fallback">${icon('layers')}Tk GUI сохранён</button><span class="secondary-status">${frozen()?'СИНТЕТИЧЕСКИЕ ДАННЫЕ':snapshot?'Снимок '+prettyTime(snapshot.captured_at):'Ожидание снимка'}</span>`;
}
function render(){
  const focus=document.activeElement?.id,pos=focus==='global-search'?document.activeElement.selectionStart:null;
  const scroll=$('#main').scrollTop,detailScroll=$('.inspector-content')?.scrollTop||0;
  renderShell();
  let content='';
  if(!snapshot?.available)content=`${titleBlock('Dashboard DEV','Чтение состояний существующего Lecture Pipeline.')}<section class="panel">${empty('Источник пока недоступен',esc(transportError||snapshot?.errors?.join(' · ')||'Получаем первый снимок. Данные не подставляются.'),'alert')}</section>`;
  else content=({home:renderHome,catalog:renderCatalog,inbox:renderInbox,courses:renderCourses,diagnostics:renderDiagnostics}[ui.view])();
  const banner=transportError?`<div class="source-banner stale-source" role="alert">${icon('alert')}<span><strong>Нет свежего снимка.</strong> Показаны последние полученные состояния. Процент, N/M, ETA и наблюдаемое устройство скрыты.</span></div>`:frozen()?`<div class="source-banner fixture-source">${icon('eye')}<span><strong>Синтетический проверочный набор.</strong> Зафиксированный пример для оценки UI. К реальным лекциям, workers и GPU он не относится.</span></div>`:`<div class="source-banner">${icon('shield')}<span><strong>Реальные read-only данные DEV.</strong> Автообновление каждые 3 секунды. Записи и системные действия отключены.</span></div>`;
  const readWarning=snapshot?.errors?.length?`<div class="callout red read-warning" role="alert" style="margin-bottom:16px">${icon('alert')}<div><strong>Данные каталога неполны</strong>Есть ошибки чтения. Нулевой каталог и итоговые счётчики не подтверждены. <button class="text-button" data-nav="diagnostics">Показать причины</button></div></div>`:'';
  $('#main').innerHTML=banner+readWarning+content;
  $('#main').scrollTop=scroll;if($('.inspector-content'))$('.inspector-content').scrollTop=detailScroll;
  fitInspector();
  document.body.classList.toggle('no-glass',!ui.glass);
  if(focus==='global-search'){const el=$('#global-search');el.focus();if(pos!==null)el.setSelectionRange(pos,pos);}
}
function fitInspector(){
  const inspector=$('.inspector');if(!inspector)return;
  if(innerWidth<=760||innerHeight<=650){inspector.style.maxHeight='none';return;}
  const room=$('#statusbar').getBoundingClientRect().top-inspector.getBoundingClientRect().top-12;
  inspector.style.maxHeight=Math.max(180,room)+'px';
}
function workerPanel(worker){
  const healthy=worker.health==='fresh',stale=worker.health==='stale'||transportError;
  const state=transportError?'Связь потеряна':worker.health==='missing'?'Нет heartbeat':worker.health==='invalid'?'Ошибка heartbeat':stale?'Heartbeat устарел':worker.reported_state==='RUNNING'?'Работает':worker.reported_state==='STOPPED'?'Остановлен':worker.reported_state||'Неизвестно';
  return `<section class="panel worker-card"><span class="worker-symbol ${healthy&&worker.reported_state==='RUNNING'&&!transportError?'green':''}">${icon(worker.id==='lecture'?'wave':'dialogue')}</span><div><span class="eyebrow">${esc(worker.label)}</span><strong>${esc(state)}</strong><small>${frozen()?'На момент снимка · ':''}${worker.heartbeat_at?`Heartbeat ${esc(known(worker.heartbeat_age_seconds)?Math.round(worker.heartbeat_age_seconds)+' с назад':'неизвестен')}`:'Наблюдений запуска нет'}</small></div><span class="health-dot ${healthy&&worker.reported_state==='RUNNING'&&!transportError?'green':stale?'amber':''}" aria-hidden="true"></span></section>`;
}
function devicePanel(){
  const observed=transportError?null:snapshot.device.observed;
  const device=typeof observed==='object'?observed?.device:observed;
  const gpu=typeof device==='string'&&/cuda|gpu/i.test(device);
  const configured=snapshot.device.configured||'неизвестен';
  return `<section class="panel worker-card"><span class="worker-symbol ${device?'green':''}">${icon('cpu')}</span><div><span class="eyebrow">ASR · large-v3</span><strong>${device?(gpu?'GPU · CUDA':'CPU · '+esc(device)):esc(configured.toUpperCase())+' выбран'}</strong><small>${device?'По свежему ASR-наблюдению':'Фактическое устройство неизвестно'}</small></div></section>`;
}
function metrics(){return `<div class="metrics">${[['ready','В очереди','clock'],['asr','Этап ASR','wave'],['waiting_ai','Ожидают ручной AI','spark'],['done','Завершено','checkCircle']].map(([key,label,ico])=>`<button class="metric" data-metric="${key}"><span class="metric-icon ${key==='done'?'green':key==='waiting_ai'?'amber':''}">${icon(ico)}</span><span><span class="metric-number mono">${count(key)}</span><span class="metric-label" style="display:block">${label}</span></span></button>`).join('')}</div>`;}
function progressView(row,compact=false){
  const p=live(row), percent=p?.stage==='asr'&&known(p.percent)?p.percent:null;
  const eta=p?.stage==='asr'&&known(p.eta_seconds)?p.eta_seconds:null;
  if(compact)return `<span class="mini-progress-label mono">${p?`${p.part_index}/${p.part_count} · ${percent===null?'процент неизвестен':Math.round(percent)+'%'}`:'Нет свежей телеметрии'}</span>`;
  return `<div class="progress-meta"><span>${percent!==null?`<strong class="mono">${Math.round(percent)}<small>%</small></strong>`:p?'<span>Процент недоступен</span>':'<span>Нет свежей телеметрии</span>'}</span><span>${eta!==null?'ETA ASR ≈ '+Math.max(1,Math.ceil(eta/60))+' мин':p?.stage==='asr'?'ETA недоступен':'ETA не наблюдается'}</span></div><div class="progress-track ${p&&percent===null?'indeterminate':''}" ${percent!==null?`role="progressbar" aria-label="Прогресс ASR" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"`:`role="status" aria-label="Прогресс неизвестен"`}><i class="progress-fill" style="width:${percent??0}%"></i></div><div class="parts-inline"><span>${p?`Текущая часть ${p.part_index} из ${p.part_count}`:`Состав: ${sizeParts(row.parts)} · текущая часть неизвестна`}</span><span>${p?esc(p.backend?.compute_type||''):''}</span></div>`;
}
function activity(){
  const rows=rowList().filter(row=>['asr','publishing'].includes(row.status)),row=rows.find(r=>live(r))||rows[0];
  if(!row&&snapshot.counts===null)return `<section class="active-job glass idle-job"><div class="active-job-head"><span class="eyebrow">ТЕКУЩАЯ ОБРАБОТКА</span>${tag('Ошибка чтения','red','alert')}</div><h2 class="job-title">Данные каталога неполны</h2><p class="job-subtitle">Не удалось прочитать часть состояний. Отсутствие лекций и обработки не подтверждено.</p><div class="unknown-values"><span>N/M <b>—</b></span><span>Процент <b>—</b></span><span>ETA <b>—</b></span></div></section>`;
  if(!row)return `<section class="active-job glass idle-job"><div class="active-job-head"><span class="eyebrow">ТЕКУЩАЯ ОБРАБОТКА</span>${tag('Наблюдений ASR нет','','clock')}</div><h2 class="job-title">${rowList().length?'Сейчас нет наблюдаемого ASR':'В DEV ещё нет лекций'}</h2><p class="job-subtitle">${rowList().length?'Этапы и результаты остаются в каталоге.':'Очередь пуста. Данные появятся после штатного приёма отдельной DEV-установкой.'}</p><div class="unknown-values"><span>N/M <b>—</b></span><span>Процент <b>—</b></span><span>ETA <b>—</b></span></div></section>`;
  return `<section class="active-job glass"><div class="active-job-head"><span class="eyebrow">${live(row)?'ТЕКУЩАЯ ОБРАБОТКА':'ПОСЛЕДНИЙ ИЗВЕСТНЫЙ ЭТАП'}</span>${rowBadge(row)}</div><h2 class="job-title">${esc(row.course_display_name)}</h2><p class="job-subtitle">Лекция ${esc(row.lecture_key)} · ${prettyDay(row.lecture_date)}</p>${progressView(row)}<div class="job-detail-link"><button class="text-button" data-row="${esc(row.id)}">Подробности ${icon('arrow')}</button></div></section>`;
}
function table(rows){
  return `<table class="lecture-table"><colgroup><col style="width:47%"><col class="optional-date" style="width:15%"><col style="width:32%"><col style="width:6%"></colgroup><thead><tr><th scope="col">Курс / лекция</th><th scope="col" class="optional-date">Дата</th><th scope="col">Этап</th><th scope="col"><span class="sr-only">Карточка</span></th></tr></thead><tbody>${rows.map(row=>`<tr class="${row.id===ui.selected?'selected':''}" data-row="${esc(row.id)}"><td><div class="lecture-name-cell">${symbol(row)}<div class="lecture-title-wrap"><button class="lecture-title-btn" data-row="${esc(row.id)}" title="${esc(identity(row))}">${esc(row.course_display_name)}</button><span class="lecture-sub">${esc(row.lecture_key)} · ${sizeParts(row.parts)}</span></div></div></td><td class="optional-date date-cell">${prettyDay(row.lecture_date)}</td><td>${rowBadge(row)}${['asr','publishing'].includes(row.status)?`<div class="mini-progress">${progressView(row,true)}</div>`:''}</td><td><button class="icon-button" data-row="${esc(row.id)}" aria-label="Карточка ${esc(row.lecture_key)}">${icon('chevron')}</button></td></tr>`).join('')}</tbody></table>`;
}
function selectedInspector(){
  const row=chosen();if(!row||ui.inspectorClosed)return sourcePanel();
  const stages=row.stages||{};
  const steps=[['ready','READY'],['asr','Распознавание'],['raw','Raw / TXT / SRT'],['ai','Ручной AI-этап'],['word','Word'],['vocabulary','Словарь / финализация']];
  const knownStage={ready:stages.ready==='available',asr:stages.raw==='available',raw:stages.raw==='available',ai:['completed','building','vocabulary_pending','ai_result_ready'].includes(stages.ai),word:stages.word==='available',vocabulary:['merged','completed'].includes(stages.vocabulary)};
  return `<aside class="inspector glass mobile-open" aria-label="Карточка лекции"><div class="inspector-top"><span class="eyebrow">КАРТОЧКА · READ ONLY</span>${iconButton('Закрыть карточку','close-inspector','close')}</div><div class="inspector-content"><div class="inspector-identity">${symbol(row)}<h2>${esc(row.course_display_name)}</h2><p>Лекция ${esc(row.lecture_key)}<br>${prettyDay(row.lecture_date)} · источник даты: ${esc(row.lecture_date_source)}</p>${rowBadge(row)}</div>${['asr','publishing'].includes(row.status)?`<section class="inspector-section">${progressView(row)}</section>`:''}${row.status==='waiting_ai'?`<section class="inspector-section"><div class="callout amber">${icon('spark')}<div><strong>Ожидается ручной AI</strong>Автоматическая отправка не подключена. Процент и время AI неизвестны.</div></div></section>`:''}${row.reasons?.length?`<section class="inspector-section"><div class="callout ${['problem','error'].includes(row.status)?'red':'amber'}">${icon('alert')}<div>${row.reasons.map(reason=>`<p>${esc(reason)}</p>`).join('')}</div></div></section>`:''}<section class="inspector-section"><div class="section-label">Состояния из backend</div><div class="stage-list">${steps.map(([id,label],index)=>`<div class="stage-row ${knownStage[id]?'passed':''}"><span class="stage-mark">${knownStage[id]?icon('check'):index+1}</span><span>${label}</span><small class="stage-state">${id==='asr'?live(row)?'Сейчас':knownStage.asr?'Готово':'—':esc(stageLabel(stages[id]))}</small></div>`).join('')}</div></section><section class="inspector-section"><dl class="info-pairs"><dt>Дата приёма</dt><dd>${esc(row.imported_at?prettyTime(row.imported_at):'Неизвестна')}</dd><dt>Время записи</dt><dd>${esc(row.recorded_at?prettyTime(row.recorded_at):'Неизвестно')}</dd><dt>Raw</dt><dd>${esc(stageLabel(stages.raw))}</dd><dt>Word</dt><dd>${esc(stageLabel(stages.word))}</dd><dt>Словарь</dt><dd>${esc(stageLabel(stages.vocabulary))}</dd></dl></section><section class="inspector-section"><p class="muted" style="font-size:10px">${esc(row.integrity||'Наблюдение backend')}</p></section></div><div class="inspector-actions"><span class="readonly-action">${icon('shield')}Только чтение. Открытие файлов и команды пока не подключены.</span></div></aside>`;
}
function sourcePanel(){return `<aside class="panel source-panel"><div class="panel-head"><h2>Прозрачные состояния</h2></div><div class="source-panel-body"><div class="source-item">${icon('file')}<div><strong>Raw: ${count('raw')}</strong><small>Наличие по существующему каталогу</small></div></div><div class="source-item">${icon('spark')}<div><strong>Ручной AI: ${count('waiting_ai')}</strong><small>Без API и выдуманного прогресса</small></div></div><div class="source-item">${icon('alert')}<div><strong>Проблемы: ${count('problems')}</strong><small>Причины из backend</small></div></div><div class="callout">${icon('info')}<div>Отсутствующий heartbeat означает отсутствие наблюдения. Состояние Windows-задачи здесь не проверяется.</div></div><button class="text-button" data-nav="diagnostics">Контракт и источник ${icon('arrow')}</button></div></aside>`;}
function renderHome(){
  if(!chosen())ui.selected=rowList().find(r=>live(r))?.id||rowList()[0]?.id||null;
  return `${titleBlock('Обзор','От записи — к готовому конспекту. Состояния существующего DEV backend.')}${metrics()}<div class="worker-grid">${snapshot.workers.map(workerPanel).join('')}${devicePanel()}</div><div class="dashboard-grid"><div class="dashboard-primary">${activity()}<section class="panel queue-panel"><div class="panel-head"><h2>Лекции и очередь</h2><button class="text-button" data-nav="catalog">Весь каталог ${icon('arrow')}</button></div>${rowList().length?table(rowList()):empty(snapshot.counts===null?'Каталог не подтверждён':'Каталог DEV пуст',snapshot.counts===null?'Проверьте ошибки чтения в диагностике.':'Это реальное состояние отдельной DEV-установки. Проверочные лекции сюда не добавляются.')}<div class="table-tail"><span>${count('total')} лекций · Raw ${count('raw')} · Inbox ${count('pending')}</span><span>Без записи состояния</span></div></section></div>${selectedInspector()}</div>`;
}
function filtered(){return rowList().filter(row=>(ui.course==='all'||row.course_id===ui.course)&&(ui.filter==='all'||ui.filter===row.status||ui.filter==='problems'&&['problem','review','error'].includes(row.status))&&`${identity(row)} ${row.lecture_date}`.toLowerCase().includes(ui.search.toLowerCase()));}
function renderCatalog(){
  const rows=filtered();if(!rows.find(r=>r.id===ui.selected))ui.selected=rows[0]?.id||null;
  return `${titleBlock(ui.filter==='waiting_ai'?'Ожидают ручной AI':ui.filter==='done'?'Готовые лекции':ui.filter==='problems'?'Требуют внимания':'Все лекции','Подтверждённые состояния и неизменяемые идентичности backend.')}<div class="filterbar"><div class="segmented">${[['all','Все'],['ready','В очереди'],['asr','ASR'],['waiting_ai','Ручной AI'],['done','Готовые']].map(([id,label])=>`<button data-filter="${id}" class="${id===ui.filter?'active':''}">${label}</button>`).join('')}</div><select id="course-filter" aria-label="Курс"><option value="all">Все курсы</option>${courseList().map(c=>`<option value="${esc(c.id)}" ${c.id===ui.course?'selected':''}>${esc(c.name)}</option>`).join('')}</select><span class="muted filter-count">${rows.length} из ${count('total')}</span></div><div class="catalog-layout"><section class="panel catalog-main">${rows.length?table(rows):empty('Записей не найдено',ui.search?'Попробуйте другое название.':'Для выбранного курса и этапа записей нет.')}<div class="table-tail"><span>${rows.length} записей</span><span>Read-only projection</span></div></section>${selectedInspector()}</div>`;
}
function renderInbox(){return `${titleBlock('Входящие','Непринятые материалы хранятся отдельно от каталога лекций.')}<section class="panel">${snapshot.pending.length?snapshot.pending.map(p=>`<article class="inbox-item"><div><h3>${esc(p.name)}</h3><p class="muted">${esc(p.course_display_name)} · ${esc(p.status)}</p><p class="inbox-reason">${esc(p.reason)}</p></div><div>${tag('Найдены части: '+p.parts.map(n=>n??'?').join(', '),'amber','layers')}</div><span class="muted" style="font-size:10px">Редактирование отключено</span></article>`).join(''):empty('Во Входящих нет материалов','Наблюдение не запускает Inbox и не создаёт lecture identity.','inbox')}</section>`;}
function renderCourses(){return `${titleBlock('Курсы','Конфигурация активного DEV workspace. Изменение настроек не подключено.')}<div class="course-grid">${courseList().map(c=>`<article class="panel course-card"><div class="course-card-head">${symbol({course_id:c.id,course_display_name:c.name})}<div><h2>${esc(c.name)}</h2><p>${esc(c.id)} · язык ${esc(c.language)}</p></div></div><div class="course-card-stats"><div>${rowList().filter(r=>r.course_id===c.id).length}<span>лекций</span></div><div>${c.enabled?'Включён':'Выключен'}<span>курс</span></div><div>${c.inbox_enabled?'Включён':'Не настроен'}<span>автоматический Inbox</span></div></div><button class="text-button" data-course="${esc(c.id)}">Открыть лекции ${icon('arrow')}</button></article>`).join('')}</div>`;}
function renderDiagnostics(){
  return `${titleBlock('Источник и диагностика','Факты о чтении данных. Без запуска preflight, GPU probe и системных задач.')}<div class="settings-panels"><section class="panel settings-block"><h2>${sourceName()}</h2><dl class="diagnostic-pairs"><dt>Контракт</dt><dd>${esc(snapshot.contract)}</dd><dt>Config</dt><dd>${esc(snapshot.source.config)}</dd><dt>DEV root</dt><dd>${esc(snapshot.source.dev_root)}</dd><dt>Workspace</dt><dd>${esc(snapshot.workspace?.id||'неизвестен')}</dd><dt>Версия установки</dt><dd>${esc(snapshot.version||'неизвестна')}</dd><dt>Ревизия</dt><dd>${esc(snapshot.revision)}</dd><dt>Снимок</dt><dd>${prettyTime(snapshot.captured_at)}</dd><dt>Длительность чтения</dt><dd>${snapshot.read_duration_ms} мс</dd><dt>Настройка ASR</dt><dd>${esc(snapshot.device.configured||'неизвестна')}</dd><dt>Фактическое устройство</dt><dd>${esc(transportError?'Связь потеряна':snapshot.device.observed?JSON.stringify(snapshot.device.observed):'Нет свежего ASR-наблюдения')}</dd><dt>Preflight</dt><dd>Не запускался этим UI</dd><dt>Windows Scheduler</dt><dd>Не опрашивается; управление отключено</dd></dl></section><section class="panel settings-block"><h2>Ошибки чтения</h2>${snapshot.errors.length?snapshot.errors.map(e=>`<div class="callout red">${icon('alert')}<div>${esc(e)}</div></div>`).join(''):'<p class="muted">Ошибок чтения каталога нет. Отсутствующие heartbeat показаны отдельно.</p>'}<h3 style="margin:18px 0 9px;font-size:12px">Прочитанные файлы (${snapshot.read_audit.file_count})</h3><pre class="diagnostics">${esc(snapshot.read_audit.files.join('\n')||'нет')}</pre><div class="callout green">${icon('shield')}<div>Содержимое аудио, Word и словаря не читается. В snapshot-контексте запись файлов и запуск процессов запрещены.</div></div></section></div>`;
}
function modal(title,content){
  const el=$('#modal');returnFocus=document.activeElement;el.innerHTML=`<div class="modal-header"><div><span class="eyebrow">VIC-28 · READ ONLY</span><h2 id="modal-title">${title}</h2></div>${iconButton('Закрыть диалог','close','close')}</div><div class="modal-body">${content}</div><div class="modal-footer">${button('Готово','close','primary')}</div>`;el.showModal();
}
function closeModal(){$('#modal').close();if(returnFocus?.isConnected)returnFocus.focus();}
async function refresh(){
  if(inFlight)return;inFlight=true;
  try{
    const response=await fetch('/api/v1/snapshot',{cache:'no-store',signal:AbortSignal.timeout(7000)});
    if(!response.ok)throw Error('HTTP '+response.status);
    const value=await response.json();if(value.contract!=='vic28.dashboard/1')throw Error('Версия контракта не поддерживается');
    snapshot=value;transportError='';
  }catch(error){transportError='Не удалось получить снимок: '+error.message;}
  finally{inFlight=false;render();}
}
document.addEventListener('click',event=>{
  const nav=event.target.closest('[data-nav]');if(nav){ui.view=nav.dataset.nav;ui.filter=nav.dataset.filter||'all';ui.search='';ui.course='all';ui.inspectorClosed=false;$('#main').scrollTop=0;return render();}
  const row=event.target.closest('[data-row]');if(row){ui.selected=row.dataset.row;ui.inspectorClosed=false;return render();}
  const course=event.target.closest('[data-course]');if(course){ui.view='catalog';ui.course=course.dataset.course;ui.filter='all';ui.search='';ui.inspectorClosed=false;return render();}
  const metric=event.target.closest('[data-metric]');if(metric){ui.view='catalog';ui.filter={ready:'ready',asr:'asr',waiting_ai:'waiting_ai',done:'done'}[metric.dataset.metric];ui.inspectorClosed=false;return render();}
  const filter=event.target.closest('[data-filter]');if(filter){ui.filter=filter.dataset.filter;ui.inspectorClosed=false;return render();}
  const action=event.target.closest('[data-action]')?.dataset.action;
  if(action==='refresh')return refresh();
  if(action==='glass'){ui.glass=!ui.glass;return render();}
  if(action==='close')return closeModal();
  if(action==='close-inspector'){ui.inspectorClosed=true;return render();}
  if(action==='fallback')return modal('Штатный Tk GUI сохранён',`<p class="muted">Этот Dashboard не заменяет существующий GUI и не управляет workers. Tk остаётся fallback и диагностическим интерфейсом.</p><div class="diagnostics" style="margin-top:15px">${esc(snapshot?.tk_fallback_entry||'Путь пока не получен')}</div><div class="callout">${icon('info')}<div>Для запуска используйте существующий DEV launcher. В этой версии веб-интерфейса запуск программ отключён.</div></div>`);
});
document.addEventListener('input',event=>{if(event.target.id==='global-search'){ui.search=event.target.value;ui.view='catalog';ui.inspectorClosed=false;render();}});
document.addEventListener('change',event=>{if(event.target.id==='course-filter'){ui.course=event.target.value;ui.inspectorClosed=false;render();}});
document.addEventListener('keydown',event=>{
  const dialog=$('#modal');
  if(event.key==='Escape'&&dialog.open){event.preventDefault();closeModal();}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'&&!dialog.open){event.preventDefault();$('#global-search').focus();}
  if(event.key==='Tab'&&dialog.open){const items=[...dialog.querySelectorAll('button:not(:disabled)')],first=items[0],last=items.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
});
$('#modal').addEventListener('cancel',event=>{event.preventDefault();closeModal();});
window.addEventListener('resize',fitInspector);
$('#main').addEventListener('scroll',()=>requestAnimationFrame(fitInspector),{passive:true});
render();refresh();timer=setInterval(()=>{if(!frozen())refresh();},3000);
