import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const money = (value) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value));
const numeric = (value) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(Number(value));

export default function Chart({ data = [], type = "bar", x = "month", y = "revenue" }) {
  if (!data.length) return <div className="chart-empty">Chart data will appear when the API returns eligible records.</div>;
  const isCurrency = /revenue|sales|amount/i.test(y);
  const formatValue = (value) => isCurrency ? money(value) : numeric(value);
  const valueLabel = y.replaceAll("_", " ");
  const ChartType = type === "line" ? LineChart : BarChart;
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <ChartType data={data} margin={{ top: 12, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="#e5e2de" strokeDasharray="2 5" />
          <XAxis dataKey={x} axisLine={false} tickLine={false} tick={{ fill: "#858694", fontSize: 11 }} dy={8} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: "#858694", fontSize: 11 }} tickFormatter={formatValue} width={66} />
          <Tooltip
            cursor={type === "line" ? { stroke: "#d9d6d1" } : { fill: "#f6f4f0" }}
            contentStyle={{ background: "#fff", border: "1px solid #e5e2de", borderRadius: "12px", boxShadow: "0 10px 24px rgba(23,25,35,.08)", fontSize: "12px" }}
            formatter={(value) => [formatValue(value), valueLabel]}
            labelStyle={{ color: "#666979", marginBottom: "4px" }}
          />
          {type === "line" ? (
            <Line type="monotone" dataKey={y} stroke="#354ffe" strokeWidth={3} dot={{ r: 3, fill: "#fff", stroke: "#354ffe", strokeWidth: 2 }} activeDot={{ r: 5, fill: "#ff573d", stroke: "#fff", strokeWidth: 2 }} />
          ) : (
            <Bar dataKey={y} radius={[5, 5, 0, 0]} maxBarSize={34}>
              {data.map((entry, index) => <Cell key={`${entry[x]}-${index}`} fill={index === 0 ? "#354ffe" : "#a7b5cc"} />)}
            </Bar>
          )}
        </ChartType>
      </ResponsiveContainer>
    </div>
  );
}
