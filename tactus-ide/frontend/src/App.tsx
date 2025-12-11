/**
 * Main App component for Tactus IDE.
 */
import React, { useState } from 'react';
import { Editor } from './Editor';

const EXAMPLE_CODE = `-- Tactus DSL Example
name("hello_world")
version("1.0.0")
description("A simple hello world procedure")

-- Define an agent
agent("greeter", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a friendly greeter"
})

-- Define outputs
output("greeting", {
    type = "string",
    required = true
})

-- Define the procedure
procedure(function()
    Log.info("Starting hello world procedure")
    
    local greeting = "Hello, Tactus IDE!"
    
    return {
        greeting = greeting
    }
end)
`;

export const App: React.FC = () => {
  const [code, setCode] = useState(EXAMPLE_CODE);
  const [fileName, setFileName] = useState('untitled.tactus.lua');
  
  const handleSave = async () => {
    try {
      const response = await fetch('http://localhost:5001/api/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: fileName,
          content: code
        })
      });
      
      if (response.ok) {
        alert('File saved successfully!');
      } else {
        alert('Error saving file');
      }
    } catch (error) {
      console.error('Save error:', error);
      alert('Error saving file: ' + error);
    }
  };
  
  const handleOpen = async () => {
    const path = prompt('Enter file path:', 'examples/hello-world.tactus.lua');
    if (!path) return;
    
    try {
      const response = await fetch(`http://localhost:5001/api/file?path=${encodeURIComponent(path)}`);
      
      if (response.ok) {
        const data = await response.json();
        setCode(data.content);
        setFileName(data.name);
      } else {
        alert('Error opening file');
      }
    } catch (error) {
      console.error('Open error:', error);
      alert('Error opening file: ' + error);
    }
  };
  
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100vh',
      background: '#1e1e1e'
    }}>
      {/* Menu Bar */}
      <div style={{
        display: 'flex',
        gap: '8px',
        padding: '8px 16px',
        background: '#2d2d2d',
        borderBottom: '1px solid #3e3e3e',
        color: '#cccccc'
      }}>
        <button 
          onClick={handleOpen}
          style={{
            padding: '6px 12px',
            background: '#0e639c',
            color: 'white',
            border: 'none',
            borderRadius: '3px',
            cursor: 'pointer'
          }}
        >
          Open File
        </button>
        <button 
          onClick={handleSave}
          style={{
            padding: '6px 12px',
            background: '#0e639c',
            color: 'white',
            border: 'none',
            borderRadius: '3px',
            cursor: 'pointer'
          }}
        >
          Save File
        </button>
        <span style={{ 
          marginLeft: 'auto', 
          display: 'flex', 
          alignItems: 'center',
          fontSize: '14px'
        }}>
          {fileName}
        </span>
      </div>
      
      {/* Editor */}
      <Editor 
        initialValue={code} 
        onValueChange={setCode}
      />
    </div>
  );
};


