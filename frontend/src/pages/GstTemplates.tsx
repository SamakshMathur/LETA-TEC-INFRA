import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, Loader2, Zap, Sparkles, Filter, FileText, CheckCircle2, 
  Copy, Download, Star, History, Bookmark, Edit3, Eye, BookOpen, 
  AlertCircle, RefreshCw, X, ChevronRight, FileDown, Layers, Info
} from 'lucide-react';
import { BASE_URL } from '../config/api';

const CATEGORIES = [
  { id: 'All', label: 'All Categories', count: 15, drafts: '1,248', status: 'READY', updated: 'Live' },
  { id: 'ITC', label: 'ITC Reversals & Compliance', count: 4, drafts: '284', status: 'READY', updated: 'Today' },
  { id: 'Appeal', label: 'Appeals & Writ Formats', count: 3, drafts: '192', status: 'READY', updated: '3d ago' },
  { id: 'Demand/Recovery', label: 'Demand & Recovery', count: 2, drafts: '214', status: 'READY', updated: 'Today' },
  { id: 'Refund', label: 'Refund Claims & Formats', count: 2, drafts: '156', status: 'READY', updated: 'Yesterday' },
  { id: 'Registration', label: 'Registration & Revocation', count: 2, drafts: '118', status: 'READY', updated: 'May 8' },
  { id: 'E-Way Bill', label: 'E-Way Bill & Penalty', count: 2, drafts: '188', status: 'READY', updated: 'May 7' },
];

const STAGES = [
  { id: 'All', label: 'All Stages' },
  { id: 'Notice Reply', label: 'Notice Replies' },
  { id: 'Appeal', label: 'Appeals' },
  { id: 'Application', label: 'Applications' },
  { id: 'Request', label: 'Formal Requests' }
];

const VAGUE_DETECTORS = [
  {
    keywords: ['itc', 'credit', 'input', '2a', '3b'],
    scenarios: [
      { label: 'ASMT-10 ITC Mismatch (GSTR-2A vs 3B)', query: 'Reply to ITC Mismatch Notice (ASMT-10)' },
      { label: 'Rule 37: 180-day reversal of ITC', query: 'Reply to SCN demanding Reversal of ITC for Non-payment to Supplier' },
      { label: 'Blocked credit under Rule 86A', query: 'Letter Requesting Unblocking of Electronic Credit Ledger' }
    ]
  },
  {
    keywords: ['refund', 'reject', 'rfd', 'unutilized'],
    scenarios: [
      { label: 'Appeal against Refund rejection order', query: 'Appeal against Rejection of Refund Claim' },
      { label: 'Delay in sanction of GST refund', query: 'Appeal against delay in refund sanction' }
    ]
  },
  {
    keywords: ['registration', 'cancel', 'suspend', 'reg'],
    scenarios: [
      { label: 'Reply to SCN REG-17 for Cancellation', query: 'Reply to SCN for Cancellation of Registration' },
      { label: 'Revocation of cancellation REG-21', query: 'Application for Revocation of Cancellation of Registration' }
    ]
  },
  {
    keywords: ['e-way', 'eway', 'detention', 'vehicle', '129'],
    scenarios: [
      { label: 'Section 129 Penalty / Detention Appeal', query: 'Appeal against Order imposing Penalty under Section 129' },
      { label: 'Mismatch in E-Way Bill vs GSTR-1', query: 'Reply to Notice for Mismatch in E-way Bill and GSTR-1' }
    ]
  }
];

