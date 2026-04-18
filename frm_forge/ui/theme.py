APP_CSS = """
<style>
:root {
  --ctp-rosewater: #f5e0dc;
  --ctp-flamingo: #f2cdcd;
  --ctp-pink: #f5c2e7;
  --ctp-mauve: #cba6f7;
  --ctp-red: #f38ba8;
  --ctp-maroon: #eba0ac;
  --ctp-peach: #fab387;
  --ctp-yellow: #f9e2af;
  --ctp-green: #a6e3a1;
  --ctp-teal: #94e2d5;
  --ctp-sky: #89dceb;
  --ctp-sapphire: #74c7ec;
  --ctp-blue: #89b4fa;
  --ctp-lavender: #b4befe;
  --ctp-text: #cdd6f4;
  --ctp-subtext1: #bac2de;
  --ctp-subtext0: #a6adc8;
  --ctp-overlay2: #9399b2;
  --ctp-overlay1: #7f849c;
  --ctp-overlay0: #6c7086;
  --ctp-surface2: #585b70;
  --ctp-surface1: #45475a;
  --ctp-surface0: #313244;
  --ctp-base: #1e1e2e;
  --ctp-mantle: #181825;
  --ctp-crust: #11111b;
}

html,
body {
  background:
    radial-gradient(circle at top left, rgba(203, 166, 247, 0.16), transparent 30%),
    radial-gradient(circle at top right, rgba(250, 179, 135, 0.12), transparent 30%),
    linear-gradient(180deg, var(--ctp-crust) 0%, var(--ctp-mantle) 42%, #0b0d14 100%);
  color: var(--ctp-text);
}

body,
.nicegui-content,
.q-layout,
.q-page-container,
.q-page,
.q-card,
.q-panel,
.q-tab-panels,
.q-tab-panel {
  background: transparent !important;
  color: var(--ctp-text) !important;
}

.frm-shell {
  width: min(1520px, calc(100vw - 28px));
  margin: 18px auto 42px;
}

.frm-hero {
  border-radius: 30px;
  padding: 30px;
  border: 1px solid rgba(180, 190, 254, 0.18);
  background:
    radial-gradient(circle at 20% 16%, rgba(137, 180, 250, 0.14), transparent 28%),
    radial-gradient(circle at 88% 10%, rgba(250, 179, 135, 0.16), transparent 32%),
    linear-gradient(135deg, rgba(30, 30, 46, 0.98), rgba(17, 17, 27, 0.98));
  box-shadow: 0 28px 88px rgba(0, 0, 0, 0.36);
}

.frm-eyebrow {
  display: inline-flex;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(137, 180, 250, 0.18);
  background: rgba(49, 50, 68, 0.72);
  color: var(--ctp-subtext1);
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.frm-title {
  margin: 16px 0 12px;
  font-size: clamp(2.2rem, 4vw, 3.9rem);
  line-height: 0.95;
  letter-spacing: -0.03em;
  font-family: "Segoe UI Variable Display", Bahnschrift, "Trebuchet MS", sans-serif;
}

.frm-muted {
  color: var(--ctp-subtext0);
}

.frm-stat-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.frm-stat {
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(205, 214, 244, 0.08);
  background: linear-gradient(180deg, rgba(49, 50, 68, 0.9), rgba(30, 30, 46, 0.94));
}

.frm-stat-label,
.frm-metric-label {
  color: var(--ctp-overlay1);
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
  border: 1px solid rgba(180, 190, 254, 0.14);
  background: linear-gradient(180deg, rgba(49, 50, 68, 0.9), rgba(24, 24, 37, 0.96));
  box-shadow: 0 24px 72px rgba(0, 0, 0, 0.28);
}

.frm-card {
  border-radius: 20px;
  padding: 18px;
  border: 1px solid rgba(205, 214, 244, 0.08);
  background: linear-gradient(180deg, rgba(49, 50, 68, 0.92), rgba(30, 30, 46, 0.96));
}

.frm-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 0.82rem;
  border: 1px solid transparent;
}

.frm-ok {
  background: rgba(166, 227, 161, 0.16);
  border-color: rgba(166, 227, 161, 0.24);
  color: var(--ctp-green);
}

.frm-warn {
  background: rgba(249, 226, 175, 0.14);
  border-color: rgba(249, 226, 175, 0.24);
  color: var(--ctp-yellow);
}

.frm-error {
  background: rgba(243, 139, 168, 0.14);
  border-color: rgba(243, 139, 168, 0.24);
  color: var(--ctp-red);
}

.frm-info {
  background: rgba(137, 180, 250, 0.16);
  border-color: rgba(137, 180, 250, 0.24);
  color: var(--ctp-blue);
}

.frm-chart svg {
  display: block;
  width: 100%;
  min-height: 260px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(24, 24, 37, 0.96), rgba(17, 17, 27, 0.98));
}

.frm-map svg {
  display: block;
  width: 100%;
  min-height: 680px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(24, 24, 37, 0.98), rgba(17, 17, 27, 1));
}

.frm-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}

.frm-metric {
  padding: 12px;
  border-radius: 16px;
  background: rgba(17, 17, 27, 0.28);
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
  background: rgba(108, 112, 134, 0.28);
}

.frm-bar > span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--ctp-teal), var(--ctp-blue));
}

.frm-row {
  border-radius: 18px;
  padding: 14px;
  background: linear-gradient(180deg, rgba(49, 50, 68, 0.78), rgba(30, 30, 46, 0.82));
  border: 1px solid rgba(205, 214, 244, 0.08);
}

.frm-caption {
  color: var(--ctp-subtext0);
  font-size: 0.9rem;
}

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
  background: rgba(49, 50, 68, 0.78);
  border: 1px solid rgba(205, 214, 244, 0.08);
  color: var(--ctp-subtext1);
  font-size: 0.82rem;
}

.q-tabs {
  border-bottom: 1px solid rgba(205, 214, 244, 0.12);
}

.q-tab {
  color: var(--ctp-subtext0) !important;
}

.q-tab--active,
.q-tab.q-tab--active {
  color: var(--ctp-text) !important;
}

.q-tab__indicator {
  background: var(--ctp-blue) !important;
  height: 3px !important;
}

.q-btn {
  border-radius: 14px !important;
  background: linear-gradient(135deg, var(--ctp-blue), var(--ctp-sapphire)) !important;
  color: var(--ctp-crust) !important;
  font-weight: 700;
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.22);
}

.q-btn .q-focus-helper {
  display: none;
}

.q-field__control,
.q-field--filled .q-field__control {
  border-radius: 14px !important;
  background: rgba(49, 50, 68, 0.9) !important;
  color: var(--ctp-text) !important;
}

.q-field__native,
.q-field__input,
.q-field__label,
.q-field__marginal,
.q-select__dropdown-icon {
  color: var(--ctp-subtext1) !important;
}

.q-menu,
.q-list {
  background: var(--ctp-surface0) !important;
  color: var(--ctp-text) !important;
  border: 1px solid rgba(205, 214, 244, 0.1);
}

.q-item,
.q-item__label {
  color: var(--ctp-text) !important;
}

.q-separator {
  background: rgba(205, 214, 244, 0.1) !important;
}

.q-checkbox__label {
  color: var(--ctp-text) !important;
}

.q-checkbox__bg {
  border-color: var(--ctp-overlay0) !important;
  background: rgba(49, 50, 68, 0.92) !important;
  border-radius: 6px;
}

.q-checkbox[aria-checked="true"] .q-checkbox__bg {
  border-color: var(--ctp-blue) !important;
  background: var(--ctp-blue) !important;
}

.q-checkbox[aria-checked="true"] .q-checkbox__svg {
  color: var(--ctp-crust) !important;
}

@media (max-width: 1180px) {
  .frm-grid-2 {
    grid-template-columns: 1fr;
  }

  .frm-map svg {
    min-height: 460px;
  }
}
</style>
"""
