
import { useState, memo, useCallback, useMemo } from "react";
import "./ScenarioBuilder.css";

const ACCENT   = "#23173a";
const HIGHLIGHT = "#f1eafe";
const RED      = "#c62828";
const BLACK    = "#232323";

const POSITIONS_BY_PLAYERS = {
  2:["SB","BB"],
  3:["BTN","SB","BB"],
  4:["CO","BTN","SB","BB"],
  5:["HJ","CO","BTN","SB","BB"],
  6:["UTG","HJ","CO","BTN","SB","BB"],
  7:["UTG","HJ","CO","BTN","SB","BB","MP"],
  8:["UTG","UTG+1","HJ","CO","BTN","SB","BB","MP"],
  9:["UTG","UTG+1","UTG+2","HJ","CO","BTN","SB","BB","MP"],
 10:["UTG","UTG+1","UTG+2","UTG+3","HJ","CO","BTN","SB","BB","MP"],
};

const RANKS = ["A","K","Q","J","10","9","8","7","6","5","4","3","2"];
const SUITS = ["♥","♠","♦","♣"]; // specific order for 2×2 grid
const SUIT_COLORS = { "♠": BLACK, "♣": BLACK, "♥": RED, "♦": RED };

function ScenarioBuilder({ onClose, onSubmit }) {
  const [step, setStep]       = useState(0);
  const [players, setPlayers] = useState(6);
  const [position, setPos]    = useState("");
  const [actions, setActions] = useState({});
  const [cards, setCards]     = useState([]);

  const positions = useMemo(()=>POSITIONS_BY_PLAYERS[players],[players]);
  const progress  = ((step+1)/5)*100;

  const next = ()=> setStep(s=>s+1);
  const back = ()=> setStep(s=>s-1);
  const toggleAction = useCallback((p,a)=> setActions(prev=>({ ...prev,[`${p}_${a}`]:!prev[`${p}_${a}`] })),[]);
  const toggleCard   = useCallback((r,s)=>{
    const id=`${r}${s}`;
    setCards(prev=> prev.includes(id)?prev.filter(c=>c!==id): prev.length<2?[...prev,id]:prev);
  },[]);
  const finish = ()=>{ onSubmit({players,position,actions,cards}); onClose(); };

  return (
    <div className="scenario-overlay" role="dialog" aria-modal="true">
      <div className="scenario-card">
        <button className="close" onClick={onClose}>×</button>
        <div className="progress"><span style={{ width:`${progress}%` }} /></div>

        {/* Step 0 – players */}
        {step===0 && (
          <section className="step fade">
            <h2>Players at the table</h2>
            <div className="grid players">
              {Array.from({length:9},(_,i)=>i+2).map(n=>(
                <button key={n} className={`pill${players===n?' active':''}`} onClick={()=>{setPlayers(n);setPos('');}}>{n}</button>
              ))}
            </div>
            <footer><button className="primary" onClick={next}>Next</button></footer>
          </section>
        )}

        {/* Step 1 – position */}
        {step===1 && (
          <section className="step fade">
            <h2>Your position</h2>
            <div className="grid positions">
              {positions.map(p=>(
                <button key={p} className={`pill${position===p?' active':''}`} onClick={()=>setPos(p)}>{p}</button>
              ))}
            </div>
            <footer>
              <button onClick={back}>Back</button>
              <button className="primary" disabled={!position} onClick={next}>Next</button>
            </footer>
          </section>
        )}

        {/* Step 2 – actions */}
        {step===2 && (
          <section className="step fade">
            <h2>Actions before you</h2>
            <div className="actions-table">
              {positions.map(p=>(
                <div key={p} className="actions-row">
                  <span className="pos">{p}</span>
                  {['Fold','Call','Raise'].map(a=>(
                    <button key={a} className={`act-btn${actions[`${p}_${a}`]?' active':''}`} onClick={()=>toggleAction(p,a)}>{a}</button>
                  ))}
                </div>
              ))}
            </div>
            <footer>
              <button onClick={back}>Back</button>
              <button className="primary" onClick={next}>Next</button>
            </footer>
          </section>
        )}

        {/* Step 3 – cards */}
        {step===3 && (
          <section className="step fade">
            <h2>Your hole cards</h2>
            <div className="cards-board">
              {SUITS.map(s=> (
                <div key={s} className="suit-box">
                  {RANKS.map(r=>{
                    const id=`${r}${s}`;
                    const sel=cards.includes(id);
                    return (
                      <button key={id} className={`card-btn${sel?' active':''}`} style={{ color:SUIT_COLORS[s] }} onClick={()=>toggleCard(r,s)}>{r}{s}</button>
                    );
                  })}
                </div>
              ))}
            </div>
            {cards.length>0 && <div className="selected">{cards.map(c=><span key={c}>{c}</span>)}</div>}
            <footer>
              <button onClick={back}>Back</button>
              <button className="primary" disabled={cards.length!==2} onClick={next}>Next</button>
            </footer>
          </section>
        )}

        {/* Step 4 – summary */}
        {step===4 && (
          <section className="step fade">
            <h2>Summary</h2>
            <p className="center"><b>{players}</b> players – Position <b>{position}</b><br/>Hand: <b>{cards.join(' · ')||'–'}</b></p>
            <footer>
              <button onClick={back}>Back</button>
              <button className="primary" onClick={finish}>Get solution</button>
            </footer>
          </section>
        )}
      </div>
    </div>
  );
}

export default memo(ScenarioBuilder);