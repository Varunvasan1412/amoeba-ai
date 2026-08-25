import { useState, useEffect, useRef, useCallback, memo } from "react";
import { MessageCircle, Send, Loader2, Trash2, Plus, MessageSquare, Square, Pencil, Sun, Moon, PanelLeftOpen, PanelLeftClose, Paperclip, SlidersHorizontal, Building2, FileText, X, AlertCircle, Mic, Download, RefreshCw, BarChart3, Table2 } from "lucide-react";
import { toast } from "react-toastify";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DynamicForm from "../components/DynamicForm";
import ChartRenderer from "../components/charts/ChartRenderer";
import { apiFetch } from "../utils/api";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

type ChatMessage = {
  role: "user" | "ai";
  text: string;
  actions?: any[]; 
  timestamp?: number;
  is_edited?: boolean;
};

type ChatSession = {
    session_id: string;
    title: string;
    updated_at: string;
};

// Enhanced Message Bubble for Full Screen
const MessageBubble = memo(({ msg, index, onSelect, onSubmitForm, onSwitchMode, onEdit, darkMode, globalViewMode, chartType }: { 
    msg: ChatMessage, 
    index: number,
    onSelect?: (val: string, index?: number) => void, 
    onSubmitForm?: (data: any) => void,
    onSwitchMode?: (mode: "assistant" | "operations") => void,
    onEdit?: (text: string, index: number) => void,
    darkMode?: boolean,
    globalViewMode?: "table" | "chart",
    chartType?: "bar" | "line" | "pie"
}) => {
  // Extract actions if present
  const choices = msg.actions?.find(a => a.type === "CHOICE");
  const entitySelection = msg.actions?.find(a => a.type === "entity_selection");
  const recordSelection = msg.actions?.find(a => a.type === "record_selection");
  const formAction = msg.actions?.find(a => a.type === "form");
  const formRequest = msg.actions?.find(a => a.type === "form_request"); // Legacy
  const confirmation = msg.actions?.find(a => a.type === "confirmation");
  const success = msg.actions?.find(a => a.type === "success");
  const switchModeAction = msg.actions?.find(a => a.type === "SWITCH_MODE");
  const sourcesAction = msg.actions?.find(a => a.type === "SOURCES");
  const dataTable = msg.actions?.find(a => a.type === "data_table");
  
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [searchTerm, setSearchTerm] = useState("");
  const [viewingSource, setViewingSource] = useState<any>(null);
  const [viewingText, setViewingText] = useState<string | null>(null);
  const [structuredPreview, setStructuredPreview] = useState<{headers: string[], rows: any[]} | null>(null);
  const [loadingText, setLoadingText] = useState(false);
  const [tablePage, setTablePage] = useState(0);
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [localViewMode, setLocalViewMode] = useState<"table" | "chart">(globalViewMode || "table");
  const chartRef = useRef<HTMLDivElement>(null);

  // Sync local mode with global preference when header toggle is used
  useEffect(() => {
    if (globalViewMode) {
      setLocalViewMode(globalViewMode);
    }
  }, [globalViewMode]);

  const filteredRecords = recordSelection?.payload?.filter((r: any) => 
    r.label.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  // Handle fetching text for non-PDF previews
  useEffect(() => {
    if (viewingSource && !viewingSource.filename.toLowerCase().endsWith('.pdf')) {
      const ext = viewingSource.filename.toLowerCase().split('.').pop();
      setLoadingText(true);
      setStructuredPreview(null);
      setViewingText(null);

      // Try structured first
      if ((ext === 'csv' || ext === 'xlsx') && viewingSource.document_id) {
          apiFetch(`/api/documents/${viewingSource.document_id}/preview`)
          .then(res => res.ok ? res.json() : null)
          .then(data => {
              if (data) {
                  setStructuredPreview(data);
              } else {
                  return apiFetch(`/api/documents/download/${viewingSource.document_id}_${viewingSource.filename}`).then(r => r.text());
              }
          })
          .then(text => { if (typeof text === 'string') setViewingText(text.slice(0, 10000)); })
          .catch(() => {})
          .finally(() => setLoadingText(false));
      } else {
          apiFetch(`/api/documents/download/${viewingSource.document_id}_${viewingSource.filename}`)
          .then(res => res.text())
          .then(text => setViewingText(text.slice(0, 10000)))
          .catch(() => setViewingText("Failed to load document content."))
          .finally(() => setLoadingText(false));
      }
    } else {
      setViewingText(null);
      setStructuredPreview(null);
    }
  }, [viewingSource]);

  // Expand to full width when there's a data table (for charts)
  const hasDataTable = !!dataTable;
  const bubbleWidth = msg.role === "user" ? "max-w-[85%]" : hasDataTable ? "max-w-full w-full" : "max-w-[85%]";

  return (
    <div className={`flex flex-col gap-2 ${bubbleWidth} ${msg.role === "user" ? "self-end items-end" : "self-start items-start"}`}> 
        {/* Main Text Bubble */}
        <div
        className={`p-4 rounded-2xl text-[15px] shadow-sm break-words leading-relaxed transition-theme ${
            hasDataTable ? "w-full" : ""
        } ${
            msg.role === "user"
            ? "bg-blue-600 text-white rounded-br-sm" 
            : darkMode 
                ? "bg-gray-800 text-gray-100 border border-gray-700 rounded-bl-sm shadow-xl"
                : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-md"
        }`}
        >
        {msg.role === "user" ? (
            <div className="flex flex-col gap-2 whitespace-pre-wrap">
                {msg.text.startsWith("📎") ? (
                    (() => {
                        const [filePart, ...textParts] = msg.text.split("\n");
                        const rawFile = filePart.replace("📎", "").trim();
                        // Support format: "filename|downloadPath" or just "filename"
                        const [fileName, downloadPath] = rawFile.includes("|") ? rawFile.split("|", 2) : [rawFile, ""];
                        const messageText = textParts.join("\n").trim();
                        return (
                            <>
                                {downloadPath ? (
                                    <a
                                        href={downloadPath}
                                        download
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium w-fit border shadow-sm cursor-pointer transition-all hover:scale-[1.02] ${
                                            darkMode 
                                            ? "bg-blue-900/30 border-blue-800/50 text-blue-300 hover:bg-blue-900/50" 
                                            : "bg-blue-50 border-blue-100 text-blue-700 hover:bg-blue-100"
                                        }`}
                                        title="Click to download"
                                    >
                                        <Download size={14} />
                                        <span>{fileName}</span>
                                    </a>
                                ) : (
                                    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium w-fit border shadow-sm ${
                                        darkMode 
                                        ? "bg-blue-900/30 border-blue-800/50 text-blue-300" 
                                        : "bg-blue-50 border-blue-100 text-blue-700"
                                    }`}>
                                        <FileText size={14} />
                                        <span>{fileName}</span>
                                    </div>
                                )}
                                {messageText && <span>{messageText}</span>}
                            </>
                        );
                    })()
                ) : (
                    <span>{msg.text}</span>
                )}
                {msg.is_edited && (
                    <span className="text-[9px] opacity-60 mt-1 italic text-right">Edited</span>
                )}
            </div>
        ) : (choices || entitySelection || recordSelection || formAction || formRequest || confirmation || success || switchModeAction || dataTable) ? (
            <div className={`font-sans text-[15px] flex flex-col gap-2 ${darkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                {/* Render textual context first if it exists alongside actions */}
                {msg.text && (
                    <div className={`prose prose-sm max-w-none prose-p:my-0 prose-headings:my-1 overflow-hidden ${darkMode ? 'prose-invert' : ''}`}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                    </div>
                )}
                {/* Paginated Data Table */}
                {dataTable && dataTable.payload && (() => {
                    const { headers, rows, total } = dataTable.payload;
                    const PAGE_SIZE = 10;
                    const totalPages = Math.ceil(rows.length / PAGE_SIZE);
                    const pageRows = rows.slice(tablePage * PAGE_SIZE, (tablePage + 1) * PAGE_SIZE);

                    // Chart eligibility: needs numeric + category columns, more than 1 row
                    const hasNumericCol = headers.some((h: string) => {
                        const val = rows[0]?.[h];
                        return val !== undefined && val !== null && !isNaN(Number(val)) && String(val).trim() !== "" && !h.toLowerCase().endsWith("_id") && h.toLowerCase() !== "id";
                    });
                    const isChartEligible = rows.length > 1 && hasNumericCol && headers.length >= 2;

                    return (
                        <div className="overflow-x-auto my-1">
                            {/* Per-message Table/Chart toggle */}
                            {isChartEligible && (
                                <div className={`flex items-center gap-1 mb-2 p-1 rounded-lg w-fit ${darkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>
                                    <button
                                        onClick={() => setLocalViewMode("table")}
                                        className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                                            localViewMode === "table"
                                            ? (darkMode ? 'bg-gray-700 text-blue-400 shadow-sm' : 'bg-white text-blue-600 shadow-sm')
                                            : (darkMode ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600')
                                        }`}
                                    >
                                        <Table2 size={12} /> Table
                                    </button>
                                    <button
                                        onClick={() => setLocalViewMode("chart")}
                                        className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                                            localViewMode === "chart"
                                            ? (darkMode ? 'bg-gray-700 text-blue-400 shadow-sm' : 'bg-white text-blue-600 shadow-sm')
                                            : (darkMode ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600')
                                        }`}
                                    >
                                        <BarChart3 size={12} /> Chart
                                    </button>
                                </div>
                            )}

                            {/* Conditional: Chart or Table */}
                            {localViewMode === "chart" && isChartEligible ? (
                                <div ref={chartRef} className="w-full bg-inherit p-4 rounded-xl">
                                    <ChartRenderer data={rows} columns={headers} darkMode={darkMode} chartType={chartType} />
                                </div>
                            ) : (
                            <>
                            <table className={`min-w-full border-collapse text-xs ${darkMode ? 'border-gray-600' : 'border-gray-300'}`}>
                                <thead className={darkMode ? 'bg-gray-700' : 'bg-gray-100'}>
                                    <tr>
                                        {headers.map((h: string) => (
                                            <th key={h} className={`px-3 py-2 text-left font-semibold border whitespace-nowrap ${darkMode ? 'border-gray-600 text-gray-200' : 'border-gray-300 text-gray-700'}`}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {pageRows.map((row: any, i: number) => (
                                        <tr key={i} className={`${darkMode ? 'hover:bg-gray-700/50' : 'hover:bg-blue-50/50'} transition-colors`}>
                                            {headers.map((h: string) => (
                                                <td key={h} className={`px-3 py-1.5 border whitespace-nowrap ${darkMode ? 'border-gray-600 text-gray-300' : 'border-gray-300 text-gray-600'}`}>{row[h] || ''}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {totalPages > 1 && (
                                <div className={`flex items-center justify-between mt-2 px-1 text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                                    <span>Page {tablePage + 1} of {totalPages} ({total} records)</span>
                                    <div className="flex gap-2">
                                        <button 
                                            onClick={() => setTablePage(p => Math.max(0, p - 1))}
                                            disabled={tablePage === 0}
                                            className={`px-3 py-1.5 rounded-lg border font-medium transition-all ${
                                                tablePage === 0 
                                                ? (darkMode ? 'border-gray-700 text-gray-600 cursor-not-allowed' : 'border-gray-200 text-gray-300 cursor-not-allowed')
                                                : (darkMode ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100')
                                            }`}
                                        >← Previous</button>
                                        <button 
                                            onClick={() => setTablePage(p => Math.min(totalPages - 1, p + 1))}
                                            disabled={tablePage >= totalPages - 1}
                                            className={`px-3 py-1.5 rounded-lg border font-medium transition-all ${
                                                tablePage >= totalPages - 1 
                                                ? (darkMode ? 'border-gray-700 text-gray-600 cursor-not-allowed' : 'border-gray-200 text-gray-300 cursor-not-allowed')
                                                : (darkMode ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100')
                                            }`}
                                        >Next →</button>
                                    </div>
                                </div>
                            )}
                            </>
                            )}

                            {/* Inline Download Button for dataTables */}
                            {dataTable.payload.query_payload && (
                                <div className="mt-3 border-t pt-2 relative">
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); setShowExportMenu(!showExportMenu); }}
                                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-bold transition-all ${
                                            darkMode 
                                            ? 'bg-blue-900/40 text-blue-300 hover:bg-blue-800/60 border border-blue-900/50' 
                                            : 'bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-100'
                                        }`}
                                    >
                                        <Download size={12} />
                                        <span>Download</span>
                                        <span className="text-[9px] opacity-70 ml-1">▼</span>
                                    </button>
                                    
                                    {showExportMenu && (
                                        <div className={`absolute bottom-full left-0 mb-1 z-50 rounded-lg shadow-xl border overflow-hidden w-40 flex flex-col ${
                                            darkMode ? "bg-gray-800 border-gray-700 shadow-black/50" : "bg-white border-gray-100 shadow-blue-500/10"
                                        }`}>
                                            {['Excel (.xlsx)', 'CSV (.csv)', 'PDF (.pdf)'].filter(label => {
                                                const format = label.includes('xlsx') ? 'xlsx' : label.includes('csv') ? 'csv' : 'pdf';
                                                return localViewMode === 'chart' ? format === 'pdf' : format !== 'pdf';
                                            }).map(formatLabel => {
                                                const formatCode = formatLabel.includes('xlsx') ? 'xlsx' : formatLabel.includes('csv') ? 'csv' : 'pdf';
                                                return (
                                                    <button 
                                                        key={formatCode}
                                                        disabled={downloadingFormat !== null}
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
                                                            setShowExportMenu(false);

                                                            // NEW: Visual Capture for Charts
                                                            if (formatCode === "pdf" && localViewMode === "chart" && chartRef.current) {
                                                                setDownloadingFormat("pdf");
                                                                try {
                                                                    const element = chartRef.current;
                                                                    // Use a slight delay to ensure everything is rendered
                                                                    const canvas = await html2canvas(element, {
                                                                        backgroundColor: darkMode ? "#1f2937" : "#ffffff",
                                                                        scale: 2, // Higher quality
                                                                        useCORS: true,
                                                                        logging: false
                                                                    });
                                                                    const imgData = canvas.toDataURL("image/png");
                                                                    const pdf = new jsPDF({
                                                                        orientation: canvas.width > canvas.height ? "landscape" : "portrait",
                                                                        unit: "px",
                                                                        format: [canvas.width, canvas.height]
                                                                    });
                                                                    pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
                                                                    pdf.save(`${dataTable.payload.title || 'chart'}.pdf`);
                                                                    toast.success("Chart PDF generated successfully!");
                                                                } catch (err) {
                                                                    console.error("PDF Capture Error:", err);
                                                                    toast.error("Failed to generate visual PDF");
                                                                } finally {
                                                                    setDownloadingFormat(null);
                                                                }
                                                                return;
                                                            }

                                                            setDownloadingFormat(formatCode);
                                                            try {
                                                                // Grab the query payload passed by the LLM service
                                                                const queryPayload = dataTable.payload.query_payload;
                                                                const currentApiKey = new URLSearchParams(window.location.search).get("api_key") || "";
                                                                const res = await apiFetch(`/api/inline-export?api_key=${currentApiKey}`, {
                                                                    method: "POST",
                                                                    body: JSON.stringify({
                                                                        format: formatCode,
                                                                        query_payload: queryPayload
                                                                    })
                                                                });

                                                                if (!res.ok) {
                                                                    const errText = await res.text();
                                                                    let detail = "Failed to generate report";
                                                                    try { detail = JSON.parse(errText).detail || detail; } catch {}
                                                                    throw new Error(detail);
                                                                }
                                                                
                                                                // Download as blob
                                                                const blob = await res.blob();
                                                                const disposition = res.headers.get("content-disposition");
                                                                let fname = `export.${formatCode}`;
                                                                if (disposition) {
                                                                    const match = disposition.match(/filename="?([^";\n]+)"?/);
                                                                    if (match) fname = match[1];
                                                                }
                                                                const url = window.URL.createObjectURL(blob);
                                                                const a = document.createElement("a");
                                                                a.href = url;
                                                                a.download = fname;
                                                                document.body.appendChild(a);
                                                                a.click();
                                                                a.remove();
                                                                window.URL.revokeObjectURL(url);
                                                            } catch (err: any) {
                                                                alert(`Export failed: ${err.message}`);
                                                            } finally {
                                                                setDownloadingFormat(null);
                                                            }
                                                        }}
                                                        className={`text-left px-4 py-2.5 text-[11px] font-medium transition-colors flex items-center justify-between ${
                                                            darkMode 
                                                            ? "text-gray-300 hover:bg-gray-700 hover:text-white disabled:opacity-50 disabled:hover:bg-transparent" 
                                                            : "text-gray-700 hover:bg-gray-50 hover:text-gray-900 disabled:opacity-50 disabled:hover:bg-transparent"
                                                        }`}
                                                    >
                                                        {formatLabel} 
                                                        {downloadingFormat === formatCode && <Loader2 size={12} className="animate-spin text-blue-500" />}
                                                    </button>
                                                )
                                            })}
                                        </div>
                                    )}
                                </div>
                            )}

                        </div>
                    );
                })()}
                
                {success && (
                    <div className={`mt-2 font-bold flex items-center gap-2 ${darkMode ? 'text-green-400' : 'text-green-600'}`}>
                        <span>✅</span> {success.payload}
                    </div>
                )}
            </div>
        ) : (
            <div className={`prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0 overflow-hidden ${darkMode ? 'prose-invert prose-pre:bg-gray-900 prose-pre:text-gray-300' : 'prose-pre:bg-gray-50 prose-pre:text-gray-700'}`}>
            <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                    table: ({ node, ...props }) => (
                        <div className="overflow-x-auto my-2">
                            <table {...props} className={`min-w-full border-collapse text-xs ${darkMode ? 'border-gray-600' : 'border-gray-300'}`} />
                        </div>
                    ),
                    thead: ({ node, ...props }) => (
                        <thead {...props} className={darkMode ? 'bg-gray-700' : 'bg-gray-100'} />
                    ),
                    th: ({ node, ...props }) => (
                        <th {...props} className={`px-3 py-1.5 text-left font-semibold border ${darkMode ? 'border-gray-600 text-gray-200' : 'border-gray-300 text-gray-700'}`} />
                    ),
                    td: ({ node, ...props }) => (
                        <td {...props} className={`px-3 py-1 border ${darkMode ? 'border-gray-600 text-gray-300' : 'border-gray-300 text-gray-600'}`} />
                    )
                }}
            >
                {msg.text}
            </ReactMarkdown>
            </div>
        )}
        </div>
        
        {/* Edit Button for User Messages */}
        {msg.role === "user" && onEdit && (
            <button 
                onClick={() => onEdit(msg.text, index)}
                className="text-[10px] text-gray-400 hover:text-blue-600 transition-colors flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100"
            >
                <Pencil size={12} /> Edit & Resend
            </button>
        )}

        {/* Action Buttons (e.g. Choices or Entity Selection) */}
        {msg.role === "ai" && (choices || entitySelection) && (
            <div className="flex flex-wrap gap-2 mt-1 duration-300">
                {(choices?.payload || entitySelection?.payload || []).map((opt: any, idx: number) => (
                    <button
                        key={idx}
                        onClick={() => onSelect && onSelect(opt.table_name || opt.label, opt.index)} 
                        className={`text-left text-sm transition-all p-3 rounded-xl shadow-sm flex items-center gap-2 group border ${
                            darkMode 
                            ? 'bg-gray-800 border-gray-700 hover:bg-gray-700 hover:border-blue-500 text-gray-200' 
                            : 'bg-white border-blue-200 hover:bg-blue-50 hover:border-blue-300 text-gray-700'
                        }`}
                    >
                        <div className={`w-1.5 h-1.5 rounded-full transition-colors ${darkMode ? 'bg-blue-500 group-hover:bg-blue-400' : 'bg-blue-400 group-hover:bg-blue-600'}`}></div>
                        <span className={`font-medium ${darkMode ? 'group-hover:text-blue-400' : 'group-hover:text-blue-800'}`}>{opt.label}</span>
                    </button>
                ))}
            </div>
        )}

        {/* Source Attribution & Confidence */}
        {msg.role === "ai" && sourcesAction && sourcesAction.payload && (
            <div className="flex flex-col gap-2 mt-2 w-full">
                <div className="flex flex-wrap gap-2">
                    {sourcesAction.payload.sources.map((src: any, idx: number) => (
                        <div 
                            key={idx}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] font-medium border shadow-sm ${
                                darkMode 
                                ? "bg-gray-800/50 border-gray-700 text-gray-400" 
                                : "bg-gray-50 border-gray-100 text-gray-600"
                            }`}
                        >
                            <FileText size={12} className="opacity-70" />
                            <span>{src.filename}</span>
                            {src.pages && src.pages.length > 0 && (
                                <span className="opacity-60 border-l pl-2 border-gray-300 ml-1">
                                    Page{src.pages.length > 1 ? 's' : ''} {src.pages.join(", ")}
                                </span>
                            )}
                            <button 
                                onClick={() => setViewingSource(src)}
                                className={`ml-1 font-bold ${darkMode ? "text-blue-400 hover:text-blue-300" : "text-blue-600 hover:text-blue-700"}`}
                            >
                                View Source
                            </button>
                        </div>
                    ))}
                </div>
                {sourcesAction.payload.confidence !== undefined && (
                    <div className="flex items-center gap-1.5 text-[10px] opacity-70 ml-1">
                        <div className={`w-2 h-2 rounded-full ${
                            sourcesAction.payload.confidence > 80 ? "bg-green-500" : 
                            sourcesAction.payload.confidence > 50 ? "bg-yellow-500" : "bg-red-500"
                        }`}></div>
                        <span>Confidence: {sourcesAction.payload.confidence}%</span>
                    </div>
                )}
            </div>
        )}

        {/* Source Preview Modal */}
        {viewingSource && (
            <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in shadow-2xl">
                <div className={`w-full max-w-4xl h-[85vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden border transition-theme ${darkMode ? "bg-gray-900 border-gray-700" : "bg-white border-gray-100"}`}>
                    <div className="p-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400">
                                <FileText size={20} />
                            </div>
                            <div>
                                <h3 className="font-bold text-sm md:text-base truncate max-w-[300px] md:max-w-md text-gray-900 dark:text-white">{viewingSource.filename}</h3>
                                {viewingSource.pages && viewingSource.pages.length > 0 && (
                                    <span className="text-xs opacity-80 text-gray-600 dark:text-gray-300">
                                        Referenced {viewingSource.pages.length > 1 ? `Pages: ${viewingSource.pages.join(", ")}` : `Page: ${viewingSource.pages[0]}`}
                                    </span>
                                )}
                            </div>
                        </div>
                        <button onClick={() => setViewingSource(null)} className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
                            <X size={20} />
                        </button>
                    </div>
                    
                    <div className="flex-1 w-full bg-gray-100 dark:bg-black/50 overflow-hidden relative">
                        {viewingSource.document_id && viewingSource.filename.toLowerCase().endsWith('.pdf') ? (
                            <iframe 
                                src={`/api/documents/download/${viewingSource.document_id}_${viewingSource.filename}#page=${viewingSource.pages && viewingSource.pages.length > 0 ? viewingSource.pages[0] : 1}`}
                                className="w-full h-full border-none"
                                title={viewingSource.filename}
                            />
                        ) : loadingText ? (
                            <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-500">
                                <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                                <p className="text-sm font-medium animate-pulse">Analyzing structure...</p>
                            </div>
                        ) : structuredPreview ? (
                            <div className="w-full h-full overflow-auto bg-white dark:bg-gray-950">
                                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800 border-collapse">
                                    <thead className="bg-gray-50 dark:bg-gray-900 sticky top-0 z-10 shadow-sm">
                                        <tr>
                                            {structuredPreview.headers.map((h, i) => (
                                                <th key={i} className="px-4 py-3 text-left text-[10px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest border-b border-gray-100 dark:border-gray-800 whitespace-nowrap">
                                                    {h}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                                        {structuredPreview.rows.map((row, i) => (
                                            <tr key={i} className="hover:bg-blue-50/30 dark:hover:bg-blue-900/10 transition-colors">
                                                {structuredPreview.headers.map((h, j) => (
                                                    <td key={j} className="px-4 py-2.5 text-xs text-gray-600 dark:text-gray-300 border-r border-gray-50 dark:border-gray-800 last:border-r-0 max-w-[300px] truncate">
                                                        {String(row[h] !== null ? row[h] : '')}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : viewingText ? (
                            <div className="w-full h-full overflow-auto p-6 font-mono text-[11px] leading-relaxed bg-white dark:bg-gray-950 text-gray-800 dark:text-gray-200">
                                <pre className="whitespace-pre-wrap font-mono">{viewingText}</pre>
                            </div>
                        ) : (
                            <div className="p-8 flex flex-col gap-4 max-w-lg mx-auto h-full justify-center text-center">
                                <div className="p-4 bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400 rounded-full w-fit mx-auto">
                                    <AlertCircle size={32} />
                                </div>
                                <h4 className="font-bold text-lg dark:text-white">Rich Preview Unavailable</h4>
                                <p className="text-sm opacity-80 leading-relaxed mb-4 dark:text-gray-300">
                                    Rich previews for **DOCX** and **XLSX** files are currently processed into searchable knowledge. For other file types, please download the file to view its contents natively.
                                </p>
                                {viewingSource.document_id && (
                                    <a 
                                        href={`/api/documents/download/${viewingSource.document_id}_${viewingSource.filename}`}
                                        download
                                        className="py-3 px-8 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold shadow-lg shadow-blue-200 transition-all hover:-translate-y-0.5 w-fit mx-auto"
                                    >
                                        <Download size={18} className="inline mr-2" /> Download File
                                    </a>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        )}

        {/* Switch Mode Button */}
        {msg.role === "ai" && switchModeAction && (
            <div className="flex gap-2 mt-1">
                <button
                    onClick={() => onSwitchMode && onSwitchMode(switchModeAction.payload)}
                    className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-bold hover:bg-blue-700 transition-all shadow-md"
                >
                    Switch to {switchModeAction.payload === "operations" ? "Operations Mode" : "Assistant Mode"}
                </button>
            </div>
        )}

        {/* SEARCHABLE RECORD SELECTOR (For Update/Delete) */}
        {msg.role === "ai" && recordSelection && recordSelection.payload && (
            <div className={`rounded-xl p-4 shadow-md mt-1 w-full max-w-sm flex flex-col gap-3 border ${darkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-100'}`}>
                <div className="relative">
                    <input 
                        type="text"
                        placeholder="Search records..."
                        className={`w-full rounded-lg px-3 py-2 text-sm outline-none transition-all border ${
                            darkMode 
                            ? 'bg-gray-800 border-gray-700 text-white focus:ring-blue-900/50' 
                            : 'bg-gray-50 border-gray-100 focus:ring-blue-100'
                        }`}
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="max-h-60 overflow-y-auto flex flex-col gap-1 scrollbar-thin">
                    {filteredRecords.length > 0 ? (
                        filteredRecords.map((r: any) => (
                            <button
                                key={r.id}
                                onClick={() => onSelect && onSelect(r.id.toString())}
                                className="text-left text-sm p-3 hover:bg-blue-50 rounded-lg transition-colors border border-transparent hover:border-blue-100"
                            >
                                {r.label}
                            </button>
                        ))
                    ) : (
                        <span className="text-xs text-gray-400 text-center py-2">No matches found</span>
                    )}
                </div>
            </div>
        )}

        {/* SMART FORM */}
        {msg.role === "ai" && formAction && formAction.payload && (
            <div className="max-w-md w-full">
                <DynamicForm 
                    fields={formAction.payload.fields} 
                    onSubmit={(data) => onSubmitForm && onSubmitForm(data)}
                    onCancel={() => onSelect && onSelect("Cancel")}
                    title={formAction.payload.table_name}
                    darkMode={darkMode}
                />
            </div>
        )}

        {/* Legacy Form Request */}
        {msg.role === "ai" && formRequest && formRequest.payload && (
            <div className={`rounded-xl p-5 shadow-sm mt-1 w-full max-w-sm flex flex-col gap-4 border ${darkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-100'}`}>
                <h4 className={`text-sm font-bold uppercase tracking-wider mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Enter Details: {formRequest.payload.entity}</h4>
                {formRequest.payload.fields.map((field: string) => (
                    <div key={field} className="flex flex-col gap-1">
                        <label className={`text-xs font-semibold uppercase ml-1 ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>{field}</label>
                        <input 
                            type="text"
                            placeholder={`Enter ${field}...`}
                            onChange={(e) => setFormData(prev => ({...prev, [field]: e.target.value}))}
                            className={`rounded-lg px-3 py-2.5 text-sm outline-none transition-all border ${
                                darkMode 
                                ? 'bg-gray-800 border-gray-700 text-white focus:ring-blue-900/50' 
                                : 'bg-gray-50 border-gray-100 focus:ring-blue-100'
                            }`}
                        />
                    </div>
                ))}
                <button 
                    onClick={() => onSubmitForm && onSubmitForm(formData)}
                    className="mt-2 bg-blue-600 text-white py-3 rounded-xl text-sm font-bold hover:bg-blue-700 transition-colors shadow-md"
                >
                    Submit Details
                </button>
            </div>
        )}

        {/* Confirmation Buttons */}
        {msg.role === "ai" && confirmation && (
            <div className="flex gap-3 mt-2">
                <button 
                    onClick={() => onSelect && onSelect("Yes")}
                    className="bg-red-600 text-white px-8 py-2.5 rounded-xl text-sm font-bold hover:bg-red-700 transition-all shadow-md"
                >
                    Confirm
                </button>
                <button 
                    onClick={() => onSelect && onSelect("Cancel")}
                    className={`px-8 py-2.5 rounded-xl text-sm font-bold transition-all border ${
                        darkMode 
                        ? 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700 hover:text-gray-300' 
                        : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200'
                    }`}
                >
                    Cancel
                </button>
            </div>
        )}
    </div>
  );
});

MessageBubble.displayName = "MessageBubble";

export default function AmoebaChat() {
  const API_BASE = "/api";
  const urlParams = new URLSearchParams(window.location.search);
  const currentApiKey = urlParams.get("api_key") || import.meta.env.VITE_API_KEY || "";

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  const [chatMode, setChatMode] = useState<"assistant" | "operations">("assistant");
  const [viewMode, setViewMode] = useState<"table" | "chart">(localStorage.getItem("amoeba_view_mode") as any || "table");
  const [chartType, setChartType] = useState<"bar" | "line" | "pie">(localStorage.getItem("amoeba_chart_type") as any || "bar");

  useEffect(() => {
    localStorage.setItem("amoeba_view_mode", viewMode);
  }, [viewMode]);

  useEffect(() => {
    localStorage.setItem("amoeba_chart_type", chartType);
  }, [chartType]);
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  
  // Speech Recognition State
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const recognitionRef = useRef<any>(null);
  const [aiConfig, setAiConfig] = useState<{provider: string, model: string} | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem("amoeba_dark_mode") === "true");
  const [isEditingIndex, setIsEditingIndex] = useState<number | null>(null);
  const [editPreserveCount, setEditPreserveCount] = useState<number | null>(null);
  
  // New States for Documents & Sources
  const [sources, setSources] = useState<{erp: boolean, documents: boolean, web: boolean}>(() => {
    try {
        const saved = localStorage.getItem("amoeba_chat_sources");
        const parsed = saved ? JSON.parse(saved) : { erp: true, documents: true, web: false };
        return { ...parsed, web: false }; // Force web to false
    } catch {
        return { erp: true, documents: true, web: false };
    }
  });
  const [showSourcesPopup, setShowSourcesPopup] = useState(false);
  const [uploadingState, setUploadingState] = useState(false);
  const [attachment, setAttachment] = useState<{name: string, path: string} | null>(null);
  const [promptHistory, setPromptHistory] = useState<string[]>(() => {
    try {
        const saved = localStorage.getItem("amoeba_prompt_history");
        return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [historyPointer, setHistoryPointer] = useState<number>(-1);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    if (type === 'success') toast.success(message);
    else if (type === 'error') toast.error(message);
    else toast.info(message);
  };

  // Persist sources selection
  useEffect(() => {
    localStorage.setItem("amoeba_chat_sources", JSON.stringify(sources));
  }, [sources]);
  
  const socketRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pendingNewAIMessage = useRef(true);

  // Apply Dark Mode effect
  useEffect(() => {
    if (darkMode) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
    localStorage.setItem("amoeba_dark_mode", darkMode.toString());
  }, [darkMode]);

  const fetchSessions = useCallback(async () => {
    try {
        const res = await apiFetch(`${API_BASE}/chat/sessions?api_key=${currentApiKey}`);
        if(res.ok) {
            const data = await res.json();
            setSessions(data);
            if(data.length > 0 && !currentSessionId) {
                setCurrentSessionId(data[0].session_id);
            }
        }
    } catch(e) {
        console.error("Error fetching sessions:", e);
    }

    // Fetch AI Config for model indicator
    try {
        const configRes = await apiFetch(`${API_BASE}/ai-config?api_key=${currentApiKey}`);
        if (configRes.ok) {
            const configData = await configRes.json();
            setAiConfig(configData);
        }
    } catch (err) {
        console.warn("⚠️ Could not fetch AI config:", err);
    }
  }, [API_BASE, currentApiKey, currentSessionId]);

  useEffect(() => {
      fetchSessions();
  }, [fetchSessions]);

  const fetchHistory = useCallback(async (sessionId: string) => {
    if (isEditingIndex !== null) return; // Prevent overwriting the UI during an edit
    setIsLoadingHistory(true);
    try {
      const res = await apiFetch(`${API_BASE}/chat/messages/${sessionId}?api_key=${currentApiKey}`);
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();

      const history = data.map((msg: any) => ({
        role: msg.role,
        text: msg.content,
        actions: msg.actions || [],
        timestamp: msg.timestamp,
        is_edited: msg.is_edited
      }));
      setMessages(history);
    } catch (err) {
      console.error("History Error:", err);
      setMessages([]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [API_BASE, currentApiKey]);

  const activeSessionRef = useRef<string>("");
  useEffect(() => {
      activeSessionRef.current = currentSessionId;
  }, [currentSessionId]);

  const setupWebSocket = useCallback((sessionId: string) => {
    // 1. Clean up existing socket without triggering its onclose reconnect logic
    if (socketRef.current) {
        socketRef.current.onclose = null; 
        socketRef.current.onerror = null;
        socketRef.current.close();
        socketRef.current = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host; 
    const wsUrl = `${protocol}//${host}/api/ws/chat?api_key=${currentApiKey}`;

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    // Heartbeat
    let heartbeatInterval: any;

    ws.onopen = () => {
        setIsConnected(true);
        heartbeatInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "pong") return;

        if (payload.type === "done") {
             setIsTyping(false);
             (window as any).__lastAmoebaMsg = null;
             return;
        }

        if (payload.text) {
             const msgFingerprint = payload.text.slice(0, 80) + (payload.actions ? JSON.stringify(payload.actions).slice(0, 40) : '');
             if ((window as any).__lastAmoebaMsg === msgFingerprint) {
                 console.log('[Amoeba] Skipping duplicate WS message');
                 return;
             }
             (window as any).__lastAmoebaMsg = msgFingerprint;
             
             pendingNewAIMessage.current = false;
             setMessages((prev) => {
                 return [...prev, { 
                     role: "ai" as const, 
                     text: payload.text,
                     actions: payload.actions || []
                 }];
             });
        }

        if (payload.actions && Array.isArray(payload.actions)) {
            payload.actions.forEach((action: any) => {
                const targetWindow = window.opener || window.parent;
                if (action.type === "NAVIGATE") {
                    targetWindow.postMessage({ type: "AMOEBA_ACTION", action: "NAVIGATE", payload: action.payload }, "*");
                    try { targetWindow.focus(); } catch(e) {}
                    setMessages(prev => [...prev, { role: "ai", text: `🚀 Switched your main window to **${action.payload}**` }]);
                } else {
                    targetWindow.postMessage({ type: "AMOEBA_ACTION", action: action.type, payload: action.payload }, "*");
                }
            });
        }
      } catch (e) {
        setMessages((prev) => [...prev, { role: "ai", text: event.data }]);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      clearInterval(heartbeatInterval);
      
      // Auto-reconnect if this is still the active session
      if (sessionId === activeSessionRef.current) {
          setTimeout(() => {
              if (sessionId === activeSessionRef.current) {
                  setupWebSocket(sessionId);
              }
          }, 3000);
      }
    };

    ws.onerror = (error) => {
      console.error("❌ WebSocket Error:", error);
      setIsTyping(false);
      ws.close();
    };
  }, [currentApiKey]); // Removed currentSessionId from deps to avoid re-creating on every state change

  useEffect(() => {
      if(currentSessionId) {
          fetchHistory(currentSessionId).then(() => {
              setupWebSocket(currentSessionId);
          });
      }
      
      return () => {
          if (socketRef.current) {
              socketRef.current.onclose = null;
              socketRef.current.close();
              socketRef.current = null;
          }
      };
  }, [currentSessionId, fetchHistory, setupWebSocket]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleNewChat = async () => {
    try {
        const res = await apiFetch(`${API_BASE}/chat/session?api_key=${currentApiKey}`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ title: "New Chat" })
        });
        if(res.ok) {
            const data = await res.json();
            setCurrentSessionId(data.session_id);
            setMessages([]);
            fetchSessions();
        }
    } catch(e) {
        console.error("Error creating session:", e);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if(!window.confirm("Are you sure you want to delete this chat session?")) return;

    try {
        const res = await apiFetch(`${API_BASE}/chat/session/${sessionId}?api_key=${currentApiKey}`, {
            method: "DELETE"
        });
        if(res.ok) {
            setSessions(prev => prev.filter(s => s.session_id !== sessionId));
            if(currentSessionId === sessionId) {
                const remaining = sessions.filter(s => s.session_id !== sessionId);
                if(remaining.length > 0) {
                    setCurrentSessionId(remaining[0].session_id);
                } else {
                    setCurrentSessionId("");
                    setMessages([]);
                }
            }
        }
    } catch(e) {
        console.error("Error deleting session:", e);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingState(true);
    const formData = new FormData();
    formData.append("file", file);
    if (currentApiKey) {
        formData.append("api_key", currentApiKey);
    } else {
        formData.append("client_id", "1"); // Fallback
    }

    try {
        const res = await apiFetch(`${API_BASE}/documents/upload`, {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) {
            let errorMsg = "Upload failed";
            try {
                const errorData = await res.json();
                errorMsg = errorData.detail || errorMsg;
            } catch (jsonErr) {
                const textError = await res.text();
                errorMsg = textError || `Server Error (${res.status})`;
            }
            throw new Error(errorMsg);
        }
        
        const data = await res.json();
        setAttachment({ name: file.name, path: data.filepath || "" }); 
        showToast("File uploaded successfully!", "success");

    } catch (err: any) {
        const msg = err.message || "Error uploading file.";
        setMessages((prev) => [...prev, { role: "ai", text: `❌ ${msg}` }]);
        showToast(msg, "error");
    } finally {
        setUploadingState(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleChoiceSelect = useCallback((label: string, index?: number) => {
    if (!socketRef.current || !isConnected) return;
    const textToSend = index !== undefined ? index.toString() : label;
    pendingNewAIMessage.current = true;
    setMessages((prev) => [...prev, { role: "user", text: label }]);
    const payload = {
        text: textToSend,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId,
        view_mode: viewMode,
        sources
    };
    socketRef.current.send(JSON.stringify(payload));
    setIsTyping(true);
  }, [isConnected, chatMode, currentApiKey, currentSessionId, sources]);

  const handleFormSubmit = useCallback((data: any) => {
    if (!socketRef.current || !isConnected) return;
    const text = JSON.stringify(data);
    pendingNewAIMessage.current = true;
    setMessages((prev) => [...prev, { role: "user", text: "Submitted form details." }]);
    const payload = {
        text: text,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId,
        view_mode: viewMode,
        sources
    };
    socketRef.current.send(JSON.stringify(payload));
    setIsTyping(true);
  }, [isConnected, chatMode, currentApiKey, currentSessionId, sources]);


  const sendMessage = (overrideText?: any) => {
    const textToProcess = typeof overrideText === 'string' ? overrideText : input;
    if (!textToProcess.trim() || !socketRef.current || !isConnected) return;

    let textToSend = textToProcess;
    let displayInput = textToProcess;

    if (attachment) {
        const contextPrefix = `[SYSTEM: User uploaded file '${attachment.name}' at '${attachment.path}']\n`;
        textToSend = contextPrefix + textToProcess;
        displayInput = `📎 ${attachment.name}${attachment.path ? '|' + attachment.path : ''}\n${textToProcess}`;
    }

    pendingNewAIMessage.current = true;
    setMessages((prev) => [...prev, { role: "user", text: displayInput }]);
    
    const payload = {
        text: textToSend,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId,
        view_mode: viewMode,
        is_edit: false,
        sources
    };
    
    socketRef.current.send(JSON.stringify(payload));
    
    // History Persistence
    if (textToProcess.trim()) {
        const newHistory = [textToProcess, ...promptHistory.filter(h => h !== textToProcess)].slice(0, 50);
        setPromptHistory(newHistory);
        localStorage.setItem("amoeba_prompt_history", JSON.stringify(newHistory));
    }
    setHistoryPointer(-1);

    setInput("");
    setAttachment(null); // Fix: Clear attachment after sending
    setIsTyping(true); 
    setIsEditingIndex(null); 
    
    // Quick refresh of sessions after first message to get updated title
    if(messages.length === 0) {
        setTimeout(() => fetchSessions(), 2000);
    }
  };


  const sendMessageEdited = () => {
    // Show loading state immediately — before any guards
    setIsTyping(true);

    if (!input.trim() || !socketRef.current || !isConnected) {
      setIsTyping(false);
      return;
    }
    
    // Grab the messages BEFORE slicing/sending
    const preservedHistory = messages.map((m) => ({ role: m.role, content: m.text || "" }));

    pendingNewAIMessage.current = true;
    setMessages((prev) => [...prev, { role: "user", text: input, is_edited: true }]);
    
    const payload = {
        text: input,
        mode: chatMode,
        api_key: currentApiKey,
        session_id: currentSessionId,
        view_mode: viewMode,
        is_edit: true,
        preserve_count: editPreserveCount ?? 0,
        history_context: preservedHistory,
        sources
    };
    
    socketRef.current.send(JSON.stringify(payload));
    
    // History Persistence
    if (input.trim()) {
        const newHistory = [input, ...promptHistory.filter(h => h !== input)].slice(0, 50);
        setPromptHistory(newHistory);
        localStorage.setItem("amoeba_prompt_history", JSON.stringify(newHistory));
    }
    setHistoryPointer(-1);

    setInput("");
    setIsEditingIndex(null);
    setEditPreserveCount(null);
  };

  const handleStop = () => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        // Send a stop signal to the backend (optionally)
             socketRef.current.send(JSON.stringify({ type: "STOP_GENERATION" }));
    }
    setIsTyping(false);
  };

  const handleEdit = (text: string, index: number) => {
    setIsEditingIndex(index);
    // preserve_count = number of messages to keep as history (everything before the edit)
    setEditPreserveCount(index);
    setMessages((prev: ChatMessage[]) => prev.slice(0, index));
    setInput(text);
    // Focus the textarea
    setTimeout(() => {
        const textarea = document.querySelector('textarea');
        if (textarea) (textarea as HTMLTextAreaElement).focus();
    }, 10);
  };

  const handleSwitchAndResend = useCallback((newMode: "assistant" | "operations") => {
    setChatMode(newMode);
    
    // Find the last user message to automatically re-run it in the new mode
    const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
    
    if (lastUserMsg && socketRef.current && isConnected) {
        
        const payload = {
            text: lastUserMsg.text,
            mode: newMode,
            api_key: currentApiKey,
            session_id: currentSessionId,
                 sources
             };
        
        socketRef.current.send(JSON.stringify(payload));
        setIsTyping(true);
    }
  }, [messages, isConnected, currentApiKey, currentSessionId, sources]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (isEditingIndex !== null) {
            sendMessageEdited();
        } else {
            sendMessage();
        }
    } else if (e.key === "ArrowUp") {
        const isAtStart = e.currentTarget.selectionStart === 0;
        if (isAtStart) {
            e.preventDefault();
            const nextPointer = historyPointer + 1;
            if (nextPointer < promptHistory.length) {
                setHistoryPointer(nextPointer);
                setInput(promptHistory[nextPointer]);
            }
        }
    } else if (e.key === "ArrowDown" && historyPointer !== -1) {
        e.preventDefault();
        const nextPointer = historyPointer - 1;
        if (nextPointer >= 0) {
            setHistoryPointer(nextPointer);
            setInput(promptHistory[nextPointer]);
        } else {
            setHistoryPointer(-1);
            setInput("");
        }
    }
  };

  const startListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }
    
    const startingText = input.trim() ? input.trim() + " " : "";
    let finalDetected = "";
    
    if (!recognitionRef.current) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = false;
        recognitionRef.current.interimResults = true;
        recognitionRef.current.lang = "en-US";
        
        recognitionRef.current.onerror = (event: any) => {
            if (event.error === 'not-allowed' || event.error === 'denied') {
                alert("Microphone access required. Please check your browser permissions.");
            }
            setIsListening(false);
        };
    }
    
    recognitionRef.current.onend = () => {
        setIsListening(false);
        if (finalDetected.trim()) {
            sendMessage(startingText + finalDetected);
        }
    };
    
    recognitionRef.current.onresult = (event: any) => {
        let interimTranscript = '';
        let currentFinal = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                currentFinal += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        
        finalDetected += currentFinal;
        setInput(startingText + finalDetected + interimTranscript);
    };

    try {
        recognitionRef.current.start();
        setIsListening(true);
    } catch (e) {
        console.error("Speech recognition error:", e);
        setIsListening(false);
    }
  };

  return (
    <div className={`flex h-screen w-full font-sans transition-colors duration-300 ${darkMode ? 'bg-gray-950 text-white' : 'bg-white text-gray-900'} pointer-events-auto`}>
    {/* Sidebar */}
    <div className={`fixed top-0 left-0 bottom-0 z-50 transition-theme border-r shadow-2xl flex flex-col ${
        isSidebarOpen ? 'w-80' : 'w-20'
    } ${darkMode ? 'bg-gray-900 border-gray-800' : 'bg-gray-50 border-gray-200'}`}>
        
        {/* Sidebar Header */}
        <div className={`h-20 flex items-center px-4 border-b transition-theme ${
            isSidebarOpen ? 'justify-between' : 'justify-center'
        } ${darkMode ? 'border-gray-800' : 'border-gray-200'}`}>
                {isSidebarOpen && (
                    <span className={`text-xs font-black uppercase tracking-[0.2em] px-2 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>
                        Sessions
                    </span>
                )}
                <button 
                    onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                    className={`p-2 rounded-lg transition-colors ${darkMode ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'}`}
                    title={isSidebarOpen ? "Collapse Sidebar" : "Expand Sidebar"}
                >
                    {isSidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
                </button>
            </div>

            <div className={`p-4 border-b transition-theme ${darkMode ? 'border-gray-800' : 'border-gray-200'}`}>
                <button 
                    onClick={handleNewChat}
                    className={`flex items-center justify-center gap-2 border shadow-sm transition-all rounded-xl font-medium ${
                        isSidebarOpen ? 'w-full py-2.5 px-4' : 'w-12 h-12 p-0 mx-auto'
                    } ${
                        darkMode 
                        ? 'bg-gray-800 border-gray-700 text-gray-200 hover:bg-gray-700 hover:border-gray-600 shadow-gray-950/50' 
                        : 'bg-white border-gray-200 text-gray-800 hover:shadow hover:border-gray-300'
                    }`}
                >
                    <Plus size={18} /> {isSidebarOpen && "New Chat"}
                </button>
            </div>
            <div className={`flex-1 overflow-y-auto space-y-1 ${isSidebarOpen ? 'p-3' : 'p-2'}`}>
                {isSidebarOpen && <div className="text-[10px] font-semibold text-gray-400 mb-2 px-2 uppercase tracking-widest opacity-60">Recent History</div>}
                {sessions.map(s => (
                    <div 
                        key={s.session_id}
                        onClick={() => setCurrentSessionId(s.session_id)}
                        className={`group w-full text-left rounded-lg text-sm truncate transition-colors flex items-center cursor-pointer ${
                            isSidebarOpen ? 'px-3 py-2.5 gap-3' : 'p-3 justify-center'
                        } ${
                            currentSessionId === s.session_id 
                            ? (darkMode ? "bg-blue-900/40 text-blue-300 font-medium border border-blue-800/50" : "bg-blue-100 text-blue-800 font-medium") 
                            : (darkMode ? "hover:bg-gray-800 text-gray-400" : "hover:bg-gray-100 text-gray-600")
                        }`}
                        title={!isSidebarOpen ? s.title : ""}
                    >
                        <MessageSquare size={16} className={currentSessionId === s.session_id ? (darkMode ? "text-blue-400 flex-shrink-0" : "text-blue-600 flex-shrink-0") : "text-gray-400 flex-shrink-0"} />
                        {isSidebarOpen && (
                            <>
                                <span className="truncate flex-1">{s.title}</span>
                                <button 
                                    onClick={(e) => handleDeleteSession(e, s.session_id)}
                                    className={`p-1 rounded-md transition-all opacity-0 group-hover:opacity-100 ${
                                        darkMode ? 'hover:bg-red-900/30 hover:text-red-400' : 'hover:bg-red-100 hover:text-red-600'
                                    } ${currentSessionId === s.session_id ? "opacity-100" : ""}`}
                                >
                                    <Trash2 size={14} />
                                </button>
                            </>
                        )}
                    </div>
                ))}
            </div>
        </div>

        {/* Main Content Area */}
    <div className={`flex-1 flex flex-col h-screen transition-theme ${isSidebarOpen ? 'ml-80' : 'ml-20'} ${darkMode ? 'bg-gray-950 text-white' : 'bg-gray-50 text-gray-900'}`}>
        
        {/* Top Floating Header */}
        <div className={`fixed top-0 right-0 z-40 h-20 px-8 flex items-center justify-between backdrop-blur-md transition-theme border-b ${
            isSidebarOpen ? 'left-80' : 'left-20'
        } ${darkMode ? 'bg-gray-950/80 border-gray-800/50' : 'bg-white/80 border-gray-200/50'}`}>
                <div className="flex items-center gap-6">
                    <h2 className={`text-lg font-bold flex items-center gap-2 ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>
                        <MessageCircle className="text-blue-600" />
                        Amoeba AI 
                        <span className={`text-xs px-2 py-1 rounded-full ml-2 ${
                            isConnected 
                            ? (darkMode ? "bg-green-900/30 text-green-400" : "bg-green-100 text-green-700") 
                            : (darkMode ? "bg-red-900/30 text-red-400" : "bg-red-100 text-red-700")
                        }`}>
                            {isConnected ? "Connected" : "Reconnecting..."}
                        </span>
                        {aiConfig && (
                            <span className={`text-[11px] font-medium px-2 py-1 rounded-lg ml-2 border ${darkMode ? 'bg-blue-900/30 text-blue-300 border-blue-800' : 'bg-blue-50 text-blue-600 border-blue-100'}`}>
                                🧠 {aiConfig.model.split(':')[0]} · {aiConfig.provider}
                            </span>
                        )}
                    </h2>
                    


                    {/* Mode Toggle */}
                    <div className={`flex p-1 rounded-xl items-center gap-1 shadow-inner ${darkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>
                        <button 
                            onClick={() => setChatMode("assistant")}
                            className={`px-4 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${chatMode === "assistant" ? (darkMode ? 'bg-gray-700 text-blue-400' : 'bg-white text-blue-600 shadow-sm') : 'text-gray-400 hover:text-gray-300'}`}
                        >
                            Assistant
                        </button>
                        <button 
                            onClick={() => setChatMode("operations")}
                            className={`px-4 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${chatMode === "operations" ? (darkMode ? 'bg-gray-700 text-blue-400' : 'bg-white text-blue-600 shadow-sm') : 'text-gray-400 hover:text-gray-300'}`}
                        >
                            Operations
                        </button>
                    </div>

                    {/* View Mode Toggle */}
                    <div className={`flex p-1 rounded-xl items-center gap-1 shadow-inner ${darkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>
                        <button 
                            onClick={() => setViewMode("table")}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${viewMode === "table" ? (darkMode ? 'bg-gray-700 text-blue-400' : 'bg-white text-blue-600 shadow-sm') : 'text-gray-400 hover:text-gray-300'}`}
                        >
                            <Table2 size={13} /> Table
                        </button>
                        <button 
                            onClick={() => setViewMode("chart")}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${viewMode === "chart" ? (darkMode ? 'bg-gray-700 text-blue-400' : 'bg-white text-blue-600 shadow-sm') : 'text-gray-400 hover:text-gray-300'}`}
                        >
                            <BarChart3 size={13} /> Chart
                        </button>
                    </div>

                    {/* Chart Type Selector (Only if chart view) */}
                    {viewMode === "chart" && (
                        <div className={`flex p-1 rounded-xl items-center gap-1 shadow-inner ${darkMode ? 'bg-gray-800' : 'bg-gray-100'}`}>
                            <button 
                                onClick={() => setChartType("bar")}
                                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase transition-all ${chartType === "bar" ? (darkMode ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'bg-blue-600 text-white shadow-lg shadow-blue-200') : 'text-gray-400 hover:text-gray-300'}`}
                            >
                                Bar
                            </button>
                            <button 
                                onClick={() => setChartType("line")}
                                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase transition-all ${chartType === "line" ? (darkMode ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'bg-blue-600 text-white shadow-lg shadow-blue-200') : 'text-gray-400 hover:text-gray-300'}`}
                            >
                                Line
                            </button>
                            <button 
                                onClick={() => setChartType("pie")}
                                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase transition-all ${chartType === "pie" ? (darkMode ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'bg-blue-600 text-white shadow-lg shadow-blue-200') : 'text-gray-400 hover:text-gray-300'}`}
                            >
                                Pie
                            </button>
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <button 
                        onClick={() => setDarkMode(!darkMode)}
                        className={`p-2.5 rounded-xl transition-all ${darkMode ? 'bg-gray-800 text-yellow-400 hover:bg-gray-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                        title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
                    >
                        {darkMode ? <Sun size={20} /> : <Moon size={20} />}
                    </button>
                </div>
            </div>
            
            <div className={`flex-1 overflow-y-auto p-8 pt-20 flex flex-col gap-6 scrollbar-custom w-full transition-theme ${darkMode ? 'bg-gray-950' : 'bg-white'}`}>
                {isLoadingHistory ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="animate-spin text-blue-500" size={32} />
                    </div>
                ) : messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
                        <div className={`p-6 rounded-full mb-6 ${darkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
                            <MessageCircle size={48} className="text-blue-500" />
                        </div>
                        <h3 className={`text-2xl font-bold mb-2 ${darkMode ? 'text-white' : 'text-gray-800'}`}>How can I help you today?</h3>
                        <p className={darkMode ? 'text-gray-400' : 'text-gray-500'}>Ask about your ERP data, generate reports, or manage your operations directly from this console.</p>
                        <p className="mt-4 text-xs font-semibold text-gray-400 uppercase tracking-widest">
                            Current Mode: <span className="text-blue-600">{chatMode}</span>
                        </p>
                    </div>
                ) : (
                    <>
                        {messages.map((msg, i) => (
                            <div key={i} className="group flex flex-col">
                                <MessageBubble 
                                    msg={msg} 
                                    index={i}
                                    onSelect={handleChoiceSelect} 
                                    onSubmitForm={handleFormSubmit}
                                    onSwitchMode={handleSwitchAndResend}
                                    onEdit={handleEdit}
                                    darkMode={darkMode}
                                    globalViewMode={viewMode}
                                    chartType={chartType}
                                />
                            </div>
                        ))}
                        {isTyping && (
                            <div className={`self-start rounded-2xl rounded-bl-sm p-4 shadow-sm flex items-center gap-1.5 w-20 h-12 border transition-colors ${
                                darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-100'
                            }`}>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                            </div>
                        )}
                        <div ref={messagesEndRef} className="h-4" />
                    </>
                )}
            </div>

            <div className={`p-4 max-w-4xl mx-auto w-full pb-8 transition-theme ${darkMode ? 'bg-gray-950' : 'bg-white'}`}>
                {/* Attachment Chip */}
                {attachment && (
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg w-fit text-sm mb-2 animate-in fade-in slide-in-from-bottom-2 transition-colors ${
                        darkMode ? 'bg-blue-900/40 text-blue-300' : 'bg-blue-50 text-blue-700'
                    }`}>
                        <Paperclip size={14} />
                        <span className="font-medium truncate max-w-[200px]">{attachment.name}</span>
                        <button 
                            onClick={() => setAttachment(null)}
                            className={`rounded-full p-0.5 ml-1 transition-colors ${darkMode ? 'hover:bg-blue-800' : 'hover:bg-blue-100'}`}
                        >
                            <X size={14} />
                        </button>
                    </div>
                )}

                <div className={`relative shadow-sm rounded-2xl border p-2 flex gap-2 overflow-visible transition-theme ${
                    darkMode 
                    ? 'bg-gray-900/40 border-gray-800/60 backdrop-blur-md focus-within:ring-2 focus-within:ring-blue-900/30' 
                    : 'bg-gray-50/80 border-gray-200 backdrop-blur-md focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-100/50'
                }`}>
                    {/* Hidden File Input */}
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        className="hidden" 
                        onChange={handleFileSelect}
                        accept=".csv,.xlsx,.xls,.pdf,.docx,.txt" 
                    />

                    {/* Sources Popup */}
                    {showSourcesPopup && chatMode === "assistant" && (
                        <div
                            className={`absolute bottom-[100%] left-0 mb-4 z-50 w-72 rounded-2xl shadow-2xl border overflow-hidden ${
                                darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                            }`}
                        >
                            <div className={`px-4 py-3 border-b ${ darkMode ? 'border-gray-700' : 'border-gray-100' }`}>
                                <span className={`text-xs font-bold uppercase tracking-widest ${ darkMode ? 'text-gray-400' : 'text-gray-500' }`}>Knowledge Sources</span>
                            </div>
                            {/* ERP Data */}
                            <div className={`flex items-center gap-3 px-4 py-3 border-b ${ darkMode ? 'border-gray-700/50' : 'border-gray-50' }`}>
                                <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${ darkMode ? 'bg-gray-700' : 'bg-gray-100' }`}>
                                    <Building2 size={16} className={darkMode ? 'text-gray-300' : 'text-gray-600'} />
                                </div>
                                <div className="flex-1 flex flex-col">
                                    <span className={`text-sm font-bold ${ darkMode ? 'text-gray-200' : 'text-gray-800' }`}>Company Data</span>
                                    <span className="text-[10px] text-gray-500">ERP & CRM Records</span>
                                </div>
                                <button
                                    onClick={() => setSources(s => ({...s, erp: !s.erp}))}
                                    className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${ sources.erp ? 'bg-blue-600' : (darkMode ? 'bg-gray-600' : 'bg-gray-200') }`}
                                >
                                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${ sources.erp ? 'translate-x-5' : 'translate-x-0' }`} />
                                </button>
                            </div>
                            {/* Documents */}
                            <div className={`flex items-center gap-3 px-4 py-3`}>
                                <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${ darkMode ? 'bg-gray-700' : 'bg-gray-100' }`}>
                                    <FileText size={16} className={darkMode ? 'text-gray-300' : 'text-gray-600'} />
                                </div>
                                <div className="flex-1 flex flex-col">
                                    <span className={`text-sm font-bold ${ darkMode ? 'text-gray-200' : 'text-gray-800' }`}>Documents</span>
                                    <span className="text-[10px] text-gray-500">PDFs, Excel, Word</span>
                                </div>
                                <button
                                    onClick={() => setSources(s => ({...s, documents: !s.documents}))}
                                    className={`relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0 ${ sources.documents ? 'bg-blue-600' : (darkMode ? 'bg-gray-600' : 'bg-gray-200') }`}
                                >
                                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${ sources.documents ? 'translate-x-5' : 'translate-x-0' }`} />
                                </button>
                            </div>
                        </div>
                    )}

                    <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={!isConnected || isLoadingHistory || uploadingState}
                        className={`p-3.5 rounded-xl transition-all flex-shrink-0 ${
                            darkMode ? 'bg-gray-800 text-gray-400 hover:bg-gray-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                        }`}
                        title="Upload Document"
                    >
                        {uploadingState ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
                    </button>

                    <button
                        onClick={() => setShowSourcesPopup(p => !p)}
                        className={`relative p-3.5 rounded-xl transition-all flex-shrink-0 ${
                            showSourcesPopup
                                ? 'bg-blue-600 text-white'
                                : (darkMode ? 'bg-gray-800 text-gray-400 hover:bg-gray-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200')
                        }`}
                        title="Knowledge Sources"
                    >
                        <SlidersHorizontal size={18} />
                        {(!sources.erp || !sources.documents) && (
                            <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-400 border border-white" />
                        )}
                    </button>

                    <div className="relative flex-1 flex items-center">
                        <textarea
                            className="w-full bg-transparent border-0 px-3 py-3 pr-10 text-[15px] outline-none resize-none max-h-48 min-h-[52px]"
                            rows={1}
                            value={input}
                            disabled={!isConnected || isLoadingHistory}
                            onChange={(e) => {
                                setInput(e.target.value);
                                if (historyPointer !== -1 && e.target.value !== promptHistory[historyPointer]) {
                                    setHistoryPointer(-1);
                                }
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder={isListening ? "Listening..." : `Message Amoeba AI in ${chatMode} mode...`}
                        />
                        {speechSupported && (
                            <button
                                onClick={isListening ? () => recognitionRef.current?.stop() : startListening}
                                disabled={!isConnected || isLoadingHistory}
                                className={`absolute right-2 p-1.5 rounded-full transition-colors ${
                                    isListening 
                                    ? 'text-red-500 bg-red-100 dark:bg-red-900/40 animate-pulse' 
                                    : darkMode ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-800' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-200'
                                }`}
                                title={isListening ? "Stop listening" : "Voice Input"}
                            >
                                <Mic size={18} />
                            </button>
                        )}
                    </div>
                    
                    {isTyping ? (
                        <button
                            onClick={handleStop}
                            className="self-end p-3.5 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-all flex items-center gap-2"
                            title="Stop Generation"
                        >
                            <Square size={18} fill="currentColor" />
                            <span className="text-xs font-bold uppercase hidden sm:inline">Stop</span>
                        </button>
                    ) : (
                        <button
                            onClick={isEditingIndex !== null ? sendMessageEdited : sendMessage}
                            disabled={!isConnected || !input.trim()}
                            className={`self-end p-3.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all flex items-center gap-2 ${
                                darkMode 
                                ? 'disabled:bg-gray-800 disabled:text-gray-600' 
                                : 'disabled:bg-gray-100 disabled:text-gray-400'
                            }`}
                            title={isEditingIndex !== null ? "Save & Resend" : "Send Message"}
                        >
                            {isEditingIndex !== null ? (
                                <>
                                    <Pencil size={18} />
                                    <span className="text-xs font-bold uppercase hidden sm:inline">Save & Resend</span>
                                </>
                            ) : (
                                <Send size={18} className={input.trim() ? "translate-x-0.5" : ""} />
                            )}
                        </button>
                    )}
                </div>
                <div className={`text-center mt-3 text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>Amoeba AI can make mistakes. Consider verifying important information.</div>
            </div>


            <style>{`
                .transition-theme {
                    transition: all 0.3s ease-in-out !important;
                }
                .scrollbar-custom::-webkit-scrollbar {
                    width: 8px;
                }
                .scrollbar-custom::-webkit-scrollbar-track {
                    background: transparent;
                }
                .scrollbar-custom::-webkit-scrollbar-thumb {
                    background: ${darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'};
                    transition: background 0.3s ease-in-out;
                    border-radius: 20px;
                    border: 2px solid transparent;
                    background-clip: content-box;
                }
                .scrollbar-custom::-webkit-scrollbar-thumb:hover {
                    background: ${darkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'};
                    background-clip: content-box;
                }
                @keyframes fadeSlideUp {
                    from { opacity: 0; transform: translateY(8px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .animate-in {
                    animation: fadeSlideUp 0.15s ease-out;
                }
            `}</style>
        </div>
    </div>
  );
}
