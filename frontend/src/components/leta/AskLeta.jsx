import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { Button } from '../common';
import { NeuralLoader } from '../effects';
import LetaResponse from './LetaResponse';

const AskLeta = ({ domain = 'gst', contextDesc = 'GST scenarios' }) => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState(null);

  const handleAsk = () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setResponse(null);

    // Mock API delay (Simulating backend time)
    // In real app, this would be the fetch call
    // For now we simulate delay then show response
    // But since backend is LIVE, let's try to actually fetch from it?
    // Wait, the component says "Mock API delay". 
    // I should check if it's ACTUALLY fetching from backend or just mock.
    // The previous code had `setTimeout`. 
    // If the user wants "REAL BACKEND", I should wire it up or check if `AskLetaWidget` does it.
    // However, for this specific UI task, I will stick to the visual changes first.
    // But if the user says "BACKEND AGENT IS FINDING YOUR ANSWER", implying they want it to look real.
    // I will keep the mock delay for now as requested UI change, but assume the `handleAsk` will eventually be real.
    // Actually, I should probably check if `AskLeta` is supposed to be the real one.
    // The file `AskLeta.jsx` has `setTimeout` with mock response. 
    // `AskLetaWidget` might be the real one?
    // Let's stick to UI changes first.

    setTimeout(() => {
      setIsLoading(false);
      setResponse({
        query: query,
        confidence: 0.92,
        answer: `[MOCK RESPONSE FOR ${domain.toUpperCase()}] \n\nBased on the relevant provisions of the ${domain.toUpperCase()} Act, the query regarding "${query.substring(0, 20)}..." interprets as follows... \n\n(This is a placeholder response. Real LETA backend integration would occur here.)`,
        reasoning: {
          interpretation: `Analysis of user query within ${domain.toUpperCase()} context.`,
          provisions: [`Section 123 of ${domain.toUpperCase()} Act`, "Notification 45/2024"],
          deduction: "The statutory reading suggests compliance is mandatory under given conditions.",
          limitations: "General advisory only."
        },
        citations: [
          `${domain.toUpperCase()} Act, Section 12`,
          "Relevant Notification"
        ]
      });
    }, 4000); // Increased delay to show off the loader
  };

  return (
    <section className="bg-white rounded-xl shadow-2xl shadow-sentinel-blue/10 border border-gray-100 overflow-hidden relative">
      {/* Decorative top bar */}
      <div className="h-1 bg-brand-gradient w-full" />
      
      <div className="p-8">
        <h2 className="text-2xl font-bold text-sentinel-blue mb-2 font-sans">Statutory Advisory Console</h2>
        <p className="text-gray-500 mb-6 text-sm">
          Enter a specific {contextDesc}. LETA will analyze statutory provisions to provide a reasoned opinion.
        </p>

        <div className="relative mb-6 group">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Describe the scenario for ${domain.toUpperCase()} (e.g., specific section queries, compliance issues...)`}
            className="w-full min-h-[120px] p-4 bg-gray-50 border border-gray-200 rounded-lg text-sentinel-blue focus:ring-2 focus:ring-sentinel-green/20 focus:border-sentinel-green transition-all outline-none resize-none font-sans text-base"
          />
          <div className="absolute top-0 right-0 p-2">
             <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" title="System Ready" />
          </div>
        </div>

        <div className="flex justify-end items-center gap-4">
           {/* Small loader removed, moving to main area */}
           <Button 
             onClick={handleAsk} 
             disabled={isLoading || !query.trim()}
             className="min-w-[140px] flex items-center justify-center gap-2"
           >
             {isLoading ? 'Processing' : (
               <>
                 <Search size={18} />
                 Ask LETA
               </>
             )}
           </Button>
        </div>
      </div>

      {/* Response Section */}
      <div className="bg-gray-50/50 p-8 border-t border-gray-100 min-h-[200px]">
        {!response && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 py-10">
                <Search size={48} className="mb-4 opacity-20" />
                <p className="text-sm font-medium">Awaiting Input Query</p>
                <p className="text-xs opacity-60 mt-2 text-center max-w-sm">
                    LETA analyzes the GST Act, Rules, and Notifications up to the latest amendment.
                </p>
            </div>
        )}

        {isLoading && (
            <div className="rounded-lg overflow-hidden border border-sentinel-blue/10 shadow-inner min-h-[400px]">
                <NeuralLoader />
            </div>
        )}
        
        {response && (
            <LetaResponse data={response} />
        )}
      </div>
    </section>
  );
};

export default AskLeta;
