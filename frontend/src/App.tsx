import { useState, useMemo } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { QueryBuilder } from './components/QueryBuilder';
import { ProgressTracker } from './components/ProgressTracker';
import { KnowledgeGraph } from './components/KnowledgeGraph';
import { SourceCard } from './components/SourceCard';
import { ClaimCard } from './components/ClaimCard';
import { DebateView } from './components/DebateView';
import { ReportViewer } from './components/ReportViewer';
import {
  BarChart3,
  FileText,
  MessageSquare,
  CheckCircle,
  AlertCircle,
  Network,
  Sparkles
} from 'lucide-react';
import type {
  Source,
  Claim,
  GraphData,
  DebateEvent,
  PlanningData
} from './types';

function App() {
  const { 
    isConnected, 
    isResearching, 
    events, 
    sessionId, 
    error,
    startResearch 
  } = useWebSocket();

  const [activeTab, setActiveTab] = useState<'overview' | 'sources' | 'claims' | 'debate' | 'report'>('overview');
  const [planningComplete, setPlanningComplete] = useState(false);

  // Extract data from events
  const { 
    status, 
    sources, 
    claims, 
    graphData, 
    debateEvents, 
    report 
  } = useMemo(() => {
    const result = {
      status: { phase: 'planning', message: 'Ready to start', progress: 0 },
      sources: [] as Source[],
      claims: [] as Claim[],
      graphData: { nodes: [], edges: [] } as GraphData,
      debateEvents: [] as DebateEvent[],
      report: ''
    };

    events.forEach(event => {
      switch (event.type) {
        case 'status':
          result.status = {
            phase: event.phase,
            message: event.message,
            progress: event.progress_percent
          };
          break;
        case 'source':
          result.sources.push(event.source);
          break;
        case 'claim':
          result.claims.push(event.claim);
          break;
        case 'graph':
          result.graphData = { nodes: event.nodes, edges: event.edges };
          break;
        case 'debate':
          result.debateEvents.push(event);
          break;
        case 'report':
          result.report = event.markdown;
          break;
      }
    });

    return result;
  }, [events]);

  const handleStartResearch = (planningData: PlanningData) => {
    // Combine all sub-questions into the main query
    const combinedQuery = planningData.userModifiedQuery;
    
    startResearch(combinedQuery, 'standard', 30);
    setPlanningComplete(true);
    setActiveTab('overview');
  };

  // Create source lookup for claim cards
  const sourceLookup = useMemo(() => {
    const lookup: Record<string, Source> = {};
    sources.forEach(s => lookup[s.id] = s);
    return lookup;
  }, [sources]);

  // Show QueryBuilder if no research started yet
  if (!planningComplete && !isResearching && events.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-violet-50">
        {/* Header */}
        <header className="bg-white/80 backdrop-blur border-b border-gray-200/50 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold bg-gradient-to-r from-violet-700 to-purple-700 bg-clip-text text-transparent">
                    Research OS
                  </h1>
                  <p className="text-xs text-gray-500">Multi-Agent Research System</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-sm text-gray-500">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-6 py-12">
          <QueryBuilder 
            onSubmit={handleStartResearch} 
            isResearching={isResearching} 
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-violet-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur border-b border-gray-200/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-violet-700 to-purple-700 bg-clip-text text-transparent">
                  Research OS
                </h1>
                <p className="text-xs text-gray-500">Multi-Agent Research System</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className="text-gray-500">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              {sessionId && (
                <span className="text-xs text-gray-400 font-mono bg-gray-100 px-2 py-1 rounded">
                  {sessionId.slice(0, 8)}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Progress Tracker */}
        {(isResearching || status.progress > 0) && (
          <section className="mb-8">
            <ProgressTracker 
              phase={status.phase}
              message={status.message}
              progress={status.progress}
            />
          </section>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Results Tabs */}
        {(sources.length > 0 || claims.length > 0 || report) && (
          <section>
            {/* Tab Navigation */}
            <div className="flex gap-1 mb-6 bg-white/80 backdrop-blur p-1.5 rounded-2xl shadow-sm border border-gray-200/50">
              {[
                { id: 'overview', label: 'Overview', icon: BarChart3, count: null },
                { id: 'sources', label: 'Sources', icon: FileText, count: sources.length },
                { id: 'claims', label: 'Claims', icon: CheckCircle, count: claims.length },
                { id: 'debate', label: 'Debate', icon: MessageSquare, count: debateEvents.length },
                { id: 'report', label: 'Report', icon: Network, count: report ? 1 : 0 },
              ].map(tab => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`
                      flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all
                      ${isActive 
                        ? 'bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-md' 
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                      }
                    `}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                    {tab.count !== null && tab.count > 0 && (
                      <span className={`ml-1 px-2 py-0.5 rounded-full text-xs ${
                        isActive ? 'bg-white/20' : 'bg-gray-200'
                      }`}>
                        {tab.count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Tab Content */}
            <div className="space-y-6">
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Stats Cards */}
                  <div className="grid grid-cols-4 gap-4">
                    {[
                      { label: 'Sources', value: sources.length, color: 'blue' },
                      { label: 'Claims', value: claims.length, color: 'violet' },
                      { label: 'Verified', value: claims.filter(c => c.verified).length, color: 'green' },
                      { label: 'Debates', value: new Set(debateEvents.map(e => e.round_number)).size, color: 'orange' },
                    ].map((stat, idx) => (
                      <div key={idx} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
                        <p className="text-sm text-gray-500 mb-1">{stat.label}</p>
                        <p className={`text-3xl font-bold text-${stat.color}-600`}>{stat.value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Knowledge Graph */}
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                    <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <Network className="w-5 h-5 text-violet-500" />
                      Knowledge Graph
                    </h3>
                    <KnowledgeGraph data={graphData} />
                  </div>
                </div>
              )}

              {activeTab === 'sources' && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Discovered Sources</h3>
                  {sources.length === 0 ? (
                    <p className="text-gray-500">No sources yet...</p>
                  ) : (
                    sources.map(source => (
                      <SourceCard key={source.id} source={source} />
                    ))
                  )}
                </div>
              )}

              {activeTab === 'claims' && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Extracted Claims</h3>
                  {claims.length === 0 ? (
                    <p className="text-gray-500">No claims yet...</p>
                  ) : (
                    claims.map(claim => (
                      <ClaimCard 
                        key={claim.id} 
                        claim={claim} 
                        source={sourceLookup[claim.source_id]}
                      />
                    ))
                  )}
                </div>
              )}

              {activeTab === 'debate' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                  <DebateView events={debateEvents} />
                </div>
              )}

              {activeTab === 'report' && (
                <div>
                  {report ? (
                    <ReportViewer markdown={report} />
                  ) : (
                    <div className="bg-gray-50 rounded-2xl p-12 text-center">
                      <p className="text-gray-500">Report will be available when synthesis is complete...</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
