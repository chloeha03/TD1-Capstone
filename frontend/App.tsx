import React, { useState } from 'react';
import { Layers, Image as ImageIcon, Sparkles, X, Download, Loader2 } from 'lucide-react';
import ActiveCall from './components/ActiveCall';
import { ScenarioType } from './types';
import { generateImageMockup } from './services/geminiService';

const App: React.FC = () => {
  const [currentScenario, setCurrentScenario] = useState<ScenarioType>('PROMOTION');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);

  const scenarios: { id: ScenarioType; label: string; description: string }[] = [
    { 
      id: 'PROMOTION', 
      label: 'Scenario 1: Promotions', 
      description: 'Active call with stacked promotion banners and a detailed recommendation popup requiring agent input.' 
    },
    { 
      id: 'CLIENT_SUMMARY', 
      label: 'Scenario 2: Client Summary', 
      description: 'Pre-call client summary overlay showing unresolved issues, services used, and priority alerts.' 
    },
    { 
      id: 'END_CALL', 
      label: 'Scenario 3: Call Recap', 
      description: 'End of call summary modal with auto-filled resolution status, accepted offers, and next steps.' 
    }
  ];

  const handleGenerateConcept = async () => {
    const activeScenario = scenarios.find(s => s.id === currentScenario);
    if (!activeScenario) return;

    setIsGenerating(true);
    setGeneratedImage(null);
    try {
      const imageUrl = await generateImageMockup(activeScenario.description);
      setGeneratedImage(imageUrl);
    } catch (e) {
      console.error(e);
      alert("Failed to generate image. Please try again.");
    } finally {
      setIsGenerating(false);
    }
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
          <h1 className="text-white font-medium text-lg tracking-wide">Agent Workspace Scenarios</h1>
        </div>

        {/* Scenario Tabs */}
        <div className="flex items-center bg-emerald-900/50 p-1 rounded-lg border border-emerald-800">
          {scenarios.map((scenario) => (
            <button
              key={scenario.id}
              onClick={() => setCurrentScenario(scenario.id)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-all flex items-center gap-2 ${
                currentScenario === scenario.id
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-emerald-200 hover:text-white hover:bg-emerald-800'
              }`}
            >
              <Layers className="w-4 h-4" />
              {scenario.label}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div>
          <button 
            onClick={handleGenerateConcept}
            disabled={isGenerating}
            className="flex items-center gap-2 px-4 py-2 bg-white text-emerald-900 hover:bg-emerald-50 rounded-lg text-sm font-bold transition-colors shadow-sm disabled:opacity-50"
          >
            {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-emerald-600" />}
            Generate AI Concept
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative">
        <ActiveCall scenario={currentScenario} />
      </main>

      {/* Generated Image Modal */}
      {(generatedImage || isGenerating) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-8">
           <div className="bg-slate-900 rounded-xl overflow-hidden max-w-6xl w-full max-h-full flex flex-col border border-slate-700 shadow-2xl">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700 bg-slate-800">
                <h3 className="text-white font-bold flex items-center gap-2">
                   <Sparkles className="w-5 h-5 text-purple-400" />
                   AI Generated Concept: {scenarios.find(s => s.id === currentScenario)?.label}
                </h3>
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
                       <p className="text-emerald-400 font-medium">Dreaming up interface concept...</p>
                       <p className="text-slate-500 text-sm">Using Gemini 3 Pro Image Preview</p>
                    </div>
                 ) : (
                    generatedImage && <img src={generatedImage} alt="AI Generated Interface" className="max-w-full max-h-full object-contain rounded shadow-lg" />
                 )}
              </div>

              {generatedImage && (
                <div className="p-4 bg-slate-800 border-t border-slate-700 flex justify-end">
                   <a 
                     href={generatedImage} 
                     download={`scenario-${currentScenario}.png`}
                     className="flex items-center gap-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold transition-colors"
                   >
                     <Download className="w-4 h-4" />
                     Download Image
                   </a>
                </div>
              )}
           </div>
        </div>
      )}
    </div>
  );
};

export default App;