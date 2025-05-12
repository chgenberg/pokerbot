import React from 'react';
import ChatInterface from './components/ChatInterface';

function App() {
  return (
    <div style={{
      minHeight: '100vh',
      background: '#f5f5f7',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <ChatInterface />
    </div>
  );
}

export default App;