const GstTemplates: React.FC = () => {
  // Core States
  const [query, setQuery] = useState<string>('');
  const [activeCategory, setActiveCategory] = useState<string>('All');
  const [activeStage, setActiveStage] = useState<string>('All');
  const [results, setResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Interaction/UX States
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
  const [editedContent, setEditedContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [isEnhancing, setIsEnhancing] = useState<boolean>(false);
  const [enhanceInstructions, setEnhanceInstructions] = useState<string>('');
  
  // Storage-backed States
  const [savedDrafts, setSavedDrafts] = useState<any[]>([]);
  const [searchHistory, setSearchHistory] = useState<string[]>([]);
  
  // Feedback Systems
  const [showCopyFeedback, setShowCopyFeedback] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  // References
  const docCanvasRef = useRef<HTMLDivElement>(null);

  // Simulated Retrieval Pipeline States & Logging Feed
  const [loadingStage, setLoadingStage] = useState<number>(0);
  const [activityLogs, setActivityLogs] = useState<any[]>([
    { id: 1, time: '16:40:15', type: 'SYS_OK', text: 'Drafting Assistant initialized with 1,248 verified templates' },
    { id: 2, time: '16:41:02', type: 'PARSE', text: 'Rule 89(5) refund template rules synced' },
    { id: 3, time: '16:42:44', type: 'OPTIMIZE', text: 'Query resolution pathways checked & ready' },
    { id: 4, time: '16:43:12', type: 'SYNC', text: 'Drafting library sync completed successfully' },
  ]);

  // Transition through loading stages when loading
  useEffect(() => {
    if (isLoading) {
      setLoadingStage(0);
      const interval = setInterval(() => {
        setLoadingStage(prev => {
          if (prev < 3) {
            return prev + 1;
          } else {
            clearInterval(interval);
            return prev;
          }
        });
      }, 400);
      return () => clearInterval(interval);
    }
  }, [isLoading]);

  // Periodic simulated live intelligence feed
  useEffect(() => {
    const LOG_EVENTS = [
      { type: 'PARSE', text: 'Section 73(10) limitation calculation verified' },
      { type: 'SYS_OK', text: 'Retrieval relevance scores updated' },
      { type: 'OPTIMIZE', text: 'Statutory citations cross-referenced with latest GST Circulars' },
      { type: 'SYNC', text: 'Precedent index updated: Appeal formats cache cleared' },
      { type: 'PARSE', text: 'Mismatch under ASMT-10 category rules aligned' },
      { type: 'OPTIMIZE', text: 'Circular 177 guidelines index synced' }
    ];

    const interval = setInterval(() => {
      const now = new Date();
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
      const randomEvent = LOG_EVENTS[Math.floor(Math.random() * LOG_EVENTS.length)];
      
      setActivityLogs(prev => {
        const nextId = prev.length > 0 ? prev[prev.length - 1].id + 1 : 1;
        const newLog = { id: nextId, time: timeStr, ...randomEvent };
        return [...prev.slice(1), newLog];
      });
    }, 4500);

    return () => clearInterval(interval);
  }, []);

  // Load favorites & search history on mount
  useEffect(() => {
    const favorites = localStorage.getItem('leta_saved_drafts');
    if (favorites) {
      try {
        setSavedDrafts(JSON.parse(favorites));
      } catch (e) {
        console.error("Failed to parse saved drafts", e);
      }
    }

    const history = localStorage.getItem('leta_search_history');
    if (history) {
      try {
        setSearchHistory(JSON.parse(history));
      } catch (e) {
        console.error("Failed to parse search history", e);
      }
    }
  }, []);

  // Fetch templates based on query & filters
  const fetchTemplates = async (searchQuery: string = '', categoryFilter: string = 'All', stageFilter: string = 'All') => {
    setIsLoading(true);
    try {
      let url = `${BASE_URL}/api/templates/search?`;
      if (searchQuery) url += `query=${encodeURIComponent(searchQuery)}&`;
      if (categoryFilter && categoryFilter !== 'All') url += `category=${encodeURIComponent(categoryFilter)}&`;
      if (stageFilter && stageFilter !== 'All') url += `stage=${encodeURIComponent(stageFilter)}&`;

      const response = await fetch(url);
      const data = await response.json();
      
      // Flatten groups to get unique template objects with matching scores
      const flattened: any[] = [];
      const groups = data.groups || [];
      
      groups.forEach((g: any) => {
        if (g.templates) {
          g.templates.forEach((t: any) => {
            if (!flattened.some(item => item.id === t.id)) {
              flattened.push({
                ...t,
                relevanceScore: t.score ? Math.round(t.score * 100) : null
              });
            }
          });
        }
      });

      setResults(flattened);
      
      // Auto-select first result if none selected
      if (flattened.length > 0 && !selectedTemplate) {
        handleSelectTemplate(flattened[0]);
      }
    } catch (error) {
      console.error("Failed to fetch templates:", error);
      triggerStatus("Failed to synchronize with litigation cloud", "error");
    } finally {
      setIsLoading(false);
    }
  };

  // Re-run search whenever filters change
  useEffect(() => {
    fetchTemplates(query, activeCategory, activeStage);
  }, [activeCategory, activeStage]);

  // Handle manual query submit
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    // Add to search history if not duplicate
    let updatedHistory = [query.trim(), ...searchHistory.filter(h => h !== query.trim())];
    updatedHistory = updatedHistory.slice(0, 5); // Limit to 5
    setSearchHistory(updatedHistory);
    localStorage.setItem('leta_search_history', JSON.stringify(updatedHistory));

    fetchTemplates(query, activeCategory, activeStage);
  };

  // Select a template, load its detailed content
  const handleSelectTemplate = async (template: any) => {
    try {
      // Fetch full content of selected template if content is null
      const response = await fetch(`${BASE_URL}/api/templates/${template.id}`);
      const data = await response.json();
      
      setSelectedTemplate(data);
      setEditedContent(data.content || '');
      setIsEditing(false); // Reset to preview mode on selection change
      setEnhanceInstructions(''); // Reset instructions

      // Smooth scroll preview to top
      if (docCanvasRef.current) {
        docCanvasRef.current.scrollTop = 0;
      }
    } catch (e) {
      console.error("Error loading template details:", e);
      triggerStatus("Failed to retrieve document template payload", "error");
    }
  };

  // Toggle favorite / save status of selected draft
  const handleToggleFavorite = () => {
    if (!selectedTemplate) return;
    
    const exists = savedDrafts.some(d => d.id === selectedTemplate.id);
    let updated;
    
    if (exists) {
      updated = savedDrafts.filter(d => d.id !== selectedTemplate.id);
      triggerStatus("Draft removed from local archives", "info");
    } else {
      const newDraft = {
        id: selectedTemplate.id,
        title: selectedTemplate.title,
        category: selectedTemplate.category,
        summary: selectedTemplate.summary,
        savedAt: new Date().toLocaleDateString()
      };
      updated = [...savedDrafts, newDraft];
      triggerStatus("Draft saved to secure local archives", "success");
    }

    setSavedDrafts(updated);
    localStorage.setItem('leta_saved_drafts', JSON.stringify(updated));
  };

  // Trigger transient status notification
  const triggerStatus = (text: string, type: 'success' | 'error' | 'info' = 'success') => {
    setStatusMessage({ text, type });
    setTimeout(() => setStatusMessage(null), 3000);
  };

  // Run Professional AI Enhancement Endpoint
  const handleEnhanceDraft = async () => {
    if (!selectedTemplate || !editedContent) return;
    
    setIsEnhancing(true);
    triggerStatus("Deploying LETA TEC neural enhancement model...", "info");

    try {
      const response = await fetch(`${BASE_URL}/api/templates/${selectedTemplate.id}/enhance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_content: editedContent,
          instructions: enhanceInstructions.trim() || undefined
        })
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setEditedContent(data.enhanced_content);
        setIsEditing(true); // Ensure they are in edit mode to see edits
        triggerStatus("Legal draft successfully optimized and calibrated", "success");
        setEnhanceInstructions(''); // Clear instructions on success
      } else {
        throw new Error(data.detail || "Enhancement failed");
      }
    } catch (err: any) {
      console.error(err);
      triggerStatus(err.message || "An error occurred during AI rewriting", "error");
    } finally {
      setIsEnhancing(false);
    }
  };

  // Download compiled Word document (.docx)
  const handleDownloadDocx = () => {
    if (!selectedTemplate) return;
    const content = isEditing ? editedContent : (selectedTemplate.content || "");
    const encodedContent = encodeURIComponent(content);
    window.open(`${BASE_URL}/api/templates/${selectedTemplate.id}/download?content=${encodedContent}`, '_blank');
  };

  // Copy current content to clipboard with feedback animation
  const handleCopyToClipboard = () => {
    const content = isEditing ? editedContent : (selectedTemplate?.content || "");
    if (!content) return;

    navigator.clipboard.writeText(content);
    setShowCopyFeedback(true);
    triggerStatus("Draft copied to clipboard", "success");
    setTimeout(() => setShowCopyFeedback(false), 2000);
  };

  // Parse query to see if user prompt is vague
  const getVagueClarifications = () => {
    if (!query || query.length > 25) return [];
    
    const lowercaseQuery = query.toLowerCase();
    for (const detector of VAGUE_DETECTORS) {
      if (detector.keywords.some(keyword => lowercaseQuery.includes(keyword))) {
        return detector.scenarios;
      }
    }
    return [];
  };

  const vagueScenarios = getVagueClarifications();

  return (
    <div className="flex h-screen overflow-hidden bg-[#000000] text-[#A1AAB8] font-sans selection:bg-[#67E8F9]/30">
      
      {/* LEFT COLUMN: ARCHIVES, DRAFT CATEGORIES & RECENT SEARCHES */}
      <div className="w-80 border-r border-white/[0.04] bg-[#10141B] flex flex-col h-full shrink-0 z-20">
        
        {/* Module Title */}
        <div className="px-6 py-6 border-b border-white/[0.04] bg-[#151922]">
          <div className="flex items-center gap-2.5">
            <Layers size={18} className="text-[#67E8F9]" />
            <h2 className="text-xs font-black tracking-[0.2em] uppercase text-white font-mono">
              LITIGATION_LIBRARY
            </h2>
          </div>
          <p className="text-[10px] text-[#A1AAB8]/50 mt-1 font-mono uppercase">
            1000+ Verified Reply Formats
          </p>
        </div>

        {/* Scrollable Filters / Archives shelf */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          
          {/* Categories shelf */}
          <div>
            <div className="flex items-center justify-between px-2 mb-2.5">
              <span className="text-[9px] font-black tracking-widest text-[#67E8F9] uppercase font-mono">
                Categories
              </span>
              <Filter size={10} className="text-white/30" />
            </div>
            
            <div className="space-y-1.5">
              {CATEGORIES.map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`w-full flex flex-col gap-1 px-3.5 py-2.5 rounded-xl text-left transition-all group border ${
                    activeCategory === cat.id 
                    ? 'bg-[#151922] text-white border-white/[0.08] shadow-lg animate-fade-in' 
                    : 'bg-transparent text-[#A1AAB8]/70 hover:text-white hover:bg-white/[0.015] border-transparent'
                  }`}
                >
                  <div className="w-full flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold truncate group-hover:translate-x-0.5 transition-transform">
                      {cat.label}
                    </span>
                    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-md ${
                      activeCategory === cat.id 
                      ? 'bg-[#67E8F9]/10 text-[#67E8F9] border border-[#67E8F9]/20' 
                      : 'bg-white/[0.02] text-[#A1AAB8]/40 border border-white/[0.04]'
                    }`}>
                      {cat.count}
                    </span>
                  </div>
                  {/* Metadata density row */}
                  <div className="flex items-center gap-2 text-[8px] font-mono text-[#A1AAB8]/35 group-hover:text-[#A1AAB8]/50 transition-colors">
                    <span>Drafts: {cat.drafts}</span>
                    <span className="opacity-40">•</span>
                    <span>{cat.updated}</span>
                    <span className="opacity-40">•</span>
                    <span className={cat.status === 'READY' ? 'text-emerald-500/60' : 'text-[#67E8F9]/60'}>
                      {cat.status}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Drafting Stage Filter */}
          <div>
            <div className="flex items-center gap-1 px-2 mb-2.5">
              <span className="text-[9px] font-black tracking-widest text-[#67E8F9] uppercase font-mono">
                Drafting Stage
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 p-1 bg-white/[0.02] border border-white/[0.05] rounded-xl">
              {STAGES.map(st => (
                <button
                  key={st.id}
                  onClick={() => setActiveStage(st.id)}
                  className={`px-2 py-1.5 rounded-lg text-[10px] font-medium text-center transition-all truncate ${
                    activeStage === st.id 
                    ? 'bg-[#151922] text-[#67E8F9] shadow-inner font-bold border border-white/[0.05]' 
                    : 'text-[#A1AAB8]/60 hover:text-white hover:bg-white/[0.02]'
                  }`}
                >
                  {st.label}
                </button>
              ))}
            </div>
          </div>

          {/* Search History */}
          {searchHistory.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 px-2 mb-2">
                <History size={10} className="text-white/30" />
                <span className="text-[9px] font-black tracking-widest text-[#67E8F9] uppercase font-mono">
                  Recent Searches
                </span>
              </div>
              <div className="flex flex-wrap gap-1 px-2">
                {searchHistory.map((hist, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setQuery(hist);
                      fetchTemplates(hist, activeCategory, activeStage);
                    }}
                    className="max-w-full truncate bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.05] text-[10px] text-[#A1AAB8]/70 hover:text-white px-2 py-1 rounded-md transition-colors font-mono text-left"
                  >
                    {hist}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Saved Drafts */}
          <div>
            <div className="flex items-center gap-1.5 px-2 mb-2.5">
              <Bookmark size={11} className="text-white/30" />
              <span className="text-[9px] font-black tracking-widest text-[#67E8F9] uppercase font-mono">
                Secure Archives
              </span>
            </div>
            
            {savedDrafts.length === 0 ? (
              <div className="border border-dashed border-white/[0.05] rounded-xl p-4 text-center">
                <Bookmark size={16} className="mx-auto mb-2 opacity-20 text-[#A1AAB8]" />
                <p className="text-[10px] text-[#A1AAB8]/40 leading-normal">
                  No drafts saved. Star a response in the preview panel to archive locally.
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {savedDrafts.map(draft => (
                  <button
                    key={draft.id}
                    onClick={() => handleSelectTemplate(draft)}
                    className={`w-full p-2.5 rounded-xl border text-left transition-all ${
                      selectedTemplate?.id === draft.id
                      ? 'bg-[#151922] border-white/[0.08] shadow-md'
                      : 'bg-[#151922]/40 border-white/[0.03] hover:border-white/[0.06] hover:bg-[#151922]/70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-semibold text-white truncate max-w-[170px]">
                        {draft.title}
                      </span>
                      <span className="text-[8px] bg-[#67E8F9]/10 text-[#67E8F9] px-1 py-0.2 rounded font-mono">
                        {draft.category}
                      </span>
                    </div>
                    <p className="text-[9px] text-[#A1AAB8]/40 mt-1 font-mono">
                      Archived: {draft.savedAt}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Live Status indicator */}
        <div className="p-4 border-t border-white/[0.06] bg-[#000000] flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
            <span className="text-[9px] font-mono tracking-wider uppercase text-white/50">LETA_TEC_ONLINE</span>
          </div>
          <span className="text-[9px] font-mono text-[#67E8F9] uppercase">v4.2-LITIG</span>
        </div>
      </div>

      {/* CENTER COLUMN: SEARCH CONSOLE & ACTIVE DRAFT FEED */}
      <div className="flex-1 flex flex-col h-full border-r border-white/[0.04] bg-[#000000] overflow-hidden relative z-10">
        

        <div className="absolute top-0 left-0 right-0 h-40 bg-gradient-to-b from-[#000000] to-transparent pointer-events-none" />

        {/* Search header container */}
        <div className="px-8 pt-8 pb-6 relative z-10">
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-[#67E8F9]" />
                <span className="text-[10px] font-mono font-black tracking-[0.3em] uppercase text-[#67E8F9]">
                  Intelligent Drafting Support
                </span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white mt-1 uppercase font-display">
                Find Relevant Drafts Instantly
              </h1>
            </div>
            
            <div className="flex gap-2">
              <span className="text-[9px] font-mono bg-white/[0.02] border border-white/[0.05] px-2.5 py-1 rounded text-[#A1AAB8]/50">
                TOTAL: 1,248 VERIFIED DRAFTS
              </span>
            </div>
          </div>

          <p className="text-xs text-[#A1AAB8]/70 max-w-xl mb-4 leading-relaxed">
            Prepare replies, notices, appeals, and compliance drafts faster with structured legal intelligence built for CAs, CS professionals, and tax practitioners.
          </p>

          {/* AI Legal Interrogation Console */}
          <form onSubmit={handleSearchSubmit} className="relative group z-10">
            {/* Soft background glow on focus */}
            <div className="absolute inset-0 bg-[#67E8F9]/[0.02] rounded-2xl blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity pointer-events-none" />
            
            <div className="relative flex items-center bg-[#10141B] border border-white/[0.08] focus-within:border-[#67E8F9]/45 rounded-2xl overflow-hidden transition-all shadow-[0_20px_40px_rgba(0,0,0,0.65)] focus-within:shadow-[0_0_30px_rgba(103,232,249,0.06)]">
              <div className="pl-6 text-white/40 flex items-center gap-2">
                <Search size={20} className="text-[#67E8F9]" />
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-ping shrink-0" />
              </div>
              <input
                type="text"
                placeholder="Describe the tax or litigation issue you are facing (e.g., 'Section 73 notice for tax mismatch')..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-transparent border-none py-5 px-4 text-sm text-white focus:outline-none focus:ring-0 placeholder-white/20 font-sans tracking-wide"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => { setQuery(''); fetchTemplates('', activeCategory, activeStage); }}
                  className="p-2.5 text-white/30 hover:text-white mr-2 transition-colors animate-fade-in"
                >
                  <X size={16} />
                </button>
              )}
              <button 
                type="submit"
                className="bg-[#151922] hover:bg-[#67E8F9] hover:text-[#000000] border-l border-white/[0.06] hover:border-transparent text-[#67E8F9] px-8 py-5 text-xs font-black tracking-[0.18em] uppercase transition-all font-mono shrink-0 flex items-center gap-2"
              >
                <Zap size={12} className="animate-pulse" />
                FIND_DRAFTS
              </button>
            </div>
          </form>

          {/* Suggested Quick Searches */}
          <div className="mt-4 flex flex-col gap-1.5 relative z-10">
            <div className="flex items-center gap-1.5 px-1">
              <Sparkles size={11} className="text-[#67E8F9]/70 animate-pulse" />
              <span className="text-[10px] font-mono font-black tracking-widest text-[#A1AAB8]/45 uppercase">
                Suggested Drafting Queries
              </span>
            </div>
            <div className="flex flex-wrap gap-2 mt-0.5">
              {[
                { label: 'Refund rejected due to limitation', query: 'Refund rejected due to limitation under Section 54' },
                { label: 'GST notice under Section 73', query: 'GST notice under Section 73 for demand of tax' },
                { label: 'ITC mismatch reply', query: 'Reply to ITC mismatch notice under ASMT-10' },
                { label: 'Appeal against demand order', query: 'Appeal against demand order under Section 107' },
                { label: 'E-way bill penalty response', query: 'E-way bill penalty response under Section 129' },
              ].map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setQuery(chip.query);
                    fetchTemplates(chip.query, activeCategory, activeStage);
                  }}
                  className="bg-white/[0.02] hover:bg-[#67E8F9]/10 border border-white/[0.04] hover:border-[#67E8F9]/25 text-xs text-[#A1AAB8]/70 hover:text-[#67E8F9] px-3 py-1.5 rounded-xl transition-all font-sans font-medium"
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>

          {/* ASSISTANT CLARIFICATION PANEL */}
          {vagueScenarios.length > 0 && (
            <div className="mt-4 p-4 rounded-xl bg-[#67E8F9]/5 border border-[#67E8F9]/10 animate-fade-in relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-[#67E8F9]/5 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-start gap-2.5 relative z-10">
                <Info size={14} className="text-[#67E8F9] mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-[10px] font-mono font-black tracking-widest text-white uppercase">
                    ASSISTANT_CLARIFICATION // Select Specific Scenario
                  </h4>
                  <p className="text-[11px] text-[#A1AAB8]/70 mt-0.5 leading-relaxed">
                    You entered a general query. Select the specific legal scenario that best matches your situation for the most accurate draft reply:
                  </p>
                  
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {vagueScenarios.map((sc, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          setQuery(sc.query);
                          fetchTemplates(sc.query, activeCategory, activeStage);
                        }}
                        className="flex items-center gap-1.5 bg-[#000000] hover:bg-[#151922] border border-[#67E8F9]/20 hover:border-[#67E8F9]/40 text-[#67E8F9] hover:text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-all shadow-sm"
                      >
                        <span>{sc.label}</span>
                        <ChevronRight size={12} />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Results Area */}
        <div className="flex-1 overflow-y-auto px-8 pb-8 custom-scrollbar relative z-10">
          
          {isLoading ? (
            <div className="space-y-5 py-6">
              {/* Dynamic Retrieval Pipeline Console */}
              <div className="bg-[#10141B] border border-[#67E8F9]/10 rounded-2xl p-6 relative overflow-hidden shadow-lg animate-fade-in">
                {/* Horizontal scanner light animation */}
                <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[#67E8F9]/40 to-transparent animate-scanner pointer-events-none" />
                
                <div className="flex items-center justify-between border-b border-white/[0.05] pb-4 mb-4">
                  <div className="flex items-center gap-2">
                    <Loader2 size={14} className="text-[#67E8F9] animate-spin" />
                    <span className="text-xs font-mono font-black tracking-widest text-white uppercase">
                      Intelligent Retrieval Active
                    </span>
                  </div>
                  <span className="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/15 animate-pulse">
                    SEARCH_PHASE_{loadingStage + 1}/4
                  </span>
                </div>

                <div className="space-y-3 font-mono text-xs text-left">
                  {[
                    { label: 'Analyzing notice context & legal questions...', delay: '12ms' },
                    { label: 'Identifying applicable tax provisions & precedents...', delay: '24ms' },
                    { label: 'Searching professional litigation draft library...', delay: '48ms' },
                    { label: 'Evaluating draft suitability & relevance...', delay: '8ms' }
                  ].map((stage, idx) => {
                    const isCompleted = loadingStage > idx;
                    const isActive = loadingStage === idx;
                    
                    return (
                      <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl transition-all duration-200 border" style={{
                        borderColor: isActive ? 'rgba(103,232,249,0.15)' : 'transparent',
                        backgroundColor: isActive ? 'rgba(255,255,255,0.01)' : 'transparent'
                      }}>
                        <div className="flex items-center gap-3">
                          {isCompleted ? (
                            <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
                          ) : isActive ? (
                            <div className="w-3.5 h-3.5 rounded-full border border-[#67E8F9]/30 flex items-center justify-center shrink-0">
                              <span className="w-1.5 h-1.5 bg-[#67E8F9] rounded-full animate-ping" />
                            </div>
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border border-white/10 flex items-center justify-center shrink-0">
                              <span className="w-1 bg-white/20 rounded-full" style={{ width: '4px', height: '4px' }} />
                            </div>
                          )}
                          <span className={`transition-colors duration-200 ${
                            isCompleted ? 'text-white/60 font-medium' : isActive ? 'text-[#67E8F9] font-bold' : 'text-white/25'
                          }`}>
                            {stage.label}
                          </span>
                        </div>
                        <span className={`text-[10px] font-mono ${
                          isCompleted ? 'text-emerald-500/60' : isActive ? 'text-[#67E8F9]/60' : 'text-white/10'
                        }`}>
                          {isCompleted ? 'OK' : isActive ? 'RUNNING' : 'QUEUED'} • {stage.delay}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Semi-transparent skeletons beneath it to preserve layout spacing */}
              <div className="space-y-4 opacity-30 pointer-events-none">
                {[1, 2].map(i => (
                  <div key={i} className="bg-[#10141B]/50 border border-white/[0.04] p-5 rounded-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="h-4 bg-white/[0.06] rounded w-2/5" />
                      <div className="h-4 bg-white/[0.06] rounded w-16" />
                    </div>
                    <div className="h-3 bg-white/[0.06] rounded w-4/5" />
                    <div className="h-3 bg-white/[0.06] rounded w-3/5" />
                  </div>
                ))}
              </div>
            </div>
          ) : results.length === 0 ? (
            <div className="space-y-6 animate-fade-in py-2">
              {/* Technical Warning Card */}
              <div className="flex items-start gap-4 p-5 border border-white/[0.05] bg-[#10141B]/30 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-[#67E8F9]/[0.01] rounded-full blur-xl pointer-events-none" />
                <div className="p-3 bg-white/[0.02] border border-white/[0.05] rounded-xl text-[#A1AAB8]/40 shrink-0">
                  <AlertCircle size={20} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider text-left">No Direct Matches Found</h3>
                  <p className="text-xs text-[#A1AAB8]/50 mt-1 leading-normal max-w-lg text-left">
                    No template explicitly satisfies your query parameters. Try widening filters, clicking suggested chips, or entering broader categories.
                  </p>
                </div>
              </div>

              {/* DRAFTING ASSISTANT OPERATIONAL METRICS */}
              <div>
                <span className="text-[10px] font-mono font-black tracking-widest text-[#67E8F9] uppercase block mb-3 px-1 text-left">
                  Drafting Assistant Operational Metrics
                </span>
                <div className="grid grid-cols-2 gap-3.5">
                  <div className="bg-[#10141B]/40 border border-white/[0.03] p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-[9px] font-mono text-[#A1AAB8]/40 uppercase tracking-wider text-left">Verified Library Size</p>
                      <h4 className="text-sm font-bold text-white font-mono mt-1 text-left">1,248 PROFESSIONAL REPLIES</h4>
                    </div>
                    <Layers size={16} className="text-[#67E8F9]/30" />
                  </div>
                  
                  <div className="bg-[#10141B]/40 border border-white/[0.03] p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-[9px] font-mono text-[#A1AAB8]/40 uppercase tracking-wider text-left">Tax & Compliance Areas</p>
                      <h4 className="text-sm font-bold text-white font-mono mt-1 text-left">GST / CUSTOMS / LITIGATION</h4>
                    </div>
                    <BookOpen size={16} className="text-[#67E8F9]/30" />
                  </div>

                  <div className="bg-[#10141B]/40 border border-white/[0.03] p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-[9px] font-mono text-[#A1AAB8]/40 uppercase tracking-wider text-left">Intelligent Drafting Support</p>
                      <h4 className="text-sm font-bold text-[#67E8F9] font-mono mt-1 text-left">ONLINE & ACTIVE</h4>
                    </div>
                    <Sparkles size={16} className="text-[#67E8F9]/40" />
                  </div>

                  <div className="bg-[#10141B]/40 border border-white/[0.03] p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-[9px] font-mono text-[#A1AAB8]/40 uppercase tracking-wider text-left">Last Library Sync</p>
                      <h4 className="text-sm font-bold text-white font-mono mt-1 text-left">SYNCED 2 MINUTES AGO</h4>
                    </div>
                    <History size={16} className="text-[#67E8F9]/30" />
                  </div>
                </div>
              </div>

              {/* LIVE SYSTEM ACTIVITY LOG */}
              <div className="bg-[#10141B] border border-white/[0.05] rounded-2xl p-5 relative overflow-hidden">
                <div className="flex items-center justify-between border-b border-white/[0.05] pb-3 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
                    <span className="text-[10px] font-mono font-black tracking-widest text-white uppercase">
                      Live System Activity Log
                    </span>
                  </div>
                  <span className="text-[9px] font-mono text-[#67E8F9] uppercase tracking-widest">
                    ASSISTANT_STATUS: READY
                  </span>
                </div>

                <div className="space-y-2.5 font-mono text-[11px] h-[130px] overflow-hidden flex flex-col justify-end">
                  {activityLogs.map((log) => (
                    <div key={log.id} className="flex items-start gap-3 text-[#A1AAB8]/70 py-0.5 animate-fade-in text-left">
                      <span className="text-[#A1AAB8]/30 shrink-0">[{log.time}]</span>
                      <span className={`font-bold shrink-0 ${
                        log.type === 'PARSE' ? 'text-amber-500/85' :
                        log.type === 'SYS_OK' ? 'text-emerald-500/85' :
                        log.type === 'OPTIMIZE' ? 'text-[#67E8F9]/85' : 'text-[#67E8F9]/85'
                      }`}>
                        [{log.type}]:
                      </span>
                      <span className="truncate text-white/80">{log.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3.5">
              <div className="text-[9px] font-mono tracking-widest uppercase text-[#A1AAB8]/30 mb-2 font-black text-left">
                MATCHES FOUND ({results.length})
              </div>
              
              {results.map((item, idx) => (
                <div 
                  key={item.id} 
                  className={`border rounded-2xl p-5 transition-all group relative overflow-hidden text-left ${
                    selectedTemplate?.id === item.id 
                    ? 'bg-[#151922] border-[#67E8F9]/30 shadow-[0_8px_20px_rgba(103,232,249,0.03)]' 
                    : 'bg-[#10141B]/70 hover:bg-[#10141B] border-white/[0.05] hover:border-white/[0.1] shadow-md'
                  }`}
                >
                  {/* Score glow accent on high score matches */}
                  {item.relevanceScore && item.relevanceScore > 80 && (
                    <div className="absolute top-0 left-0 w-[3px] h-full bg-[#67E8F9]" />
                  )}

                  <div className="flex items-start justify-between gap-4 mb-2.5">
                    <div>
                      <h3 className="text-sm font-bold text-white group-hover:text-[#67E8F9] transition-colors leading-tight">
                        {item.title}
                      </h3>
                      <p className="text-[11px] text-[#A1AAB8]/40 mt-1 font-mono uppercase tracking-tighter">
                        Category: <span className="text-[#A1AAB8]/60 font-medium">{item.category}</span>
                        {item.sub_category && <> // Sub-category: <span className="text-[#A1AAB8]/60 font-medium">{item.sub_category}</span></>}
                      </p>
                    </div>

                    {/* Match Score Gauge */}
                    {item.relevanceScore && (
                      <div className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-black tracking-tighter shrink-0 border ${
                        item.relevanceScore > 80 
                        ? 'bg-[#67E8F9]/10 text-[#67E8F9] border-[#67E8F9]/20 shadow-sm' 
                        : 'bg-[#A1AAB8]/5 text-[#A1AAB8]/60 border-white/[0.05]'
                      }`}>
                        {item.relevanceScore}% MATCH RELEVANCE
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-[#A1AAB8]/80 leading-relaxed mb-4">
                    {item.summary}
                  </p>

                  {/* Draft Suitability & Relevant Provisions */}
                  <div className="bg-[#000000] border border-white/[0.03] rounded-xl p-3 mb-4 flex items-center justify-between gap-4 text-left">
                    <div className="flex-1 space-y-1 font-mono text-[10px] text-[#A1AAB8]/50 overflow-hidden">
                      <div className="flex items-center gap-1.5">
                        <span className="text-white/30 shrink-0">Classification:</span>
                        <span className="text-[#67E8F9] font-semibold truncate">{item.category} • {item.sub_category || 'General'}</span>
                      </div>
                      <div className="flex items-center gap-1.5 overflow-hidden">
                        <span className="text-white/30 shrink-0">Relevant Provisions:</span>
                        <span className="text-white/70 font-semibold truncate">{item.keywords && item.keywords.slice(0, 3).join(', ')}</span>
                      </div>
                    </div>

                    {/* Match Relevance Gauge */}
                    {item.relevanceScore && (
                      <div className="flex flex-col items-end gap-1.5 shrink-0 border-l border-white/[0.05] pl-4">
                        <div className="flex items-center gap-1">
                          <span className="text-[9px] font-mono text-white/30 uppercase tracking-widest">Relevance:</span>
                          <span className={`text-[11px] font-mono font-black ${
                            item.relevanceScore > 85 ? 'text-emerald-400' : 'text-[#67E8F9]'
                          }`}>
                            {item.relevanceScore}%
                          </span>
                        </div>
                        {/* Micro-bar */}
                        <div className="w-20 h-1 bg-white/[0.05] rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${
                            item.relevanceScore > 85 ? 'bg-emerald-500' : 'bg-[#67E8F9]'
                          }`} style={{ width: `${item.relevanceScore}%` }} />
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-4 pt-3.5 border-t border-white/[0.04]">
                    {/* Key Words */}
                    <div className="flex flex-wrap gap-1">
                      {item.keywords && item.keywords.slice(0, 4).map((kw: string, i: number) => (
                        <span 
                          key={i} 
                          className="text-[9px] font-mono bg-[#000000] border border-white/[0.05] text-[#A1AAB8]/50 px-2 py-0.5 rounded"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>

                    {/* Primary Action Row */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSelectTemplate(item)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold tracking-tight flex items-center gap-1.5 transition-all ${
                          selectedTemplate?.id === item.id
                          ? 'bg-[#67E8F9]/10 text-[#67E8F9] border border-[#67E8F9]/20'
                          : 'bg-white/[0.02] hover:bg-white/[0.05] text-[#A1AAB8]/80 hover:text-white border border-white/[0.05]'
                        }`}
                      >
                        <Eye size={12} />
                        Preview
                      </button>

                      <button
                        onClick={() => {
                          handleSelectTemplate(item);
                          setIsEditing(true);
                          // Delay scroll right to ensure the edit canvas renders
                          setTimeout(() => {
                            if (docCanvasRef.current) {
                              docCanvasRef.current.scrollIntoView({ behavior: 'smooth' });
                            }
                          }, 150);
                        }}
                        className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-[#67E8F9] text-[#000000] hover:bg-[#5EEAD4] transition-colors flex items-center gap-1"
                      >
                        <Edit3 size={12} />
                        Use Draft
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

        </div>
      </div>

      {/* RIGHT COLUMN: PREVIEW CANVAS & EDITING CONTROLS */}
      <div className="w-[520px] bg-[#10141B] border-l border-white/[0.04] flex flex-col h-full shrink-0 relative z-20">
        
        {/* Detail Header */}
        <div className="px-6 py-6 border-b border-white/[0.06] bg-[#151922] flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <BookOpen size={14} className="text-[#67E8F9]" />
              <span className="text-[10px] font-mono font-black tracking-widest uppercase text-white/50">
                Active Draft Reply
              </span>
            </div>
            <h3 className="text-xs font-bold text-white mt-0.5 uppercase tracking-tight max-w-[340px] truncate">
              {selectedTemplate ? selectedTemplate.title : "No Template Loaded"}
            </h3>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleToggleFavorite}
              disabled={!selectedTemplate}
              className={`p-2 rounded-lg border transition-all ${
                selectedTemplate && savedDrafts.some(d => d.id === selectedTemplate.id)
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-500'
                : 'bg-white/[0.02] border-white/[0.05] text-[#A1AAB8]/40 hover:text-white'
              }`}
              title="Archive locally"
            >
              <Star size={14} fill={selectedTemplate && savedDrafts.some(d => d.id === selectedTemplate.id) ? "currentColor" : "none"} />
            </button>
          </div>
        </div>

        {/* Transient status banner */}
        {statusMessage && (
          <div className={`px-6 py-2.5 text-xs font-mono font-black tracking-tight text-center animate-fade-in ${
            statusMessage.type === 'success' 
            ? 'bg-emerald-500/10 text-emerald-400 border-b border-emerald-500/20' 
            : statusMessage.type === 'error'
            ? 'bg-rose-500/10 text-rose-400 border-b border-rose-500/20'
            : 'bg-sky-500/10 text-sky-400 border-b border-sky-500/20'
          }`}>
            {statusMessage.text}
          </div>
        )}

        {/* Main interactive area */}
        {selectedTemplate ? (
          <div className="flex-1 flex flex-col overflow-hidden">
            
            {/* Editor vs Preview Mode Ribbon */}
            <div className="px-6 py-2 border-b border-white/[0.04] bg-[#151922]/50 flex items-center justify-between">
              <div className="flex bg-[#000000] p-0.5 rounded-lg border border-white/[0.05]">
                <button
                  onClick={() => setIsEditing(false)}
                  className={`px-3 py-1.5 rounded-md text-[10px] font-mono font-bold tracking-wider uppercase transition-all flex items-center gap-1.5 ${
                    !isEditing 
                    ? 'bg-[#151922] text-[#67E8F9] border border-white/[0.05] shadow' 
                    : 'text-[#A1AAB8]/50 hover:text-white'
                  }`}
                >
                  <Eye size={10} />
                  Preview Draft
                </button>
                <button
                  onClick={() => setIsEditing(true)}
                  className={`px-3 py-1.5 rounded-md text-[10px] font-mono font-bold tracking-wider uppercase transition-all flex items-center gap-1.5 ${
                    isEditing 
                    ? 'bg-[#151922] text-[#67E8F9] border border-white/[0.05] shadow' 
                    : 'text-[#A1AAB8]/50 hover:text-white'
                  }`}
                >
                  <Edit3 size={10} />
                  Edit Inline
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyToClipboard}
                  className="p-2 rounded-lg bg-white/[0.02] hover:bg-[#151922] border border-white/[0.05] hover:border-white/[0.1] text-white/70 hover:text-white transition-all"
                  title="Copy to Clipboard"
                >
                  {showCopyFeedback ? <CheckCircle2 size={13} className="text-emerald-500" /> : <Copy size={13} />}
                </button>

                <button
                  onClick={handleDownloadDocx}
                  className="flex items-center gap-1.5 bg-[#67E8F9] text-[#000000] px-3.5 py-1.5 rounded-lg text-[10px] font-mono font-black tracking-widest uppercase hover:bg-[#5EEAD4] transition-colors shadow-lg"
                  title="Export .DOCX Word Format"
                >
                  <FileDown size={12} />
                  EXPORT
                </button>
              </div>
            </div>

            {/* Document Canvas Shelf */}
            <div className="flex-1 overflow-y-auto p-6 bg-[#000000]/50 custom-scrollbar flex flex-col justify-between">
              
              {/* Paper physics simulation container */}
              <div 
                ref={docCanvasRef}
                className="w-full bg-[#fcfbf9] shadow-[0_15px_40px_rgba(0,0,0,0.6)] rounded-xl p-8 text-[#1f2022] leading-relaxed font-serif relative group overflow-y-auto max-h-[460px] custom-scrollbar border border-neutral-200"
              >
                {/* Simulated Watermark */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none opacity-[0.03] rotate-[35deg] select-none text-6xl font-sans font-black tracking-widest">
                  LETA_TEC_DRAFT
                </div>

                {isEditing ? (
                  <textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    className="w-full bg-transparent border-none text-[13px] text-[#1a1b1d] focus:outline-none focus:ring-0 resize-none font-serif min-h-[380px] leading-relaxed"
                  />
                ) : (
                  <div className="whitespace-pre-wrap text-[13px] relative z-10 font-serif leading-relaxed">
                    {editedContent || selectedTemplate.content || "No Draft content synthesized."}
                  </div>
                )}
              </div>

              {/* AI DRAFT ENHANCEMENT CONTROLS */}
              <div className="mt-5 p-4 rounded-xl bg-[#10141B] border border-white/[0.05] space-y-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <Sparkles size={13} className="text-[#67E8F9]" />
                    <span className="text-[10px] font-mono font-black tracking-widest uppercase text-white">
                      AI Draft Enhancer
                    </span>
                  </div>
                  <span className="text-[8px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                    Legal Assistant v4.0
                  </span>
                </div>

                <p className="text-[11px] text-[#A1AAB8]/60 leading-relaxed">
                  Instruct LETA TEC to add specific legal arguments, emphasize certain sections, or adapt references to your client's fact patterns.
                </p>

                <div className="relative">
                  <input
                    type="text"
                    placeholder="E.g., 'Strengthen the limitation argument under Section 73'"
                    value={enhanceInstructions}
                    onChange={(e) => setEnhanceInstructions(e.target.value)}
                    className="w-full bg-[#000000] border border-white/[0.06] rounded-xl py-2.5 px-4 pr-12 text-xs text-white placeholder-white/20 focus:outline-none focus:border-[#67E8F9]/30"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleEnhanceDraft();
                      }
                    }}
                  />
                  <button
                    onClick={handleEnhanceDraft}
                    disabled={isEnhancing || !editedContent}
                    className="absolute right-1.5 top-1.5 p-1.5 rounded-lg bg-[#151922] hover:bg-[#67E8F9] hover:text-[#000000] border border-white/[0.05] hover:border-transparent text-[#67E8F9] transition-all disabled:opacity-30 disabled:pointer-events-none"
                  >
                    {isEnhancing ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <RefreshCw size={13} />
                    )}
                  </button>
                </div>
              </div>

              {/* METADATA SUMMARY & INSIGHTS */}
              <div className="mt-5 space-y-4">
                {/* Active citations checklist */}
                <div>
                  <div className="flex items-center gap-1.5 mb-2 px-1">
                    <CheckCircle2 size={12} className="text-[#67E8F9]" />
                    <span className="text-[9px] font-mono font-black tracking-widest uppercase text-white/50">
                      Applicable Statutes & Keywords
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {selectedTemplate.keywords && selectedTemplate.keywords.map((kw: string, i: number) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.01] border border-white/[0.04]">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        <span className="text-[10px] font-mono text-white/80 truncate uppercase">{kw}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI strategic recommendations */}
                <div className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.04] space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Info size={12} className="text-[#67E8F9]" />
                    <span className="text-[9px] font-mono font-black tracking-widest uppercase text-white/60">
                      Strategic Drafting Recommendations
                    </span>
                  </div>
                  <ul className="space-y-1.5 list-disc pl-4 text-[10px] text-[#A1AAB8]/70 leading-relaxed font-sans">
                    <li>Verify details matching current assessment year (AY) limits.</li>
                    <li>Ensure supplier GSTINs and invoices align exactly with the ASMT-10 parameters.</li>
                    <li>Preserve standard verification prayers at the footer before submitting.</li>
                  </ul>
                </div>
              </div>

            </div>

          </div>
        ) : (
          <div className="flex-1 flex flex-col p-6 overflow-y-auto justify-center space-y-6 bg-[#000000]/10 custom-scrollbar animate-fade-in">
            {/* Blueprint Header */}
            <div className="text-center space-y-1">
              <div className="w-10 h-10 rounded-full border border-white/[0.06] bg-[#10141B] flex items-center justify-center mx-auto shadow-md">
                <FileText size={18} className="text-[#67E8F9] animate-pulse" />
              </div>
              <h4 className="text-xs font-mono font-black tracking-[0.25em] uppercase text-white">
                DRAFT PREVIEW CANVAS
              </h4>
              <p className="text-[10px] text-[#A1AAB8]/40 uppercase font-mono tracking-wider">
                Select a draft from the center column to preview
              </p>
            </div>

            {/* Wireframe Mock Layout */}
            <div className="border border-[#67E8F9]/10 rounded-2xl bg-[#10141B]/40 p-4 relative overflow-hidden space-y-3.5 shadow-inner">
              {/* Drafting grid lines in background */}
              <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(103,232,249,0.01)_1px,transparent_1px),linear-gradient(to_bottom,rgba(103,232,249,0.01)_1px,transparent_1px)] bg-[size:1rem_1rem] pointer-events-none" />
              
              {/* Wireframe Header block */}
              <div className="flex items-center justify-between border-b border-white/[0.05] pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-white/10" />
                  <div className="h-3 bg-white/[0.04] rounded w-28" />
                </div>
                <div className="h-4 bg-[#67E8F9]/5 border border-[#67E8F9]/10 rounded w-14" />
              </div>

              {/* Wireframe Body block */}
              <div className="space-y-2 text-left">
                <div className="h-3 bg-white/[0.04] rounded w-full" />
                <div className="h-3 bg-white/[0.04] rounded w-11/12" />
                <div className="h-3 bg-[#67E8F9]/5 rounded w-4/5" />
                <div className="h-3 bg-white/[0.04] rounded w-full" />
              </div>

              {/* Wireframe Footer block */}
              <div className="pt-3 border-t border-white/[0.03] flex justify-between">
                <div className="h-3 bg-white/[0.03] rounded w-16" />
                <div className="h-3 bg-[#67E8F9]/10 rounded w-12" />
              </div>
            </div>

            {/* Blueprint Key Architecture features */}
            <div className="space-y-3 px-1 text-left">
              <span className="text-[9px] font-mono font-black tracking-widest text-[#67E8F9] uppercase">
                PREVIEW & EDITING FEATURES:
              </span>
              
              <div className="space-y-2">
                {[
                  {
                    title: 'Formal Legal Layout',
                    desc: 'High-fidelity rendering of formal litigation layout'
                  },
                  {
                    title: 'Statutory Citations',
                    desc: 'In-line statutory citations, circulars & case precedents'
                  },
                  {
                    title: 'Interactive Drafting Canvas',
                    desc: 'Full inline editing controls to customize drafts before export'
                  },
                  {
                    title: 'Strategic Legal Rewriting',
                    desc: "Adapt response to client fact-patterns, section nuances, or assessment parameters"
                  }
                ].map((cap, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.01] hover:bg-white/[0.02] border border-white/[0.03] transition-colors">
                    <div className="w-5 h-5 rounded-md bg-[#67E8F9]/5 border border-[#67E8F9]/10 text-[#67E8F9] flex items-center justify-center shrink-0 font-mono text-[10px] font-bold mt-0.5">
                      0{idx + 1}
                    </div>
                    <div>
                      <h5 className="text-[11px] font-bold text-white uppercase tracking-wide">{cap.title}</h5>
                      <p className="text-[10px] text-[#A1AAB8]/50 mt-0.5 leading-normal">{cap.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
          height: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(103, 232, 249, 0.2);
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(5px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fadeIn 0.4s cubic-bezier(0.23, 1, 0.32, 1) forwards;
        }
        @keyframes scanner {
          0% { transform: translateY(0); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(180px); opacity: 0; }
        }
        .animate-scanner {
          animation: scanner 2.2s linear infinite;
        }
      `}</style>

    </div>
  );
};

export default GstTemplates;
