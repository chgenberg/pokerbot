{!showSkillModal && (
  <div className="app-card minimalist">
    {/* HEADER MED LOGO HÖGST UPP */}
    <div className="header-solid">
      <img src="/Prom.png" className="logo-img" alt="Poker Coach Logo" />
      <div className="title">POKER COACH</div>
    </div>
    {/* ...resten av chatten... */}
    <div className="chat-area" ref={chatDivRef}>
      {messages.map((msg, idx) => (
        <div
          key={idx}
          className={`message-row ${msg.sender === 'user' ? 'user' : 'bot'}`}
        >
          <div className={`bubble ${msg.sender}`}>
            {msg.text}
          </div>
        </div>
      ))}
      {loading && (
        <div className="message-row bot">
          <div className="bubble bot loading-bubble">
            <span className="dots"><span>.</span><span>.</span><span>.</span></span>
          </div>
        </div>
      )}
    </div>
    {/* ...resten av koden... */}
    <div className="input-row minimalist">
      {/* KORTSYMBOL-KNAPP TILL VÄNSTER OM INPUT */}
      <button
        className="scenario-btn minimalist"
        title="Build scenario"
        onClick={() => setShowScenario(true)}
      >
        <img src="/assets/ui/poker-chip.svg" className="scenario-chip" alt="Open scenario builder" />
      </button>
      <input
        className="text-input minimalist"
        type="text"
        placeholder={mode === 'coaching'
          ? "Type a hand, position or scenario..."
          : "Ask any poker question..."}
        value={inputText}
        onChange={e => setInputText(e.target.value)}
        onKeyDown={handleInputKeyDown}
        disabled={loading}
        ref={inputRef}
        style={{ marginRight: 8 }}
      />
      <button
        className={`mic-btn minimalist${isRecording ? ' recording' : ''}`}
        title={isRecording ? "Recording..." : "Hold to record"}
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={stopRecording}
      >
        {isRecording ? (
          <span className="mic-recording">
            <span className="mic-dot"></span> Recording...
          </span>
        ) : (
          <span className="mic-icon">🎤</span>
        )}
      </button>
    </div>
  </div>
)}

function stripMarkdown(text) {
  // Enkel regex för att ta bort **, __, #, *, >, etc.
  return text
    .replace(/[*_~`>#-]/g, '') // tar bort *, _, ~, `, >, #, -
    .replace(/\[(.*?)\]\(.*?\)/g, '$1'); // tar bort [länk](url)
} 