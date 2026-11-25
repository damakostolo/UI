import { useEffect, useRef, useState } from 'react';
import { allWidgets, labels, orders, type Layout, type Widget } from './layouts';

type Mode = 'static'|'rule'|'hybrid';
type Profile = {participant_id:string;token:string;current_layout:Layout};
type Suggestion = {request_id:string;model_name:string;current_layout:Layout;proposed_layout:Layout;confidence:number;decision:'propose'|'no_change';reasons:string[];synthetic_mode:boolean};
type Task = 'find_task'|'open_report'|'use_quick_action';
const api = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const taskTarget: Record<Task,Widget> = {find_task:'tasks',open_report:'reports',use_quick_action:'quick_actions'};
const taskNames: Record<Task,string> = {find_task:'Знайти завдання',open_report:'Відкрити звіт',use_quick_action:'Скористатися швидкою дією'};
const reasonText: Record<string,string> = {cold_start:'Ще замало дозволених подій.',low_confidence:'Оцінка моделі нижча за поріг.',low_gain:'Перевага над поточним макетом замала.',cooldown:'Період очікування після зміни ще триває.',active_task:'Під час завдання макет не змінюється.',same_layout:'Поточний макет уже відповідає пропозиції.',user_disabled:'Адаптацію вимкнено.',model_unavailable:'Модель недоступна; поточний макет збережено.',suggestion_available:'Система пропонує переглянути інший макет.'};

