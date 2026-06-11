import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie
} from 'recharts';
import {
  Activity,
  Play,
  Square,
  RefreshCw,
  CloudLightning,
  CloudRain,
  Sun,
  ShieldCheck,
  AlertTriangle,
  Clock,
  TrendingUp,
  MapPin,
  ListTodo,
  Terminal,
  Database,
  Sliders,
  Sparkles,
  CheckCircle,
  HelpCircle
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  // Simulator State
  const [simStatus, setSimStatus] = useState({
    running: false,
    weather: 'Clear',
    order_rate: 0.5,
    speed_multiplier: 60.0,
    active_order_count: 0,
    total_orders_generated: 0,
    simulation_time: ''
  });
  
  // Dashboard Analytics
  const [summary, setSummary] = useState({
    total_orders: 0,
    total_clean_orders: 0,
    compliance_rate: 100.0,
    avg_duration_mins: 0.0,
    avg_prep_mins: 0.0,
    avg_transit_mins: 0.0,
    avg_dispatch_mins: 0.0,
    dq_fail_count: 0
  });

  const [breaches, setBreaches] = useState([]);
  const [trends, setTrends] = useState([]);
  const [dqReport, setDqReport] = useState({ rule_metrics: [], recent_failures: [] });
  const [orders, setOrders] = useState([]);
  const [events, setEvents] = useState([]);
  
  // Optimization States
  const [recommendations, setRecommendations] = useState([]);
  const [schedulerStatus, setSchedulerStatus] = useState(true);

  // Form inputs
  const [weatherInput, setWeatherInput] = useState('Clear');
  const [orderRateInput, setOrderRateInput] = useState(0.5);
  const [speedInput, setSpeedInput] = useState(60);

  // ETL manual sync trigger state
  const [isEtlRunning, setIsEtlRunning] = useState(false);
  const [etlMessage, setEtlMessage] = useState('');

  // Fetch all dashboard stats
  const fetchData = async () => {
    try {
      // 1. Simulator Status
      const simRes = await fetch(`${API_BASE_URL}/api/simulator/status`);
      if (simRes.ok) {
        const data = await simRes.json();
        setSimStatus(data);
      }

      // 2. Summary KPI Cards
      const summaryRes = await fetch(`${API_BASE_URL}/api/dashboard/summary`);
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }

      // 3. Breaches breakdown
      const breachesRes = await fetch(`${API_BASE_URL}/api/dashboard/breaches`);
      if (breachesRes.ok) {
        const data = await breachesRes.json();
        setBreaches(data);
      }

      // 4. Trends line chart
      const trendsRes = await fetch(`${API_BASE_URL}/api/dashboard/trends`);
      if (trendsRes.ok) {
        const data = await trendsRes.json();
        setTrends(data);
      }

      // 5. Data Quality reports
      const dqRes = await fetch(`${API_BASE_URL}/api/dashboard/data-quality`);
      if (dqRes.ok) {
        const data = await dqRes.json();
        setDqReport(data);
      }

      // 6. Detailed Orders List
      const ordersRes = await fetch(`${API_BASE_URL}/api/dashboard/orders`);
      if (ordersRes.ok) {
        const data = await ordersRes.json();
        setOrders(data);
      }

      // 7. Recent Events Logs
      const eventsRes = await fetch(`${API_BASE_URL}/api/events?limit=50`);
      if (eventsRes.ok) {
        const data = await eventsRes.json();
        setEvents(data);
      }

      // 8. Background ETL Auto-Scheduler status
      const schedRes = await fetch(`${API_BASE_URL}/api/scheduler/status`);
      if (schedRes.ok) {
        const data = await schedRes.json();
        setSchedulerStatus(data.auto_etl_enabled);
      }

      // 9. Operational Recommendations
      const recsRes = await fetch(`${API_BASE_URL}/api/dashboard/recommendations`);
      if (recsRes.ok) {
        const data = await recsRes.json();
        setRecommendations(data);
      }

    } catch (err) {
      console.error('Error fetching dashboard stats:', err);
    }
  };

  // Poll databases on mount and every 3 seconds
  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 3000);
    return () => clearInterval(timer);
  }, []);

  // Pre-fill inputs when status changes
  useEffect(() => {
    if (simStatus.weather) setWeatherInput(simStatus.weather);
    if (simStatus.order_rate) setOrderRateInput(simStatus.order_rate);
    if (simStatus.speed_multiplier) setSpeedInput(simStatus.speed_multiplier);
  }, [simStatus.weather, simStatus.order_rate, simStatus.speed_multiplier]);

  // Actions
  const handleStartSim = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/simulator/start`, { method: 'POST' });
      fetchData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStopSim = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/simulator/stop`, { method: 'POST' });
      fetchData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateConfig = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_BASE_URL}/api/simulator/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          weather: weatherInput,
          order_rate: parseFloat(orderRateInput),
          speed_multiplier: parseFloat(speedInput)
        })
      });
      fetchData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleScheduler = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/scheduler/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSchedulerStatus(data.auto_etl_enabled);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerEtl = async () => {
    setIsEtlRunning(true);
    setEtlMessage('Running ETL Batch pipeline...');
    try {
      const res = await fetch(`${API_BASE_URL}/api/orchestrator/run`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const s = data.stats;
        setEtlMessage(
          `ETL Run Completed. Processed: ${s.processed_count} | DQ Pass: ${s.dq_pass_count} | DQ Fail: ${s.dq_fail_count} | Breaches: ${s.breach_count}`
        );
        fetchData();
      } else {
        const err = await res.json();
        setEtlMessage(`ETL Failed: ${err.detail || 'Unknown Error'}`);
      }
    } catch (e) {
      setEtlMessage(`ETL Run Failed: Connection error`);
    } finally {
      setIsEtlRunning(false);
      setTimeout(() => setEtlMessage(''), 8000);
    }
  };

  const handleResetDatabase = async () => {
    if (window.confirm("Are you sure you want to WIPE all databases and restart the simulator? This cannot be undone.")) {
      try {
        const res = await fetch(`${API_BASE_URL}/api/database/reset`, { method: 'POST' });
        if (res.ok) {
          alert("Databases wiped and re-initialized successfully!");
          fetchData();
        } else {
          const err = await res.json();
          alert(`Reset failed: ${err.detail || 'Unknown Error'}`);
        }
      } catch (e) {
        alert("Failed to connect to backend for database reset.");
      }
    }
  };


  // Weather Badge Helpers
  const getWeatherIcon = (w) => {
    switch (w) {
      case 'Rain': return <CloudRain size={16} />;
      case 'Storm': return <CloudLightning size={16} />;
      default: return <Sun size={16} />;
    }
  };

  // Color mappings for breach charts
  const COLORS = {
    'Weather Delay (Rain)': '#3b82f6',
    'Weather Delay (Storm)': '#1d4ed8',
    'Peak Demand Delay': '#f59e0b',
    'Kitchen Operational Delay': '#ef4444',
    'Rider Dispatch Delay': '#a855f7',
    'No Breach': '#10b981'
  };

  // Format Data Quality metrics for Donut Chart
  const passSum = dqReport.rule_metrics.reduce((acc, x) => acc + x.pass_count, 0);
  const failSum = dqReport.rule_metrics.reduce((acc, x) => acc + x.fail_count, 0);
  const dqPieData = [
    { name: 'Passing checks', value: passSum || 1 }, // default 1 to render pie on startup
    { name: 'Failing audits', value: failSum }
  ];

  // Stacked SLA actuals vs target
  const delayStageData = [
    { name: 'Rider Dispatch', Actual: summary.avg_dispatch_mins, Target: 5.0 },
    { name: 'Kitchen Prep', Actual: summary.avg_prep_mins, Target: 15.0 },
    { name: 'Rider Transit', Actual: summary.avg_transit_mins, Target: 15.0 }
  ];

  return (
    <div className="app-container">
      {/* HEADER SECTION */}
      <header className="glass-panel app-header">
        <div className="logo-section">
          <h1>
            <Activity className="text-primary" size={28} />
            Delivery SLA & Data Quality Hub
            <span>STAR SCHEMA</span>
          </h1>
        </div>
        <div className="header-controls">
          {/* Background ETL Status */}
          <button 
            onClick={handleToggleScheduler} 
            className={`badge ${schedulerStatus ? 'badge-success' : 'badge-warning'}`}
            style={{ border: '1px solid transparent', cursor: 'pointer' }}
            title="Click to toggle auto scheduler"
          >
            <RefreshCw size={14} className={schedulerStatus ? 'animate-spin' : ''} style={{ animationDuration: '6s' }} />
            Auto-ETL: {schedulerStatus ? 'ACTIVE (10s)' : 'PAUSED'}
          </button>
          
          <div className={`badge ${simStatus.running ? 'badge-success' : 'badge-danger'}`}>
            <span className={`pulse-dot ${simStatus.running ? '' : 'stopped'}`}></span>
            Simulator {simStatus.running ? 'Running' : 'Stopped'}
          </div>
          <div className="badge badge-info">
            {getWeatherIcon(simStatus.weather)}
            Weather: {simStatus.weather}
          </div>
           <button 
            onClick={handleTriggerEtl} 
            className="btn btn-primary"
            disabled={isEtlRunning}
          >
            <RefreshCw size={16} className={isEtlRunning ? 'animate-spin' : ''} />
            Sync Now
          </button>
          <button 
            onClick={handleResetDatabase} 
            className="btn btn-danger"
          >
            Reset DB
          </button>
        </div>
      </header>

      {/* ALERT FOR ETL SUMMARY */}
      {etlMessage && (
        <div className={`badge ${etlMessage.includes('Failed') ? 'badge-danger' : 'badge-success'}`} style={{ width: '100%', padding: '16px', display: 'flex', justifyContent: 'center' }}>
          <Database size={18} style={{ marginRight: '8px' }} />
          {etlMessage}
        </div>
      )}

      {/* DASHBOARD GRID */}
      <div className="dashboard-grid">
        
        {/* SIMULATOR CONTROLS */}
        <div className="glass-panel grid-item-4 card-content" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <h2 className="section-title">
              <Sliders size={18} />
              Simulation Settings
            </h2>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
              <button 
                onClick={handleStartSim} 
                className="btn btn-success" 
                style={{ flex: 1 }}
                disabled={simStatus.running}
              >
                <Play size={16} /> Start
              </button>
              <button 
                onClick={handleStopSim} 
                className="btn btn-danger" 
                style={{ flex: 1 }}
                disabled={!simStatus.running}
              >
                <Square size={16} /> Stop
              </button>
            </div>
            
            <form onSubmit={handleUpdateConfig} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="control-group">
                <label>Set Environment Weather</label>
                <select 
                  value={weatherInput} 
                  onChange={(e) => setWeatherInput(e.target.value)}
                  className="select-input"
                >
                  <option value="Clear">Clear (Normal Speed)</option>
                  <option value="Rain">Rain (1.5x Travel Delay)</option>
                  <option value="Storm">Storm (2.5x Travel Delay)</option>
                </select>
              </div>
              
              <div className="control-group">
                <label>Simulated Order Rate (orders/min)</label>
                <input 
                  type="number" 
                  step="0.1" 
                  min="0.1" 
                  max="5.0"
                  value={orderRateInput} 
                  onChange={(e) => setOrderRateInput(e.target.value)}
                  className="number-input"
                />
              </div>
              
              <div className="control-group">
                <label>Simulation Clock Speed: {speedInput}x</label>
                <input 
                  type="range" 
                  min="20" 
                  max="300"
                  value={speedInput} 
                  onChange={(e) => setSpeedInput(e.target.value)}
                  style={{ accentColor: '#6366f1' }}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  1 real second = {speedInput} simulated seconds
                </span>
              </div>

              <button type="submit" className="btn btn-secondary" style={{ marginTop: '4px' }}>
                Apply Configuration
              </button>
            </form>
          </div>

          <div style={{ paddingTop: '16px', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justify_content: 'space-between', justifyContent: 'space-between' }}>
              <span className="text-secondary">Simulated Time:</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>
                {simStatus.simulation_time ? new Date(simStatus.simulation_time).toLocaleTimeString() : 'N/A'}
              </span>
            </div>
            <div style={{ display: 'flex', justify_content: 'space-between', justifyContent: 'space-between' }}>
              <span className="text-secondary">Active Orders Queue:</span>
              <span className="badge badge-info" style={{ padding: '2px 8px', fontSize: '0.75rem' }}>
                {simStatus.active_order_count}
              </span>
            </div>
            <div style={{ display: 'flex', justify_content: 'space-between', justifyContent: 'space-between' }}>
              <span className="text-secondary">Total Orders Generated:</span>
              <span style={{ fontWeight: 'bold' }}>{simStatus.total_orders_generated}</span>
            </div>
          </div>
        </div>

        {/* SUMMARY KPI CARDS */}
        <div className="grid-item-8" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="kpi-container">
            <div className="glass-panel kpi-card">
              <div className="kpi-header">
                Total Orders
                <Database size={16} />
              </div>
              <div className="kpi-value">{summary.total_orders}</div>
              <div className="kpi-footer">Passing Data Quality Check</div>
            </div>

            <div className="glass-panel kpi-card" style={{ borderLeft: '3px solid var(--success)' }}>
              <div className="kpi-header">
                SLA Compliance
                <TrendingUp size={16} className="text-success" />
              </div>
              <div className="kpi-value" style={{ color: 'var(--success)' }}>
                {summary.compliance_rate}%
              </div>
              <div className="kpi-footer">Target delivery &lt; 30m</div>
            </div>

            <div className="glass-panel kpi-card">
              <div className="kpi-header">
                Average Duration
                <Clock size={16} />
              </div>
              <div className="kpi-value">{summary.avg_duration_mins}m</div>
              <div className="kpi-footer">End-to-end average</div>
            </div>

            <div className="glass-panel kpi-card" style={{ borderLeft: '3px solid var(--danger)' }}>
              <div className="kpi-header">
                DQ Anomaly Alerts
                <AlertTriangle size={16} className="text-danger" />
              </div>
              <div className="kpi-value" style={{ color: summary.dq_fail_count > 0 ? 'var(--danger)' : 'white' }}>
                {summary.dq_fail_count}
              </div>
              <div className="kpi-footer">Quarantined records</div>
            </div>
          </div>

          {/* DELAY STAGE BOTTLE-NECK COMPARISON CHART (Optimized) */}
          <div className="glass-panel card-content" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h2 className="section-title" style={{ marginBottom: '4px' }}>
              <Clock size={18} />
              Stage-by-Stage SLA Bottleneck Auditor (Actuals vs Targets)
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', alignItems: 'center' }}>
              
              {/* Text values */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', justify_content: 'space-between', justifyContent: 'space-between' }}>
                  <span className="text-secondary">Rider Dispatch:</span>
                  <span style={{ fontWeight: 'bold' }}>{summary.avg_dispatch_mins}m <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>/ 5.0m</span></span>
                </div>
                <div style={{ display: 'flex', justify_content: 'space-between', justifyContent: 'space-between' }}>
                  <span className="text-secondary">Kitchen Prep:</span>
                  <span style={{ fontWeight: 'bold' }}>{summary.avg_prep_mins}m <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>/ 15.0m</span></span>
                </div>
                <div style={{ display: 'flex', justify_content: 'space-between', justifyContent: 'space-between' }}>
                  <span className="text-secondary">Rider Transit:</span>
                  <span style={{ fontWeight: 'bold' }}>{summary.avg_transit_mins}m <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>/ 15.0m</span></span>
                </div>
              </div>

              {/* Horizontal comparison chart */}
              <div style={{ width: '100%', height: 110 }}>
                <ResponsiveContainer>
                  <BarChart data={delayStageData} layout="vertical" margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                    <XAxis type="number" stroke="var(--text-muted)" fontSize={9} />
                    <YAxis dataKey="name" type="category" stroke="var(--text-muted)" fontSize={9} width={90} />
                    <Tooltip contentStyle={{ background: '#12161e', borderColor: 'var(--border-color)', color: 'white' }} />
                    <Legend wrapperStyle={{ fontSize: '10px' }} />
                    <Bar dataKey="Actual" name="Actual Duration" fill="var(--primary)" barSize={8} />
                    <Bar dataKey="Target" name="SLA Threshold" fill="rgba(255,255,255,0.15)" barSize={4} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

            </div>
          </div>
        </div>

        {/* COMPLIANCE TRENDS CHART */}
        <div className="glass-panel grid-item-8 card-content">
          <h2 className="section-title">
            <TrendingUp size={18} />
            Hourly SLA Compliance Trends (%)
          </h2>
          <div style={{ width: '100%', height: 260 }}>
            {trends.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                Waiting for ETL warehouse runs...
              </div>
            ) : (
              <ResponsiveContainer>
                <LineChart data={trends} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="time_label" stroke="var(--text-muted)" fontSize={11} />
                  <YAxis stroke="var(--text-muted)" domain={[0, 100]} fontSize={11} />
                  <Tooltip contentStyle={{ background: '#12161e', borderColor: 'var(--border-color)', color: 'white' }} />
                  <Legend />
                  <Line 
                    type="monotone" 
                    dataKey="compliance_rate" 
                    name="Compliance %" 
                    stroke="var(--primary)" 
                    strokeWidth={3}
                    activeDot={{ r: 8 }} 
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* BREACH BREAKDOWN CHART */}
        <div className="glass-panel grid-item-4 card-content">
          <h2 className="section-title">
            <AlertTriangle size={18} />
            SLA Breach Root-Causes
          </h2>
          <div style={{ width: '100%', height: 260, display: 'flex', flexDirection: 'column' }}>
            {breaches.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                No active breaches recorded in the warehouse.
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={breaches} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="category" stroke="var(--text-muted)" fontSize={8} interval={0} />
                    <YAxis stroke="var(--text-muted)" fontSize={11} />
                    <Tooltip contentStyle={{ background: '#12161e', borderColor: 'var(--border-color)', color: 'white' }} />
                    <Bar dataKey="breach_count" name="Breach Count">
                      {breaches.map((entry, index) => (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={COLORS[entry.category] || COLORS['Rider Dispatch Delay']} 
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ fontSize: '0.72rem', display: 'flex', flexDirection: 'column', gap: '4px', overflowY: 'auto', maxHeight: '75px', marginTop: '10px' }}>
                  {breaches.map((b, idx) => (
                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: COLORS[b.category] || '#ccc' }}></span>
                        {b.category}
                      </span>
                      <span style={{ fontWeight: 'bold' }}>{b.breach_count}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* DYNAMIC OPERATIONAL RECOMMENDATIONS (Optimized Insights) */}
        <div className="glass-panel grid-item-4 card-content" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h2 className="section-title">
            <Sparkles size={18} className="text-warning" />
            Actionable Recommendations
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1, overflowY: 'auto', maxHeight: '320px' }}>
            {recommendations.map((rec, i) => (
              <div 
                key={i} 
                className={`badge ${
                  rec.severity === 'SUCCESS' ? 'badge-success' : 
                  rec.severity === 'WARNING' ? 'badge-warning' : 'badge-danger'
                }`}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '6px', padding: '12px', width: '100%', borderLeftWidth: '3px' }}
              >
                <span style={{ fontWeight: 'bold', fontSize: '0.85rem', textTransform: 'uppercase' }}>
                  {rec.title}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-primary)', textAlign: 'left' }}>
                  {rec.recommendation}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 'bold', marginTop: '4px' }}>
                  ACTION: {rec.action}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* DATA QUALITY AUDIT LAYER (Optimized with Donut Chart) */}
        <div className="glass-panel grid-item-4 card-content" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h2 className="section-title">
            <ShieldCheck size={18} />
            Data Quality Audit Layer
          </h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', alignItems: 'center' }}>
            
            {/* DQ Donut Chart */}
            <div style={{ width: '100%', height: 110, display: 'flex', justifyContent: 'center' }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={dqPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={25}
                    outerRadius={40}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    <Cell fill="var(--success)" />
                    <Cell fill={failSum > 0 ? "var(--danger)" : "rgba(255,255,255,0.15)"} />
                  </Pie>
                  <Tooltip contentStyle={{ background: '#12161e', borderColor: 'var(--border-color)', color: 'white' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Passes stats */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-secondary">Passes:</span>
                <span style={{ color: 'var(--success)', fontWeight: 'bold' }}>{passSum} checks</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-secondary">Quarantined:</span>
                <span style={{ color: failSum > 0 ? 'var(--danger)' : 'var(--text-muted)', fontWeight: 'bold' }}>
                  {failSum} fails
                </span>
              </div>
            </div>

          </div>

          <div className="logs-ticker" style={{ height: '180px' }}>
            {dqReport.recent_failures && dqReport.recent_failures.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', display: 'flex', justifyContent: 'center', padding: '20px' }}>
                No active audit anomalies found. Data streams healthy!
              </div>
            ) : (
              dqReport.recent_failures.map((err, i) => (
                <div key={i} className="log-entry fail">
                  <div>
                    <span style={{ color: 'var(--danger)', fontWeight: 'bold' }}>[{err.rule_name}]</span> {err.order_id}: {err.error_message}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                    {new Date(err.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* RAW STREAMING LOGS */}
        <div className="glass-panel grid-item-4 card-content">
          <h2 className="section-title">
            <Terminal size={18} />
            Live Ingestion Logs (SQLite event_store)
          </h2>
          <div className="logs-ticker" style={{ height: '320px' }}>
            {events.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', display: 'flex', justifyContent: 'center', padding: '20px' }}>
                No active events. Start the simulator.
              </div>
            ) : (
              events.map((ev, i) => (
                <div key={i} className="log-entry">
                  <div>
                    <span style={{ color: 'var(--info)' }}>[{ev.event_type}]</span> {ev.order_id} 
                    <span style={{ color: 'var(--text-muted)', marginLeft: '10px' }}>
                      (Load: {ev.order_volume})
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {new Date(ev.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* STAR SCHEMA WAREHOUSE RECORDS */}
        <div className="glass-panel grid-item-12 card-content">
          <h2 className="section-title">
            <Database size={18} />
            OLAP Data Warehouse - Star Schema (fact_orders)
          </h2>
          <div className="table-wrapper" style={{ maxHeight: '400px', overflowY: 'auto' }}>
            {orders.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '30px' }}>
                Warehouse currently empty. Generating events and waiting for scheduled auto-sync...
              </div>
            ) : (
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Order Key</th>
                    <th>Customer</th>
                    <th>Restaurant</th>
                    <th>Rider</th>
                    <th>Placement Time</th>
                    <th>Actual (mins)</th>
                    <th>DQ Audit</th>
                    <th>SLA Status</th>
                    <th>Attributed Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((ord, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{ord.order_id}</td>
                      <td>{ord.customer}</td>
                      <td>{ord.restaurant}</td>
                      <td>{ord.rider}</td>
                      <td>{new Date(ord.placement_time).toLocaleString()}</td>
                      <td style={{ fontWeight: 'bold' }}>{ord.duration}m</td>
                      <td>
                        <span className={`badge ${ord.dq_status === 'PASS' ? 'badge-success' : 'badge-danger'}`} style={{ padding: '2px 8px', fontSize: '0.7rem' }}>
                          {ord.dq_status}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${ord.is_breached ? 'badge-danger' : 'badge-success'}`} style={{ padding: '2px 8px', fontSize: '0.7rem' }}>
                          {ord.is_breached ? 'BREACHED' : 'MET SLA'}
                        </span>
                      </td>
                      <td>
                        <span 
                          className="badge" 
                          style={{ 
                            padding: '2px 8px', 
                            fontSize: '0.7rem',
                            backgroundColor: ord.is_breached ? `${COLORS[ord.breach_reason] || COLORS['Rider Dispatch Delay']}20` : 'rgba(255,255,255,0.05)',
                            color: ord.is_breached ? COLORS[ord.breach_reason] || '#fff' : 'var(--text-secondary)',
                            borderColor: ord.is_breached ? `${COLORS[ord.breach_reason] || COLORS['Rider Dispatch Delay']}40` : 'rgba(255,255,255,0.1)'
                          }}
                        >
                          {ord.is_breached ? ord.breach_reason : 'No Breach'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
