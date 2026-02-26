import { useState, useEffect, useRef, useCallback } from "react";
import { LineChart, Line, AreaChart, Area, RadialBarChart, RadialBar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

// ─── Config ────────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:5000/api";
const WS_URL   = "http://localhost:5000";

// Simulated data for demo (replace with real WebSocket when backend is running)
const generateSensorData = (scenario = 'normal') => {
  const base = {
    normal:   { mq2: 80 + Math.random()*60,  mq135: 50+Math.random()*40,  temp: 26+Math.random()*4,  hum: 45+Math.random()*10, vib: 0.1+Math.random()*0.2, tilt: 0.5+Math.random()*0.5 },
    warning:  { mq2: 350+Math.random()*100, mq135: 180+Math.random()*60, temp: 40+Math.random()*8,  hum: 65+Math.random()*10, vib: 1.2+Math.random()*0.5, tilt: 2.5+Math.random()*1   },
    critical: { mq2: 800+Math.random()*200, mq135: 320+Math.random()*80, temp: 58+Math.random()*12, hum: 82+Math.random()*12, vib: 3.5+Math.random()*1.5, tilt: 7.0+Math.random()*3   },
  };
  const d = base[scenario];
  return { ...d, liquid_level: 35+Math.random()*20, flame: scenario==='critical' && Math.random()>0.7, sound: 55+Math.random()*20 };
};

const computeRisk = (d) => {
  const norm = (v, s, w, c) => Math.min(1, v < s ? v/s*0.4 : v < w ? 0.4+(v-s)/(w-s)*0.3 : v < c ? 0.7+(v-w)/(c-w)*0.2 : 0.95);
  let score = 0;
  score += 0.25 * norm(d.mq2, 200, 500, 1000);
  score += 0.20 * norm(d.mq135, 100, 200, 400);
  score += 0.10 * norm(d.temp, 35, 50, 70);
  score += 0.08 * norm(d.hum, 60, 80, 95);
  score += 0.07 * norm(d.vib, 0.5, 2, 5);
  score += 0.05 * norm(d.tilt, 2, 5, 10);
  score += 0.20 * (d.flame ? 1 : 0);
  if (d.flame && d.mq2 > 100) score = Math.min(1, score * 1.5);
  return Math.round(score * 100 * 10) / 10;
};

const ZONES_INIT = [
  { zone_id: 'zone_01', name: 'Chemical Storage A', type: 'CHEMICAL', workers: 2 },
  { zone_id: 'zone_02', name: 'Sewage Pit B',        type: 'SEWAGE',   workers: 1 },
  { zone_id: 'zone_03', name: 'Boiler Room C',       type: 'BOILER',   workers: 3 },
  { zone_id: 'zone_04', name: 'Confined Tank D',     type: 'CONFINED', workers: 0 },
];

const WORKERS = [
  { id:1, name:'Rajan Kumar',  role:'Safety Officer', rfid:'A1B2C3D4', inside:true,  zone:'zone_01' },
  { id:2, name:'Priya Sharma', role:'Technician',     rfid:'E5F6G7H8', inside:true,  zone:'zone_03' },
  { id:3, name:'Suresh Patel', role:'Supervisor',     rfid:'I9J0K1L2', inside:false, zone:null       },
  { id:4, name:'Kavitha Raj',  role:'Inspector',      rfid:'M3N4O5P6', inside:true,  zone:'zone_03' },
];

// ─── Styling Constants ─────────────────────────────────────────────────────────
const COLORS = {
  safe:     '#00f5a0',
  warning:  '#ffb347',
  critical: '#ff4444',
  bg:       '#080c14',
  surface:  '#0d1421',
  surface2: '#111827',
  border:   '#1e2d45',
  text:     '#e2e8f0',
  muted:    '#64748b',
  accent:   '#00d4ff',
  purple:   '#7c3aed',
};

const STATUS_COLOR = { SAFE: COLORS.safe, WARNING: COLORS.warning, CRITICAL: COLORS.critical };
const ZONE_ICONS = { CHEMICAL: '⚗️', SEWAGE: '🚰', BOILER: '🔥', CONFINED: '⬛', FACTORY: '🏭' };

// ─── Sub-components ────────────────────────────────────────────────────────────

function RiskGauge({ score }) {
  const radius = 70;
  const stroke = 12;
  const normalizedRadius = radius - stroke / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const progress = circumference - (score / 100) * circumference;
  const color = score < 40 ? COLORS.safe : score < 70 ? COLORS.warning : COLORS.critical;
  const glowId = `glow-${Math.random().toString(36).slice(2)}`;

  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', position:'relative' }}>
      <svg height={radius*2+20} width={radius*2+20} style={{ overflow:'visible' }}>
        <defs>
          <filter id={glowId}>
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>
        {/* Background arc */}
        <circle cx={radius+10} cy={radius+10} r={normalizedRadius} fill="none"
          stroke={COLORS.border} strokeWidth={stroke} />
        {/* Progress arc */}
        <circle cx={radius+10} cy={radius+10} r={normalizedRadius} fill="none"
          stroke={color} strokeWidth={stroke}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={progress}
          strokeLinecap="round"
          style={{ transform:`rotate(-90deg)`, transformOrigin:`${radius+10}px ${radius+10}px`, transition:'all 0.5s ease', filter:`url(#${glowId})` }} />
        {/* Center text */}
        <text x={radius+10} y={radius+10} textAnchor="middle" dominantBaseline="middle"
          fill={color} fontSize="28" fontWeight="800" fontFamily="'Courier New', monospace">
          {Math.round(score)}
        </text>
        <text x={radius+10} y={radius+30} textAnchor="middle"
          fill={COLORS.muted} fontSize="11" fontFamily="monospace">
          /100
        </text>
      </svg>
    </div>
  );
}

