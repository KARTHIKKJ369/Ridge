import React from 'react';
import { 
  Zap, 
  Layers, 
  Search, 
  ShieldCheck, 
  Globe, 
  Edit3, 
  Sparkles 
} from 'lucide-react';

export interface TraceEvent {
  node: string;
  message: string;
  timestamp?: string;
  documents?: string[];
  doc_grades?: any[];
  answer?: string;
  confidence?: any;
  conflict_data?: any;
  latency_ms?: number;
  sub_queries?: string[];
  expanded_count?: number;
}

export const getNodeDetails = (nodeName: string): { title: string; desc: string; icon: React.ReactNode; color: string } => {
  switch (nodeName) {
    case 'cache_hit_node':
      return {
        title: 'Semantic Query Cache',
        desc: 'Direct sub-millisecond retrieval from verified vector cache',
        icon: <Zap size={13} />,
        color: 'moss'
      };
    case 'decompose_node':
      return {
        title: 'Query Decomposition',
        desc: 'Multi-hop compound question splitter with parallel retrieval',
        icon: <Layers size={13} />,
        color: 'indigo'
      };
    case 'retrieve_node':
      return { 
        title: 'Hybrid Retrieval', 
        desc: 'Dense pgvector HNSW + Sparse GIN FTS with SQL RRF & FlashRank', 
        icon: <Search size={13} />, 
        color: 'teal' 
      };
    case 'grade_node':
      return { 
        title: 'Relevance Grading', 
        desc: 'Strict LLM veracity evaluation', 
        icon: <ShieldCheck size={13} />, 
        color: 'rust' 
      };
    case 'web_search_node':
      return { 
        title: 'Web Search Fallback', 
        desc: 'DuckDuckGo knowledge search and retrieval', 
        icon: <Globe size={13} />, 
        color: 'amber' 
      };
    case 'rewrite_node':
      return { 
        title: 'Query Reformulation', 
        desc: 'Adaptive query rewriting with domain glossary expansion', 
        icon: <Edit3 size={13} />, 
        color: 'moss' 
      };
    case 'generate_node':
      return { 
        title: 'Answer Synthesis', 
        desc: 'Grounded generation from verified context', 
        icon: <Sparkles size={13} />, 
        color: 'summit' 
      };
    case 'check_hallucination_node':
      return { 
        title: 'Hallucination Auditor', 
        desc: 'Post-generation grounding and faithfulness verification', 
        icon: <ShieldCheck size={13} />, 
        color: 'moss' 
      };
    default:
      return { 
        title: nodeName, 
        desc: 'Pipeline state executed', 
        icon: <Zap size={13} />, 
        color: 'summit' 
      };
  }
};

interface TraceWaterfallProps {
  traces: TraceEvent[];
}

export const TraceWaterfall: React.FC<TraceWaterfallProps> = ({ traces }) => {
  const validTraces = (traces || []).filter(t => t && t.node && t.node.endsWith('_node'));
  if (validTraces.length === 0) {
    return (
      <div className="trace-empty-state">
        <Zap size={28} className="text-slate-400 opacity-60" />
        <h4>No active ascent trace</h4>
        <p>Ask a question to observe live LangGraph execution steps and node telemetry.</p>
      </div>
    );
  }

  return (
    <div className="trace-stepper-list">
      {validTraces.map((trace, i) => {
        const nodeInfo = getNodeDetails(trace.node);
        return (
          <div key={i} className="stepper-item">
            <div className={`stepper-icon-bullet ${nodeInfo.color}`}>
              {nodeInfo.icon}
            </div>
            <div className="stepper-content">
              <div className="stepper-head">
                <span className="node-title">{nodeInfo.title}</span>
                {trace.latency_ms != null && (
                  <span className="latency-tag">{trace.latency_ms} ms</span>
                )}
              </div>
              <div className="stepper-body">
                <span className="output-msg">{trace.message}</span>
                {trace.node === 'decompose_node' && trace.sub_queries && trace.sub_queries.length > 1 && (
                  <div className="subqueries-list">
                    {trace.sub_queries.map((sq, sqIdx) => (
                      <span key={sqIdx} className="subquery-item">
                        ↳ {sq}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
