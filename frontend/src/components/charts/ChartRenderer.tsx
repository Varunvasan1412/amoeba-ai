import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from "recharts";

interface ChartRendererProps {
  data: any[];
  columns: string[];
  darkMode?: boolean;
}

const COLORS = [
  "#6366f1", "#8b5cf6", "#a855f7", "#d946ef",
  "#ec4899", "#f43f5e", "#f97316", "#eab308",
  "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6",
];

// Columns that should NEVER be treated as chartable numeric values
const SKIP_PATTERNS = [
  /^id$/i,
  /_id$/i,
  /created_by/i,
  /updated_by/i,
  /modified_by/i,
  /deleted_by/i,
  /user_id/i,
  /client_id/i,
  /category_id/i,
  /serial_no/i,
  /part_number/i,
  /phone/i,
  /mobile/i,
  /zip/i,
  /pin/i,
  /code$/i,
  /password/i,
  /token/i,
  /key$/i,
  /_at$/i,    // timestamps: created_at, updated_at
  /_on$/i,
  /date/i,
];

/**
 * Returns true if this column name looks like it should be skipped for charting
 */
function shouldSkipColumn(colName: string): boolean {
  return SKIP_PATTERNS.some(pattern => pattern.test(colName));
}

/**
 * Returns true if a column has meaningful numeric variance (not just 0/1 flags)
 */
function hasNumericVariance(data: any[], col: string): boolean {
  const values = data
    .map(r => Number(r[col]))
    .filter(v => !isNaN(v));
  
  if (values.length < 2) return false;
  
  const unique = new Set(values);
  // If all values are the same, or it's just 0/1 flags, skip it
  if (unique.size <= 1) return false;
  if (unique.size === 2 && unique.has(0) && unique.has(1)) return false;
  
  // Check if the column is basically a "status" field (very few unique values relative to rows)
  // If <=3 unique values across many rows, it's likely categorical
  if (data.length > 10 && unique.size <= 3) return false;

  return true;
}

function detectChartType(data: any[], categoryCol: string, numericCols: string[]): "bar" | "pie" | "line" {
  if (data.length <= 8 && numericCols.length === 1) return "pie";

  const sample = String(data[0]?.[categoryCol] || "");
  if (/\d{4}-\d{2}/.test(sample) || /\d{2}\/\d{2}/.test(sample)) return "line";

  return "bar";
}

