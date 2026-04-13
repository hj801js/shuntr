import os

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QAbstractSpinBox

from shunt_reactor_engineering.app import AdminSettingsDialog, MainWindow
from shunt_reactor_engineering.settings import load_settings


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_auto_compensation_updates_until_manual_override(qt_app: QApplication) -> None:
    window = MainWindow()
    try:
        assert window.compensation_input.value() == pytest.approx(2.0)
        assert "8.045 A/km" in window.metric_current.value_label.text()

        window.route_length_input.setValue(1.0)
        assert window.compensation_input.value() == pytest.approx(3.0)

        window.compensation_input.setValue(4.5)
        window.route_length_input.setValue(1.5)
        assert window.compensation_input.value() == pytest.approx(4.5)
        assert window.collect_input().compensation_mvar == pytest.approx(4.5)
    finally:
        window.close()


def test_admin_dialog_capacitance_editor_uses_numeric_input_only(qt_app: QApplication) -> None:
    dialog = AdminSettingsDialog(load_settings())
    try:
        spin = dialog.cable_table.cellWidget(0, 1)
        before_value = spin.value()
        wheel_event = QWheelEvent(
            QPointF(8.0, 8.0),
            QPointF(8.0, 8.0),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        spin.wheelEvent(wheel_event)

        assert spin.suffix() == ""
        assert spin.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
        assert dialog.cable_table.rowHeight(0) >= 48
        assert spin.value() == before_value
    finally:
        dialog.close()


def test_main_panels_start_at_same_top_offset(qt_app: QApplication) -> None:
    window = MainWindow()
    try:
        left_layout = window.left_panel.layout()
        right_layout = window.right_panel.layout()

        assert left_layout.contentsMargins().top() == 0
        assert right_layout.contentsMargins().top() == 0
    finally:
        window.close()


def test_logo_badge_is_anchored_in_top_right_header(qt_app: QApplication) -> None:
    window = MainWindow()
    try:
        top_card = window.right_panel.layout().itemAt(0).widget()
        header_row = top_card.layout().itemAt(0).layout()

        assert header_row.itemAt(2).widget() is window.logo_badge
    finally:
        window.close()


def test_busy_indicator_appears_while_generating(qt_app: QApplication) -> None:
    window = MainWindow()
    try:
        assert window.busy_row.isHidden() is True
        assert window.busy_spinner.is_spinning() is False
        assert window.generate_button.text() == "PDF 생성"

        window.set_busy_state(True)

        assert window.busy_row.isHidden() is False
        assert window.busy_spinner.is_spinning() is True
        assert window.generate_button.text() == "PDF 생성 중"

        window.set_busy_state(False)

        assert window.busy_row.isHidden() is True
        assert window.busy_spinner.is_spinning() is False
        assert window.generate_button.text() == "PDF 생성"
    finally:
        window.close()
