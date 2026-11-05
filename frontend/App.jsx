
import { useState } from "react";
import axios from "axios";

import {
  LayoutDashboard,
  TrendingUp,
  Package,
  BrainCircuit,
  Upload,
  Download,
  ShoppingCart,
  BarChart3,
  RefreshCw,
  CheckCircle,
  AlertCircle,
} from "lucide-react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
} from "recharts";

import "./App.css";

const API = "http://127.0.0.1:8000";

const formatNumber = (value) => {
  if (value === null || value === undefined || value === "") return "—";

  const result = Number(value);

  return Number.isFinite(result)
    ? result.toLocaleString("en-IN", { maximumFractionDigits: 2 })
    : "—";
};

// Case-insensitive field lookup
function getValue(object, ...names) {
  if (!object) return null;

  for (const name of names) {
    const key = Object.keys(object).find(
      (item) =>
        item.trim().toLowerCase() === name.trim().toLowerCase()
    );

    if (
      key !== undefined &&
      object[key] !== null &&
      object[key] !== undefined &&
      String(object[key]).trim() !== ""
    ) {
      return object[key];
    }
  }

  return null;
}

// Parse CSV returned by FastAPI
function parseCSV(csv) {
  if (!csv || typeof csv !== "string") return [];

  const lines = csv.trim().split(/\r?\n/);

  if (lines.length < 2) return [];

  function splitLine(line) {
    const values = [];
    let current = "";
    let insideQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];

      if (char === '"' && line[i + 1] === '"') {
        current += '"';
        i++;
      } else if (char === '"') {
        insideQuotes = !insideQuotes;
      } else if (char === "," && !insideQuotes) {
        values.push(current.trim());
        current = "";
      } else {
        current += char;
      }
    }

    values.push(current.trim());
    return values;
  }

  const headers = splitLine(lines[0]).map((header) =>
    header.replace(/^\uFEFF/, "").replace(/^"|"$/g, "").trim()
  );

  return lines.slice(1).filter(Boolean).map((line) => {
    const values = splitLine(line);
    const row = {};

    headers.forEach((header, index) => {
      row[header] = (values[index] || "")
        .replace(/^"|"$/g, "")
        .trim();
    });

    return row;
  });
}

// Display category names only: Milk, Juice, Yogurt, etc.
function getProductName(item) {
  return (
    getValue(item, "category", "product_category", "product category") ||
    "Unknown Product"
  );
}