export default function ChartRenderer({ data, columns, darkMode = false, chartType: manualChartType }: ChartRendererProps) {
  const [groupSlices, setGroupSlices] = useState(true);

  const analysis = useMemo(() => {
    if (!data || data.length === 0 || !columns || columns.length < 2) return null;

    const numericCols: string[] = [];
    const categoryCols: string[] = [];

    for (const col of columns) {
      // Skip columns by name pattern
      if (shouldSkipColumn(col)) {
        // Still can be a category
        categoryCols.push(col);
        continue;
      }
      
      // Sample multiple rows to determine type
      const sampleValues = data.slice(0, 10).map(r => r[col]).filter(v => v != null);
      if (sampleValues.length === 0) continue;

      // Check if majority are numeric
      const numericCount = sampleValues.filter(v => {
        const n = Number(v);
        return !isNaN(n) && typeof v !== "boolean" && String(v).trim() !== "";
      }).length;

      const isNumeric = numericCount / sampleValues.length > 0.7;

      if (isNumeric && hasNumericVariance(data, col)) {
        numericCols.push(col);
      } else {
        categoryCols.push(col);
      }
    }

    // AUTO-AGGREGATION FALLBACK: If no numeric columns, count rows by best category
    if (numericCols.length === 0) {
      const candidateCols = columns.filter(c => {
        if (shouldSkipColumn(c)) return false;
        const uniqueVals = new Set(data.map(r => r[c]).filter(v => v != null));
        return uniqueVals.size >= 2 && uniqueVals.size <= Math.min(data.length, 50);
      });

      const bestCatCol = candidateCols[0];
      if (!bestCatCol) return null;

      const counts: Record<string, number> = {};
      for (const row of data) {
        const key = String(row[bestCatCol] || "Other").slice(0, 25);
        counts[key] = (counts[key] || 0) + 1;
      }

      const sortedEntries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      
      let aggData: any[] = [];
      const threshold = (manualChartType === "pie" || (!manualChartType && sortedEntries.length <= 10)) ? 8 : 20;

      if (groupSlices && sortedEntries.length > threshold) {
        const top = sortedEntries.slice(0, threshold - 1);
        const otherCount = sortedEntries.slice(threshold - 1).reduce((acc, curr) => acc + curr[1], 0);
        aggData = top.map(([name, count]) => ({ [bestCatCol]: name, Count: count }));
        aggData.push({ [bestCatCol]: "Other", Count: otherCount });
      } else {
        aggData = sortedEntries.map(([name, count]) => ({ [bestCatCol]: name, Count: count }));
      }

      const detectedType = aggData.length <= 8 ? "pie" : "bar";
      const finalType = manualChartType || detectedType;
      return { chartData: aggData, categoryCol: bestCatCol, numericCols: ["Count"], chartType: finalType as "bar" | "pie" | "line" };
    }
    
    let categoryCol = categoryCols.find(c => !shouldSkipColumn(c)) || categoryCols[0] || columns[0];
    
    if (numericCols.includes(categoryCol)) {
      const alt = columns.find(c => !numericCols.includes(c));
      if (alt) categoryCol = alt;
      else return null;
    }

    const detectedType = detectChartType(data, categoryCol, numericCols);
    const finalType = manualChartType || detectedType;

    // Limit data points for readability with "Other" grouping for Pie
    const maxPoints = finalType === "pie" ? 10 : 30;
    let chartData: any[] = [];

    if (groupSlices && finalType === "pie" && data.length > maxPoints) {
      const sortedData = [...data].sort((a, b) => (Number(b[numericCols[0]]) || 0) - (Number(a[numericCols[0]]) || 0));
      const top = sortedData.slice(0, maxPoints - 1);
      const otherValue = sortedData.slice(maxPoints - 1).reduce((acc, curr) => acc + (Number(curr[numericCols[0]]) || 0), 0);
      
      chartData = top.map(row => {
        const cleaned: any = {};
        cleaned[categoryCol] = String(row[categoryCol] || "—").slice(0, 25);
        for (const nc of numericCols) cleaned[nc] = Number(row[nc]) || 0;
        return cleaned;
      });
      
      const otherRow: any = { [categoryCol]: "Other" };
      otherRow[numericCols[0]] = otherValue;
      chartData.push(otherRow);
    } else {
      chartData = data.slice(0, maxPoints).map(row => {
        const cleaned: any = {};
        cleaned[categoryCol] = String(row[categoryCol] || "—").slice(0, 25);
        for (const nc of numericCols) cleaned[nc] = Number(row[nc]) || 0;
        return cleaned;
      });
    }

    return { chartData, categoryCol, numericCols, chartType: finalType };
  }, [data, columns, manualChartType, groupSlices]);

  if (!analysis) {
    return (
      <div className={`text-center py-8 text-sm ${darkMode ? "text-gray-400" : "text-gray-500"}`}>
        <p>📊 Chart not available for this dataset.</p>
        <p className="text-xs mt-1 opacity-70">No meaningful numeric columns detected for visualization.</p>
      </div>
    );
  }

  const { chartData, categoryCol, numericCols, chartType } = analysis;

  const axisStyle = {
    fontSize: 11,
    fill: darkMode ? "#9ca3af" : "#6b7280",
  };

  const gridColor = darkMode ? "#374151" : "#e5e7eb";

  const tooltipStyle = {
    backgroundColor: darkMode ? "#1f2937" : "#fff",
    borderColor: darkMode ? "#374151" : "#e5e7eb",
    borderRadius: 8,
    fontSize: 12,
    color: darkMode ? "#e5e7eb" : "#1f2937",
  };

  if (chartType === "pie") {
    const RADIAN = Math.PI / 180;
    const renderCustomizedLabel = (props: any) => {
      const { cx, cy, midAngle, innerRadius, outerRadius, percent, name, index } = props;
      
      const threshold = groupSlices ? 0.03 : 0.01;
      if (percent <= threshold) return null;

      const sin = Math.sin(-RADIAN * midAngle);
      const cos = Math.cos(-RADIAN * midAngle);
      
      // Arc detection
      const isBottom = midAngle < -45 && midAngle > -135;
      
      // Point on the edge of the pie
      const sx = cx + (outerRadius + 2) * cos;
      const sy = cy + (outerRadius + 2) * sin;
      
      // 1. TIERED ELBOW: Alternate radial distance to spread labels out
      const elbowDist = isBottom ? (index % 2 === 0 ? 50 : 25) : 35;
      const mx = cx + (outerRadius + elbowDist) * cos;
      const my = cy + (outerRadius + elbowDist) * sin;
      
      // 2. STAGGERED EXTENSION: Alternate horizontal line length
      const extension = index % 3 === 0 ? 40 : (index % 3 === 1 ? 20 : 60);
      const ex = mx + (cos >= 0 ? 1 : -1) * extension;
      
      // 3. AGGRESSIVE VERTICAL STAGGER: Push labels up/down at the bottom
      const yOffset = isBottom ? (index % 2 === 0 ? 30 : -15) : 0;
      const ey = my + yOffset;
      
      const textAnchor = cos >= 0 ? "start" : "end";

      return (
        <g>
          {/* Multi-segment bended line */}
          <path 
            d={`M${sx},${sy}L${mx},${my}H${ex}`} 
            stroke={darkMode ? "#9ca3af" : "#6b7280"} 
            strokeWidth={1.2}
            fill="none" 
            opacity={0.8}
          />
          <text 
            x={ex + (cos >= 0 ? 1 : -1) * 8} 
            y={ey} 
            dy={4}
            textAnchor={textAnchor} 
            fill={darkMode ? "#e5e7eb" : "#374151"} 
            className="text-[10px] font-bold"
          >
            {`${name} (${(percent * 100).toFixed(0)}%)`}
          </text>
        </g>
      );
    };

    return (
      <div className="w-full min-w-0 flex flex-col items-center">
        {/* Inline Toggle */}
        <div className="flex items-center gap-2 mb-2 self-end px-4">
            <span className={`text-[10px] font-bold uppercase tracking-wider ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Group Minor
            </span>
            <button 
                onClick={() => setGroupSlices(!groupSlices)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${groupSlices ? 'bg-blue-600' : (darkMode ? 'bg-gray-700' : 'bg-gray-300')}`}
            >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${groupSlices ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
        </div>
        
        <ResponsiveContainer width="100%" height={550}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey={numericCols[0]}
              nameKey={categoryCol}
              cx="50%"
              cy="45%"
              outerRadius={130}
              innerRadius={50}
              paddingAngle={2}
              label={renderCustomizedLabel}
              labelLine={false}
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: darkMode ? "#d1d5db" : "#4b5563" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartType === "line") {
    return (
      <div className="w-full min-w-0">
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey={categoryCol} tick={axisStyle} angle={-35} textAnchor="end" height={70} />
            <YAxis tick={axisStyle} width={60} />
            <Tooltip contentStyle={tooltipStyle} />
            {numericCols.map((col, i) => (
              <Line
                key={col}
                type="monotone"
                dataKey={col}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            ))}
            {numericCols.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Default: Bar chart
  return (
    <div className="w-full min-w-0">
      <ResponsiveContainer width="100%" height={380}>
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={categoryCol} tick={axisStyle} angle={-35} textAnchor="end" height={70} />
          <YAxis tick={axisStyle} width={60} />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ fill: darkMode ? "rgba(99,102,241,0.1)" : "rgba(59,130,246,0.08)" }}
          />
          {numericCols.map((col, i) => (
            <Bar
              key={col}
              dataKey={col}
              fill={COLORS[i % COLORS.length]}
              radius={[4, 4, 0, 0]}
              maxBarSize={50}
            />
          ))}
          {numericCols.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
