import React, { useState, useEffect } from 'react';
import mermaid from 'mermaid';
import { 
  Activity, 
  Copy, 
  Check, 
  Code, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Minimize2 
} from 'lucide-react';

mermaid.initialize({
  startOnLoad: false,
  suppressErrorRendering: true,
  theme: 'base',
  securityLevel: 'loose',
  flowchart: {
    useMaxWidth: false,
    htmlLabels: true,
    curve: 'basis',
    nodeSpacing: 30,
    rankSpacing: 36,
    padding: 10,
  },
  themeVariables: {
    fontFamily: "'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: '12.5px',
    lineColor: '#64748b',
    primaryColor: '#ffffff',
    primaryTextColor: '#1e293b',
    primaryBorderColor: '#0284c7',
    secondaryColor: '#f1f5f9',
    tertiaryColor: '#f8fafc',
    mainBkg: '#ffffff',
    nodeBorder: '#0284c7',
    clusterBkg: 'rgba(2, 132, 199, 0.03)',
    clusterBorder: 'rgba(2, 132, 199, 0.25)',
    titleColor: '#1e293b',
    edgeLabelBackground: '#ffffff',
  }
});

export const isMermaidComplete = (text: string): boolean => {
  if (!text || !text.trim()) return false;
  const trimmed = text.trim();
  const lines = trimmed.split('\n');
  if (lines.length < 2) return false;

  const quotesCount = (trimmed.match(/"/g) || []).length;
  if (quotesCount % 2 !== 0) return false;

  if (/(-->|->|==>|-\.->|--|\(|\[|\{)\s*$/.test(trimmed)) return false;

  const subgraphCount = (trimmed.match(/\bsubgraph\b/gi) || []).length;
  const endCount = (trimmed.match(/\bend\b/gi) || []).length;
  if (subgraphCount > endCount) return false;

  return true;
};

export const sanitizeMermaidChart = (raw: string): string => {
  if (!raw) return '';
  let text = raw.trim();
  text = text.replace(/^```(mermaid)?\n?/i, '').replace(/```$/i, '').trim();

  // 1. Normalize Unicode hyphens/dashes to ASCII hyphen
  text = text.replace(/[\u2011\u2012\u00AD\u2013\u2014\u2212]/g, '-');

  // 2. Convert Unicode arrows & box-drawing characters to standard ASCII Mermaid arrows
  text = text.replace(/[\u2192\u27F6]/g, '-->');
  text = text.replace(/[\u21D2\u27F9]/g, '==>');
  text = text.replace(/\u2500{2,}>/g, '-->');
  text = text.replace(/\u2500>/g, '-->');
  text = text.replace(/\u2500{2,}/g, '--');
  text = text.replace(/-{3,}>/g, '-->');
  text = text.replace(/-\s*\.\s*->|-\.\s*->/g, '-.->');

  // 3. Strip HTML tags
  text = text.replace(/<[^>]+>/g, '');

  // 4. Fix subgraph syntax
  text = text.replace(/subgraph\s+([a-zA-Z0-9_-]+)\s*\[\s*(.*?)\s*\]/g, (_, id, label) => {
    const cleanLabel = label.replace(/^"|"$/g, '').replace(/"/g, "'").trim();
    return `subgraph ${id} ["${cleanLabel}"]`;
  });

  // 5. Fix stadium shapes
  text = text.replace(/\b([A-Za-z0-9_]+)\(\[\s*([^"\[\]\n]+?)\s*\]\)/g, (_, nodeId, label) => {
    return `${nodeId}(["${label.replace(/"/g, "'").trim()}"])`;
  });

  // 6. Fix subroutine shapes
  text = text.replace(/\b([A-Za-z0-9_]+)\[\[\s*([^"\[\]\n]+?)\s*\]\]/g, (_, nodeId, label) => {
    return `${nodeId}[["${label.replace(/"/g, "'").trim()}"]]`;
  });

  // 7. Auto-quote [] node labels
  text = text.replace(/\b([A-Za-z0-9_]+)\[([^"\[\]\n]+)\]/g, (_, nodeId, label) => {
    return `${nodeId}["${label.replace(/"/g, "'").trim()}"]`;
  });

  // 8. Auto-quote () node labels
  text = text.replace(/\b([A-Za-z0-9_]+)\((?!\()([^"()\n]+)\)(?!\))/g, (_, nodeId, label) => {
    return `${nodeId}("${label.replace(/"/g, "'").trim()}")`;
  });

  // 9. Auto-quote {} node labels
  text = text.replace(/\b([A-Za-z0-9_]+)\{([^"\{\}\n]+)\}/g, (_, nodeId, label) => {
    return `${nodeId}{"${label.replace(/"/g, "'").trim()}"}`;
  });

  // 10. Clean edge labels inside |...|
  text = text.replace(/([=-]>|--)\s*\|([^|\n]+)\|\s*([A-Za-z0-9_]+)/g, (_, arrow, label, target) => {
    const cleanLabel = label.replace(/["'\[\]()]/g, '').trim();
    return `${arrow}|${cleanLabel}| ${target}`;
  });

  return text;
};

const mermaidSvgCache = new Map<string, string>();

export const MermaidDiagram: React.FC<{ chart: string }> = ({ chart }) => {
  const initialClean = sanitizeMermaidChart(chart);
  const cachedSvg = mermaidSvgCache.get(initialClean);

  const [svg, setSvg] = useState<string>(cachedSvg || '');
  const [isRendered, setIsRendered] = useState<boolean>(!!cachedSvg);
  const [showCode, setShowCode] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [renderError, setRenderError] = useState<string>('');
  const [cleanChart, setCleanChart] = useState<string>(initialClean);
  const [zoom, setZoom] = useState<number>(1.0);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    if (!chart || !chart.trim()) return;

    const sanitized = sanitizeMermaidChart(chart);
    if (isMounted) setCleanChart(sanitized);

    if (mermaidSvgCache.has(sanitized)) {
      const hit = mermaidSvgCache.get(sanitized)!;
      if (isMounted) {
        setSvg(hit);
        setIsRendered(true);
        setRenderError('');
      }
      return;
    }

    if (!isMermaidComplete(sanitized)) {
      return;
    }

    const renderChart = async () => {
      try {
        const id = `mermaid_${Math.random().toString(36).substring(2, 9)}_${Date.now()}`;
        const { svg: renderedSvg } = await mermaid.render(id, sanitized);
        if (isMounted && renderedSvg) {
          mermaidSvgCache.set(sanitized, renderedSvg);
          setSvg(renderedSvg);
          setIsRendered(true);
          setRenderError('');
        }
      } catch (err: unknown) {
        console.error('[MermaidDiagram] render failed:', err);
        const msg = err instanceof Error ? err.message : String(err);
        if (isMounted) setRenderError(msg);
        setTimeout(() => {
          const strayError = document.querySelectorAll('svg[aria-roledescription="error"]');
          strayError.forEach(el => el.remove());
        }, 100);
      }
    };

    const timer = setTimeout(renderChart, 40);
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [chart]);

  const handleCopyCode = () => {
    navigator.clipboard.writeText((cleanChart || chart).trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleZoomIn = () => setZoom(prev => Math.min(2.2, +(prev + 0.15).toFixed(2)));
  const handleZoomOut = () => setZoom(prev => Math.max(0.55, +(prev - 0.15).toFixed(2)));
  const handleZoomReset = () => setZoom(1.0);

  return (
    <>
      <div className="mermaid-diagram-card">
        <div className="mermaid-diagram-header">
          <div className="mermaid-header-left">
            <span className="mermaid-diagram-badge">
              <Activity size={12} />
              <span>Interactive Diagram</span>
            </span>
            {renderError && (
              <span className="mermaid-render-error-badge" title={renderError}>
                ⚠ Render Error
              </span>
            )}
          </div>
          <div className="mermaid-header-right">
            {isRendered && !renderError && !showCode && (
              <div className="mermaid-zoom-controls">
                <button
                  type="button"
                  className="mermaid-icon-tool-btn"
                  onClick={handleZoomOut}
                  title="Zoom out diagram"
                  aria-label="Zoom out"
                  disabled={zoom <= 0.55}
                >
                  <ZoomOut size={12} />
                </button>
                <button
                  type="button"
                  className="mermaid-icon-tool-btn zoom-text-btn"
                  onClick={handleZoomReset}
                  title="Reset diagram zoom"
                  aria-label="Reset zoom"
                >
                  {Math.round(zoom * 100)}%
                </button>
                <button
                  type="button"
                  className="mermaid-icon-tool-btn"
                  onClick={handleZoomIn}
                  title="Zoom in diagram"
                  aria-label="Zoom in"
                  disabled={zoom >= 2.2}
                >
                  <ZoomIn size={12} />
                </button>
                <button
                  type="button"
                  className="mermaid-icon-tool-btn"
                  onClick={() => setIsFullscreen(true)}
                  title="Expand diagram fullscreen"
                  aria-label="Expand diagram fullscreen"
                >
                  <Maximize2 size={12} />
                </button>
              </div>
            )}
            {isRendered && (
              <button 
                type="button"
                className="mermaid-tool-btn"
                onClick={() => setShowCode(!showCode)}
                title={showCode ? "Show visual diagram" : "View diagram source code"}
              >
                <Code size={12} />
                <span>{showCode ? "Visual" : "Source"}</span>
              </button>
            )}
            <button 
              type="button"
              className="mermaid-tool-btn"
              onClick={handleCopyCode}
              title="Copy Mermaid code"
            >
              {copied ? <Check size={12} className="text-moss" /> : <Copy size={12} />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
        </div>

        {showCode ? (
          <pre className="mermaid-code-preview">{(cleanChart || chart).trim()}</pre>
        ) : renderError ? (
          <pre className="mermaid-code-preview">{(cleanChart || chart).trim()}</pre>
        ) : isRendered && svg ? (
          <div className="mermaid-diagram-canvas-wrapper">
            <div 
              className="mermaid-diagram-canvas"
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        ) : (
          <div className="mermaid-diagram-loading">
            <div className="shimmer-pulse-dot" />
            <div className="shimmer-pulse-dot" />
            <div className="shimmer-pulse-dot" />
            <span>Rendering visual diagram...</span>
          </div>
        )}
      </div>

      {isFullscreen && (
        <div className="recall-modal-backdrop mermaid-fullscreen-backdrop" onClick={() => setIsFullscreen(false)}>
          <div className="mermaid-fullscreen-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <Activity size={16} className="text-teal" />
                <h3>Expanded Diagram View</h3>
              </div>
              <div className="mermaid-fullscreen-header-actions">
                <div className="mermaid-zoom-controls">
                  <button type="button" className="mermaid-icon-tool-btn" onClick={handleZoomOut} title="Zoom out" disabled={zoom <= 0.55}>
                    <ZoomOut size={13} />
                  </button>
                  <button type="button" className="mermaid-icon-tool-btn zoom-text-btn" onClick={handleZoomReset} title="Reset zoom">
                    {Math.round(zoom * 100)}%
                  </button>
                  <button type="button" className="mermaid-icon-tool-btn" onClick={handleZoomIn} title="Zoom in" disabled={zoom >= 2.5}>
                    <ZoomIn size={13} />
                  </button>
                </div>
                <button 
                  type="button"
                  className="mermaid-tool-btn"
                  onClick={handleCopyCode}
                  title="Copy Mermaid code"
                >
                  {copied ? <Check size={13} className="text-moss" /> : <Copy size={13} />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
                <button className="modal-close-btn" onClick={() => setIsFullscreen(false)} title="Exit fullscreen view">
                  <Minimize2 size={16} />
                </button>
              </div>
            </div>
            <div className="mermaid-fullscreen-body">
              <div 
                className="mermaid-diagram-canvas fullscreen-canvas"
                style={{ transform: `scale(${zoom})`, transformOrigin: 'center center' }}
                dangerouslySetInnerHTML={{ __html: svg }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
};
