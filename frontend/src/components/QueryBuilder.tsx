/**
 * Modern Query Builder with Multi-Step Planning Workflow
 * Step 1: User enters query
 * Step 2: AI understands and rewrites query - user validates
 * Step 3: AI suggests research angles - user selects/modifies
 * Step 4: AI decomposes into sub-questions - user reviews
 * Step 5: Start research
 */
import { useState, useRef, useEffect } from 'react';
import { 
  Sparkles, 
  ArrowRight, 
  ArrowLeft, 
  Check, 
  Edit3, 
  Lightbulb, 
  Search,
  Loader2,
  MessageSquare,
  List,
  Play,
  RotateCcw
} from 'lucide-react';

interface PlanningData {
  originalQuery: string;
  understoodQuery: string;
  userModifiedQuery: string;
  selectedAngles: string[];
  customAngle: string;
  subQuestions: string[];
  userModifiedSubQuestions: string[];
}

interface QueryBuilderProps {
  onSubmit: (data: PlanningData) => void;
  isResearching: boolean;
}

type Step = 'input' | 'understanding' | 'angles' | 'decomposition' | 'ready';

const API_BASE = 'http://localhost:8000';

export function QueryBuilder({ onSubmit, isResearching }: QueryBuilderProps) {
  const [step, setStep] = useState<Step>('input');
  const [query, setQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Planning data
  const [planningData, setPlanningData] = useState<PlanningData>({
    originalQuery: '',
    understoodQuery: '',
    userModifiedQuery: '',
    selectedAngles: [],
    customAngle: '',
    subQuestions: [],
    userModifiedSubQuestions: []
  });

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [query]);

  // Step 1: Understand query via API
  const processQueryUnderstanding = async (inputQuery: string) => {
    setIsProcessing(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/planning/understand`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: inputQuery })
      });
      
      if (!response.ok) throw new Error('Failed to understand query');
      
      const data = await response.json();
      
      setPlanningData(prev => ({
        ...prev,
        originalQuery: inputQuery,
        understoodQuery: data.understood_query,
        userModifiedQuery: data.understood_query
      }));
      setStep('understanding');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsProcessing(false);
    }
  };

  // Step 2: Get research angles via API
  const processAngles = async () => {
    setIsProcessing(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/planning/angles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          understood_query: planningData.userModifiedQuery,
          domain: 'general'
        })
      });
      
      if (!response.ok) throw new Error('Failed to get angles');
      
      const data = await response.json();
      
      setPlanningData(prev => ({
        ...prev,
        selectedAngles: data.angles.slice(0, 4) // Pre-select first 4
      }));
      setStep('angles');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsProcessing(false);
    }
  };

  // Step 3: Decompose into sub-questions via API
  const processDecomposition = async () => {
    setIsProcessing(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/planning/decompose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          understood_query: planningData.userModifiedQuery,
          selected_angles: planningData.customAngle 
            ? [...planningData.selectedAngles, planningData.customAngle]
            : planningData.selectedAngles
        })
      });
      
      if (!response.ok) throw new Error('Failed to decompose query');
      
      const data = await response.json();
      
      setPlanningData(prev => ({
        ...prev,
        subQuestions: data.sub_questions,
        userModifiedSubQuestions: data.sub_questions
      }));
      setStep('decomposition');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsProcessing(false);
    }
  };

  const startResearch = () => {
    onSubmit(planningData);
  };

  const reset = () => {
    setStep('input');
    setQuery('');
    setPlanningData({
      originalQuery: '',
      understoodQuery: '',
      userModifiedQuery: '',
      selectedAngles: [],
      customAngle: '',
      subQuestions: [],
      userModifiedSubQuestions: []
    });
    setError(null);
  };

  // Step 1: Input
  if (step === 'input') {
    return (
      <div className="w-full max-w-4xl mx-auto animate-fade-in">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-violet-500 to-purple-600 mb-6 shadow-xl shadow-violet-200">
            <Sparkles className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-5xl font-bold bg-gradient-to-r from-gray-900 via-violet-700 to-purple-700 bg-clip-text text-transparent mb-4">
            Research OS
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto leading-relaxed">
            AI-powered multi-agent research with knowledge graphs, 
            real-time verification, and intelligent planning
          </p>
        </div>

        {/* Large Input Area */}
        <div className="bg-white rounded-3xl shadow-2xl border border-gray-100 p-8 mb-8">
          <label className="block text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
            What would you like to research?
          </label>
          <textarea
            ref={textareaRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your research question or topic...&#10;&#10;Example: What are the cardiovascular effects of GLP-1 drugs in diabetic patients?"
            className="w-full min-h-[160px] text-xl text-gray-800 placeholder:text-gray-400 border-2 border-gray-200 rounded-2xl p-6 focus:border-violet-500 focus:ring-4 focus:ring-violet-100 transition-all outline-none resize-none"
            disabled={isProcessing}
          />
          
          {/* Character count and hint */}
          <div className="flex items-center justify-between mt-4">
            <span className="text-sm text-gray-400">
              {query.length > 0 && `${query.length} characters`}
            </span>
            <span className="text-sm text-gray-500">
              Be specific for better results
            </span>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600">
              {error}
            </div>
          )}

          {/* Action Button */}
          <button
            onClick={() => query.trim() && processQueryUnderstanding(query)}
            disabled={!query.trim() || isProcessing}
            className="w-full mt-6 py-5 px-8 bg-gradient-to-r from-violet-600 to-purple-600 text-white text-lg font-semibold rounded-2xl hover:from-violet-700 hover:to-purple-700 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl flex items-center justify-center gap-3"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                Understanding your query...
              </>
            ) : (
              <>
                <Sparkles className="w-6 h-6" />
                Start Planning
                <ArrowRight className="w-6 h-6" />
              </>
            )}
          </button>
        </div>

        {/* Example Queries */}
        <div className="flex flex-wrap justify-center gap-3">
          <span className="text-sm text-gray-500">Try:</span>
          {[
            "GLP-1 cardiovascular effects",
            "AI safety alignment research", 
            "Climate change mitigation strategies"
          ].map((example) => (
            <button
              key={example}
              onClick={() => setQuery(example)}
              className="text-sm px-4 py-2 bg-gray-100 hover:bg-violet-100 text-gray-600 hover:text-violet-700 rounded-full transition-colors"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Step 2: Understanding Validation
  if (step === 'understanding') {
    return (
      <div className="w-full max-w-4xl mx-auto animate-fade-in">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center">
            <span className="text-violet-600 font-bold">1</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Query Understanding</h2>
            <p className="text-gray-500">I've interpreted your research intent</p>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8 mb-6">
          {/* Original */}
          <div className="mb-8">
            <label className="block text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Your Original Query
            </label>
            <div className="p-4 bg-gray-50 rounded-xl text-gray-700">
              {planningData.originalQuery}
            </div>
          </div>

          {/* AI Understanding */}
          <div className="mb-8">
            <label className="flex items-center gap-2 text-sm font-semibold text-violet-600 uppercase tracking-wider mb-3">
              <Sparkles className="w-4 h-4" />
              My Understanding
            </label>
            <textarea
              value={planningData.userModifiedQuery}
              onChange={(e) => setPlanningData(prev => ({ ...prev, userModifiedQuery: e.target.value }))}
              className="w-full min-h-[120px] text-lg text-gray-800 border-2 border-violet-200 rounded-xl p-4 focus:border-violet-500 focus:ring-4 focus:ring-violet-100 transition-all outline-none resize-none"
            />
            <p className="text-sm text-gray-500 mt-2">
              Feel free to edit my understanding to better match your intent
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600">
              {error}
            </div>
          )}

          {/* Navigation */}
          <div className="flex gap-4">
            <button
              onClick={() => setStep('input')}
              className="flex-1 py-4 px-6 border-2 border-gray-200 text-gray-600 font-semibold rounded-xl hover:border-gray-300 hover:bg-gray-50 transition-all flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back
            </button>
            <button
              onClick={processAngles}
              disabled={isProcessing}
              className="flex-1 py-4 px-6 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-semibold rounded-xl hover:from-violet-700 hover:to-purple-700 transition-all flex items-center justify-center gap-2"
            >
              {isProcessing ? (
                <><Loader2 className="w-5 h-5 animate-spin" /> Thinking...</>
              ) : (
                <><>Continue</> <ArrowRight className="w-5 h-5" /></>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 3: Research Angles
  if (step === 'angles') {
    const toggleAngle = (angle: string) => {
      setPlanningData(prev => ({
        ...prev,
        selectedAngles: prev.selectedAngles.includes(angle)
          ? prev.selectedAngles.filter(a => a !== angle)
          : [...prev.selectedAngles, angle]
      }));
    };

    const allAngles = planningData.selectedAngles.length > 0 
      ? planningData.selectedAngles 
      : [
          'Clinical trials and efficacy data',
          'Mechanism of action and pharmacology',
          'Safety profile and side effects',
          'Comparative analysis with alternatives',
          'Recent regulatory updates and guidelines',
          'Patient outcomes and real-world evidence',
          'Economic and cost-effectiveness analysis',
          'Future research directions and emerging therapies'
        ];

    return (
      <div className="w-full max-w-4xl mx-auto animate-fade-in">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center">
            <span className="text-violet-600 font-bold">2</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Research Angles</h2>
            <p className="text-gray-500">Select the perspectives you want to explore</p>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {allAngles.map((angle) => (
              <button
                key={angle}
                onClick={() => toggleAngle(angle)}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  planningData.selectedAngles.includes(angle)
                    ? 'border-violet-500 bg-violet-50'
                    : 'border-gray-200 hover:border-violet-300 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 ${
                    planningData.selectedAngles.includes(angle)
                      ? 'bg-violet-500 border-violet-500'
                      : 'border-gray-300'
                  }`}>
                    {planningData.selectedAngles.includes(angle) && (
                      <Check className="w-3 h-3 text-white" />
                    )}
                  </div>
                  <span className={`font-medium ${
                    planningData.selectedAngles.includes(angle) ? 'text-violet-900' : 'text-gray-700'
                  }`}>
                    {angle}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Custom Angle */}
          <div className="mb-8">
            <label className="flex items-center gap-2 text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
              <Edit3 className="w-4 h-4" />
              Add Your Own Angle (Optional)
            </label>
            <input
              type="text"
              value={planningData.customAngle}
              onChange={(e) => setPlanningData(prev => ({ ...prev, customAngle: e.target.value }))}
              placeholder="e.g., Ethical considerations, Environmental impact..."
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-violet-500 focus:ring-4 focus:ring-violet-100 transition-all outline-none"
            />
          </div>

          {/* Selected Count */}
          <div className="flex items-center justify-between mb-6">
            <span className="text-sm text-gray-500">
              {planningData.selectedAngles.length} angles selected
            </span>
            <span className="text-sm text-violet-600">
              {planningData.selectedAngles.length < 2 && 'Select at least 2 angles'}
            </span>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600">
              {error}
            </div>
          )}

          {/* Navigation */}
          <div className="flex gap-4">
            <button
              onClick={() => setStep('understanding')}
              className="flex-1 py-4 px-6 border-2 border-gray-200 text-gray-600 font-semibold rounded-xl hover:border-gray-300 hover:bg-gray-50 transition-all flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back
            </button>
            <button
              onClick={processDecomposition}
              disabled={planningData.selectedAngles.length < 2 || isProcessing}
              className="flex-1 py-4 px-6 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-semibold rounded-xl hover:from-violet-700 hover:to-purple-700 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              {isProcessing ? (
                <><Loader2 className="w-5 h-5 animate-spin" /> Decomposing...</>
              ) : (
                <><>Continue</> <ArrowRight className="w-5 h-5" /></>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 4: Sub-questions
  if (step === 'decomposition') {
    return (
      <div className="w-full max-w-4xl mx-auto animate-fade-in">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center">
            <span className="text-violet-600 font-bold">3</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Research Plan</h2>
            <p className="text-gray-500">I've broken this down into sub-questions</p>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8 mb-6">
          <div className="mb-6">
            <label className="flex items-center gap-2 text-sm font-semibold text-violet-600 uppercase tracking-wider mb-4">
              <List className="w-4 h-4" />
              Sub-Questions to Research
            </label>
            <p className="text-gray-500 mb-4">
              Each sub-question will be searched independently and results combined
            </p>
          </div>

          <div className="space-y-4 mb-8">
            {planningData.userModifiedSubQuestions.map((sq, idx) => (
              <div key={idx} className="flex items-start gap-3">
                <span className="w-8 h-8 rounded-full bg-violet-100 text-violet-600 font-semibold flex items-center justify-center flex-shrink-0">
                  {idx + 1}
                </span>
                <input
                  type="text"
                  value={sq}
                  onChange={(e) => {
                    const newSqs = [...planningData.userModifiedSubQuestions];
                    newSqs[idx] = e.target.value;
                    setPlanningData(prev => ({ ...prev, userModifiedSubQuestions: newSqs }));
                  }}
                  className="flex-1 px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-violet-500 focus:ring-4 focus:ring-violet-100 transition-all outline-none"
                />
              </div>
            ))}
          </div>

          {/* Add custom sub-question */}
          <button
            onClick={() => setPlanningData(prev => ({
              ...prev,
              userModifiedSubQuestions: [...prev.userModifiedSubQuestions, '']
            }))}
            className="w-full py-3 border-2 border-dashed border-gray-300 text-gray-500 rounded-xl hover:border-violet-400 hover:text-violet-600 transition-all flex items-center justify-center gap-2 mb-8"
          >
            <Edit3 className="w-4 h-4" />
            Add Custom Sub-Question
          </button>

          {/* Navigation */}
          <div className="flex gap-4">
            <button
              onClick={() => setStep('angles')}
              className="flex-1 py-4 px-6 border-2 border-gray-200 text-gray-600 font-semibold rounded-xl hover:border-gray-300 hover:bg-gray-50 transition-all flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back
            </button>
            <button
              onClick={() => setStep('ready')}
              className="flex-1 py-4 px-6 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-semibold rounded-xl hover:from-violet-700 hover:to-purple-700 transition-all flex items-center justify-center gap-2"
            >
              <Check className="w-5 h-5" />
              Review & Start
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 5: Ready to Start
  if (step === 'ready') {
    return (
      <div className="w-full max-w-4xl mx-auto animate-fade-in">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <Check className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Ready to Research</h2>
            <p className="text-gray-500">Review your plan before starting</p>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8 mb-6">
          {/* Summary */}
          <div className="space-y-6 mb-8">
            <div className="p-4 bg-violet-50 rounded-xl">
              <label className="text-sm font-semibold text-violet-600 uppercase tracking-wider mb-2 block">
                Research Focus
              </label>
              <p className="text-gray-800">{planningData.userModifiedQuery}</p>
            </div>

            <div>
              <label className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 block">
                Selected Angles ({planningData.selectedAngles.length})
              </label>
              <div className="flex flex-wrap gap-2">
                {planningData.selectedAngles.map(angle => (
                  <span key={angle} className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-full text-sm">
                    {angle}
                  </span>
                ))}
                {planningData.customAngle && (
                  <span className="px-3 py-1.5 bg-violet-100 text-violet-700 rounded-full text-sm">
                    {planningData.customAngle}
                  </span>
                )}
              </div>
            </div>

            <div>
              <label className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 block">
                Sub-Questions ({planningData.userModifiedSubQuestions.length})
              </label>
              <ul className="space-y-2">
                {planningData.userModifiedSubQuestions.map((sq, idx) => (
                  <li key={idx} className="flex items-start gap-3 text-gray-700">
                    <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-semibold flex items-center justify-center flex-shrink-0">
                      {idx + 1}
                    </span>
                    {sq}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Mode Selection */}
          <div className="mb-8">
            <label className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4 block">
              Research Depth
            </label>
            <div className="grid grid-cols-3 gap-4">
              {[
                { id: 'quick', label: 'Quick', time: '~2 min', sources: '15 sources', icon: Search },
                { id: 'standard', label: 'Standard', time: '~5 min', sources: '30 sources', icon: Lightbulb },
                { id: 'deep', label: 'Deep', time: '~10 min', sources: '50 sources', icon: MessageSquare },
              ].map((mode) => {
                const Icon = mode.icon;
                return (
                  <button
                    key={mode.id}
                    className="p-4 border-2 border-violet-500 bg-violet-50 rounded-xl text-center"
                  >
                    <Icon className="w-6 h-6 mx-auto mb-2 text-violet-600" />
                    <div className="font-semibold text-violet-900">{mode.label}</div>
                    <div className="text-sm text-violet-600">{mode.time}</div>
                    <div className="text-xs text-violet-500">{mode.sources}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Start Button */}
          <button
            onClick={startResearch}
            disabled={isResearching}
            className="w-full py-5 px-8 bg-gradient-to-r from-violet-600 to-purple-600 text-white text-xl font-bold rounded-2xl hover:from-violet-700 hover:to-purple-700 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl flex items-center justify-center gap-3"
          >
            {isResearching ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                Starting Research...
              </>
            ) : (
              <>
                <Play className="w-6 h-6" />
                Start Research
              </>
            )}
          </button>

          <button
            onClick={reset}
            className="w-full mt-4 py-3 text-gray-500 hover:text-gray-700 transition-colors flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Start Over
          </button>
        </div>
      </div>
    );
  }

  return null;
}
