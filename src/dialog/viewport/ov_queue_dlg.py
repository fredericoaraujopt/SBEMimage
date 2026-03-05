from __future__ import annotations

import os

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import utils
from acq_guardrails import now_timestamp


class OVQueueDlg(QDialog):
    """Modeless OV queue/status panel for fast operator workflow."""

    def __init__(self, ovm, viewport):
        super().__init__(viewport)
        self.ovm = ovm
        self.viewport = viewport
        self.setWindowTitle('OV Queue')
        self.setWindowIcon(utils.get_window_icon())
        self.setWindowModality(Qt.NonModal)
        self.resize(620, 340)

        root = QVBoxLayout(self)
        root.addWidget(QLabel('Overviews (active state, acquisition status, lock state)'))

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ['OV', 'Active', 'Imaged', 'Last Result', 'Last Timestamp', 'Locked'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)

        row = QHBoxLayout()
        self.button_refresh = QPushButton('Refresh')
        self.button_toggle_active = QPushButton('Activate/Deactivate')
        self.button_acquire = QPushButton('Acquire Selected')
        self.button_clear = QPushButton('Clear Image')
        self.button_delete = QPushButton('Delete')
        row.addWidget(self.button_refresh)
        row.addWidget(self.button_toggle_active)
        row.addWidget(self.button_acquire)
        row.addWidget(self.button_clear)
        row.addWidget(self.button_delete)
        root.addLayout(row)

        self.button_refresh.clicked.connect(self.refresh_table)
        self.button_toggle_active.clicked.connect(self.toggle_active)
        self.button_acquire.clicked.connect(self.acquire_selected)
        self.button_clear.clicked.connect(self.clear_selected)
        self.button_delete.clicked.connect(self.delete_selected)

        self.refresh_table()

    def selected_ov_index(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.text().replace('OV ', '').strip())
        except Exception:
            return None

    def refresh_table(self):
        self.table.setRowCount(self.ovm.number_ov)
        for ov_index in range(self.ovm.number_ov):
            ov = self.ovm[ov_index]
            has_image = bool(ov.vp_file_path and os.path.isfile(ov.vp_file_path))
            values = [
                f'OV {ov_index}',
                'yes' if ov.active else 'no',
                'yes' if has_image or ov.acquired else 'no',
                ov.last_acquisition_result or 'not_imaged',
                ov.last_acquisition_timestamp or '',
                'yes' if ov.locked else 'no',
            ]
            for col, value in enumerate(values):
                self.table.setItem(ov_index, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()

    def toggle_active(self):
        ov_index = self.selected_ov_index()
        if ov_index is None:
            return
        ov = self.ovm[ov_index]
        ov.active = not ov.active
        self.viewport.main_controls_trigger.transmit('OV SETTINGS CHANGED')
        self.viewport.vp_draw()
        self.refresh_table()

    def acquire_selected(self):
        ov_index = self.selected_ov_index()
        if ov_index is None:
            return
        self.viewport.vp_acquire_specific_overview(ov_index)
        self.refresh_table()

    def clear_selected(self):
        ov_index = self.selected_ov_index()
        if ov_index is None:
            return
        ov = self.ovm[ov_index]
        ov.vp_file_path = ''
        ov.mark_not_acquired(result='cleared', timestamp=now_timestamp())
        self.viewport.vp_draw()
        self.refresh_table()

    def delete_selected(self):
        ov_index = self.selected_ov_index()
        if ov_index is None:
            return
        if ov_index == 0:
            QMessageBox.information(
                self,
                'OV 0 protected',
                'OV 0 is a persistent anchor and cannot be deleted.',
                QMessageBox.Ok,
            )
            return
        if ov_index != self.ovm.number_ov - 1:
            QMessageBox.information(
                self,
                'Delete order',
                'For consistency, only the highest OV index can be deleted.',
                QMessageBox.Ok,
            )
            return
        result = QMessageBox.question(
            self,
            'Delete overview',
            f'Delete OV {ov_index}?',
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if result != QMessageBox.Ok:
            return
        self.ovm.delete_overview()
        self.viewport.main_controls_trigger.transmit('OV SETTINGS CHANGED')
        self.viewport.vp_draw()
        self.refresh_table()
