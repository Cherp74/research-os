import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import type { KnowledgeGraphProps, GraphNode } from '../types';

export function KnowledgeGraph({ data, onNodeClick }: KnowledgeGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [zoomTransform, setZoomTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity);

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // Clear previous render

    const width = containerRef.current?.clientWidth || 800;
    const height = 500;

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        setZoomTransform(event.transform);
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Create main group for zoom
    const g = svg.append('g');

    // Create arrow markers for edges
    const defs = svg.append('defs');
    
    ['SUPPORTS', 'CONTRADICTS', 'ABOUT', 'FROM', 'RELATED_TO'].forEach(relation => {
      const color = relation === 'SUPPORTS' ? '#10b981' :
                   relation === 'CONTRADICTS' ? '#ef4444' : '#9ca3af';
      
      defs.append('marker')
        .attr('id', `arrow-${relation}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 25)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color);
    });

    // Create force simulation
    const simulation = d3.forceSimulation(data.nodes as any)
      .force('link', d3.forceLink(data.edges)
        .id((d: any) => d.id)
        .distance(100)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => d.size + 10));

    // Draw edges
    const links = g.append('g')
      .selectAll('line')
      .data(data.edges)
      .enter()
      .append('line')
      .attr('stroke', (d: any) => d.color)
      .attr('stroke-width', (d: any) => d.width)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', (d: any) => `url(#arrow-${d.relation})`);

    // Draw edge labels
    const edgeLabels = g.append('g')
      .selectAll('text')
      .data(data.edges.filter((e: any) => e.relation === 'CONTRADICTS' || e.relation === 'SUPPORTS'))
      .enter()
      .append('text')
      .attr('font-size', '10px')
      .attr('fill', (d: any) => d.color)
      .attr('text-anchor', 'middle')
      .text((d: any) => d.relation === 'CONTRADICTS' ? '⚠️' : '✓');

    // Draw nodes
    const nodes = g.append('g')
      .selectAll('g')
      .data(data.nodes)
      .enter()
      .append('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<any, any>()
        .on('start', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d: any) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // Node circles
    nodes.append('circle')
      .attr('r', (d: any) => d.size)
      .attr('fill', (d: any) => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))');

    // Node labels
    nodes.append('text')
      .attr('dy', (d: any) => d.size + 15)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', '#374151')
      .attr('font-weight', '500')
      .text((d: any) => {
        const label = d.label;
        return label.length > 25 ? label.slice(0, 25) + '...' : label;
      });

    // Node type indicators
    nodes.append('text')
      .attr('dy', 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .text((d: any) => {
        if (d.type === 'claim') return '📄';
        if (d.type === 'entity') return '🏷️';
        if (d.type === 'source') return '🔗';
        return '?';
      });

    // Click handler
    nodes.on('click', (event, d: any) => {
      event.stopPropagation();
      setSelectedNode(d);
      if (onNodeClick) onNodeClick(d);
    });

    // Update positions on simulation tick
    simulation.on('tick', () => {
      links
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      edgeLabels
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2);

      nodes.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [data, onNodeClick]);

  const handleZoomIn = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(
        (d3.zoom() as any).transform,
        zoomTransform.scale(zoomTransform.k * 1.3)
      );
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(
        (d3.zoom() as any).transform,
        zoomTransform.scale(zoomTransform.k / 1.3)
      );
    }
  };

  const handleReset = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(
        (d3.zoom() as any).transform,
        d3.zoomIdentity
      );
    }
  };

  if (!data.nodes.length) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-xl">
        <p className="text-gray-500">Knowledge graph will appear here...</p>
      </div>
    );
  }

  return (
    <div className="relative" ref={containerRef}>
      {/* Controls */}
      <div className="absolute top-4 right-4 flex gap-2 z-10">
        <button
          onClick={handleZoomIn}
          className="p-2 bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow"
          title="Zoom in"
        >
          <ZoomIn className="w-5 h-5 text-gray-600" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow"
          title="Zoom out"
        >
          <ZoomOut className="w-5 h-5 text-gray-600" />
        </button>
        <button
          onClick={handleReset}
          className="p-2 bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow"
          title="Reset view"
        >
          <Maximize className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur rounded-lg shadow-md p-3 z-10">
        <h4 className="text-xs font-semibold text-gray-700 mb-2">Legend</h4>
        <div className="space-y-1 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-500"></span>
            <span className="text-gray-600">Claim</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-green-500"></span>
            <span className="text-gray-600">Entity</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-gray-500"></span>
            <span className="text-gray-600">Source</span>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="w-6 h-0.5 bg-green-500"></span>
            <span className="text-gray-600">Supports</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-0.5 bg-red-500"></span>
            <span className="text-gray-600">Contradicts</span>
          </div>
        </div>
      </div>

      {/* Node Details Panel */}
      {selectedNode && (
        <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg p-4 max-w-xs z-10">
          <div className="flex items-start justify-between">
            <h4 className="font-semibold text-gray-900 capitalize">
              {selectedNode.type}: {selectedNode.label.slice(0, 30)}
              {selectedNode.label.length > 30 ? '...' : ''}
            </h4>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          </div>
          <div className="mt-2 text-sm text-gray-600">
            {Object.entries(selectedNode.data).map(([key, value]) => (
              <div key={key} className="flex justify-between py-1">
                <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                <span className="font-medium">
                  {typeof value === 'number' ? value.toFixed(2) : String(value).slice(0, 50)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Graph */}
      <svg
        ref={svgRef}
        className="w-full h-96 bg-gray-50 rounded-xl border border-gray-200"
      />
    </div>
  );
}
