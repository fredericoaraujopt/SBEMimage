from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import utils


FIELD_ORDER_OVERVIEW = (
    'frame_size_selector',
    'pixel_size',
    'dwell_time_selector',
    'bit_depth_selector',
    'acq_interval',
    'acq_interval_offset',
)

FIELD_ORDER_GRID = FIELD_ORDER_OVERVIEW + (
    'overlap',
    'row_shift',
)


class BatchImagingSettingsDlg(QDialog):
    """Apply selected imaging-setting fields to many grids or overviews."""

    def __init__(self, kind, sem, source_values, target_label, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.sem = sem
        self.source_values = dict(source_values)
        self.target_label = str(target_label)
        self._field_widgets = {}
        self._field_checks = {}

        self.setWindowTitle('Batch imaging settings')
        self.setWindowIcon(utils.get_window_icon())
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(440, 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        intro = QLabel(
            f'Apply imaging settings to {self.target_label}.\n'
            'Only checked fields will be propagated. Unchecked fields stay unchanged.')
        intro.setWordWrap(True)
        root.addWidget(intro)

        if self.kind == 'grid':
            note = QLabel(
                'Grid layout changes still follow the fixed-footprint rule: '
                'changing frame size, pixel size, overlap, or row shift will '
                're-derive rows/columns inside the existing footprint.')
            note.setWordWrap(True)
            root.addWidget(note)

        controls_row = QHBoxLayout()
        button_check_all = QPushButton('Check all')
        button_clear_all = QPushButton('Clear all')
        controls_row.addWidget(button_check_all)
        controls_row.addWidget(button_clear_all)
        controls_row.addStretch(1)
        root.addLayout(controls_row)

        group_box = QGroupBox('Fields to propagate', self)
        form = QFormLayout(group_box)
        form.setContentsMargins(10, 12, 10, 10)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(group_box)

        for field_name in self._field_order():
            check = QCheckBox(group_box)
            editor = self._make_editor(field_name, group_box)
            self._field_checks[field_name] = check
            self._field_widgets[field_name] = editor
            row_widget = QWidget(group_box)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(check)
            row_layout.addWidget(editor, 1)
            form.addRow(self._field_label(field_name), row_widget)
            self._connect_editor(field_name, editor, check)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        root.addWidget(button_box)

        button_check_all.clicked.connect(self._check_all_fields)
        button_clear_all.clicked.connect(self._clear_all_fields)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _field_order(self):
        if self.kind == 'grid':
            return FIELD_ORDER_GRID
        return FIELD_ORDER_OVERVIEW

    def _field_label(self, field_name):
        labels = {
            'frame_size_selector': 'Frame size',
            'pixel_size': 'Pixel size (nm)',
            'dwell_time_selector': 'Dwell time',
            'bit_depth_selector': 'Bit depth',
            'acq_interval': 'Acquire interval',
            'acq_interval_offset': 'Acquire interval offset',
            'overlap': 'Tile overlap (px)',
            'row_shift': 'Row shift (px)',
        }
        return labels[field_name]

    def _make_editor(self, field_name, parent):
        if field_name == 'frame_size_selector':
            editor = QComboBox(parent)
            editor.addItems(
                [f'{res[0]} x {res[1]}' for res in self.sem.STORE_RES])
            editor.setCurrentIndex(int(self.source_values[field_name]))
            return editor
        if field_name == 'dwell_time_selector':
            editor = QComboBox(parent)
            editor.addItems([str(value) for value in self.sem.DWELL_TIME])
            editor.setCurrentIndex(int(self.source_values[field_name]))
            return editor
        if field_name == 'bit_depth_selector':
            editor = QComboBox(parent)
            editor.addItems(['8 bit', '16 bit'])
            editor.setCurrentIndex(int(self.source_values[field_name]))
            return editor
        if field_name == 'pixel_size':
            editor = QDoubleSpinBox(parent)
            editor.setDecimals(3)
            editor.setRange(0.001, 100000.0)
            editor.setValue(float(self.source_values[field_name]))
            return editor
        editor = QSpinBox(parent)
        if field_name in ('acq_interval',):
            editor.setRange(1, 100000)
        elif field_name in ('acq_interval_offset', 'row_shift'):
            editor.setRange(0, 100000)
        else:
            editor.setRange(-100000, 100000)
        editor.setValue(int(self.source_values[field_name]))
        return editor

    def _connect_editor(self, field_name, editor, checkbox):
        del field_name
        if isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(
                lambda *_: checkbox.setChecked(True))
        elif isinstance(editor, QDoubleSpinBox):
            editor.valueChanged.connect(
                lambda *_: checkbox.setChecked(True))
        elif isinstance(editor, QSpinBox):
            editor.valueChanged.connect(
                lambda *_: checkbox.setChecked(True))

    def _check_all_fields(self):
        for check in self._field_checks.values():
            check.setChecked(True)

    def _clear_all_fields(self):
        for check in self._field_checks.values():
            check.setChecked(False)

    def selected_values(self):
        values = {}
        for field_name in self._field_order():
            if not self._field_checks[field_name].isChecked():
                continue
            editor = self._field_widgets[field_name]
            if isinstance(editor, QComboBox):
                values[field_name] = editor.currentIndex()
            elif isinstance(editor, QDoubleSpinBox):
                values[field_name] = float(editor.value())
            elif isinstance(editor, QSpinBox):
                values[field_name] = int(editor.value())
        return values

    def accept(self):
        if not self.selected_values():
            self.reject()
            return
        super().accept()