function SensorBar({ label, value, max, unit, color }) {
  const pct = Math.min(100, (value / max) * 100);
  const barColor = pct < 40 ? COLORS.safe : pct < 70 ? COLORS.warning : COLORS.critical;
  return (
    <div style={{ marginBottom:10 }}>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:COLORS.muted, marginBottom:3, fontFamily:'monospace' }}>
        <span>{label}</span>
        <span style={{ color:COLORS.text }}>{typeof value === 'number' ? value.toFixed(1) : value} {unit}</span>
      </div>
      <div style={{ height:5, background:COLORS.border, borderRadius:3, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${pct}%`, background:barColor, borderRadius:3,
          transition:'width 0.6s ease', boxShadow:`0 0 6px ${barColor}` }} />
      </div>
    </div>
  );
}

function AlertBadge({ count, severity }) {
  if (!count) return null;
  const c = severity === 'CRITICAL' ? COLORS.critical : COLORS.warning;
  return (
    <span style={{ background:c+'22', color:c, border:`1px solid ${c}`, borderRadius:12,
      padding:'2px 8px', fontSize:11, fontWeight:700, fontFamily:'monospace' }}>
      {count} {severity}
    </span>
  );
}

function WorkerBadge({ worker }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 12px',
      background:COLORS.surface2, borderRadius:8, border:`1px solid ${COLORS.border}`,
      fontSize:12 }}>
      <div style={{ width:32, height:32, borderRadius:'50%', background:COLORS.purple+'33',
        display:'flex', alignItems:'center', justifyContent:'center', fontSize:14,
        border:`2px solid ${worker.inside ? COLORS.safe : COLORS.border}` }}>
        👷
      </div>
      <div>
        <div style={{ color:COLORS.text, fontWeight:600 }}>{worker.name}</div>
        <div style={{ color:COLORS.muted }}>{worker.role}</div>
      </div>
      <div style={{ marginLeft:'auto', display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4 }}>
        <span style={{ color: worker.inside ? COLORS.safe : COLORS.muted, fontSize:10, fontWeight:700 }}>
          {worker.inside ? '● INSIDE' : '○ OUTSIDE'}
        </span>
        {worker.inside && <span style={{ color:COLORS.muted, fontSize:10 }}>{worker.zone}</span>}
      </div>
    </div>
  );
}

// ─── Main Dashboard ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [activeZone, setActiveZone]     = useState('zone_01');
  const [zoneData, setZoneData]         = useState({});
  const [chartHistory, setChartHistory] = useState([]);
  const [alerts, setAlerts]             = useState([]);
  const [simScenario, setSimScenario]   = useState('normal');
  const [activeTab, setActiveTab]       = useState('dashboard');
  const [lastUpdate, setLastUpdate]     = useState(new Date());
  const [rfidInput, setRfidInput]       = useState('');
  const [rfidResult, setRfidResult]     = useState(null);
  const historyRef = useRef({});

  // Simulate real-time sensor data
  const updateSensors = useCallback(() => {
    const newZoneData = {};
    ZONES_INIT.forEach((zone, idx) => {
      const scenario = idx === 0 ? simScenario : ['normal','normal','warning','normal'][idx];
      const sensors  = generateSensorData(scenario);
      const risk     = computeRisk(sensors);
      const status   = risk < 40 ? 'SAFE' : risk < 70 ? 'WARNING' : 'CRITICAL';
      newZoneData[zone.zone_id] = { ...zone, sensors, risk, status };

      // Create alerts for critical zones
      if (risk >= 70 && Math.random() > 0.7) {
        const newAlert = {
          id: Date.now() + idx,
          zone_id: zone.zone_id,
          zone_name: zone.name,
          type: sensors.flame ? 'FIRE' : 'GAS',
          severity: risk >= 85 ? 'CRITICAL' : 'HIGH',
          message: sensors.flame
            ? `Flame detected in ${zone.name}!`
            : `Gas levels critical in ${zone.name}. MQ2: ${sensors.mq2.toFixed(0)} ppm`,
          time: new Date().toLocaleTimeString(),
          risk,
        };
        setAlerts(prev => [newAlert, ...prev.slice(0, 19)]);
      }
    });
    setZoneData(newZoneData);

    // Update chart history for active zone
    setChartHistory(prev => {
      const d = newZoneData[activeZone];
      if (!d) return prev;
      const newPoint = {
        time: new Date().toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit', second:'2-digit' }),
        risk: d.risk,
        mq2: Math.round(d.sensors.mq2),
        mq135: Math.round(d.sensors.mq135),
        temp: d.sensors.temp,
      };
      return [...prev.slice(-30), newPoint];
    });
    setLastUpdate(new Date());
  }, [simScenario, activeZone]);

  useEffect(() => {
    updateSensors();
    const interval = setInterval(updateSensors, 3000);
    return () => clearInterval(interval);
  }, [updateSensors]);

  const handleRFIDScan = () => {
    const uid = rfidInput.toUpperCase();
    const worker = WORKERS.find(w => w.rfid === uid);
    const zone = zoneData[activeZone];
    if (!worker) {
      setRfidResult({ success: false, message: 'Unknown worker. Access denied.', color: COLORS.critical });
      return;
    }
    if (zone && zone.risk >= 70) {
      setRfidResult({
        success: false,
        message: `Access DENIED for ${worker.name}. Zone unsafe! Risk: ${zone.risk}/100`,
        color: COLORS.critical
      });
    } else {
      setRfidResult({
        success: true,
        message: `Access GRANTED to ${worker.name} (${worker.role})`,
        color: COLORS.safe
      });
    }
    setTimeout(() => setRfidResult(null), 4000);
    setRfidInput('');
  };

  const activeZoneData = zoneData[activeZone];
  const totalWorkers = WORKERS.filter(w => w.inside).length;
  const criticalZones = Object.values(zoneData).filter(z => z.status === 'CRITICAL').length;
  const warningZones = Object.values(zoneData).filter(z => z.status === 'WARNING').length;

  const styles = {
    app: {
      minHeight: '100vh',
      background: COLORS.bg,
      color: COLORS.text,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
      fontSize: 13,
    },
    header: {
      background: COLORS.surface,
      borderBottom: `1px solid ${COLORS.border}`,
      padding: '12px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    },
    logo: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
    },
    logoIcon: {
      width: 40, height: 40,
      background: `linear-gradient(135deg, ${COLORS.accent}33, ${COLORS.purple}33)`,
      border: `1px solid ${COLORS.accent}`,
      borderRadius: 10,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 20,
    },
    logoText: { fontSize: 16, fontWeight: 800, color: COLORS.accent, letterSpacing: 1 },
    logoDesc: { fontSize: 10, color: COLORS.muted },
    statusDot: (status) => ({
      width: 8, height: 8, borderRadius: '50%',
      background: STATUS_COLOR[status] || COLORS.muted,
      boxShadow: `0 0 6px ${STATUS_COLOR[status] || COLORS.muted}`,
      display: 'inline-block',
    }),
    card: {
      background: COLORS.surface,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 12,
      padding: 16,
    },
    tab: (active) => ({
      padding: '6px 16px',
      borderRadius: 8,
      border: 'none',
      cursor: 'pointer',
      fontSize: 12,
      fontFamily: 'monospace',
      fontWeight: 600,
      background: active ? COLORS.accent+'22' : 'transparent',
      color: active ? COLORS.accent : COLORS.muted,
      borderBottom: active ? `2px solid ${COLORS.accent}` : '2px solid transparent',
    }),
  };

  return (
    <div style={styles.app}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>🏭</div>
          <div>
            <div style={styles.logoText}>AI-MSIHPS</div>
            <div style={styles.logoDesc}>Multi-Sensor Industrial Hazard Prediction System</div>
          </div>
        </div>

        <div style={{ display:'flex', gap:8 }}>
          {['dashboard','zones','workers','alerts','simulate'].map(tab => (
            <button key={tab} style={styles.tab(activeTab===tab)} onClick={() => setActiveTab(tab)}>
              {tab.toUpperCase()}
            </button>
          ))}
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:16, fontSize:11, color:COLORS.muted }}>
          <span>🕐 {lastUpdate.toLocaleTimeString()}</span>
          <span style={{ color:COLORS.safe }}>● LIVE</span>
        </div>
      </header>

      {/* Stats Bar */}
      <div style={{ background:COLORS.surface2, borderBottom:`1px solid ${COLORS.border}`,
        padding:'8px 24px', display:'flex', gap:32 }}>
        {[
          { label:'TOTAL ZONES', value:ZONES_INIT.length, color:COLORS.accent },
          { label:'CRITICAL',    value:criticalZones,      color:COLORS.critical },
          { label:'WARNING',     value:warningZones,       color:COLORS.warning },
          { label:'WORKERS IN',  value:totalWorkers,       color:COLORS.safe },
          { label:'ACTIVE ALERTS', value:alerts.length,   color:COLORS.warning },
        ].map(s => (
          <div key={s.label}>
            <div style={{ fontSize:9, color:COLORS.muted, letterSpacing:1 }}>{s.label}</div>
            <div style={{ fontSize:22, fontWeight:800, color:s.color }}>{s.value}</div>
          </div>
        ))}

        <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontSize:11, color:COLORS.muted }}>SCENARIO:</span>
          {['normal','warning','critical'].map(s => (
            <button key={s} onClick={() => setSimScenario(s)}
              style={{ padding:'4px 10px', borderRadius:6, border:'none', cursor:'pointer',
                fontSize:11, fontFamily:'monospace', fontWeight:600,
                background: simScenario===s ? STATUS_COLOR[s.toUpperCase()]+'33' : COLORS.surface,
                color: simScenario===s ? STATUS_COLOR[s.toUpperCase()] : COLORS.muted }}>
              {s.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding:24 }}>

        {/* ─── DASHBOARD TAB ─── */}
        {activeTab === 'dashboard' && (
          <div>
            {/* Zone Cards */}
            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:20 }}>
              {ZONES_INIT.map(zone => {
                const zd = zoneData[zone.zone_id];
                const risk = zd?.risk || 0;
                const status = zd?.status || 'SAFE';
                const color = STATUS_COLOR[status];
                return (
                  <div key={zone.zone_id}
                    onClick={() => setActiveZone(zone.zone_id)}
                    style={{ ...styles.card, cursor:'pointer',
                      border:`1px solid ${activeZone === zone.zone_id ? color : COLORS.border}`,
                      borderTop:`3px solid ${color}`,
                      boxShadow: activeZone===zone.zone_id ? `0 0 20px ${color}22` : 'none' }}>
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                      <div>
                        <div style={{ fontSize:18, marginBottom:4 }}>{ZONE_ICONS[zone.type]}</div>
                        <div style={{ fontWeight:700, marginBottom:2 }}>{zone.name}</div>
                        <div style={{ fontSize:10, color:COLORS.muted }}>{zone.type}</div>
                      </div>
                      <div style={{ textAlign:'right' }}>
                        <div style={{ fontSize:28, fontWeight:800, color, lineHeight:1 }}>{Math.round(risk)}</div>
                        <div style={{ fontSize:9, color:COLORS.muted }}>RISK</div>
                      </div>
                    </div>
                    <div style={{ marginTop:10, display:'flex', justifyContent:'space-between', fontSize:10 }}>
                      <span style={{ ...styles.statusDot(status) }} /> {' '}
                      <span style={{ color }}>{status}</span>
                      <span style={{ color:COLORS.muted }}>👷 {zone.workers}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Main content: Selected zone detail */}
            {activeZoneData && (
              <div style={{ display:'grid', gridTemplateColumns:'300px 1fr 280px', gap:16 }}>

                {/* Left: Risk gauge + sensor breakdown */}
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  <div style={{ ...styles.card, textAlign:'center' }}>
                    <div style={{ fontSize:11, color:COLORS.muted, marginBottom:8, letterSpacing:2 }}>
                      RISK SCORE — {activeZoneData.name}
                    </div>
                    <RiskGauge score={activeZoneData.risk} />
                    <div style={{ marginTop:8, padding:'6px 12px', borderRadius:8,
                      background: STATUS_COLOR[activeZoneData.status]+'22',
                      color: STATUS_COLOR[activeZoneData.status], fontSize:12, fontWeight:700 }}>
                      {activeZoneData.status}
                      {activeZoneData.risk >= 70 && ' — ENTRY DENIED'}
                    </div>
                  </div>

                  <div style={styles.card}>
                    <div style={{ fontSize:10, color:COLORS.muted, letterSpacing:2, marginBottom:12 }}>SENSOR READINGS</div>
                    <SensorBar label="Methane/LPG (MQ2)"  value={activeZoneData.sensors.mq2}   max={1000} unit="ppm" />
                    <SensorBar label="Toxic Gas (MQ135)"  value={activeZoneData.sensors.mq135} max={400}  unit="ppm" />
                    <SensorBar label="Temperature"         value={activeZoneData.sensors.temp}  max={70}   unit="°C"  />
                    <SensorBar label="Humidity"            value={activeZoneData.sensors.hum}   max={95}   unit="%"   />
                    <SensorBar label="Vibration"           value={activeZoneData.sensors.vib}   max={5}    unit="Hz"  />
                    <SensorBar label="Tilt Angle"          value={activeZoneData.sensors.tilt}  max={10}   unit="°"   />
                    <div style={{ marginTop:12, padding:'8px', borderRadius:8,
                      background: activeZoneData.sensors.flame ? COLORS.critical+'22' : COLORS.surface2,
                      border:`1px solid ${activeZoneData.sensors.flame ? COLORS.critical : COLORS.border}` }}>
                      <span style={{ fontSize:10, color: activeZoneData.sensors.flame ? COLORS.critical : COLORS.muted }}>
                        {activeZoneData.sensors.flame ? '🔴 FLAME DETECTED!' : '⚫ No Flame'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Center: Chart */}
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  <div style={styles.card}>
                    <div style={{ fontSize:10, color:COLORS.muted, letterSpacing:2, marginBottom:12 }}>
                      REAL-TIME RISK TREND — {activeZoneData.name}
                    </div>
                    <ResponsiveContainer width="100%" height={180}>
                      <AreaChart data={chartHistory} margin={{ left:-20 }}>
                        <defs>
                          <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={STATUS_COLOR[activeZoneData.status]} stopOpacity={0.3}/>
                            <stop offset="95%" stopColor={STATUS_COLOR[activeZoneData.status]} stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} />
                        <XAxis dataKey="time" tick={{ fill:COLORS.muted, fontSize:9 }} />
                        <YAxis domain={[0,100]} tick={{ fill:COLORS.muted, fontSize:9 }} />
                        <Tooltip contentStyle={{ background:COLORS.surface, border:`1px solid ${COLORS.border}`, fontSize:11 }} />
                        <Area type="monotone" dataKey="risk" stroke={STATUS_COLOR[activeZoneData.status]}
                          fill="url(#riskGrad)" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="risk" stroke={STATUS_COLOR[activeZoneData.status]}
                          strokeWidth={2} dot={false} />
                        {/* Danger threshold line */}
                        <CartesianGrid y={70} stroke={COLORS.critical} strokeDasharray="5 5" strokeOpacity={0.5} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>

                  <div style={styles.card}>
                    <div style={{ fontSize:10, color:COLORS.muted, letterSpacing:2, marginBottom:12 }}>GAS CONCENTRATION TREND</div>
                    <ResponsiveContainer width="100%" height={160}>
                      <LineChart data={chartHistory} margin={{ left:-20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} />
                        <XAxis dataKey="time" tick={{ fill:COLORS.muted, fontSize:9 }} />
                        <YAxis tick={{ fill:COLORS.muted, fontSize:9 }} />
                        <Tooltip contentStyle={{ background:COLORS.surface, border:`1px solid ${COLORS.border}`, fontSize:11 }} />
                        <Legend wrapperStyle={{ fontSize:10 }} />
                        <Line type="monotone" dataKey="mq2"   stroke={COLORS.warning} strokeWidth={2} dot={false} name="MQ2 (ppm)" />
                        <Line type="monotone" dataKey="mq135" stroke={COLORS.critical} strokeWidth={2} dot={false} name="MQ135 (ppm)" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Right: RFID + Info */}
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  {/* RFID Scanner */}
                  <div style={styles.card}>
                    <div style={{ fontSize:10, color:COLORS.muted, letterSpacing:2, marginBottom:12 }}>RFID ACCESS CONTROL</div>
                    <div style={{ fontSize:10, color:COLORS.muted, marginBottom:8 }}>Zone: {activeZoneData.name}</div>
                    <div style={{ fontSize:10, color:COLORS.muted, marginBottom:6 }}>Entry will be {activeZoneData.risk >= 70 ? 'DENIED ⛔' : 'ALLOWED ✅'} (Risk: {Math.round(activeZoneData.risk)}/100)</div>
                    <input
                      value={rfidInput}
                      onChange={e => setRfidInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleRFIDScan()}
                      placeholder="Scan RFID / Enter UID..."
                      style={{ width:'100%', padding:'8px 10px', borderRadius:8, fontSize:12,
                        background:COLORS.surface2, border:`1px solid ${COLORS.border}`,
                        color:COLORS.text, fontFamily:'monospace', boxSizing:'border-box', marginBottom:8 }} />
                    <button onClick={handleRFIDScan}
                      style={{ width:'100%', padding:'8px', borderRadius:8, border:'none', cursor:'pointer',
                        background:COLORS.accent, color:COLORS.bg, fontFamily:'monospace',
                        fontWeight:700, fontSize:12 }}>
                      CHECK ACCESS
                    </button>
                    {rfidResult && (
                      <div style={{ marginTop:10, padding:'10px', borderRadius:8, fontSize:11,
                        background:rfidResult.color+'22', border:`1px solid ${rfidResult.color}`,
                        color:rfidResult.color, fontWeight:600 }}>
                        {rfidResult.message}
                      </div>
                    )}
                    <div style={{ marginTop:10, fontSize:10, color:COLORS.muted }}>
                      <div style={{ marginBottom:4 }}>Sample UIDs to test:</div>
                      {WORKERS.map(w => (
                        <div key={w.id} style={{ display:'flex', justifyContent:'space-between', marginBottom:2 }}>
                          <span>{w.name.split(' ')[0]}</span>
                          <span style={{ color:COLORS.accent, cursor:'pointer' }}
                            onClick={() => setRfidInput(w.rfid)}>{w.rfid}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* AI Recommendation */}
                  <div style={{ ...styles.card, border:`1px solid ${STATUS_COLOR[activeZoneData.status]}55` }}>
                    <div style={{ fontSize:10, color:COLORS.muted, letterSpacing:2, marginBottom:8 }}>AI RECOMMENDATION</div>
                    <div style={{ fontSize:11, color: STATUS_COLOR[activeZoneData.status], lineHeight:1.6 }}>
                      {activeZoneData.risk >= 85 ? '🔴 IMMEDIATE EVACUATION — Critical levels detected across multiple sensors.'
                       : activeZoneData.risk >= 70 ? '🟠 EVACUATE — Unsafe conditions. Block entry. Activate ventilation.'
                       : activeZoneData.risk >= 55 ? '🟡 WARNING — Limit exposure. Alert supervisor. Monitor continuously.'
                       : activeZoneData.risk >= 40 ? '🟡 CAUTION — Borderline readings. Increase monitoring frequency.'
                       : '🟢 SAFE — Normal conditions. Standard monitoring protocol active.'}
                    </div>
                    <div style={{ marginTop:10, fontSize:10, color:COLORS.muted }}>
                      Prediction: {activeZoneData.risk < 40
                        ? 'No risk detected in next 60 min'
                        : `Conditions may worsen in ~${Math.round(60 - activeZoneData.risk * 0.5)} min`}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── WORKERS TAB ─── */}
        {activeTab === 'workers' && (
          <div style={{ maxWidth:700 }}>
            <div style={{ fontSize:14, fontWeight:700, marginBottom:16, color:COLORS.accent }}>
              WORKER STATUS — {totalWorkers} INSIDE HAZARD ZONES
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {WORKERS.map(w => <WorkerBadge key={w.id} worker={w} />)}
            </div>
          </div>
        )}

        {/* ─── ALERTS TAB ─── */}
        {activeTab === 'alerts' && (
          <div style={{ maxWidth:800 }}>
            <div style={{ fontSize:14, fontWeight:700, marginBottom:16, color:COLORS.accent }}>
              ACTIVE ALERTS — {alerts.length} TOTAL
            </div>
            {alerts.length === 0 && (
              <div style={{ ...styles.card, textAlign:'center', color:COLORS.muted, padding:40 }}>
                ✅ No active alerts. All zones nominal.
              </div>
            )}
            {alerts.map(alert => (
              <div key={alert.id} style={{ ...styles.card, marginBottom:8,
                borderLeft:`4px solid ${alert.severity==='CRITICAL' ? COLORS.critical : COLORS.warning}` }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                  <div>
                    <div style={{ fontWeight:700, color: alert.severity==='CRITICAL' ? COLORS.critical : COLORS.warning }}>
                      [{alert.severity}] {alert.type} — {alert.zone_name}
                    </div>
                    <div style={{ fontSize:11, color:COLORS.muted, marginTop:4 }}>{alert.message}</div>
                  </div>
                  <div style={{ textAlign:'right', fontSize:10, color:COLORS.muted }}>
                    <div>Risk: {Math.round(alert.risk)}/100</div>
                    <div>{alert.time}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ─── ZONES TAB ─── */}
        {activeTab === 'zones' && (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:16 }}>
            {ZONES_INIT.map(zone => {
              const zd = zoneData[zone.zone_id];
              if (!zd) return null;
              const color = STATUS_COLOR[zd.status];
              return (
                <div key={zone.zone_id} style={{ ...styles.card, borderTop:`3px solid ${color}` }}>
                  <div style={{ display:'flex', justifyContent:'space-between', marginBottom:12 }}>
                    <div>
                      <div style={{ fontSize:16 }}>{ZONE_ICONS[zone.type]} <b>{zone.name}</b></div>
                      <div style={{ fontSize:10, color:COLORS.muted }}>{zone.type} | {zone.workers} workers</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:32, fontWeight:800, color, lineHeight:1 }}>{Math.round(zd.risk)}</div>
                      <div style={{ fontSize:9, color }}>RISK / 100</div>
                    </div>
                  </div>
                  <SensorBar label="MQ2 Gas"     value={zd.sensors.mq2}   max={1000} unit="ppm" />
                  <SensorBar label="Toxic Gas"   value={zd.sensors.mq135} max={400}  unit="ppm" />
                  <SensorBar label="Temperature" value={zd.sensors.temp}  max={70}   unit="°C" />
                  <SensorBar label="Vibration"   value={zd.sensors.vib}   max={5}    unit="Hz" />
                </div>
              );
            })}
          </div>
        )}

        {/* ─── SIMULATE TAB ─── */}
        {activeTab === 'simulate' && (
          <div style={{ maxWidth:600 }}>
            <div style={{ fontSize:14, fontWeight:700, marginBottom:16, color:COLORS.accent }}>
              DEMO SIMULATION CONTROL
            </div>
            <div style={styles.card}>
              <div style={{ fontSize:11, color:COLORS.muted, marginBottom:16 }}>
                Use these controls to demonstrate different hazard scenarios to the judges.
                In production, this data comes from real ESP32 sensors via MQTT.
              </div>
              {['normal','warning','critical'].map(s => (
                <button key={s}
                  onClick={() => { setSimScenario(s); setActiveTab('dashboard'); }}
                  style={{ display:'block', width:'100%', padding:14, marginBottom:8,
                    borderRadius:10, border:`2px solid ${STATUS_COLOR[s.toUpperCase()] || COLORS.border}`,
                    cursor:'pointer', textAlign:'left', fontFamily:'monospace',
                    background: STATUS_COLOR[s.toUpperCase()]+'11', color:STATUS_COLOR[s.toUpperCase()] || COLORS.text,
                    fontWeight:700, fontSize:13 }}>
                  {s === 'normal'   && '🟢 NORMAL — All sensors in safe range. Risk < 40.'}
                  {s === 'warning'  && '🟡 WARNING — Gas levels elevated. Risk 40–70. Alert sent to supervisor.'}
                  {s === 'critical' && '🔴 CRITICAL — Multiple hazards. Risk > 70. Entry DENIED. Evacuation triggered.'}
                </button>
              ))}
              <div style={{ marginTop:16, padding:12, borderRadius:8, background:COLORS.surface2,
                fontSize:11, color:COLORS.muted, lineHeight:1.8 }}>
                <b style={{ color:COLORS.accent }}>System Flow:</b><br/>
                ESP32 → MQTT Broker → Flask Backend → AI Risk Engine → PostgreSQL → WebSocket → Dashboard<br/><br/>
                <b style={{ color:COLORS.accent }}>AI Models:</b><br/>
                • Random Forest Classifier (status: SAFE/WARNING/CRITICAL)<br/>
                • LSTM Predictor (time-to-danger: minutes)<br/>
                • Weighted Sensor Fusion (real-time score)<br/>
                • Z-score Anomaly Detector (sudden spikes)
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}