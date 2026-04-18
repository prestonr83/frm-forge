APP_CSS = """
<style>
body {
  background:
    radial-gradient(circle at top left, rgba(80, 214, 194, 0.16), transparent 35%),
    radial-gradient(circle at top right, rgba(255, 177, 77, 0.14), transparent 34%),
    linear-gradient(180deg, #0e1922 0%, #09121a 52%, #060b10 100%);
  color: #eff4f5;
}
.frm-shell {
  width: min(1520px, calc(100vw - 28px));
  margin: 18px auto 42px;
}
.frm-hero {
  border-radius: 30px;
  padding: 28px;
  border: 1px solid rgba(120, 183, 255, 0.14);
  background:
    radial-gradient(circle at 18% 18%, rgba(80, 214, 194, 0.22), transparent 26%),
    radial-gradient(circle at 88% 0%, rgba(255, 177, 77, 0.24), transparent 30%),
    linear-gradient(135deg, rgba(16, 38, 51, 0.98), rgba(10, 22, 30, 0.98));
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.35);
}
.frm-eyebrow {
  display: inline-flex;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #9ab1bb;
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.frm-title {
  margin: 14px 0 12px;
  font-size: clamp(2.4rem, 5vw, 4.4rem);
  line-height: 0.94;
  font-family: Bahnschrift, "Franklin Gothic Medium", "Trebuchet MS", sans-serif;
}
.frm-muted { color: #9ab1bb; }
.frm-stat-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}
.frm-stat {
  padding: 18px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.frm-stat-label {
  color: #69808a;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.frm-stat-value {
  margin-top: 10px;
  font-size: 2rem;
  font-weight: 700;
}
.frm-panel {
  border-radius: 24px;
  border: 1px solid rgba(121, 157, 173, 0.2);
  background: linear-gradient(180deg, rgba(18, 33, 44, 0.95), rgba(10, 20, 27, 0.95));
  box-shadow: 0 24px 72px rgba(0, 0, 0, 0.28);
}
.frm-card {
  border-radius: 20px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
}
.frm-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 0.82rem;
}
.frm-ok { background: rgba(169, 240, 108, 0.16); color: #d3ffc1; }
.frm-warn { background: rgba(255, 177, 77, 0.16); color: #ffe0b4; }
.frm-error { background: rgba(255, 107, 107, 0.16); color: #ffd8d8; }
.frm-info { background: rgba(120, 183, 255, 0.18); color: #d6ebff; }
.frm-chart svg { width: 100%; min-height: 220px; }
.frm-map svg { width: 100%; min-height: 620px; }
.frm-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}
.frm-metric {
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
}
.frm-metric-label {
  color: #69808a;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.frm-metric-value {
  display: block;
  margin-top: 8px;
  font-size: 1.2rem;
  font-weight: 700;
}
.frm-bar {
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
}
.frm-bar > span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #54dcc8, #78b7ff);
}
.frm-row {
  border-radius: 18px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.frm-caption { color: #9ab1bb; font-size: 0.9rem; }
.frm-grid-2 {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.75fr);
}
.frm-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.08);
  color: #9ab1bb;
  font-size: 0.82rem;
}
@media (max-width: 1180px) {
  .frm-grid-2 { grid-template-columns: 1fr; }
  .frm-map svg { min-height: 420px; }
}
</style>
"""
