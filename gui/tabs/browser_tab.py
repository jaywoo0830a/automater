"""브라우저 설정 탭 — 환경 + 핑거프린트 위장."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QLabel,
)

from gui.collapsible import CollapsibleSection


class BrowserTab(QWidget):

    def __init__(self) -> None:
        super().__init__()

        # ── 기본 설정 ──
        self._locale = QLineEdit("ko-KR")
        self._timezone = QComboBox()
        self._timezone.addItems(["Asia/Seoul", "Asia/Tokyo", "America/New_York", "Europe/London"])
        self._timezone.setEditable(True)

        basic_form = QFormLayout()
        basic_form.addRow("Locale:", self._locale)
        basic_form.addRow("시간대:", self._timezone)

        basic_group = QGroupBox("기본 환경")
        basic_group.setLayout(basic_form)

        # ── 핑거프린트 ──
        self._fp_webdriver = QCheckBox("navigator.webdriver 위장")
        self._fp_webdriver.setChecked(True)
        self._fp_plugins = QCheckBox("navigator.plugins 위장")
        self._fp_plugins.setChecked(True)
        self._fp_chrome = QCheckBox("window.chrome.runtime 위장")
        self._fp_chrome.setChecked(True)
        self._fp_languages = QCheckBox("navigator.languages 위장")
        self._fp_languages.setChecked(True)

        fp_form = QFormLayout()
        fp_form.addRow(self._fp_webdriver)
        fp_form.addRow(self._fp_plugins)
        fp_form.addRow(self._fp_chrome)
        fp_form.addRow(self._fp_languages)

        fp_group = QGroupBox("핑거프린트 위장")
        fp_group.setLayout(fp_form)

        # ── 고급 설정 (접힘) ──
        self._viewport_w = QSpinBox()
        self._viewport_w.setRange(800, 3840)
        self._viewport_w.setValue(1920)
        self._viewport_h = QSpinBox()
        self._viewport_h.setRange(600, 2160)
        self._viewport_h.setValue(1080)

        self._user_agent = QLineEdit()
        self._user_agent.setPlaceholderText("비워두면 Playwright 기본값 사용")

        self._color_scheme = QComboBox()
        self._color_scheme.addItems(["light", "dark"])

        self._scale_factor = QSpinBox()
        self._scale_factor.setRange(1, 3)
        self._scale_factor.setValue(1)

        self._geo_lat = QLineEdit()
        self._geo_lat.setPlaceholderText("37.497")
        self._geo_lng = QLineEdit()
        self._geo_lng.setPlaceholderText("127.027")

        advanced = CollapsibleSection("고급 설정")
        advanced.add_row("뷰포트 너비:", self._viewport_w)
        advanced.add_row("뷰포트 높이:", self._viewport_h)
        advanced.add_row("User-Agent:", self._user_agent)
        advanced.add_row("색상 모드:", self._color_scheme)
        advanced.add_row("DPI 배율:", self._scale_factor)
        advanced.add_row("위도:", self._geo_lat)
        advanced.add_row("경도:", self._geo_lng)

        layout = QVBoxLayout()
        layout.addWidget(basic_group)
        layout.addWidget(fp_group)
        layout.addWidget(advanced)
        layout.addStretch()
        self.setLayout(layout)

    def to_dict(self) -> dict:
        browser: dict = {}

        browser["viewport"] = [self._viewport_w.value(), self._viewport_h.value()]

        ua = self._user_agent.text().strip()
        if ua:
            browser["user_agent"] = ua

        browser["locale"] = self._locale.text().strip() or "ko-KR"
        browser["timezone"] = self._timezone.currentText().strip() or "Asia/Seoul"
        browser["color_scheme"] = self._color_scheme.currentText()
        browser["device_scale_factor"] = self._scale_factor.value()

        lat = self._geo_lat.text().strip()
        lng = self._geo_lng.text().strip()
        if lat and lng:
            try:
                browser["geolocation"] = [float(lat), float(lng)]
            except ValueError:
                pass

        browser["fingerprint"] = {
            "webdriver": not self._fp_webdriver.isChecked(),
            "plugins": self._fp_plugins.isChecked(),
            "chrome_runtime": self._fp_chrome.isChecked(),
            "languages": self._fp_languages.isChecked(),
        }

        return {"browser": browser}

    def from_dict(self, data: dict) -> None:
        browser = data.get("browser", {})

        self._locale.setText(browser.get("locale", "ko-KR"))

        tz = browser.get("timezone", "Asia/Seoul")
        idx = self._timezone.findText(tz)
        if idx >= 0:
            self._timezone.setCurrentIndex(idx)
        else:
            self._timezone.setEditText(tz)

        vp = browser.get("viewport", [1920, 1080])
        if isinstance(vp, (list, tuple)) and len(vp) >= 2:
            self._viewport_w.setValue(int(vp[0]))
            self._viewport_h.setValue(int(vp[1]))

        self._user_agent.setText(browser.get("user_agent", ""))

        cs = browser.get("color_scheme", "light")
        idx = self._color_scheme.findText(cs)
        if idx >= 0:
            self._color_scheme.setCurrentIndex(idx)

        self._scale_factor.setValue(int(browser.get("device_scale_factor", 1)))

        geo = browser.get("geolocation")
        if isinstance(geo, (list, tuple)) and len(geo) >= 2:
            self._geo_lat.setText(str(geo[0]))
            self._geo_lng.setText(str(geo[1]))

        fp = browser.get("fingerprint", {})
        self._fp_webdriver.setChecked(not fp.get("webdriver", False))
        self._fp_plugins.setChecked(fp.get("plugins", True))
        self._fp_chrome.setChecked(fp.get("chrome_runtime", True))
        self._fp_languages.setChecked(fp.get("languages", True))