function App() {
  const [overview, setOverview] = useState(null);
  const [models, setModels] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [inventory, setInventory] = useState([]);

  const [uploadId, setUploadId] = useState("");
  const [filename, setFilename] = useState("");

  const [uploading, setUploading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");

  // Fetch results using the unique upload ID
  const loadResults = async (id) => {
    const types = ["forecast", "inventory", "performance"];

    const responses = await Promise.all(
      types.map((type) =>
        axios.get(`${API}/api/results/${id}/${type}`, {
          responseType: "text",
          timeout: 120000,
        })
      )
    );

    const forecastRows = parseCSV(responses[0].data);
    const inventoryRows = parseCSV(responses[1].data);
    const modelRows = parseCSV(responses[2].data);

    console.log("INVENTORY UPLOAD ID:", id);
    console.log(
      "INVENTORY CSV HEADERS:",
      Object.keys(inventoryRows[0] || {})
    );
    console.log("INVENTORY FIRST ROW:", inventoryRows[0]);
    console.log(
      "PRODUCT CATEGORY RECEIVED:",
      inventoryRows[0]?.category
    );

    setForecast(forecastRows);
    setInventory(inventoryRows);
    setModels(modelRows);
  };

  // Upload dataset
  const handleUpload = async (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    const extension = file.name.split(".").pop().toLowerCase();

    if (!["csv", "xlsx"].includes(extension)) {
      setUploadStatus("error");
      setUploadMessage("Please select a CSV or XLSX file.");
      event.target.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    setError("");
    setUploadMessage("");
    setUploadStatus("");

    try {
      const response = await axios.post(
        `${API}/api/upload`,
        formData,
        { timeout: 300000 }
      );

      const result = response.data;
      const analysis = result.analysis || result;

      if (!result.upload_id) {
        throw new Error("The server did not return an upload ID.");
      }

      setUploadId(result.upload_id);
      setFilename(result.filename || file.name);

      setOverview({
        total_sales: analysis.total_units_sold,
        total_products: analysis.products,
        average_daily_demand:
          analysis.average_units_per_product_day,
        forecast_days: analysis.forecast_days,
        rows: analysis.rows,
        columns: analysis.columns,
        missing_values: analysis.missing_values,
        duplicate_rows: analysis.duplicate_rows,
        date_from: analysis.date_from,
        date_to: analysis.date_to,
        analysis_type: analysis.analysis_type,
      });

      await loadResults(result.upload_id);

      setUploadStatus("success");
      setUploadMessage(
        `Successfully analyzed ${file.name}. ${formatNumber(
          analysis.rows
        )} rows and ${formatNumber(analysis.columns)} columns.`
      );
    } catch (err) {
      console.error("Upload error:", err);

      setUploadStatus("error");
      setUploadMessage(
        err.response?.data?.detail ||
          err.message ||
          "Dataset analysis failed."
      );
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  // Refresh dashboard
  const handleRefresh = async () => {
    if (!uploadId) {
      setError("Please upload a dataset before refreshing.");
      return;
    }

    setRefreshing(true);
    setError("");

    try {
      await loadResults(uploadId);
    } catch (err) {
      console.error("Refresh error:", err);

      setError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to refresh dashboard."
      );
    } finally {
      setRefreshing(false);
    }
  };

  // Download forecast CSV
  const downloadForecast = () => {
    if (!uploadId) {
      setError("Upload a dataset before downloading the forecast.");
      return;
    }

    window.open(
      `${API}/api/results/${uploadId}/forecast`,
      "_blank"
    );
  };

  // Prepare forecast chart data
  const chartData = Object.values(
    forecast.reduce((result, item) => {
      const date = getValue(item, "date");

      const demand = Number(
        getValue(
          item,
          "predicted_demand",
          "forecast",
          "prediction"
        )
      );

      if (!date || !Number.isFinite(demand)) return result;

      if (!result[date]) {
        result[date] = {
          date,
          demand: 0,
        };
      }

      result[date].demand += demand;

      return result;
    }, {})
  ).sort((a, b) => a.date.localeCompare(b.date));

  // Prepare model performance data
  const modelData = models.map((model, index) => ({
    name: getValue(model, "Model", "model") || `Model ${index + 1}`,
    mae: Number(getValue(model, "MAE", "mae")) || 0,
    rmse: Number(getValue(model, "RMSE", "rmse")) || 0,
    r2: Number(
      getValue(model, "R2 Score", "r2_score", "r2")
    ) || 0,
  }));

  const bestModel = modelData.length
    ? modelData.reduce((best, current) =>
        current.mae < best.mae ? current : best
      )
    : null;

  return (
    <div className="app-container">

      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand">
          <BrainCircuit size={28} />
          <h2>RetailIQ</h2>
        </div>

        <nav className="navigation">
          <a href="#overview">
            <LayoutDashboard size={18} />
            Overview
          </a>

          <a href="#forecast">
            <TrendingUp size={18} />
            Forecast
          </a>

          <a href="#models">
            <BrainCircuit size={18} />
            Model Performance
          </a>

          <a href="#inventory">
            <Package size={18} />
            Inventory
          </a>
        </nav>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main-content">

        {/* HEADER */}
        <header className="topbar">
          <div>
            <span className="breadcrumb">
              Workspace / Dashboard
            </span>

            <h1>Retail Intelligence Dashboard</h1>

            <p>
              Monitor demand, forecast sales and optimize inventory.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={handleRefresh}
            disabled={refreshing || uploading || !uploadId}
          >
            <RefreshCw size={16} />
            {refreshing ? "Refreshing..." : "Refresh Data"}
          </button>
        </header>

        {/* ERROR */}
        {error && (
          <div className="error-message">
            <AlertCircle size={18} />
            {error}
          </div>
        )}

        {/* CURRENT DATASET */}
        {filename && (
          <p className="breadcrumb">
            Current dataset: <strong>{filename}</strong>
          </p>
        )}

        {/* KPI CARDS */}
        <section id="overview" className="kpi-grid">

          <div className="kpi-card">
            <div className="kpi-top">
              <span>Total Units Sold</span>
              <div className="kpi-icon purple">
                <ShoppingCart size={21} />
              </div>
            </div>

            <h2>{formatNumber(overview?.total_sales)}</h2>

            <span className="kpi-note">
              Historical sales volume
            </span>
          </div>

          <div className="kpi-card">
            <div className="kpi-top">
              <span>Products Tracked</span>
              <div className="kpi-icon blue">
                <Package size={21} />
              </div>
            </div>

            <h2>{formatNumber(overview?.total_products)}</h2>

            <span className="kpi-note">
              Unique product SKUs
            </span>
          </div>

          <div className="kpi-card">
            <div className="kpi-top">
              <span>Average Demand</span>
              <div className="kpi-icon green">
                <BarChart3 size={21} />
              </div>
            </div>

            <h2>{formatNumber(overview?.average_daily_demand)}</h2>

            <span className="kpi-note">
              Average units per product-day
            </span>
          </div>

          <div className="kpi-card">
            <div className="kpi-top">
              <span>Forecast Horizon</span>
              <div className="kpi-icon orange">
                <TrendingUp size={21} />
              </div>
            </div>

            <h2>
              {overview ? `${overview.forecast_days} Days` : "—"}
            </h2>

            <span className="kpi-note">
              Future demand predictions
            </span>
          </div>

        </section>

        {/* DATASET PROFILE */}
        {overview && (
          <section className="content-card">
            <h2>Dataset Profile</h2>

            <p>
              {formatNumber(overview.rows)} rows ·{" "}
              {formatNumber(overview.columns)} columns ·{" "}
              {formatNumber(overview.missing_values)} missing values ·{" "}
              {formatNumber(overview.duplicate_rows)} duplicate rows
            </p>

            {overview.date_from && overview.date_to && (
              <p>
                Date range: {overview.date_from} to {overview.date_to}
              </p>
            )}
          </section>
        )}

        {/* FORECAST */}
        <section id="forecast" className="content-card">
          <div className="section-heading">
            <div>
              <h2>Demand Forecast</h2>
              <p>
                Predicted total demand across all products
              </p>
            </div>

            <TrendingUp size={23} />
          </div>

          <div className="chart-container">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(value) => value.slice(5)}
                  />

                  <YAxis tick={{ fontSize: 11 }} />

                  <Tooltip />
                  <Legend />

                  <Line
                    type="monotone"
                    dataKey="demand"
                    name="Predicted Demand"
                    stroke="#6658e8"
                    strokeWidth={3}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">
                {uploadId
                  ? "No forecast data available for this dataset."
                  : "Upload a retail dataset to generate a forecast."}
              </div>
            )}
          </div>
        </section>

        {/* MODEL PERFORMANCE */}
        <section id="models" className="content-card">
          <div className="section-heading">
            <div>
              <h2>Model Performance</h2>
              <p>
                Comparison of trained machine learning models
              </p>
            </div>

            <BrainCircuit size={23} />
          </div>

          {modelData.length > 0 ? (
            <>
              <div className="model-grid">
                {modelData.map((model) => (
                  <div className="model-card" key={model.name}>
                    <div className="model-name">
                      <span>{model.name}</span>

                      {bestModel?.name === model.name && (
                        <span className="best-tag">
                          Best MAE
                        </span>
                      )}
                    </div>

                    <div className="model-metric">
                      <span>MAE</span>
                      <strong>{formatNumber(model.mae)}</strong>
                    </div>

                    <div className="model-metric">
                      <span>RMSE</span>
                      <strong>{formatNumber(model.rmse)}</strong>
                    </div>

                    <div className="model-metric">
                      <span>R² Score</span>
                      <strong>{formatNumber(model.r2)}</strong>
                    </div>
                  </div>
                ))}
              </div>

              <div className="chart-container small-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={modelData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                    />

                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />

                    <Bar
                      dataKey="mae"
                      name="MAE"
                      fill="#6658e8"
                      radius={[5, 5, 0, 0]}
                    />

                    <Bar
                      dataKey="rmse"
                      name="RMSE"
                      fill="#23a78b"
                      radius={[5, 5, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : (
            <div className="empty-state">
              No model performance data available.
            </div>
          )}
        </section>

        {/* INVENTORY RECOMMENDATIONS */}
        <section id="inventory" className="content-card">
          <div className="section-heading">
            <div>
              <h2>Inventory Recommendations</h2>
              <p>
                Suggested reorder levels for tracked products
              </p>
            </div>

            <Package size={23} />
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Product Name</th>
                  <th>Avg. Daily Demand</th>
                  <th>Lead Time</th>
                  <th>Safety Stock</th>
                  <th>Reorder Point</th>
                  <th>Recommended Qty</th>
                </tr>
              </thead>

              <tbody>
                {inventory.length > 0 ? (
                  inventory.map((item, index) => (
                    <tr
                      key={
                        getValue(item, "sku", "product", "product_id") ||
                        index
                      }
                    >
                      <td>
                        <strong>{getProductName(item)}</strong>
                      </td>

                      <td>
                        {formatNumber(
                          getValue(item, "average_daily_demand")
                        )}
                      </td>

                      <td>
                        {formatNumber(
                          getValue(item, "lead_time_days")
                        )} days
                      </td>

                      <td>
                        {formatNumber(
                          getValue(item, "safety_stock")
                        )}
                      </td>

                      <td>
                        {formatNumber(
                          getValue(item, "reorder_point")
                        )}
                      </td>

                      <td>
                        <span className="quantity-tag">
                          {formatNumber(
                            getValue(
                              item,
                              "recommended_order_quantity"
                            )
                          )}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="empty-table">
                      No inventory recommendations available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* DATASET MANAGEMENT */}
        <section className="content-card upload-section">
          <div className="section-heading dataset-heading">
            <div>
              <h2>Dataset Management</h2>
              <p>
                Upload a CSV or Excel dataset for analysis
              </p>
            </div>

            <div className="dataset-actions">
              <button
                className="download-button"
                onClick={downloadForecast}
                type="button"
                disabled={!uploadId}
              >
                <Download size={17} />
                Download Forecast CSV
              </button>

              <Upload size={23} />
            </div>
          </div>

          <div className="upload-area">
            <Upload size={32} />

            <h3>Upload your dataset</h3>

            <p>
              Supported formats: CSV and XLSX
            </p>

            <label className="upload-button">
              {uploading ? "Analyzing dataset..." : "Choose Dataset"}

              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={handleUpload}
                disabled={uploading}
                hidden
              />
            </label>

            {uploadMessage && (
              <p className={`upload-message ${uploadStatus}`}>
                {uploadStatus === "success" && (
                  <CheckCircle size={15} />
                )}

                {uploadStatus === "error" && (
                  <AlertCircle size={15} />
                )}

                {uploadMessage}
              </p>
            )}
          </div>
        </section>

        {/* FOOTER */}
        <footer className="footer">
          <span>
            RetailIQ · Retail Demand Forecasting System
          </span>

          <span>
            <CheckCircle size={14} />
            Powered by FastAPI & Machine Learning
          </span>
        </footer>

      </main>
    </div>
  );
}

export default App;
