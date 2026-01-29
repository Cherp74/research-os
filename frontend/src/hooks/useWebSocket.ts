import { useState, useCallback, useRef, useEffect } from 'react';
import type { ResearchEvent } from '../types';

interface UseWebSocketReturn {
  isConnected: boolean;
  isResearching: boolean;
  events: ResearchEvent[];
  sessionId: string | null;
  error: string | null;
  startResearch: (query: string, mode: string, targetSources: number) => void;
  disconnect: () => void;
  clearEvents: () => void;
}

export function useWebSocket(url: string = 'ws://localhost:8000/ws/research'): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isResearching, setIsResearching] = useState(false);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsResearching(false);
  }, []);

  const startResearch = useCallback((query: string, mode: string, targetSources: number) => {
    // Disconnect any existing connection
    disconnect();
    
    setError(null);
    setEvents([]);
    setIsResearching(true);
    
    const ws = new WebSocket(url);
    wsRef.current = ws;
    
    ws.onopen = () => {
      setIsConnected(true);
      // Send research request with planning data
      ws.send(JSON.stringify({
        query,
        mode,
        target_sources: targetSources
      }));
    };
    
    ws.onmessage = (event) => {
      try {
        const data: ResearchEvent = JSON.parse(event.data);
        
        setEvents((prev) => [...prev, data]);
        
        if (data.type === 'session_created') {
          setSessionId(data.session_id);
        }
        
        if (data.type === 'report' && data.complete) {
          setIsResearching(false);
        }
        
        if (data.type === 'error') {
          setError(data.message);
          setIsResearching(false);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };
    
    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setError('WebSocket connection error');
      setIsConnected(false);
      setIsResearching(false);
    };
    
    ws.onclose = () => {
      setIsConnected(false);
      setIsResearching(false);
    };
  }, [url, disconnect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isResearching,
    events,
    sessionId,
    error,
    startResearch,
    disconnect,
    clearEvents
  };
}
