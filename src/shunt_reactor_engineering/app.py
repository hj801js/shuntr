from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import fitz
from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .cables import CABLE_LIBRARY, CableSpec, get_cable_spec
from .paths import ensure_runtime_dirs, reports_dir
from .reporting import GeneratedReport, default_report_filename, generate_report, sanitize_report_filename
from .settings import (
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_LOGO_PATH,
    AppSettings,
    load_settings,
    normalize_path_for_storage,
    resolve_logo_path,
    save_settings,
    verify_admin_credentials,
)
from .studies import DEFAULT_PROJECT_NAME, ChargingCurrentStudyInput, ChargingCurrentStudyResult, evaluate_study


def format_decimal(value: float, digits: int = 3) -> str:
    formatted = f"{value:.{digits}f}"
    if "." not in formatted:
        return formatted
    return formatted.rstrip("0").rstrip(".")


def make_unit_row(editor: QWidget, unit_text: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(editor, 1)

    unit_label = QLabel(unit_text)
    unit_label.setObjectName("UnitLabel")
    unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    unit_label.setMinimumWidth(54)
    layout.addWidget(unit_label)
    return container


def make_display_row(value_label: QLabel, unit_text: str) -> QWidget:
    value_label.setObjectName("DisplayValue")
    return make_unit_row(value_label, unit_text)


class ReportWorker(QThread):
    report_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        study_input: ChargingCurrentStudyInput,
        filename_stem: str,
        output_directory: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.study_input = study_input
        self.filename_stem = filename_stem
        self.output_directory = output_directory

    def run(self) -> None:
        try:
            report = generate_report(
                self.study_input,
                filename_stem=self.filename_stem,
                output_directory=self.output_directory,
            )
        except Exception as exc:  # pragma: no cover - exercised through UI flow
            self.failed.emit(str(exc))
            return

        self.report_ready.emit(report)


class PdfPreviewWidget(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewSurface")
        self.current_pdf_path: Path | None = None
        self.zoom_percent = 130
        self.page_width_points: float | None = None
        self.page_height_points: float | None = None

        self.placeholder = QLabel("생성된 PDF가 여기에 표시됩니다.")
        self.placeholder.setObjectName("PreviewPlaceholder")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(24, 24, 24, 24)
        self.container_layout.setSpacing(18)
        self.container_layout.addWidget(self.placeholder)
        self.container_layout.addStretch(1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

    def clear_preview(self, message: str | None = None) -> None:
        self.current_pdf_path = None
        self.page_width_points = None
        self.page_height_points = None
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.placeholder.setText(message or "생성된 PDF가 여기에 표시됩니다.")
        self.container_layout.addWidget(self.placeholder)
        self.container_layout.addStretch(1)

    def set_zoom_percent(self, zoom_percent: int) -> None:
        self.zoom_percent = zoom_percent
        if self.current_pdf_path is not None and self.current_pdf_path.exists():
            self.load_pdf(self.current_pdf_path)

    def load_pdf(self, pdf_path: Path) -> int:
        self.current_pdf_path = pdf_path
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        page_count = 0
        document = fitz.open(pdf_path)
        try:
            scale = self.zoom_percent / 100.0
            page_count = document.page_count
            for page_index in range(page_count):
                page = document.load_page(page_index)
                if page_index == 0:
                    self.page_width_points = float(page.rect.width)
                    self.page_height_points = float(page.rect.height)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = QImage(
                    pixmap.samples,
                    pixmap.width,
                    pixmap.height,
                    pixmap.stride,
                    QImage.Format.Format_RGB888,
                ).copy()

                label = QLabel()
                label.setPixmap(QPixmap.fromImage(image))
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

                card = QFrame()
                card.setObjectName("PreviewPageCard")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(18, 18, 18, 18)
                card_layout.addWidget(label)
                self.container_layout.addWidget(card)
        finally:
            document.close()

        self.container_layout.addStretch(1)
        return page_count

    def fit_to_width(self) -> int:
        if self.current_pdf_path is None or self.page_width_points is None:
            return self.zoom_percent
        available_width = max(self.scroll_area.viewport().width() - 110, 200)
        zoom_percent = max(30, min(300, int((available_width / self.page_width_points) * 100)))
        self.set_zoom_percent(zoom_percent)
        return zoom_percent

    def fit_to_height(self) -> int:
        if self.current_pdf_path is None or self.page_height_points is None:
            return self.zoom_percent
        available_height = max(self.scroll_area.viewport().height() - 110, 200)
        zoom_percent = max(30, min(300, int((available_height / self.page_height_points) * 100)))
        self.set_zoom_percent(zoom_percent)
        return zoom_percent


class LogoBadge(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LogoBadge")
        self.setFixedSize(220, 92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fallback_title = QLabel("UPTEC")
        self.fallback_title.setObjectName("LogoFallbackTitle")
        self.fallback_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fallback_subtitle = QLabel("ENERGY REPORT")
        self.fallback_subtitle.setObjectName("LogoFallbackSubtitle")
        self.fallback_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.fallback_title)
        layout.addWidget(self.fallback_subtitle)

        self.set_logo_path(None)

    def set_logo_path(self, logo_path: Path | None) -> None:
        if logo_path is not None:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    180,
                    58,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled)
                self.image_label.show()
                self.fallback_title.hide()
                self.fallback_subtitle.hide()
                return

        self.image_label.clear()
        self.image_label.hide()
        self.fallback_title.show()
        self.fallback_subtitle.show()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class BusySpinner(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(22, 22)
        self.hide()

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def start(self) -> None:
        self._angle = 0
        self.show()
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def is_spinning(self) -> bool:
        return self._timer.isActive()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        if not self._timer.isActive():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)

        for step in range(12):
            color = QColor("#1a5c69")
            color.setAlphaF((step + 1) / 12.0)
            pen = QPen(color, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.save()
            painter.rotate(self._angle - (step * 30))
            painter.drawLine(0, -7, 0, -10)
            painter.restore()


class LoginDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("관리자 로그인")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        helper = QLabel("관리자 메뉴에 접근하려면 인증이 필요합니다.")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.username_input = QLineEdit(DEFAULT_ADMIN_USERNAME)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("사용자명", self.username_input)
        form.addRow("비밀번호", self.password_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def credentials(self) -> tuple[str, str]:
        return self.username_input.text().strip(), self.password_input.text()


class AdminSettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("관리자 설정")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        logo_group = QGroupBox("로고 설정")
        logo_layout = QFormLayout(logo_group)
        logo_layout.setContentsMargins(14, 18, 14, 14)
        logo_layout.setHorizontalSpacing(12)
        logo_layout.setVerticalSpacing(12)

        self.logo_path_input = QLineEdit(settings.logo_path)
        browse_button = QPushButton("찾아보기")
        browse_button.clicked.connect(self.browse_logo_path)

        logo_row = QHBoxLayout()
        logo_row.addWidget(self.logo_path_input, 1)
        logo_row.addWidget(browse_button)

        hint_label = QLabel("파일이 없으면 우측 상단 로고 영역에는 오류 대신 UPTEC 텍스트가 표시됩니다.")
        hint_label.setWordWrap(True)

        logo_layout.addRow("로고 파일", logo_row)
        logo_layout.addRow("", hint_label)

        cable_group = QGroupBox("케이블 정전용량 설정")
        cable_layout = QVBoxLayout(cable_group)
        cable_layout.setContentsMargins(14, 18, 14, 14)

        self.cable_table = QTableWidget(len(settings.cables), 2)
        self.cable_table.setHorizontalHeaderLabels(["케이블", "정전용량 (uF/km)"])
        self.cable_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cable_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.cable_table.verticalHeader().setVisible(False)

        for row_index, spec in enumerate(settings.cables):
            label_item = QTableWidgetItem(spec.label)
            label_item.setData(Qt.ItemDataRole.UserRole, spec.code)
            label_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.cable_table.setItem(row_index, 0, label_item)

            capacitance_spin = NoWheelDoubleSpinBox()
            capacitance_spin.setRange(0.001, 10.0)
            capacitance_spin.setDecimals(3)
            capacitance_spin.setValue(spec.capacitance_uf_per_km)
            capacitance_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            capacitance_spin.setMinimumHeight(38)
            self.cable_table.setCellWidget(row_index, 1, capacitance_spin)
            self.cable_table.setRowHeight(row_index, 48)

        cable_layout.addWidget(self.cable_table)

        restore_button = QPushButton("기본값 복원")
        restore_button.clicked.connect(self.restore_defaults)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        footer = QHBoxLayout()
        footer.addWidget(restore_button)
        footer.addStretch(1)
        footer.addWidget(buttons)

        layout.addWidget(logo_group)
        layout.addWidget(cable_group, 1)
        layout.addLayout(footer)

    def browse_logo_path(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "로고 파일 선택",
            self.logo_path_input.text().strip() or str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp *.svg)",
        )
        if file_path:
            self.logo_path_input.setText(normalize_path_for_storage(file_path))

    def restore_defaults(self) -> None:
        self.logo_path_input.setText(DEFAULT_LOGO_PATH)
        for row_index, spec in enumerate(CABLE_LIBRARY):
            widget = self.cable_table.cellWidget(row_index, 1)
            if isinstance(widget, QDoubleSpinBox):
                widget.setValue(spec.capacitance_uf_per_km)

    def build_settings(self) -> AppSettings:
        cables: list[CableSpec] = []
        for row_index in range(self.cable_table.rowCount()):
            label_item = self.cable_table.item(row_index, 0)
            widget = self.cable_table.cellWidget(row_index, 1)
            if label_item is None or not isinstance(widget, QDoubleSpinBox):
                continue

            cables.append(
                CableSpec(
                    code=str(label_item.data(Qt.ItemDataRole.UserRole)),
                    label=label_item.text().strip(),
                    capacitance_uf_per_km=widget.value(),
                )
            )

        logo_path = self.logo_path_input.text().strip() or DEFAULT_LOGO_PATH
        return AppSettings(logo_path=logo_path, cables=tuple(cables))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.admin_authenticated = False
        self.auto_filename = ""
        self.filename_manually_edited = False
        self.compensation_manually_edited = False
        self.last_report: GeneratedReport | None = None
        self.last_requested_filename = ""
        self.worker: ReportWorker | None = None

        self.setWindowTitle("분로리엑터 설계 프로그램")
        ensure_runtime_dirs()

        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            minimum_width = min(1500, max(1280, available.width() - 120))
            minimum_height = min(920, max(820, available.height() - 120))
            self.setMinimumSize(minimum_width, minimum_height)

            default_width = min(max(int(available.width() * 0.9), 1840), available.width() - 36)
            default_height = min(max(int(available.height() * 0.9), 1040), available.height() - 48)
            self.resize(max(default_width, minimum_width), max(default_height, minimum_height))
        else:
            self.setMinimumSize(1500, 920)
            self.resize(1880, 1080)

        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(18)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.left_panel = self.build_left_panel()
        self.right_panel = self.build_right_panel()
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(10)
        splitter.setSizes([520, 1460])
        root_layout.addWidget(splitter, 1)

        self.statusBar().showMessage("실행 준비 완료")
        self.build_menu()
        self.apply_styles()
        self.refresh_cable_options()
        self.refresh_auto_filename(force=True)
        self.sync_capacitance_from_selection()
        self.refresh_logo_display()
        self.refresh_live_metrics()
        self.update_action_buttons()
        self.update_admin_state()

    def build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("파일")

        self.generate_action = QAction("PDF 생성", self)
        self.generate_action.triggered.connect(self.generate_report)
        file_menu.addAction(self.generate_action)

        self.open_pdf_action = QAction("PDF 열기", self)
        self.open_pdf_action.triggered.connect(self.open_pdf)
        file_menu.addAction(self.open_pdf_action)

        self.open_folder_action = QAction("출력 폴더 열기", self)
        self.open_folder_action.triggered.connect(self.open_reports_folder)
        file_menu.addAction(self.open_folder_action)

        file_menu.addSeparator()

        self.file_login_action = QAction("관리자 로그인...", self)
        self.file_login_action.triggered.connect(self.prompt_admin_login)
        file_menu.addAction(self.file_login_action)

        exit_action = QAction("종료", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        admin_menu = self.menuBar().addMenu("관리자")

        self.admin_login_action = QAction("로그인...", self)
        self.admin_login_action.triggered.connect(self.prompt_admin_login)
        admin_menu.addAction(self.admin_login_action)

        self.admin_settings_action = QAction("설정...", self)
        self.admin_settings_action.triggered.connect(self.open_admin_settings)
        admin_menu.addAction(self.admin_settings_action)

        self.admin_logout_action = QAction("로그아웃", self)
        self.admin_logout_action.triggered.connect(self.logout_admin)
        admin_menu.addAction(self.admin_logout_action)

    def build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LeftPanel")
        panel.setMinimumWidth(470)
        panel.setMaximumWidth(560)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header_card = QFrame()
        header_card.setObjectName("HeroCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(22, 22, 22, 22)
        header_layout.setSpacing(8)

        title = QLabel("분로리엑터 설계 프로그램")
        title.setObjectName("HeroTitle")
        title.setFont(QFont("Malgun Gothic", 22, QFont.Weight.Bold))

        self.status_badge = QLabel("대기 중")
        self.status_badge.setObjectName("Badge")
        self.status_badge.hide()

        self.admin_badge = QLabel("관리자 잠금")
        self.admin_badge.setObjectName("Badge")
        self.admin_badge.hide()

        header_layout.addWidget(title)

        layout.addWidget(header_card)
        layout.addWidget(self.build_project_group())
        layout.addWidget(self.build_condition_group())
        layout.addWidget(self.build_action_group())
        layout.addStretch(1)

        return panel

    def build_metric_cards(self) -> QWidget:
        card = QFrame()
        card.setObjectName("MetricGrid")
        layout = QGridLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(0)

        self.metric_current = self.create_metric_card("충전전류", "대기 중")
        self.metric_reactive = self.create_metric_card("무효전력", "대기 중")
        self.metric_switching = self.create_metric_card("개폐전류 검토", "대기 중")

        layout.addWidget(self.metric_current, 0, 0)
        layout.addWidget(self.metric_reactive, 0, 1)
        layout.addWidget(self.metric_switching, 0, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        return card

    def create_metric_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")

        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        value_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        card.value_label = value_label  # type: ignore[attr-defined]
        return card

    def build_project_group(self) -> QFrame:
        group = QFrame()
        group.setObjectName("InputGroup")
        form = QFormLayout(group)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.project_name_input = QLineEdit(DEFAULT_PROJECT_NAME)
        self.project_name_input.setPlaceholderText("프로젝트명")
        self.project_name_input.textChanged.connect(self.on_project_name_changed)
        self.project_name_input.textChanged.connect(self.refresh_live_metrics)

        self.report_filename_input = QLineEdit()
        self.report_filename_input.setPlaceholderText("파일명 입력, .pdf 제외")
        self.report_filename_input.textEdited.connect(self.on_report_filename_edited)

        self.route_length_input = QDoubleSpinBox()
        self.route_length_input.setRange(0.001, 500.0)
        self.route_length_input.setDecimals(3)
        self.route_length_input.setValue(0.5)
        self.route_length_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.route_length_input.valueChanged.connect(self.refresh_live_metrics)

        self.circuit_count_input = QComboBox()
        self.circuit_count_input.addItem("1회선", 1)
        self.circuit_count_input.addItem("2회선", 2)
        self.circuit_count_input.setCurrentIndex(0)
        self.circuit_count_input.currentIndexChanged.connect(self.refresh_live_metrics)

        form.addRow("프로젝트명", self.project_name_input)
        form.addRow("보고서 파일명", self.report_filename_input)
        form.addRow("회선 길이", make_unit_row(self.route_length_input, "km"))
        form.addRow("회선 수", self.circuit_count_input)

        return group

    def build_condition_group(self) -> QFrame:
        group = QFrame()
        group.setObjectName("InputGroup")
        form = QFormLayout(group)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.voltage_display = QLabel("154.0")
        self.frequency_display = QLabel("60.0")

        self.cable_combo = QComboBox()
        self.cable_combo.currentIndexChanged.connect(self.sync_capacitance_from_selection)

        self.capacitance_display = QLabel("-")

        self.switching_limit_input = QDoubleSpinBox()
        self.switching_limit_input.setRange(1.0, 5000.0)
        self.switching_limit_input.setDecimals(1)
        self.switching_limit_input.setValue(400.0)
        self.switching_limit_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.switching_limit_input.valueChanged.connect(self.refresh_live_metrics)

        self.compensation_input = QDoubleSpinBox()
        self.compensation_input.setRange(0.1, 5000.0)
        self.compensation_input.setDecimals(3)
        self.compensation_input.setValue(2.0)
        self.compensation_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.compensation_input.valueChanged.connect(self.on_compensation_edited)

        form.addRow("정격전압", make_display_row(self.voltage_display, "kV"))
        form.addRow("주파수", make_display_row(self.frequency_display, "Hz"))
        form.addRow("케이블", self.cable_combo)
        form.addRow("정전용량", make_display_row(self.capacitance_display, "uF/km"))
        form.addRow("개폐전류 기준", make_unit_row(self.switching_limit_input, "A"))
        form.addRow("보상 용량", make_unit_row(self.compensation_input, "MVar"))

        return group

    def build_action_group(self) -> QWidget:
        card = QFrame()
        card.setObjectName("ActionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.generate_button = QPushButton("PDF 생성")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self.generate_report)

        self.open_pdf_button = QPushButton("PDF 열기")
        self.open_pdf_button.setObjectName("SecondaryButton")
        self.open_pdf_button.clicked.connect(self.open_pdf)

        self.open_folder_button = QPushButton("출력 폴더 열기")
        self.open_folder_button.setObjectName("SecondaryButton")
        self.open_folder_button.clicked.connect(self.open_reports_folder)

        button_row.addWidget(self.generate_button, 1)
        button_row.addWidget(self.open_pdf_button, 1)
        button_row.addWidget(self.open_folder_button, 1)

        self.output_directory_input = QLineEdit(str(reports_dir()))
        self.output_directory_input.setPlaceholderText("출력 폴더")

        self.output_browse_button = QPushButton("찾아보기")
        self.output_browse_button.setObjectName("SecondaryButton")
        self.output_browse_button.clicked.connect(self.browse_output_directory)

        output_label = QLabel("출력 폴더")
        output_label.setObjectName("MiniLabel")

        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        output_row.addWidget(self.output_directory_input, 1)
        output_row.addWidget(self.output_browse_button)

        self.busy_row = QWidget()
        self.busy_row.setObjectName("BusyRow")
        busy_layout = QHBoxLayout(self.busy_row)
        busy_layout.setContentsMargins(0, 0, 0, 0)
        busy_layout.setSpacing(8)

        self.busy_spinner = BusySpinner(self.busy_row)
        self.busy_text = QLabel("PDF 변환 중...")
        self.busy_text.setObjectName("BusyText")

        busy_layout.addStretch(1)
        busy_layout.addWidget(self.busy_spinner)
        busy_layout.addWidget(self.busy_text)
        busy_layout.addStretch(1)
        self.busy_row.hide()

        layout.addLayout(button_row)
        layout.addWidget(output_label)
        layout.addLayout(output_row)
        layout.addWidget(self.busy_row)

        return card

    def build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("RightPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        top_card = QFrame()
        top_card.setObjectName("TopMetricsCard")
        top_layout = QVBoxLayout(top_card)
        top_layout.setContentsMargins(22, 22, 22, 22)
        top_layout.setSpacing(16)

        overview_title = QLabel("검토 결과")
        overview_title.setObjectName("OverviewTitle")

        self.logo_badge = LogoBadge()

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)
        header_row.addWidget(overview_title, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addStretch(1)
        header_row.addWidget(self.logo_badge, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        top_layout.addLayout(header_row)
        top_layout.addWidget(self.build_metric_cards())

        header = QFrame()
        header.setObjectName("PreviewHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        preview_title = QLabel("PDF 미리보기")
        preview_title.setObjectName("PreviewCompactTitle")

        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(10)

        self.fit_width_button = QPushButton("너비 맞춤")
        self.fit_width_button.setObjectName("SecondaryButton")
        self.fit_width_button.setShortcut("Ctrl+1")
        self.fit_width_button.clicked.connect(self.fit_preview_width)

        self.fit_height_button = QPushButton("높이 맞춤")
        self.fit_height_button.setObjectName("SecondaryButton")
        self.fit_height_button.setShortcut("Ctrl+2")
        self.fit_height_button.clicked.connect(self.fit_preview_height)

        self.zoom_100_button = QPushButton("100%")
        self.zoom_100_button.setObjectName("SecondaryButton")
        self.zoom_100_button.setShortcut("Ctrl+0")
        self.zoom_100_button.clicked.connect(self.set_preview_zoom_100)

        zoom_row.addStretch(1)
        zoom_row.addWidget(self.fit_width_button)
        zoom_row.addWidget(self.fit_height_button)
        zoom_row.addWidget(self.zoom_100_button)

        header_layout.addWidget(preview_title)
        header_layout.addLayout(zoom_row)

        self.preview_widget = PdfPreviewWidget()
        self.preview_meta_card = self.build_preview_meta_card()

        layout.addWidget(top_card)
        layout.addWidget(header)
        layout.addWidget(self.preview_widget, 1)
        layout.addWidget(self.preview_meta_card)

        return panel

    def build_preview_meta_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("PreviewMetaCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.preview_page_count_label = QLabel("페이지 수: -")
        self.preview_page_count_label.setObjectName("MiniValue")
        self.preview_filename_label = QLabel("파일명: -")
        self.preview_filename_label.setObjectName("MiniValue")
        self.preview_path_label = QLabel("아직 생성된 보고서가 없습니다.")
        self.preview_path_label.setObjectName("PreviewPathLabel")
        self.preview_path_label.setWordWrap(True)
        self.preview_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(self.preview_page_count_label)
        layout.addWidget(self.preview_filename_label)
        layout.addWidget(self.preview_path_label)
        return card

    def on_project_name_changed(self, _value: str) -> None:
        self.refresh_auto_filename()

    def on_report_filename_edited(self, value: str) -> None:
        self.filename_manually_edited = bool(value.strip())
        if not self.filename_manually_edited:
            self.refresh_auto_filename(force=True)

    def on_compensation_edited(self, _value: float) -> None:
        self.compensation_manually_edited = True
        self.refresh_live_metrics()

    def refresh_auto_filename(self, force: bool = False) -> None:
        project_name = self.project_name_input.text().strip() or DEFAULT_PROJECT_NAME
        self.auto_filename = default_report_filename(project_name)
        if force or not self.filename_manually_edited or not self.report_filename_input.text().strip():
            previous_state = self.report_filename_input.blockSignals(True)
            self.report_filename_input.setText(self.auto_filename)
            self.report_filename_input.blockSignals(previous_state)

    def refresh_cable_options(self) -> None:
        selected_code = self.cable_combo.currentData()
        self.cable_combo.blockSignals(True)
        self.cable_combo.clear()
        for spec in self.settings.cables:
            self.cable_combo.addItem(spec.label, spec.code)
        self.cable_combo.blockSignals(False)

        default_code = selected_code or "xlpe_1200"
        index = self.cable_combo.findData(default_code)
        if index < 0:
            index = self.cable_combo.findData("xlpe_1200")
        if index < 0 and self.cable_combo.count() > 0:
            index = 0
        if index >= 0:
            self.cable_combo.setCurrentIndex(index)

    def sync_capacitance_from_selection(self) -> None:
        code = self.cable_combo.currentData()
        if code is None:
            return

        spec = next((item for item in self.settings.cables if item.code == code), None)
        if spec is None:
            spec = get_cable_spec(str(code))

        self.capacitance_display.setText(format_decimal(spec.capacitance_uf_per_km))
        self.refresh_live_metrics()

    def refresh_logo_display(self) -> None:
        self.logo_badge.set_logo_path(resolve_logo_path(self.settings))

    def browse_output_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "출력 폴더 선택",
            self.output_directory_input.text().strip() or str(reports_dir()),
        )
        if selected:
            self.output_directory_input.setText(selected)

    def get_output_directory(self) -> Path:
        value = self.output_directory_input.text().strip()
        if not value:
            return reports_dir()
        return Path(value).expanduser().resolve(strict=False)

    def fit_preview_width(self) -> None:
        zoom_percent = self.preview_widget.fit_to_width()
        self.statusBar().showMessage(f"미리보기 너비 맞춤 {zoom_percent}%", 3000)

    def fit_preview_height(self) -> None:
        zoom_percent = self.preview_widget.fit_to_height()
        self.statusBar().showMessage(f"미리보기 높이 맞춤 {zoom_percent}%", 3000)

    def set_preview_zoom_100(self) -> None:
        self.preview_widget.set_zoom_percent(100)
        self.statusBar().showMessage("미리보기 100%", 3000)

    def refresh_live_metrics(self) -> None:
        try:
            study_input = self.collect_input()
            result = evaluate_study(study_input)
        except Exception:
            self.update_metric_cards(None)
            return

        if not self.compensation_manually_edited:
            previous_state = self.compensation_input.blockSignals(True)
            self.compensation_input.setValue(result.recommended_compensation_mvar)
            self.compensation_input.blockSignals(previous_state)
            study_input = self.collect_input()
            result = evaluate_study(study_input)

        self.update_metric_cards(result)

    def collect_input(self) -> ChargingCurrentStudyInput:
        project_name = self.project_name_input.text().strip()
        if not project_name:
            raise ValueError("프로젝트명을 입력하세요.")

        cable_name = self.cable_combo.currentText().strip()
        if not cable_name:
            raise ValueError("케이블을 선택하세요.")

        return ChargingCurrentStudyInput(
            project_name=project_name,
            line_voltage_kv=float(self.voltage_display.text()),
            frequency_hz=float(self.frequency_display.text()),
            cable_name=cable_name,
            capacitance_uf_per_km=float(self.capacitance_display.text()),
            route_length_km=self.route_length_input.value(),
            circuit_count=int(self.circuit_count_input.currentData()),
            switching_limit_a=self.switching_limit_input.value(),
            compensation_mvar=self.compensation_input.value() if self.compensation_manually_edited else None,
        )

    def generate_report(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return

        try:
            study_input = self.collect_input()
        except ValueError as exc:
            self.show_error("입력 오류", str(exc))
            return

        requested_filename = self.report_filename_input.text().strip() or self.auto_filename
        filename_stem = sanitize_report_filename(requested_filename)
        self.last_requested_filename = filename_stem
        output_directory = self.get_output_directory()
        output_directory.mkdir(parents=True, exist_ok=True)

        self.set_busy_state(True)
        self.worker = ReportWorker(
            study_input=study_input,
            filename_stem=filename_stem,
            output_directory=output_directory,
            parent=self,
        )
        self.worker.report_ready.connect(self.on_report_ready)
        self.worker.failed.connect(self.on_report_failed)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def _cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def on_report_ready(self, report: GeneratedReport) -> None:
        self.last_report = report
        self.set_busy_state(False)
        self.update_action_buttons()
        self.update_metric_cards(report.study_result)

        try:
            page_count = self.preview_widget.load_pdf(report.pdf_path)
        except Exception as exc:
            self.preview_widget.clear_preview("PDF를 미리보기에 불러오지 못했습니다.")
            self.preview_page_count_label.setText("페이지 수: -")
            self.preview_filename_label.setText(f"파일명: {report.pdf_path.name}")
            self.preview_path_label.setText(str(report.pdf_path))
            self.set_badge_state(self.status_badge, "미리보기 오류", "warning")
            self.statusBar().showMessage(f"PDF 생성은 완료됐지만 미리보기 로드에 실패했습니다: {exc}", 8000)
            return

        self.preview_page_count_label.setText(f"페이지 수: {page_count}")
        self.preview_filename_label.setText(f"파일명: {report.pdf_path.name}")
        self.preview_path_label.setText(str(report.pdf_path))
        self.set_badge_state(self.status_badge, "생성 완료", "ready")

        saved_name = report.pdf_path.stem
        if saved_name != report.requested_stem:
            message = f"동일 파일명이 있어 {report.pdf_path.name} 로 저장했습니다."
        else:
            message = f"{report.pdf_path.name} 생성 완료"
        self.statusBar().showMessage(message, 8000)

    def on_report_failed(self, error_message: str) -> None:
        self.set_busy_state(False)
        self.update_action_buttons()
        self.set_badge_state(self.status_badge, "생성 실패", "danger")
        self.statusBar().showMessage("PDF 생성 실패", 6000)
        self.show_error("PDF 생성 실패", error_message)

    def update_metric_cards(self, result: ChargingCurrentStudyResult | None) -> None:
        if result is None:
            self.metric_current.value_label.setText("계산 대기")  # type: ignore[attr-defined]
            self.metric_reactive.value_label.setText("계산 대기")  # type: ignore[attr-defined]
            self.metric_switching.value_label.setText("검토 대기")  # type: ignore[attr-defined]
            return

        self.metric_current.value_label.setText(  # type: ignore[attr-defined]
            f"km당 충전전류: {format_decimal(result.charging_current_per_km_a)} A/km\n"
            f"선로 충전전류: {format_decimal(result.charging_current_a)} A"
        )
        self.metric_reactive.value_label.setText(  # type: ignore[attr-defined]
            f"계산 용량: {format_decimal(result.reactive_power_mvar)} MVar\n"
            f"보상 용량: {format_decimal(result.recommended_compensation_mvar)} MVar"
        )
        if result.switching_limit_exceeded:
            switching_text = "불만족"
        else:
            switching_text = "만족"
        self.metric_switching.value_label.setText(switching_text)  # type: ignore[attr-defined]

    def set_busy_state(self, busy: bool) -> None:
        self.generate_button.setEnabled(not busy)
        self.generate_action.setEnabled(not busy)
        self.generate_button.setText("PDF 생성 중" if busy else "PDF 생성")
        self.busy_row.setVisible(busy)
        if busy:
            self.busy_spinner.start()
        else:
            self.busy_spinner.stop()
        if busy:
            self.set_badge_state(self.status_badge, "조판 중", "busy")
            self.statusBar().showMessage("LaTeX PDF를 생성하는 중입니다...")
        self.update_action_buttons()

    def update_action_buttons(self) -> None:
        has_report = self.last_report is not None and self.last_report.pdf_path.exists()
        worker_running = self.worker is not None and self.worker.isRunning()

        self.generate_button.setEnabled(not worker_running)
        self.generate_action.setEnabled(not worker_running)
        self.open_pdf_button.setEnabled(has_report)
        self.open_pdf_action.setEnabled(has_report)
        self.open_folder_button.setEnabled(True)
        self.open_folder_action.setEnabled(True)

    def update_admin_state(self) -> None:
        self.admin_settings_action.setEnabled(self.admin_authenticated)
        self.admin_logout_action.setEnabled(self.admin_authenticated)
        self.admin_login_action.setEnabled(not self.admin_authenticated)
        self.file_login_action.setEnabled(not self.admin_authenticated)

        if self.admin_authenticated:
            self.set_badge_state(self.admin_badge, "관리자 모드", "ready")
        else:
            self.set_badge_state(self.admin_badge, "관리자 잠금", "neutral")

    def set_badge_state(self, label: QLabel, text: str, state: str) -> None:
        label.setText(text)
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def prompt_admin_login(self) -> None:
        dialog = LoginDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        username, password = dialog.credentials()
        if verify_admin_credentials(username, password):
            self.admin_authenticated = True
            self.update_admin_state()
            self.statusBar().showMessage("관리자 모드로 전환했습니다.", 5000)
            return

        QMessageBox.warning(self, "로그인 실패", "사용자명 또는 비밀번호가 올바르지 않습니다.")

    def open_admin_settings(self) -> None:
        if not self.admin_authenticated:
            self.prompt_admin_login()
            if not self.admin_authenticated:
                return

        dialog = AdminSettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_code = self.cable_combo.currentData()
        self.settings = dialog.build_settings()
        save_settings(self.settings)
        self.refresh_cable_options()

        if selected_code is not None:
            index = self.cable_combo.findData(selected_code)
            if index >= 0:
                self.cable_combo.setCurrentIndex(index)

        self.refresh_logo_display()
        self.sync_capacitance_from_selection()
        self.refresh_live_metrics()
        self.statusBar().showMessage("관리자 설정을 저장했습니다.", 5000)

    def logout_admin(self) -> None:
        self.admin_authenticated = False
        self.update_admin_state()
        self.statusBar().showMessage("관리자 모드를 종료했습니다.", 5000)

    def open_pdf(self) -> None:
        if self.last_report is None or not self.last_report.pdf_path.exists():
            self.show_error("열기 실패", "열 수 있는 PDF가 아직 없습니다.")
            return
        self.open_path(self.last_report.pdf_path)

    def open_reports_folder(self) -> None:
        output_directory = self.get_output_directory()
        output_directory.mkdir(parents=True, exist_ok=True)
        self.open_path(output_directory)

    def open_path(self, path: Path) -> None:
        path = path.resolve(strict=False)
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            return

        try:
            if sys.platform.startswith("win") and hasattr(os, "startfile"):
                os.startfile(str(path))  # type: ignore[attr-defined]
                return
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
                return
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # pragma: no cover - platform dependent
            self.show_error("열기 실패", f"경로를 열 수 없습니다.\n{path}\n\n{exc}")

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#AppRoot {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f6f2e8,
                    stop: 0.45 #eef5f4,
                    stop: 1 #e3eef2
                );
                color: #1b2d38;
                font-family: "Malgun Gothic";
                font-size: 10pt;
            }
            QMenuBar, QStatusBar {
                background: rgba(255, 255, 255, 0.88);
            }
            QFrame#LeftPanel,
            QFrame#RightPanel {
                background: transparent;
            }
            QFrame#HeroCard,
            QFrame#TopMetricsCard,
            QFrame#InputGroup,
            QFrame#ActionCard,
            QFrame#PreviewHeader,
            QFrame#PreviewSurface,
            QFrame#PreviewMetaCard,
            QFrame#MetricCard,
            QFrame#LogoBadge {
                background: rgba(255, 255, 255, 0.90);
                border: 1px solid rgba(17, 56, 71, 0.08);
                border-radius: 20px;
            }
            QFrame#HeroCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #12344a,
                    stop: 0.55 #1a5c69,
                    stop: 1 #cc8f3d
                );
                border: none;
            }
            QLabel#HeroTitle {
                color: white;
            }
            QLabel#Badge {
                padding: 6px 12px;
                border-radius: 999px;
                font-weight: 700;
                background: rgba(20, 44, 57, 0.08);
                color: #244152;
            }
            QLabel#Badge[state="ready"] {
                background: #d7f2e6;
                color: #0f6249;
            }
            QLabel#Badge[state="busy"] {
                background: #fde7bb;
                color: #8a5b00;
            }
            QLabel#Badge[state="danger"] {
                background: #f9d3d0;
                color: #8c2720;
            }
            QLabel#Badge[state="warning"] {
                background: #f6e6c9;
                color: #875d13;
            }
            QLabel#Badge[state="neutral"] {
                background: rgba(255, 255, 255, 0.18);
                color: white;
            }
            QFrame#MetricCard {
                min-height: 118px;
            }
            QLabel#MetricTitle {
                color: #16324a;
                font-size: 14pt;
                font-weight: 800;
            }
            QLabel#MetricValue {
                color: #4f6571;
                font-size: 10.5pt;
                font-weight: 600;
            }
            QFrame#PreviewHeader {
                background: rgba(248, 251, 252, 0.96);
            }
            QFrame#InputGroup {
                margin-top: 0;
            }
            QLabel#PreviewPathLabel {
                color: #5b7480;
            }
            QLabel#OverviewTitle {
                font-size: 22pt;
                font-weight: 800;
                color: #16324a;
            }
            QLabel#PreviewCompactTitle {
                font-size: 12pt;
                font-weight: 800;
                color: #16324a;
            }
            QLabel#MiniLabel {
                color: #4c6977;
                font-weight: 600;
            }
            QLabel#MiniValue {
                color: #173444;
                font-weight: 700;
            }
            QFrame#PreviewMetaCard {
                background: rgba(255, 255, 255, 0.94);
            }
            QWidget#BusyRow {
                min-height: 30px;
            }
            QLabel#BusyText {
                color: #1a5c69;
                font-weight: 700;
            }
            QLabel#DisplayValue {
                background: #f3f6f8;
                border: 1px solid rgba(22, 50, 74, 0.14);
                padding: 9px 10px;
                color: #173444;
                min-height: 22px;
            }
            QLabel#UnitLabel {
                background: #edf2f5;
                border: 1px solid rgba(22, 50, 74, 0.14);
                padding: 9px 10px;
                color: #4c6977;
                font-weight: 700;
                min-height: 22px;
            }
            QLabel#PreviewPlaceholder {
                color: #607884;
                font-size: 13pt;
                padding: 72px 16px;
            }
            QFrame#PreviewPageCard {
                background: #f8fbfc;
                border: 1px solid rgba(22, 50, 74, 0.10);
                border-radius: 16px;
            }
            QPushButton {
                min-height: 40px;
                border-radius: 0;
                padding: 0 16px;
                font-weight: 700;
            }
            QPushButton#PrimaryButton {
                background: #173a51;
                color: white;
                border: 1px solid #173a51;
            }
            QPushButton#PrimaryButton:hover {
                background: #1c4965;
            }
            QPushButton#PrimaryButton:pressed {
                background: #0f2d3f;
                border: 1px solid #0f2d3f;
                padding-top: 2px;
                padding-left: 18px;
            }
            QPushButton#PrimaryButton:disabled {
                background: #557080;
                color: #deeaef;
                border: 1px solid #557080;
            }
            QPushButton#SecondaryButton {
                background: #f4f7f8;
                color: #183645;
                border: 1px solid rgba(22, 50, 74, 0.10);
            }
            QPushButton#SecondaryButton:hover {
                background: #ebf1f3;
            }
            QPushButton#SecondaryButton:pressed {
                background: #dde6ea;
                border: 1px solid rgba(22, 50, 74, 0.18);
                padding-top: 2px;
                padding-left: 18px;
            }
            QLineEdit,
            QComboBox,
            QDoubleSpinBox,
            QTableWidget {
                background: #fbfcfd;
                border: 1px solid rgba(22, 50, 74, 0.14);
                border-radius: 0;
                padding: 8px 10px;
            }
            QLineEdit:focus,
            QComboBox:focus,
            QDoubleSpinBox:focus {
                border: 1px solid #1a7c76;
            }
            QComboBox {
                color: #173444;
                padding-right: 24px;
            }
            QComboBox QAbstractItemView {
                background: #fbfcfd;
                color: #5a717c;
                selection-background-color: #dfe8ec;
                selection-color: #173444;
                border: 1px solid rgba(22, 50, 74, 0.12);
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
            }
            QFrame#LogoBadge {
                background: transparent;
                border: none;
            }
            QLabel#LogoFallbackTitle {
                color: #173444;
                font-size: 18pt;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QLabel#LogoFallbackSubtitle {
                color: #7a8d97;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 2px;
            }
            """
        )
        self.set_badge_state(self.status_badge, self.status_badge.text(), "neutral")


def main() -> int:
    ensure_runtime_dirs()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("분로리엑터 설계 프로그램")
    app.setOrganizationName("UPTEC")
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 10))

    window = MainWindow()
    window.show()
    return app.exec()


__all__ = ["MainWindow", "main"]
