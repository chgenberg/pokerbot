import React, { useReducer, useRef, useEffect, useCallback } from 'react';
import ScenarioBuilder from './ScenarioBuilder';
import './ChatInterface.css';

const API_URL = 'https://pokerbot.onrender.com';

const MODES = {
  coaching: { label: 'Coaching', icon: '🎯', desc: 'Ask about hands, positions or scenarios.' },
  questions: { label: 'Questions', icon: '❓', desc: 'Ask any poker question.' }
};

// --- Markdown-stripper ---
function stripMarkdown(text) {
  let clean = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/__(.*?)__/g, '$1');
  clean = clean.replace(/\*(.*?)\*/g, '$1').replace(/_(.*?)_/g, '$1');
  clean = clean.replace(/^#+\s?/gm, '');
  clean = clean.replace(/^>\s?/gm, '');
  clean = clean.replace(/^\s*[-*+]\s+/gm, '');
  clean = clean.replace(/^\s*\d+\.\s+/gm, '');
  clean = clean.replace(/\[(.*?)\]\(.*?\)/g, '$1');
  clean = clean.replace(/`{1,3}[^`]*`{1,3}/g, '');
  clean = clean.replace(/([^\n])\n([^\n])/g, '$1\n\n$2');
  return clean.trim();
}

const initial = {
  showSkillModal: !localStorage.getItem('pokerSkillLevel'),
  skill: localStorage.getItem('pokerSkillLevel') || null,
  mode: 'coaching',
  messages: [{ sender: 'bot', text: 'Welcome! Ask me anything about poker strategy.' }],
  input: '',
  loading: false,
  recording: false,
  showScenario: false
};

function reducer(state, action) {
  switch (action.type) {
    case 'SET_SKILL':
      return { ...state, skill: action.value };
    case 'START_CHAT':
      return { ...state, showSkillModal: false, messages: [{ sender: 'bot', text: action.welcome }] };
    case 'SET_MODE':
      return { ...state, mode: action.mode, messages: [{ sender: 'bot', text: MODES[action.mode].desc }], input: '' };
    case 'SET_INPUT':
      return { ...state, input: action.value };
    case 'PUSH':
      return { ...state, messages: [...state.messages, action.message] };
    case 'LOADING':
      return { ...state, loading: action.value };
    case 'TOGGLE_SCENARIO':
      return { ...state, showScenario: !state.showScenario };
    default:
      return state;
  }
}

export default function ChatInterface() {
  const [state, dispatch] = useReducer(reducer, initial);
  const chatRef = useRef(null);
  const inputRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      requestAnimationFrame(() => {
        chatRef.current.scrollTop = chatRef.current.scrollHeight;
      });
    }
  }, [state.messages, state.loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [state.mode]);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape' && state.showScenario) dispatch({ type: 'TOGGLE_SCENARIO' });
      if (e.ctrlKey && e.key === 'ArrowUp') inputRef.current?.focus();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [state.showScenario]);

  // --- Send message (text) ---
  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;
    dispatch({ type: 'PUSH', message: { sender: 'user', text } });
    dispatch({ type: 'LOADING', value: true });

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Mode': state.mode, 'X-Skill-Level': state.skill || '' },
        body: JSON.stringify({ question: text, chat_history: state.messages.map(m => [m.sender, m.text]) }),
        signal: abortRef.current.signal
      });
      const data = await res.json();
      dispatch({ type: 'PUSH', message: { sender: 'bot', text: stripMarkdown(data.answer) } });
    } catch (e) {
      if (e.name !== 'AbortError') dispatch({ type: 'PUSH', message: { sender: 'bot', text: '⚠️ Network error' } });
    }
    dispatch({ type: 'LOADING', value: false });
  }, [state.mode, state.skill, state.messages]);

  // --- Scenario submit ---
  const handleScenarioSubmit = async (payload) => {
    dispatch({ type: 'PUSH', message: { sender: 'user', text: '[Scenario submitted]' } });
    dispatch({ type: 'LOADING', value: true });
    try {
      const res = await fetch(`${API_URL}/solve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const d = await res.json();
      dispatch({ type: 'PUSH', message: { sender: 'bot', text: stripMarkdown(`Optimal: ${d.bestMove}\n\nEquity: ${d.equity}%`) } });
    } catch {
      dispatch({ type: 'PUSH', message: { sender: 'bot', text: '⚠️ Could not solve right now.' } });
    }
    dispatch({ type: 'LOADING', value: false });
  };

  // --- Mode change, input, key ---
  const changeMode = (m) => dispatch({ type: 'SET_MODE', mode: m });
  const onInput = (e) => dispatch({ type: 'SET_INPUT', value: e.target.value });
  const onKey = (e) => { if (e.key === 'Enter' && !state.loading) { sendMessage(state.input); dispatch({ type: 'SET_INPUT', value: '' }); } };

  // --- Render ---
  return (
    <div className="app-card minimalist">
      <Header />
      {/* chat log */}
      <section className="chat-area" role="log" aria-live="polite" ref={chatRef}>
        {state.messages.map((m, i) => (
          <div key={i} className={`message-row ${m.sender}`}>
            <div className={`bubble ${m.sender}`}>
              {stripMarkdown(m.text).split(/\n{2,}/).map((para, j) => (
                <div key={j} style={{ marginBottom: 8 }}>{para}</div>
              ))}
            </div>
          </div>
        ))}
        {state.loading && <div className="message-row bot"><div className="bubble bot">…</div></div>}
      </section>
      {/* mode switcher */}
      <nav className="mode-buttons-row minimalist">
        {Object.entries(MODES).map(([k, v]) => (
          <button key={k} className={`mode-btn minimalist${state.mode === k ? ' active' : ''}`} onClick={() => changeMode(k)}>
            {v.icon} {v.label}
          </button>
        ))}
      </nav>
      {/* input row */}
      <div className="input-row minimalist">
        <button className="scenario-btn minimalist" aria-label="Build scenario" onClick={() => dispatch({ type: 'TOGGLE_SCENARIO' })}>🃏</button>
        <input ref={inputRef} className="text-input minimalist" value={state.input} onChange={onInput} onKeyDown={onKey}
               placeholder={state.mode === 'coaching' ? 'Type a hand, position…' : 'Ask anything…'} disabled={state.loading} />
        <button className="mic-btn minimalist" onClick={() => { sendMessage(state.input); dispatch({ type: 'SET_INPUT', value: '' }); }} disabled={state.loading}>➤</button>
      </div>
      {/* modals */}
      {state.showSkillModal && <SkillModal skill={state.skill} dispatch={dispatch} />}
      {state.showScenario && <ScenarioBuilder onClose={() => dispatch({ type: 'TOGGLE_SCENARIO' })} onSubmit={handleScenarioSubmit} />}
    </div>
  );
}

