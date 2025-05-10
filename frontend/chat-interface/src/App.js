// /home/ubuntu/mcp_server_project/frontend/chat-interface/src/App.js
import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleInputChange = (event) => {
    setInput(event.target.value);
  };

  const displayMessage = (text, sender, type = 'text') => {
    setMessages(prevMessages => [...prevMessages, { text, sender, type }]);
  };

  const handleSendMessage = async () => {
    if (input.trim() === '') return;

    const userInput = input;
    displayMessage(userInput, 'user');
    setInput(''); // Clear input field immediately

    // Basic command parsing (very simplistic for now)
    // Example: "GET /dna/intent/api/v1/site"
    // Example: "POST /dna/intent/api/v1/template-programmer/template data:{\"name\":\"MyTemplate\"}"
    const parts = userInput.match(/^(\S+)\s+(\S+)(?:\s+data:(.+))?$/i);

    if (!parts) {
      displayMessage(`Invalid command format. Use: METHOD /path [data:{"key":"value"}]`, 'bot', 'error');
      return;
    }

    const method = parts[1].toUpperCase();
    const endpointPath = parts[2];
    let requestData = null;

    if (parts[3]) {
      try {
        requestData = JSON.parse(parts[3]);
      } catch (e) {
        displayMessage(`Invalid JSON data: ${e.message}`, 'bot', 'error');
        return;
      }
    }
    
    displayMessage(`Sending ${method} request to ${endpointPath}...`, 'bot');

    try {
      const response = await fetch('/api/catalyst/request', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          method: method,
          endpoint_path: endpointPath,
          data: requestData, // Will be null if not provided, backend handles this
          // params: {} // Add if query params are needed, parse from input
        }),
      });

      const responseBody = await response.json();

      if (!response.ok) {
        // Server responded with an error status code
        const errorMsg = responseBody.details || responseBody.error || JSON.stringify(responseBody);
        displayMessage(`Error ${response.status}: ${errorMsg}`, 'bot', 'error');
      } else {
        // Success
        if (response.status === 204) {
            displayMessage("Operation successful, no content returned.", 'bot');
        } else {
            displayMessage(JSON.stringify(responseBody, null, 2), 'bot', 'code');
        }
      }
    } catch (error) {
      console.error('Network error or failed to parse JSON:', error);
      displayMessage(`Network error or server is unreachable: ${error.message}`, 'bot', 'error');
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      handleSendMessage();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Catalyst Center API Chat</h1>
      </header>
      <div className="chat-window">
        <div className="messages-area">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.sender} ${msg.type || ''}`}>
              <pre>{msg.text}</pre>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div className="input-area">
          <input
            type="text"
            value={input}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder="e.g., GET /dna/intent/api/v1/site"
          />
          <button onClick={handleSendMessage}>Send</button>
        </div>
      </div>
    </div>
  );
}

export default App;

