import { MessageSquare, User, Scale } from 'lucide-react';
import type { DebateViewProps, DebateEvent } from '../types';

export function DebateView({ events }: DebateViewProps) {
  if (events.length === 0) {
    return null;
  }

  // Group events by round
  const rounds: Record<number, DebateEvent[]> = {};
  events.forEach(event => {
    if (!rounds[event.round_number]) {
      rounds[event.round_number] = [];
    }
    rounds[event.round_number].push(event);
  });

  const getAgentColor = (agentName: string) => {
    switch (agentName.toLowerCase()) {
      case 'scout':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'skeptic':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'analyst':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-gray-900">
        <Scale className="w-5 h-5 text-orange-500" />
        <h3 className="font-semibold">Agent Debate</h3>
        <span className="text-sm text-gray-500">
          ({events.length} arguments across {Object.keys(rounds).length} rounds)
        </span>
      </div>

      <div className="space-y-6">
        {Object.entries(rounds).map(([roundNum, roundEvents]) => (
          <div key={roundNum} className="border-l-2 border-orange-200 pl-4">
            <h4 className="text-sm font-medium text-orange-700 mb-3">
              Round {roundNum}
            </h4>
            
            <div className="space-y-3">
              {roundEvents.map((event, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-lg border ${getAgentColor(event.agent_name)}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <User className="w-4 h-4" />
                    <span className="font-medium capitalize">{event.agent_name}</span>
                    <span className="text-xs opacity-70">
                      confidence: {(event.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-sm">{event.argument}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-orange-50 rounded-lg p-4 text-sm text-orange-800">
        <p className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4" />
          <strong>Why debate?</strong> When agents find contradictory evidence, 
          they debate to determine the most reliable conclusion. This helps identify 
          genuine uncertainty vs. clear consensus.
        </p>
      </div>
    </div>
  );
}