/* ---------------- sub-components ---------------- */
function Header() {
  return (
    <header className="header-solid">
      <img src="/Prom.png" alt="Logo" className="logo-img" />
      <h1 className="title">POKER COACH</h1>
    </header>
  );
}

function SkillModal({ skill, dispatch }) {
  const select = (level) => dispatch({ type: 'SET_SKILL', value: level });
  const start  = () => {
    if (!skill) return;
    localStorage.setItem('pokerSkillLevel', skill);
    const label = skill <= 2 ? 'Beginner' : skill >= 9 ? 'Expert' : 'Intermediate';
    dispatch({ type: 'START_CHAT', welcome: `Welcome! Skill level set to ${skill} (${label}).` });
  };
  return (
    <div className="skill-modal-overlay">
      <div className="skill-modal" role="dialog" aria-modal="true">
        <h2>Rate your poker skills</h2>
        <p className="skill-desc">Select a level to personalise coaching.</p>
        <div className="skill-scale">{Array.from({ length: 10 }, (_, i) => (
          <button key={i+1} className={`skill-number${skill===(i+1)?' selected':''}`} onClick={() => select(i+1)}>{i+1}</button>
        ))}</div>
        <div className="skill-labels">
          <span>Beginner</span>
          <span>Expert</span>
        </div>
        <button className="start-chat-btn" disabled={!skill} onClick={start}>Start Chat</button>
      </div>
    </div>
  );
}