from pathlib import Path

paths = [
    Path("custom_components/anthbot_map/frontend/anthbot-map-card.js"),
    Path("www/anthbot-map/anthbot-map-card.js"),
]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


helper_methods = r'''
  parseRainHoldDetectedAt(value) {
    if (value === null || value === undefined) {
      return null;
    }
    const raw = String(value).trim();
    if (!raw) {
      return null;
    }
    const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`;
    const timestamp = Date.parse(normalized);
    return Number.isFinite(timestamp) ? timestamp : null;
  }

  rainHoldRemainingSeconds(rainHoldEntity) {
    if (rainHoldEntity?.state !== "on") {
      return null;
    }
    const duration = Number(rainHoldEntity.attributes?.rain_continue_time);
    const detectedAt = this.parseRainHoldDetectedAt(rainHoldEntity.attributes?.detected_at);
    if (!Number.isFinite(duration) || duration < 0 || detectedAt === null) {
      return null;
    }
    const endAt = detectedAt + duration * 1000;
    return Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
  }

  formatRainHoldCountdown(totalSeconds) {
    const total = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  updateRainHoldDisplay() {
    const rainHoldEntity = this.getRelatedEntity("rainHold");
    const active = rainHoldEntity?.state === "on";
    const remaining = this.rainHoldRemainingSeconds(rainHoldEntity);
    const rainHoldText = remaining === null
      ? this.translateStatus("rain_hold")
      : `${this.translateStatus("rain_hold")} · ${this.formatRainHoldCountdown(remaining)}`;
    this.shadowRoot?.querySelectorAll('[data-role="rain-hold-line"]').forEach((line) => {
      line.hidden = !active;
      line.textContent = active ? rainHoldText : "";
    });
  }

  startRainCountdownTimer() {
    if (this.rainCountdownTimer) {
      return;
    }
    this.rainCountdownTimer = window.setInterval(() => this.updateRainHoldDisplay(), 1000);
  }

  stopRainCountdownTimer() {
    if (this.rainCountdownTimer) {
      window.clearInterval(this.rainCountdownTimer);
      this.rainCountdownTimer = null;
    }
  }

'''

for path in paths:
    source = path.read_text(encoding="utf-8")

    source = replace_once(
        source,
        "    this.refreshTimer = null;\n    this.refreshInFlight = false;",
        "    this.refreshTimer = null;\n    this.rainCountdownTimer = null;\n    this.refreshInFlight = false;",
        f"{path}: constructor timer",
    )

    source = replace_once(
        source,
        "    this.startRefreshTimer();\n    if (previousLanguage !== this.language || customButtonsChanged) {",
        "    this.startRefreshTimer();\n    this.startRainCountdownTimer();\n    if (previousLanguage !== this.language || customButtonsChanged) {",
        f"{path}: hass timer start",
    )

    source = replace_once(
        source,
        "  disconnectedCallback() {\n    this.stopRefreshTimer();\n    window.clearTimeout(this.pendingRefreshTimer);",
        "  disconnectedCallback() {\n    this.stopRefreshTimer();\n    this.stopRainCountdownTimer();\n    window.clearTimeout(this.pendingRefreshTimer);",
        f"{path}: timer cleanup",
    )

    source = replace_once(
        source,
        '          .map-live-status [data-role="mower-status"] { display:block; max-width:230px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; line-height:1.15; }\n          .map-live-status .mowing-live-line { margin-top:3px; font-size:11px; }',
        '          .map-live-status [data-role="mower-status"] { display:block; max-width:230px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; line-height:1.15; }\n          .map-live-status .rain-hold-line { display:block; margin-top:3px; font-size:11px; font-weight:600; line-height:1.2; }\n          .map-live-status .rain-hold-line[hidden] { display:none; }\n          .map-live-status .mowing-live-line { margin-top:3px; font-size:11px; }',
        f"{path}: rain hold CSS",
    )

    source = replace_once(
        source,
        '              <strong data-role="mower-status">-</strong>\n              <span class="mowing-live-line" data-role="mowing-live-line" hidden>',
        '              <strong data-role="mower-status">-</strong>\n              <span class="rain-hold-line" data-role="rain-hold-line" hidden></span>\n              <span class="mowing-live-line" data-role="mowing-live-line" hidden>',
        f"{path}: rain hold markup",
    )

    old_status = '''    const statusEntity = this.getRelatedEntity("status");
    const rainHoldEntity = this.getRelatedEntity("rainHold");
    const displayedStatus = rainHoldEntity?.state === "on"
      ? this.translateStatus("rain_hold")
      : statusEntity ? this.translateStatus(statusEntity.state) : "-";
    this.shadowRoot.querySelectorAll('[data-role="mower-status"]').forEach((mowerStatus) => {
      mowerStatus.textContent = displayedStatus;
    });
'''
    new_status = '''    const statusEntity = this.getRelatedEntity("status");
    const displayedStatus = statusEntity ? this.translateStatus(statusEntity.state) : "-";
    this.shadowRoot.querySelectorAll('[data-role="mower-status"]').forEach((mowerStatus) => {
      mowerStatus.textContent = displayedStatus;
    });
    this.updateRainHoldDisplay();
'''
    source = replace_once(source, old_status, new_status, f"{path}: primary status")

    source = replace_once(
        source,
        "  updateRenderer() {\n",
        helper_methods + "  updateRenderer() {\n",
        f"{path}: countdown helpers",
    )

    path.write_text(source, encoding="utf-8")


test_path = Path("tests/test_rain_hold_status.py")
tests = test_path.read_text(encoding="utf-8")
old_test = '''    def test_card_overrides_visible_status_while_rain_hold_is_on(self) -> None:
        card = (COMPONENT / "frontend" / "anthbot-map-card.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('rainHold: ["binary_sensor", ["rain_hold"]]', card)
        self.assertIn('rainHoldEntity?.state === "on"', card)
        self.assertIn('this.translateStatus("rain_hold")', card)

'''
new_test = '''    def test_card_keeps_primary_status_and_renders_rain_hold_below(self) -> None:
        card = (COMPONENT / "frontend" / "anthbot-map-card.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('rainHold: ["binary_sensor", ["rain_hold"]]', card)
        self.assertIn('const displayedStatus = statusEntity ? this.translateStatus(statusEntity.state) : "-";', card)
        self.assertNotIn('const displayedStatus = rainHoldEntity?.state === "on"', card)
        self.assertIn('data-role="rain-hold-line"', card)
        self.assertIn('rainHoldEntity?.state === "on"', card)
        self.assertIn('rain_continue_time', card)
        self.assertIn('detected_at', card)
        self.assertIn('this.updateRainHoldDisplay();', card)
        self.assertIn('setInterval(() => this.updateRainHoldDisplay(), 1000)', card)
        self.assertIn('this.translateStatus("rain_hold")', card)

'''
tests = replace_once(tests, old_test, new_test, "test update")
test_path.write_text(tests, encoding="utf-8")
