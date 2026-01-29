/**
 * Modern Progress Tracker with animated progress bar and phase indicators
 */
import { 
  Loader2, 
  Search, 
  Download, 
  Filter, 
  Brain, 
  Network, 
  CheckCircle, 
  MessageSquare, 
  FileText,
  AlertCircle,
  Sparkles
} from 'lucide-react';
import type { ProgressTrackerProps } from '../types';

const phaseConfig: Record<string, { 
  icon: typeof Loader2; 
  label: string; 
  color: string;
  bgColor: string;
}> = {
  planning: { 
    icon: Sparkles, 
    label: 'Planning', 
    color: 'text-violet-500',
    bgColor: 'bg-violet-500'
  },
  searching: { 
    icon: Search, 
    label: 'Searching', 
    color: 'text-blue-500',
    bgColor: 'bg-blue-500'
  },
  crawling: { 
    icon: Download, 
    label: 'Crawling', 
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-500'
  },
  curating: { 
    icon: Filter, 
    label: 'Curating', 
    color: 'text-teal-500',
    bgColor: 'bg-teal-500'
  },
  extracting: { 
    icon: Brain, 
    label: 'Extracting', 
    color: 'text-indigo-500',
    bgColor: 'bg-indigo-500'
  },
  building_graph: { 
    icon: Network, 
    label: 'Building Graph', 
    color: 'text-violet-500',
    bgColor: 'bg-violet-500'
  },
  verifying: { 
    icon: CheckCircle, 
    label: 'Verifying', 
    color: 'text-green-500',
    bgColor: 'bg-green-500'
  },
  debating: { 
    icon: MessageSquare, 
    label: 'Debating', 
    color: 'text-orange-500',
    bgColor: 'bg-orange-500'
  },
  synthesizing: { 
    icon: FileText, 
    label: 'Synthesizing', 
    color: 'text-pink-500',
    bgColor: 'bg-pink-500'
  },
  complete: { 
    icon: CheckCircle, 
    label: 'Complete', 
    color: 'text-green-600',
    bgColor: 'bg-green-600'
  },
  error: { 
    icon: AlertCircle, 
    label: 'Error', 
    color: 'text-red-500',
    bgColor: 'bg-red-500'
  },
};

export function ProgressTracker({ phase, message, progress }: ProgressTrackerProps) {
  const config = phaseConfig[phase] || { 
    icon: Loader2, 
    label: phase, 
    color: 'text-gray-500',
    bgColor: 'bg-gray-500'
  };
  const Icon = config.icon;

  const phases = [
    { key: 'planning', label: 'Plan' },
    { key: 'searching', label: 'Search' },
    { key: 'crawling', label: 'Crawl' },
    { key: 'curating', label: 'Curate' },
    { key: 'extracting', label: 'Extract' },
    { key: 'verifying', label: 'Verify' },
    { key: 'synthesizing', label: 'Synth' },
    { key: 'complete', label: 'Done' },
  ];
  const currentPhaseIndex = phases.findIndex(p => p.key === phase);

  return (
    <div className="w-full">
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <div className={`p-3 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100 ${config.color}`}>
            <Icon className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900">{config.label}</h3>
            <p className="text-sm text-gray-500">{message}</p>
          </div>
          <div className="text-3xl font-bold bg-gradient-to-r from-violet-600 to-purple-600 bg-clip-text text-transparent">
            {progress}%
          </div>
        </div>

        {/* Progress Bar */}
        <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden mb-6">
          <div
            className={`absolute top-0 left-0 h-full ${config.bgColor} transition-all duration-700 ease-out rounded-full`}
            style={{ width: `${progress}%` }}
          />
          
          {/* Animated shimmer */}
          {progress < 100 && (
            <div 
              className="absolute top-0 left-0 h-full w-1/3 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer"
              style={{ 
                animation: 'shimmer 2s infinite linear',
                transform: 'translateX(-100%)',
              }} 
            />
          )}
        </div>

        {/* Phase Indicators */}
        <div className="flex justify-between">
          {phases.map((p, i) => {
            const isActive = phase === p.key;
            const isPast = currentPhaseIndex > i;
            const isComplete = phase === 'complete';

            return (
              <div
                key={p.key}
                className="flex flex-col items-center gap-1.5"
              >
                <div
                  className={`
                    w-2.5 h-2.5 rounded-full transition-all duration-300
                    ${isActive ? `${config.bgColor} scale-150 ring-4 ring-opacity-30 ring-current` :
                      isPast || isComplete ? 'bg-green-500' : 'bg-gray-300'}
                  `}
                />
                <span className={`text-xs font-medium
                  ${isActive ? 'text-gray-900' :
                    isPast || isComplete ? 'text-green-600' : 'text-gray-400'}
                `}>
                  {p.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
        .animate-shimmer {
          animation: shimmer 2s infinite linear;
        }
      `}</style>
    </div>
  );
}
