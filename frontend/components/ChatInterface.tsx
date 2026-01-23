import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, AlertCircle, Loader2, StopCircle } from 'lucide-react';
import { sendMessageToAssistant } from '../services/geminiService';
import { Message } from '../types';
import ReactMarkdown from 'react-markdown';

const ChatInterface: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'model',
      content: "Hello agent. I'm Nexus AI with Deep Thinking enabled. I can help you resolve complex customer inquiries, analyze billing discrepancies, or provide technical troubleshooting steps. How can I assist?",
      timestamp: new Date()
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    setIsThinking(true);

    try {
      const stream = await sendMessageToAssistant(userMsg.content);
      
      let fullResponse = '';
      const responseMsgId = (Date.now() + 1).toString();
      
      // Initial placeholder for the model response
      setMessages(prev => [
        ...prev, 
        { id: responseMsgId, role: 'model', content: '', timestamp: new Date() }
      ]);

      for await (const chunk of stream) {
        setIsThinking(false); // First chunk received, thinking is done
        const chunkText = chunk.text || '';
        fullResponse += chunkText;
        
        setMessages(prev => 
          prev.map(msg => 
            msg.id === responseMsgId 
              ? { ...msg, content: fullResponse } 
              : msg
          )
        );
      }
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'system',
        content: 'Error: Failed to connect to AI service. Please try again.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="bg-slate-50 px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="bg-emerald-600 p-1.5 rounded-lg">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-800 text-sm">Nexus Assistant</h3>
            <span className="text-xs text-emerald-600 flex items-center font-medium">
              <Sparkles className="w-3 h-3 mr-1" />
              Gemini 3 Pro (Deep Thinking)
            </span>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-slate-50/50">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-2`}>
              
              {/* Avatar */}
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                msg.role === 'user' ? 'bg-slate-200' : 
                msg.role === 'system' ? 'bg-rose-100' : 'bg-emerald-100'
              }`}>
                {msg.role === 'user' ? <User className="w-5 h-5 text-slate-600" /> : 
                 msg.role === 'system' ? <AlertCircle className="w-5 h-5 text-rose-600" /> :
                 <Bot className="w-5 h-5 text-emerald-600" />}
              </div>

              {/* Bubble */}
              <div className={`p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
                msg.role === 'user' 
                  ? 'bg-slate-800 text-white rounded-tr-none' 
                  : msg.role === 'system'
                  ? 'bg-rose-50 text-rose-800 border border-rose-200'
                  : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'
              }`}>
                {msg.role === 'model' ? (
                   <ReactMarkdown 
                    className="prose prose-sm prose-slate max-w-none"
                    components={{
                        p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
                        ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal ml-4 mb-2" {...props} />,
                        li: ({node, ...props}) => <li className="mb-1" {...props} />,
                        strong: ({node, ...props}) => <span className="font-bold text-emerald-700" {...props} />
                    }}
                   >
                     {msg.content}
                   </ReactMarkdown>
                ) : (
                  msg.content
                )}
                <span className={`text-[10px] block mt-1 opacity-70 ${msg.role === 'user' ? 'text-slate-300' : 'text-slate-400'}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          </div>
        ))}

        {/* Thinking Indicator */}
        {isThinking && (
          <div className="flex justify-start w-full animate-pulse">
             <div className="flex flex-row items-start gap-2 max-w-[85%]">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center border border-emerald-100">
                  <Bot className="w-5 h-5 text-emerald-400" />
                </div>
                <div className="bg-white border border-emerald-100 p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center space-x-3">
                  <Loader2 className="w-4 h-4 text-emerald-500 animate-spin" />
                  <span className="text-sm text-emerald-600 font-medium">Deep reasoning in progress...</span>
                </div>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-100">
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the customer issue for deep analysis..."
            disabled={isLoading}
            className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent resize-none text-sm disabled:opacity-50 min-h-[50px] max-h-[120px]"
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="absolute right-2 bottom-2 p-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-lg transition-colors duration-200"
          >
            {isLoading ? <StopCircle className="w-4 h-4" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-2 text-center">
          Gemini 3 Pro Preview enabled. Responses may take longer due to extended thinking budget (32k).
        </p>
      </div>
    </div>
  );
};

export default ChatInterface;