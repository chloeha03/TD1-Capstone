
import React, { useState } from 'react';
import { X, Download, Loader2 } from 'lucide-react';
import ActiveCall from './components/ActiveCall';
import { generateImageMockup } from './services/geminiService';

const App: React.FC = () => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [sessionKey, setSessionKey] = useState(0); // Used to restart the call flow

  const restartSession = () => {
    setSessionKey(prev => prev + 1);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans">
      {/* Top Navigation Bar */}
      <header className="h-16 bg-emerald-950 flex items-center justify-between px-6 shadow-md z-30 flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-white rounded flex items-center justify-center">
             <span className="text-emerald-900 font-bold text-xl tracking-tighter">TD</span>
          </div>
          <div className="h-8 w-px bg-emerald-800 mx-2"></div>
          <h1 className="text-white font-medium text-lg tracking-wide">Agent Workspace</h1>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-6">
          <button 
            onClick={restartSession}
            className="text-emerald-200 hover:text-white text-xs font-bold underline px-2"
          >
            Reset Call
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative">
        <ActiveCall key={sessionKey} />
      </main>

      {/* Generated Image Modal (Kept for internal logic if needed, though button removed) */}
      {(generatedImage || isGenerating) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-8">
           <div className="bg-slate-900 rounded-xl overflow-hidden max-w-6xl w-full max-h-full flex flex-col border border-slate-700 shadow-2xl">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700 bg-slate-800">
                <h3 className="text-white font-bold">Concept View</h3>
                <button 
                  onClick={() => {
                    setGeneratedImage(null);
                    setIsGenerating(false);
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              
              <div className="flex-1 bg-black flex items-center justify-center p-4 overflow-hidden relative min-h-[400px]">
                 {isGenerating ? (
                    <div className="text-center space-y-4">
                       <Loader2 className="w-12 h-12 text-emerald-500 animate-spin mx-auto" />
                       <p className="text-emerald-400 font-medium">Synthesizing...</p>
                    </div>
                 ) : (
                    generatedImage && <img src={generatedImage} alt="Concept" className="max-w-full max-h-full object-contain rounded shadow-lg" />
                 )}
              </div>
           </div>
        </div>
      )}
    </div>
  );
};

export default App;
