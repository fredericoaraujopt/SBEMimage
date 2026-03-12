from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import utils
from ImagingConditions import (
    ImagingConditionDuplicateNameError,
    ImagingConditionPreset,
)


class ImagingConditionEditDialog(QDialog):
    def __init__(self, preset, parent=None):
        super().__init__(parent)
        self.preset = preset
        self.setWindowTitle('Edit Imaging Condition')
        self.setWindowIcon(utils.get_window_icon())
        self.setWindowModality(Qt.ApplicationModal)

        root = QVBoxLayout(self)
        summary = QLabel(
            f'Source: {preset.source_dialog} | '
            f'SEM: {preset.source_sem_device}')
        root.addWidget(summary)

        form = QFormLayout()
        self.lineEdit_name = QLineEdit(preset.name)
        self.spinBox_frameWidth = QSpinBox()
        self.spinBox_frameWidth.setRange(1, 1000000)
        self.spinBox_frameWidth.setValue(int(preset.frame_size_px[0]))
        self.spinBox_frameHeight = QSpinBox()
        self.spinBox_frameHeight.setRange(1, 1000000)
        self.spinBox_frameHeight.setValue(int(preset.frame_size_px[1]))
        self.doubleSpinBox_pixelSize = QDoubleSpinBox()
        self.doubleSpinBox_pixelSize.setDecimals(4)
        self.doubleSpinBox_pixelSize.setRange(0.0001, 1000000)
        self.doubleSpinBox_pixelSize.setValue(float(preset.pixel_size_nm))
        self.doubleSpinBox_dwellTime = QDoubleSpinBox()
        self.doubleSpinBox_dwellTime.setDecimals(6)
        self.doubleSpinBox_dwellTime.setRange(0.000001, 1000000)
        self.doubleSpinBox_dwellTime.setValue(float(preset.dwell_time_us))

        form.addRow('Name:', self.lineEdit_name)
        form.addRow('Frame width (px):', self.spinBox_frameWidth)
        form.addRow('Frame height (px):', self.spinBox_frameHeight)
        form.addRow('Pixel size (nm):', self.doubleSpinBox_pixelSize)
        form.addRow('Dwell time (us):', self.doubleSpinBox_dwellTime)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setMinimumWidth(360)

    def edited_preset(self):
        return ImagingConditionPreset(
            name=self.lineEdit_name.text().strip(),
            source_dialog=self.preset.source_dialog,
            source_sem_device=self.preset.source_sem_device,
            frame_size_px=[
                self.spinBox_frameWidth.value(),
                self.spinBox_frameHeight.value(),
            ],
            pixel_size_nm=self.doubleSpinBox_pixelSize.value(),
            dwell_time_us=self.doubleSpinBox_dwellTime.value(),
        )


class ImagingConditionManagerDlg(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle('Manage Imaging Conditions')
        self.setWindowIcon(utils.get_window_icon())
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(760, 360)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            'Saved imaging conditions are shared for this SBEMimage '
            'installation.'))

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ['Name', 'Source', 'Frame Size', 'Pixel Size (nm)',
             'Dwell (us)', 'SEM'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)

        button_row = QHBoxLayout()
        self.pushButton_edit = QPushButton('Edit...')
        self.pushButton_duplicate = QPushButton('Duplicate...')
        self.pushButton_delete = QPushButton('Delete')
        button_row.addWidget(self.pushButton_edit)
        button_row.addWidget(self.pushButton_duplicate)
        button_row.addWidget(self.pushButton_delete)
        button_row.addStretch(1)
        root.addLayout(button_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

        self.pushButton_edit.clicked.connect(self.edit_selected)
        self.pushButton_duplicate.clicked.connect(self.duplicate_selected)
        self.pushButton_delete.clicked.connect(self.delete_selected)

        self.refresh_table()

    def refresh_table(self, selected_preset_id=None):
        presets = self.store.list_presets()
        self.table.setRowCount(len(presets))
        selected_row = 0 if presets else -1
        for row, preset in enumerate(presets):
            values = [
                preset.name,
                preset.source_dialog,
                f'{preset.frame_size_px[0]} x {preset.frame_size_px[1]}',
                f'{preset.pixel_size_nm:.4f}',
                f'{preset.dwell_time_us:.6f}',
                preset.source_sem_device,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, preset.preset_id)
                self.table.setItem(row, col, item)
            if preset.preset_id == selected_preset_id:
                selected_row = row
        self.table.resizeColumnsToContents()
        if selected_row >= 0:
            self.table.selectRow(selected_row)

    def selected_preset_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def selected_preset(self):
        preset_id = self.selected_preset_id()
        if preset_id is None:
            return None
        return self.store.get_preset(preset_id)

    def _warn(self, title, message):
        QMessageBox.warning(self, title, message, QMessageBox.Ok)

    def edit_selected(self):
        preset = self.selected_preset()
        if preset is None:
            self._warn(
                'No imaging condition selected',
                'Please select a saved imaging condition first.')
            return
        dialog = ImagingConditionEditDialog(preset, self)
        if not dialog.exec():
            return
        updated = dialog.edited_preset()
        try:
            updated = self.store.update_preset(preset.preset_id, updated)
        except ImagingConditionDuplicateNameError as exc:
            self._warn('Duplicate name', str(exc))
            return
        except Exception as exc:
            self._warn('Preset could not be updated', str(exc))
            return
        self.refresh_table(updated.preset_id)

    def duplicate_selected(self):
        preset = self.selected_preset()
        if preset is None:
            self._warn(
                'No imaging condition selected',
                'Please select a saved imaging condition first.')
            return
        new_name, ok = QInputDialog.getText(
            self,
            'Duplicate imaging condition',
            'New preset name:',
            text=f'{preset.name} copy')
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            self._warn('Preset name required', 'Please provide a preset name.')
            return
        try:
            duplicated = self.store.duplicate_preset(preset.preset_id, new_name)
        except ImagingConditionDuplicateNameError as exc:
            self._warn('Duplicate name', str(exc))
            return
        except Exception as exc:
            self._warn('Preset could not be duplicated', str(exc))
            return
        self.refresh_table(duplicated.preset_id)

    def delete_selected(self):
        preset = self.selected_preset()
        if preset is None:
            self._warn(
                'No imaging condition selected',
                'Please select a saved imaging condition first.')
            return
        result = QMessageBox.question(
            self,
            'Delete imaging condition',
            f'Delete imaging condition "{preset.name}"?',
            QMessageBox.Ok | QMessageBox.Cancel)
        if result != QMessageBox.Ok:
            return
        try:
            self.store.delete_preset(preset.preset_id)
        except Exception as exc:
            self._warn('Preset could not be deleted', str(exc))
            return
        self.refresh_table()