export default function App() {
  const [layout,setLayout] = useState<Layout>(() => (localStorage.getItem('layout') as Layout) || 'standard');
  const [mode,setMode] = useState<Mode>('static');
  const [consent,setConsent] = useState(false);
  const [profile,setProfile] = useState<Profile|null>(()=>{
    try { return JSON.parse(sessionStorage.getItem('research_profile')||'null') as Profile|null; } catch { return null; }
  });
  const [suggestion,setSuggestion] = useState<Suggestion|null>(null);
  const [previous,setPrevious] = useState<Layout|null>(null);
  const [lastAccepted,setLastAccepted] = useState<string|null>(null);
  const [paused,setPaused] = useState(false);
  const [demo,setDemo] = useState(false);
  const [message,setMessage] = useState('Статична панель готова. Збирання подій вимкнено.');
  const [activeTask,setActiveTask] = useState<Task|null>(null);
  const [taskCount,setTaskCount] = useState(0);
  const [done,setDone] = useState(false);
  const [reminder,setReminder] = useState(false);
  const [noticeVisible,setNoticeVisible] = useState(true);
  const [activityCount,setActivityCount] = useState(0);
  const [restoreToken,setRestoreToken] = useState('');
  const taskStart = useRef(0), clicks = useRef(0), sessionId = useRef('ses_'+crypto.randomUUID().replaceAll('-',''));
  useEffect(() => { localStorage.setItem('layout',layout); },[layout]);
  useEffect(() => {
    if (!profile) return;
    void fetch(api+'/consent',{headers:{Authorization:`Bearer ${profile.token}`}}).then(r=>r.ok?r.json():null).then(data=>{
      if (data?.enabled) setConsent(true);
    }).catch(()=>{});
  },[]);
  useEffect(() => {
    if (!suggestion) return;
    const onEscape = (e:KeyboardEvent) => { if (e.key==='Escape') void reject(); };
    window.addEventListener('keydown',onEscape);
    return () => window.removeEventListener('keydown',onEscape);
  },[suggestion]);

  async function request(path:string, method='GET', body?:unknown, token=profile?.token) {
    const response = await fetch(api+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:body?JSON.stringify(body):undefined});
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json();
  }
  async function grant() {
    try {
      const p:Profile = profile || await request('/profiles','POST');
      await request('/consent','POST',{version:'draft-1'},p.token);
      sessionStorage.setItem('research_profile',JSON.stringify(p)); setProfile(p); setConsent(true); setMessage('Згоду на мінімальні події ввімкнено. Її можна відкликати будь-коли.');
    } catch { setMessage('API недоступний. Панель працює статично, події не зберігаються.'); }
  }
  async function revoke() {
    setConsent(false); setMode('static'); setSuggestion(null);
    try { if (profile) await request('/consent','DELETE'); } catch { /* local collection is already off */ }
    setMessage('Згоду відкликано. Нові події не надсилаються. Для очищення попередніх даних натисніть «Видалити профіль».');
  }
  function event(event_type:string,widget_id:Widget|'none'='none') {
    if (!consent || !profile) return;
    void request('/events','POST',{event_id:'evt_'+crypto.randomUUID().replaceAll('-',''),participant_id:profile.participant_id,session_id:sessionId.current,
      occurred_at:new Date().toISOString(),event_type,widget_id,source:'volunteer',is_synthetic:false,consent_version:'draft-1'}).catch(()=>setMessage('Подію не вдалося зберегти; роботу можна продовжити.'));
  }
  async function recommend() {
    if (!profile || !consent) { setMessage('Для рекомендацій потрібна явна згода та доступний API.'); return; }
    try {
      const result:Suggestion = await request('/recommendations','POST',{mode,current_layout:layout,active_task:Boolean(activeTask),enabled:!paused,synthetic_mode:demo});
      setSuggestion(result); setMessage(result.reasons.map(r=>reasonText[r]||r).join(' '));
      if (result.decision==='propose') event('layout_preview');
    } catch { setMessage('Рекомендація недоступна; макет залишився без змін.'); }
  }
  async function accept() {
    if (!suggestion || suggestion.decision!=='propose' || activeTask) return;
    try { await request(`/recommendations/${suggestion.request_id}/accept`,'POST'); } catch { setMessage('Підтвердження не збережене. Макет не змінено.'); return; }
    setPrevious(layout); setLayout(suggestion.proposed_layout); setLastAccepted(suggestion.request_id); event('layout_accept'); setSuggestion(null);
    setMessage('Макет змінено за вашим підтвердженням. Можна скасувати зміну.');
  }
  async function reject() {
    if (suggestion) { try { await request(`/recommendations/${suggestion.request_id}/reject`,'POST'); } catch {/* local reject still applies */} }
    setSuggestion(null); event('layout_reject'); setMessage('Пропозицію відхилено.');
  }
  async function undo() {
    if (!previous) return;
    const old=previous; setLayout(old); setPrevious(null); event('layout_undo');
    if (lastAccepted) { try { await request(`/recommendations/${lastAccepted}/undo`,'POST'); } catch { setMessage('Локально відновлено попередній макет; серверне узгодження очікує з’єднання.'); return; } }
    setMessage('Попередній макет відновлено.');
  }
  function startTask(task:Task) {
    if (!consent) { setMessage('Для дослідницького завдання потрібна добровільна згода.'); return; }
    taskStart.current=performance.now(); clicks.current=0; setActiveTask(task); event('task_start',taskTarget[task]);
    setMessage(`Завдання «${taskNames[task]}» розпочато. Скористайтеся відповідним віджетом.`);
  }
  async function openWidget(widget:Widget) {
    setActivityCount(n=>n+1);
    event(widget==='quick_actions'?'quick_action':'widget_open',widget);
    if (activeTask) {
      clicks.current++;
      if (widget===taskTarget[activeTask]) {
        const task=activeTask; setActiveTask(null); event('task_complete',widget); setTaskCount(n=>n+1);
        if (profile) {
          try { await request('/study/trials','POST',{trial_id:'tri_'+crypto.randomUUID().replaceAll('-',''),participant_id:profile.participant_id,
            session_id:sessionId.current,task_id:task,condition:mode,layout_variant:layout,sequence_index:taskCount,
            elapsed_ms:Math.round(performance.now()-taskStart.current),click_count:clicks.current,completed:true,error_count:Math.max(0,clicks.current-1),
            source:'volunteer',is_synthetic:false,consent_version:'draft-1'}); } catch { setMessage('Завдання завершено, але спробу не збережено.'); return; }
        }
        setMessage(`Завдання «${taskNames[task]}» завершено.`);
      }
    } else setMessage(`Відкрито віджет «${labels[widget]}».`);
  }
  async function exportData() {
    if (!profile) return;
    try { const data=await request('/export/me'); const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
      const link=document.createElement('a'); link.href=url; link.download='my-research-data.json'; link.click(); URL.revokeObjectURL(url); }
    catch { setMessage('Експорт недоступний.'); }
  }
  async function restore() {
    try {
      const data = await request('/export/me','GET',undefined,restoreToken.trim());
      const p:Profile = {participant_id:data.participant_id,token:restoreToken.trim(),current_layout:data.current_layout};
      sessionStorage.setItem('research_profile',JSON.stringify(p)); setProfile(p); setLayout(data.current_layout);
      const c=await request('/consent','GET',undefined,p.token); setConsent(Boolean(c.enabled)); setRestoreToken('');
      setMessage('Профіль відновлено за кодом доступу.');
    } catch { setMessage('Не вдалося відновити профіль: перевірте код і доступність API.'); }
  }
  async function removeProfile() {
    if (profile) { try { await request('/profile/me','DELETE'); } catch { setMessage('Видалення на сервері не підтверджено. Повторіть після відновлення з’єднання.'); return; } }
    sessionStorage.removeItem('research_profile'); setProfile(null); setConsent(false); setMode('static'); setLayout('standard'); setSuggestion(null); localStorage.removeItem('layout'); setMessage('Локальний профіль і серверні дані видалено.');
  }
  const cardText:Record<Widget,string>={tasks:'Поточні завдання та пріоритети',calendar:'Події та заплановані зустрічі',activity:'Огляд недавньої активності',quick_actions:'Найчастіші дії в один крок',reports:'Зведені звіти за період',notifications:'Важливі повідомлення'};
  const widgetContent:Record<Widget,React.ReactNode>={
    tasks:<div className="widget-content"><p><strong>{done?'✓ Завершено':'○ До виконання'}</strong> · Підготувати короткий звіт</p><button className="mini" onClick={()=>setDone(v=>!v)}>{done?'Повернути до роботи':'Позначити виконаним'}</button></div>,
    calendar:<div className="widget-content"><p><strong>Сьогодні</strong> · Огляд плану</p><p><strong>Завтра</strong> · Перевірка звіту</p></div>,
    activity:<div className="widget-content"><p>Відкриттів віджетів у цій вкладці: <strong>{activityCount}</strong></p><p>Завершених дослідницьких завдань: <strong>{taskCount}</strong></p></div>,
    quick_actions:<div className="widget-content"><p>{reminder?'Нагадування додано локально.':'Нагадування ще не додано.'}</p><button className="mini" onClick={()=>setReminder(v=>!v)}>{reminder?'Прибрати нагадування':'Додати нагадування'}</button></div>,
    reports:<div className="widget-content"><p>Локальний огляд поточної вкладки</p><p>Відкриттів: <strong>{activityCount}</strong> · Завдань: <strong>{done?1:0}</strong></p></div>,
    notifications:<div className="widget-content"><p>{noticeVisible?'Ознайомтеся з можливістю експорту й видалення даних.':'Немає непрочитаних сповіщень.'}</p>{noticeVisible&&<button className="mini" onClick={()=>setNoticeVisible(false)}>Позначити прочитаним</button>}</div>
  };
  return <div className={`app layout-${layout}`}>
    <a className="skip" href="#main">До основного вмісту</a>
    <header className="top"><div><span className="eyebrow">ДОСЛІДНИЦЬКИЙ ПРОТОТИП</span><h1>Робоча панель</h1><p>Три компонування · однакові функції · зміни під вашим контролем</p></div><div className="badge">{layout.toUpperCase()}</div></header>
    <nav aria-label="Основна навігація" className="nav">{allWidgets.map(w=><a key={w} href={'#'+w}>{labels[w]}</a>)}</nav>
    <main id="main">
      <section className="intro" aria-labelledby="overview"><div><span className="eyebrow">ОГЛЯД</span><h2 id="overview">Ваш простір для роботи</h2><p>Відкривайте модулі та виконуйте демонстраційні завдання. Макет змінюється лише після підтвердження.</p></div><div className="metric"><strong>06</strong><span>доступних модулів</span></div></section>
      <section className="controls" aria-labelledby="control-title"><h2 id="control-title">Керування адаптацією</h2>
        <div className="control-grid"><div><label htmlFor="mode">Режим</label><select id="mode" value={mode} onChange={e=>setMode(e.target.value as Mode)} disabled={!consent}><option value="static">Статичний</option><option value="rule">Правила</option><option value="hybrid">ML + контроль</option></select></div>
        <div><label htmlFor="layout">Макет вручну</label><select id="layout" value={layout} onChange={e=>{setPrevious(layout);setLayout(e.target.value as Layout);setSuggestion(null)}} disabled={Boolean(activeTask)}><option value="standard">Звичайний</option><option value="compact">Компактний</option><option value="focus">Фокус</option></select></div>
        <div className="check"><label><input type="checkbox" checked={paused} onChange={e=>setPaused(e.target.checked)} /> Пауза адаптації</label></div>
        <div className="check"><label><input type="checkbox" checked={demo} onChange={e=>setDemo(e.target.checked)} /> DEMO: синтетична ML-модель</label></div></div>
        <div className="actions"><button onClick={recommend} disabled={!consent || mode==='static'}>Отримати пропозицію</button><button className="secondary" onClick={undo} disabled={!previous || Boolean(activeTask)}>Скасувати зміну</button></div>
        {suggestion && <div className="suggestion" role="status"><strong>Система пропонує: {suggestion.proposed_layout}</strong><p>{suggestion.reasons.map(r=>reasonText[r]||r).join(' ')} {suggestion.synthetic_mode?'DEMO — синтетична модель, без висновку про реальних людей.':''}</p><p>Оцінка моделі: {Math.round(suggestion.confidence*100)}%. Це ймовірність прогнозованої переваги, не обіцянка швидшої роботи.</p>{suggestion.decision==='propose' && <div className="preview" aria-label="Попередній перегляд порядку віджетів"><span>Порядок після підтвердження:</span><ol>{orders[suggestion.proposed_layout].map(w=><li key={w}>{labels[w]}</li>)}</ol></div>}{suggestion.decision==='propose' && <button onClick={accept} disabled={Boolean(activeTask)}>Підтвердити зміну</button>}<button className="secondary" onClick={reject}>Відхилити</button></div>}
      </section>
      <section className="dashboard" aria-label="Віджети панелі">{orders[layout].map((w,i)=><article id={w} key={w} className={`card card-${w} ${layout==='focus'&&i===0?'featured':''}`}><div className="card-top"><span className="card-number">0{i+1}</span><span aria-hidden="true" className="dot"/></div><h2>{labels[w]}</h2><p>{cardText[w]}</p>{widgetContent[w]}<button data-testid={`open-${w}`} onClick={()=>void openWidget(w)}>Відкрити {labels[w].toLowerCase()}</button></article>)}</section>
      <section className="study" aria-labelledby="study-title"><span className="eyebrow">ДОСЛІДЖЕННЯ</span><h2 id="study-title">Виконання завдань</h2><p>Спроби записуються лише за згодою. Час, кількість дій і успішність належать до окремого UX-досліду.</p><div className="actions">{(Object.keys(taskNames) as Task[]).map(t=><button key={t} className="secondary" onClick={()=>startTask(t)} disabled={!consent || Boolean(activeTask)}>{taskNames[t]}</button>)}</div>{activeTask&&<p className="task-active">Активне завдання: {taskNames[activeTask]}. Макет тимчасово заблоковано.</p>}</section>
      <section className="privacy" aria-labelledby="privacy-title"><span className="eyebrow">ПРИВАТНІСТЬ</span><h2 id="privacy-title">Ваші дані</h2><p>За замовчуванням нічого не збирається. За згодою записуються лише тип віджета, тип дії та показники завдання. Текст полів, URL, IP і cookies не входять до набору даних.</p><div className="actions">{consent?<button onClick={revoke}>Відкликати згоду</button>:<button onClick={grant}>Надати згоду на події</button>}<button className="secondary" onClick={exportData} disabled={!profile}>Експортувати мої дані</button><button className="danger" onClick={removeProfile} disabled={!profile}>Видалити профіль</button></div><div className="recovery">{profile?<><p className="small">Збережіть код доступу, якщо потрібно повернутися до експорту або видалення після закриття вкладки. Не передавайте його іншим.</p><button className="secondary" onClick={()=>void navigator.clipboard.writeText(profile.token).then(()=>setMessage('Код доступу скопійовано.')).catch(()=>setMessage('Не вдалося скопіювати код.'))}>Скопіювати код доступу</button></>:<><label htmlFor="restore-token">Код доступу для відновлення профілю</label><input id="restore-token" type="password" value={restoreToken} onChange={e=>setRestoreToken(e.target.value)} autoComplete="off" /><button className="secondary" onClick={restore} disabled={!restoreToken.trim()}>Відновити профіль</button></>}</div><p className="small">Версія тексту згоди: draft-1. Для реального дослідження процедура має бути погоджена окремо.</p></section>
      <p className="live" role="status" aria-live="polite">{message}</p>
    </main><footer>Локальний дослідницький прототип · 2026</footer>
  </div>;
}
