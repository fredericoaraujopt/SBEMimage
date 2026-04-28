import os
import numpy as np

from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QColor, QIcon, QPainter, QPixmap
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import constants
import utils
from dialog.viewport.BatchImagingSettingsDlg import BatchImagingSettingsDlg
from dialog.viewport.TileActivationMap import TileActivationMap


ROLE_KIND = Qt.UserRole
ROLE_IDENTIFIER = Qt.UserRole + 1

KIND_GROUP = 'group'
KIND_OVERVIEW = 'overview'
KIND_GRID = 'grid'
KIND_BUCKET_OVERVIEW = 'bucket_ov'
KIND_BUCKET_GRID = 'bucket_grid'

STATUS_ORDER = (
    ('active', 'Active', QColor(28, 152, 92)),
    ('locked', 'Locked', QColor(55, 71, 79)),
    ('acquired', 'Acquired', QColor(40, 118, 200)),
    ('failed', 'Failed', QColor(198, 40, 40)),
    ('deferred', 'Deferred', QColor(181, 116, 27)),
)

NON_FAILURE_RESULTS = {'', 'not_imaged', 'success', 'running', 'cleared'}

VIEW_PRESETS = {
    'All items': {
        'filter_active_only': False,
        'filter_locked_only': False,
        'filter_failed_only': False,
        'filter_current_group_only': False,
    },
    'Active review': {
        'filter_active_only': True,
        'filter_locked_only': False,
        'filter_failed_only': False,
        'filter_current_group_only': False,
    },
    'Locked review': {
        'filter_active_only': False,
        'filter_locked_only': True,
        'filter_failed_only': False,
        'filter_current_group_only': False,
    },
    'Failure triage': {
        'filter_active_only': False,
        'filter_locked_only': False,
        'filter_failed_only': True,
        'filter_current_group_only': False,
    },
    'Current group focus': {
        'filter_active_only': False,
        'filter_locked_only': False,
        'filter_failed_only': False,
        'filter_current_group_only': True,
    },
}


class AcquisitionTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drop_callback = None

    def set_drop_callback(self, callback):
        self._drop_callback = callback

    def dropEvent(self, event):
        super().dropEvent(event)
        if self._drop_callback is not None:
            QTimer.singleShot(0, self._drop_callback)


class AcquisitionManagerDlg(QDialog):
    """Modeless tree/inspector dialog for acquisition grouping."""

    def __init__(self, acq_groups, viewport):
        super().__init__(viewport)
        self.acq_groups = acq_groups
        self.viewport = viewport
        self.gm = viewport.gm
        self.ovm = viewport.ovm
        self.acq = viewport.acq
        self.autofocus = viewport.autofocus

        self._tree_refreshing = False
        self._inspector_refreshing = False
        self._filter_refreshing = False
        self._item_index = {}
        self._current_grid_for_tile_map = None
        self._last_current_group_filter_id = None

        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle('Acquisition manager')
        self.setWindowIcon(utils.get_window_icon())
        self.setWindowModality(Qt.NonModal)
        self.resize(1080, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QLabel(
            'Organize grids and overviews into visual groups. '
            'Groups control active state and colour only; acquisition order stays unchanged.')
        header.setWordWrap(True)
        root.addWidget(header)

        toolbar = QHBoxLayout()
        self.button_new_group = QPushButton('New group')
        self.button_new_subgroup = QPushButton('New subgroup')
        self.button_delete_group = QPushButton('Delete group')
        self.button_refresh = QPushButton('Refresh')
        toolbar.addWidget(self.button_new_group)
        toolbar.addWidget(self.button_new_subgroup)
        toolbar.addWidget(self.button_delete_group)
        toolbar.addStretch(1)
        toolbar.addWidget(self.button_refresh)
        root.addLayout(toolbar)

        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel('Workflow preset:'))
        self.combo_view_preset = QComboBox(self)
        self.combo_view_preset.addItems(list(VIEW_PRESETS) + ['Custom'])
        self.checkBox_filterActive = QCheckBox('Show only active', self)
        self.checkBox_filterLocked = QCheckBox('Only locked', self)
        self.checkBox_filterFailed = QCheckBox('Only failed', self)
        self.checkBox_filterCurrentGroup = QCheckBox('Only current group', self)
        filter_bar.addWidget(self.combo_view_preset)
        filter_bar.addSpacing(8)
        filter_bar.addWidget(self.checkBox_filterActive)
        filter_bar.addWidget(self.checkBox_filterLocked)
        filter_bar.addWidget(self.checkBox_filterFailed)
        filter_bar.addWidget(self.checkBox_filterCurrentGroup)
        filter_bar.addStretch(1)
        root.addLayout(filter_bar)

        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.tree = AcquisitionTreeWidget(left_panel)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(['Item', 'Status'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        left_layout.addWidget(self.tree, 1)
        tree_hint = QLabel(
            'Use Shift-click or Ctrl-click to select multiple rows. Drag selected grids or overviews onto a group to assign them together. '
            'Drop them onto an ungrouped bucket to remove the assignment. The status column shows active, locked, acquired, failed, and deferred state.')
        tree_hint.setWordWrap(True)
        left_layout.addWidget(tree_hint)
        splitter.addWidget(left_panel)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.inspector_stack = QStackedWidget(right_panel)
        right_layout.addWidget(self.inspector_stack, 1)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([410, 570])

        self._build_placeholder_page()
        self._build_group_page()
        self._build_overview_page()
        self._build_grid_page()

        self.button_new_group.clicked.connect(self._create_group)
        self.button_new_subgroup.clicked.connect(self._create_subgroup)
        self.button_delete_group.clicked.connect(self._delete_selected_group)
        self.button_refresh.clicked.connect(self.refresh_view)
        self.combo_view_preset.currentTextChanged.connect(
            self._preset_changed)
        self.checkBox_filterActive.toggled.connect(self._filter_state_changed)
        self.checkBox_filterLocked.toggled.connect(self._filter_state_changed)
        self.checkBox_filterFailed.toggled.connect(self._filter_state_changed)
        self.checkBox_filterCurrentGroup.toggled.connect(
            self._filter_state_changed)
        self.tree.itemChanged.connect(self._tree_item_changed)
        self.tree.currentItemChanged.connect(self._tree_current_item_changed)
        self.tree.itemSelectionChanged.connect(self._tree_selection_changed)
        self.tree.itemExpanded.connect(self._tree_item_expanded)
        self.tree.itemCollapsed.connect(self._tree_item_collapsed)
        self.tree.set_drop_callback(self._tree_reordered)
        self.tree.customContextMenuRequested.connect(
            self._open_tree_context_menu)

        self._load_filter_state()
        self.refresh_view()

    def _build_placeholder_page(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.placeholder_title = QLabel('Selection')
        self.placeholder_title.setStyleSheet('font-weight: bold;')
        self.placeholder_body = QLabel('')
        self.placeholder_body.setWordWrap(True)
        layout.addWidget(self.placeholder_title)
        layout.addWidget(self._make_separator())
        layout.addWidget(self.placeholder_body)
        layout.addStretch(1)
        self.page_placeholder = page
        self.inspector_stack.addWidget(page)

    def _build_group_page(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.group_title = QLabel('Group')
        self.group_title.setStyleSheet('font-weight: bold;')
        layout.addWidget(self.group_title)
        layout.addWidget(self._make_separator())

        settings_box = QGroupBox('Group settings', page)
        settings_form = QFormLayout(settings_box)
        settings_form.setContentsMargins(10, 12, 10, 10)
        self.group_name_edit = QLineEdit(settings_box)
        self.group_colour_combo = QComboBox(settings_box)
        for colour_index in range(10):
            self.group_colour_combo.addItem(
                self._colour_icon(colour_index),
                f'Colour {colour_index}')
        settings_form.addRow('Name', self.group_name_edit)
        settings_form.addRow('Colour', self.group_colour_combo)
        layout.addWidget(settings_box)

        summary_box = QGroupBox('Summary', page)
        summary_form = QFormLayout(summary_box)
        summary_form.setContentsMargins(10, 12, 10, 10)
        self.group_parent_label = self._value_label()
        self.group_path_label = self._value_label()
        self.group_active_ov_label = self._value_label()
        self.group_active_grid_label = self._value_label()
        self.group_active_tiles_label = self._value_label()
        self.group_locked_label = self._value_label()
        self.group_acquired_label = self._value_label()
        self.group_intervallic_label = self._value_label()
        summary_form.addRow('Parent', self.group_parent_label)
        summary_form.addRow('Path', self.group_path_label)
        summary_form.addRow('Active overviews', self.group_active_ov_label)
        summary_form.addRow('Active grids', self.group_active_grid_label)
        summary_form.addRow('Active tiles', self.group_active_tiles_label)
        summary_form.addRow('Locked items', self.group_locked_label)
        summary_form.addRow('Acquired items', self.group_acquired_label)
        summary_form.addRow('Intervallic items', self.group_intervallic_label)
        layout.addWidget(summary_box)

        self.group_slice_note = QLabel('')
        self.group_slice_note.setWordWrap(True)
        layout.addWidget(self.group_slice_note)

        group_button_row = QHBoxLayout()
        self.button_group_new_subgroup = QPushButton('New subgroup')
        self.button_group_delete = QPushButton('Delete group')
        self.button_group_refresh = QPushButton('Refresh')
        group_button_row.addWidget(self.button_group_new_subgroup)
        group_button_row.addWidget(self.button_group_delete)
        group_button_row.addStretch(1)
        group_button_row.addWidget(self.button_group_refresh)
        layout.addLayout(group_button_row)

        self.group_execution_note = QLabel('')
        self.group_execution_note.setWordWrap(True)
        layout.addWidget(self.group_execution_note)
        layout.addStretch(1)

        self.button_group_new_subgroup.clicked.connect(self._create_subgroup)
        self.button_group_delete.clicked.connect(self._delete_selected_group)
        self.button_group_refresh.clicked.connect(self.refresh_view)
        self.group_name_edit.editingFinished.connect(self._group_name_edited)
        self.group_colour_combo.currentIndexChanged.connect(
            self._group_colour_changed)

        self.page_group = page
        self.inspector_stack.addWidget(page)

    def _build_overview_page(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.ov_title = QLabel('Overview')
        self.ov_title.setStyleSheet('font-weight: bold;')
        layout.addWidget(self.ov_title)
        layout.addWidget(self._make_separator())

        row_top = QHBoxLayout()
        self.button_ov_open = QPushButton('Open settings')
        self.button_ov_acquire = QPushButton('Acquire selected')
        self.button_ov_clear = QPushButton('Clear image')
        self.button_ov_lock = QPushButton('Lock')
        row_top.addWidget(self.button_ov_open)
        row_top.addWidget(self.button_ov_acquire)
        row_top.addWidget(self.button_ov_clear)
        row_top.addWidget(self.button_ov_lock)
        layout.addLayout(row_top)

        row_bottom = QHBoxLayout()
        self.button_ov_delete = QPushButton('Delete')
        self.button_ov_refresh = QPushButton('Refresh')
        row_bottom.addWidget(self.button_ov_delete)
        row_bottom.addStretch(1)
        row_bottom.addWidget(self.button_ov_refresh)
        layout.addLayout(row_bottom)

        details_box = QGroupBox('Overview details', page)
        details_form = QFormLayout(details_box)
        details_form.setContentsMargins(10, 12, 10, 10)
        self.ov_group_label = self._value_label()
        self.ov_status_label = self._value_label()
        self.ov_last_result_label = self._value_label()
        self.ov_last_timestamp_label = self._value_label()
        self.ov_frame_size_label = self._value_label()
        self.ov_pixel_size_label = self._value_label()
        self.ov_dwell_time_label = self._value_label()
        self.ov_interval_label = self._value_label()
        self.ov_image_label = self._value_label()
        details_form.addRow('Group', self.ov_group_label)
        details_form.addRow('Status', self.ov_status_label)
        details_form.addRow('Last result', self.ov_last_result_label)
        details_form.addRow('Last timestamp', self.ov_last_timestamp_label)
        details_form.addRow('Frame size', self.ov_frame_size_label)
        details_form.addRow('Pixel size', self.ov_pixel_size_label)
        details_form.addRow('Dwell time', self.ov_dwell_time_label)
        details_form.addRow('Acquire interval', self.ov_interval_label)
        details_form.addRow('Viewport image', self.ov_image_label)
        layout.addWidget(details_box)
        layout.addStretch(1)

        self.button_ov_open.clicked.connect(self._open_selected_overview_settings)
        self.button_ov_acquire.clicked.connect(self._acquire_selected_overview)
        self.button_ov_clear.clicked.connect(self._clear_selected_overview)
        self.button_ov_lock.clicked.connect(self._toggle_selected_overview_lock)
        self.button_ov_delete.clicked.connect(self._delete_selected_overview)
        self.button_ov_refresh.clicked.connect(self.refresh_view)

        self.page_overview = page
        self.inspector_stack.addWidget(page)

    def _build_grid_page(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.grid_title = QLabel('Grid')
        self.grid_title.setStyleSheet('font-weight: bold;')
        layout.addWidget(self.grid_title)
        layout.addWidget(self._make_separator())

        row_top = QHBoxLayout()
        self.button_grid_open = QPushButton('Open settings')
        self.button_grid_acquire = QPushButton('Acquire selected')
        self.button_grid_clear = QPushButton('Clear previews')
        self.button_grid_lock = QPushButton('Lock')
        row_top.addWidget(self.button_grid_open)
        row_top.addWidget(self.button_grid_acquire)
        row_top.addWidget(self.button_grid_clear)
        row_top.addWidget(self.button_grid_lock)
        layout.addLayout(row_top)

        row_bottom = QHBoxLayout()
        self.button_grid_delete = QPushButton('Delete')
        self.button_grid_select_all = QPushButton('Select all tiles')
        self.button_grid_deselect_all = QPushButton('Deselect all tiles')
        self.button_grid_refresh = QPushButton('Refresh')
        row_bottom.addWidget(self.button_grid_delete)
        row_bottom.addWidget(self.button_grid_select_all)
        row_bottom.addWidget(self.button_grid_deselect_all)
        row_bottom.addStretch(1)
        row_bottom.addWidget(self.button_grid_refresh)
        layout.addLayout(row_bottom)

        details_box = QGroupBox('Grid details', page)
        details_form = QFormLayout(details_box)
        details_form.setContentsMargins(10, 12, 10, 10)
        self.grid_group_label = self._value_label()
        self.grid_status_label = self._value_label()
        self.grid_last_result_label = self._value_label()
        self.grid_last_timestamp_label = self._value_label()
        self.grid_size_label = self._value_label()
        self.grid_frame_size_label = self._value_label()
        self.grid_pixel_size_label = self._value_label()
        self.grid_dwell_time_label = self._value_label()
        self.grid_interval_label = self._value_label()
        self.grid_active_tiles_label = self._value_label()
        details_form.addRow('Group', self.grid_group_label)
        details_form.addRow('Status', self.grid_status_label)
        details_form.addRow('Last result', self.grid_last_result_label)
        details_form.addRow('Last timestamp', self.grid_last_timestamp_label)
        details_form.addRow('Grid size', self.grid_size_label)
        details_form.addRow('Frame size', self.grid_frame_size_label)
        details_form.addRow('Pixel size', self.grid_pixel_size_label)
        details_form.addRow('Dwell time', self.grid_dwell_time_label)
        details_form.addRow('Acquire interval', self.grid_interval_label)
        details_form.addRow('Active tiles', self.grid_active_tiles_label)
        layout.addWidget(details_box)

        tile_box = QGroupBox('Tile activation map', page)
        tile_layout = QVBoxLayout(tile_box)
        tile_layout.setContentsMargins(10, 12, 10, 10)
        self.tile_map = TileActivationMap(tile_box)
        self.tile_map_note = QLabel('')
        self.tile_map_note.setWordWrap(True)
        self.tile_map.set_changed_callback(self._tile_map_changed)
        tile_layout.addWidget(self.tile_map, 1)
        tile_layout.addWidget(self.tile_map_note)
        layout.addWidget(tile_box, 1)

        self.button_grid_open.clicked.connect(self._open_selected_grid_settings)
        self.button_grid_acquire.clicked.connect(self._acquire_selected_grid)
        self.button_grid_clear.clicked.connect(self._clear_selected_grid)
        self.button_grid_lock.clicked.connect(self._toggle_selected_grid_lock)
        self.button_grid_delete.clicked.connect(self._delete_selected_grid)
        self.button_grid_select_all.clicked.connect(self._select_all_tiles)
        self.button_grid_deselect_all.clicked.connect(self._deselect_all_tiles)
        self.button_grid_refresh.clicked.connect(self.refresh_view)

        self.page_grid = page
        self.inspector_stack.addWidget(page)

    def _make_separator(self):
        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _value_label(self):
        label = QLabel('')
        label.setWordWrap(True)
        return label

    def _colour_icon(self, colour_index):
        pixmap = QPixmap(18, 12)
        pixmap.fill(QColor(*constants.COLOUR_SELECTOR[colour_index]))
        return QIcon(pixmap)

    def _item_key(self, kind, identifier):
        return f'{kind}:{identifier}'

    def _selected_item(self):
        return self.tree.currentItem()

    def _selected_items(self):
        return self.tree.selectedItems()

    def _selected_item_key(self):
        item = self._selected_item()
        if item is None:
            return None
        return self._item_key(
            item.data(0, ROLE_KIND),
            item.data(0, ROLE_IDENTIFIER))

    def _selected_kind_identifier_pairs(self):
        return [
            (item.data(0, ROLE_KIND), item.data(0, ROLE_IDENTIFIER))
            for item in self._selected_items()]

    def _selected_indices(self, kind):
        return [
            identifier
            for item_kind, identifier in self._selected_kind_identifier_pairs()
            if item_kind == kind]

    def _selection_summary(self):
        summary = {
            KIND_GROUP: 0,
            KIND_OVERVIEW: 0,
            KIND_GRID: 0,
            KIND_BUCKET_OVERVIEW: 0,
            KIND_BUCKET_GRID: 0,
        }
        for kind, _ in self._selected_kind_identifier_pairs():
            summary[kind] = summary.get(kind, 0) + 1
        return summary

    def _filter_state(self):
        return {
            'view_preset': self.combo_view_preset.currentText(),
            'filter_active_only': self.checkBox_filterActive.isChecked(),
            'filter_locked_only': self.checkBox_filterLocked.isChecked(),
            'filter_failed_only': self.checkBox_filterFailed.isChecked(),
            'filter_current_group_only': (
                self.checkBox_filterCurrentGroup.isChecked()),
        }

    def _load_filter_state(self):
        state = self.acq_groups.load_ui_state()
        self._filter_refreshing = True
        self.checkBox_filterActive.setChecked(state['filter_active_only'])
        self.checkBox_filterLocked.setChecked(state['filter_locked_only'])
        self.checkBox_filterFailed.setChecked(state['filter_failed_only'])
        self.checkBox_filterCurrentGroup.setChecked(
            state['filter_current_group_only'])
        preset_name = state['view_preset']
        if preset_name not in VIEW_PRESETS and preset_name != 'Custom':
            preset_name = self._matching_view_preset_name() or 'Custom'
        self.combo_view_preset.setCurrentText(preset_name)
        self._filter_refreshing = False

    def _save_filter_state(self):
        self.acq_groups.save_ui_state(self._filter_state())

    def _matching_view_preset_name(self):
        current_flags = {
            'filter_active_only': self.checkBox_filterActive.isChecked(),
            'filter_locked_only': self.checkBox_filterLocked.isChecked(),
            'filter_failed_only': self.checkBox_filterFailed.isChecked(),
            'filter_current_group_only': (
                self.checkBox_filterCurrentGroup.isChecked()),
        }
        for name, flags in VIEW_PRESETS.items():
            if flags == current_flags:
                return name
        return None

    def _filters_active(self):
        return any([
            self.checkBox_filterActive.isChecked(),
            self.checkBox_filterLocked.isChecked(),
            self.checkBox_filterFailed.isChecked(),
            self.checkBox_filterCurrentGroup.isChecked(),
        ])

    def _tree_reorder_enabled(self):
        return self._is_mutating_enabled() and not self._filters_active()

    def _preset_changed(self, preset_name):
        if self._filter_refreshing:
            return
        if preset_name in VIEW_PRESETS:
            self._filter_refreshing = True
            flags = VIEW_PRESETS[preset_name]
            self.checkBox_filterActive.setChecked(flags['filter_active_only'])
            self.checkBox_filterLocked.setChecked(flags['filter_locked_only'])
            self.checkBox_filterFailed.setChecked(flags['filter_failed_only'])
            self.checkBox_filterCurrentGroup.setChecked(
                flags['filter_current_group_only'])
            self._filter_refreshing = False
        self._save_filter_state()
        self.refresh_view()

    def _filter_state_changed(self):
        if self._filter_refreshing:
            return
        self._filter_refreshing = True
        self.combo_view_preset.setCurrentText(
            self._matching_view_preset_name() or 'Custom')
        self._filter_refreshing = False
        self._save_filter_state()
        self.refresh_view()

    def _current_filter_group_id(self):
        if not self.checkBox_filterCurrentGroup.isChecked():
            return None
        current = self._selected_item()
        if current is None:
            return None
        kind = current.data(0, ROLE_KIND)
        identifier = current.data(0, ROLE_IDENTIFIER)
        if kind == KIND_GROUP:
            return identifier
        if kind == KIND_OVERVIEW:
            return self._overview_group_id_cached(identifier)
        if kind == KIND_GRID:
            return self._grid_group_id_cached(identifier)
        return None

    def _overview_group_id_cached(self, ov_index):
        if 0 <= ov_index < len(self.acq_groups._ov_group_ids):
            return self.acq_groups._ov_group_ids[ov_index]
        return None

    def _grid_group_id_cached(self, grid_index):
        if 0 <= grid_index < len(self.acq_groups._grid_group_ids):
            return self.acq_groups._grid_group_ids[grid_index]
        return None

    def _result_failed(self, result_text):
        return str(result_text or '').strip().lower() not in NON_FAILURE_RESULTS

    def _status_state(self, kind, identifier):
        if kind == KIND_OVERVIEW:
            overview = self.ovm[identifier]
            return {
                'active': bool(overview.active),
                'locked': bool(overview.locked),
                'acquired': bool(overview.acquired),
                'failed': self._result_failed(overview.last_acquisition_result),
                'deferred': False,
            }
        if kind == KIND_GRID:
            grid = self.gm[identifier]
            return {
                'active': bool(grid.active),
                'locked': bool(grid.locked),
                'acquired': bool(grid.acquired),
                'failed': self._result_failed(grid.last_acquisition_result),
                'deferred': bool(grid.is_deferred_polygon_roi()),
            }
        return {name: False for name, _, _ in STATUS_ORDER}

    def _status_icon(self, status_state):
        pixmap = QPixmap(86, 14)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        x_pos = 3
        for name, _, colour in STATUS_ORDER:
            enabled = bool(status_state.get(name))
            fill_colour = colour if enabled else QColor(200, 200, 200, 70)
            pen_colour = colour if enabled else QColor(170, 170, 170, 120)
            painter.setPen(pen_colour)
            painter.setBrush(fill_colour)
            painter.drawEllipse(x_pos, 3, 8, 8)
            x_pos += 15
        painter.end()
        return QIcon(pixmap)

    def _status_tooltip(self, status_state):
        labels = [
            label.lower()
            for name, label, _ in STATUS_ORDER
            if status_state.get(name)]
        if not labels:
            return 'No active status flags.'
        return ', '.join(labels)

    def _register_item(self, item, kind, identifier):
        item.setData(0, ROLE_KIND, kind)
        item.setData(0, ROLE_IDENTIFIER, identifier)
        self._item_index[self._item_key(kind, identifier)] = item

    def _is_mutating_enabled(self):
        return not (self.viewport.busy or self.acq.acq_in_progress)

    def _bucket_flags(self):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._tree_reorder_enabled():
            flags |= Qt.ItemIsDropEnabled
        return flags

    def _group_flags(self):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._is_mutating_enabled():
            flags |= Qt.ItemIsUserCheckable
        if self._tree_reorder_enabled():
            flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return flags

    def _leaf_flags(self):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._is_mutating_enabled():
            flags |= Qt.ItemIsUserCheckable
        if self._tree_reorder_enabled():
            flags |= Qt.ItemIsDragEnabled
        return flags

    def _item_matches_filters(self, kind, identifier):
        current_group_id = self._current_filter_group_id()
        if current_group_id is not None:
            allowed_group_ids = {
                current_group_id,
                *self.acq_groups.descendant_group_ids(current_group_id),
            }
            if kind == KIND_OVERVIEW:
                if self._overview_group_id_cached(identifier) not in allowed_group_ids:
                    return False
            elif kind == KIND_GRID:
                if self._grid_group_id_cached(identifier) not in allowed_group_ids:
                    return False
            elif kind == KIND_GROUP and identifier not in allowed_group_ids:
                return False
        if kind == KIND_OVERVIEW:
            overview = self.ovm[identifier]
            if self.checkBox_filterActive.isChecked() and not overview.active:
                return False
            if self.checkBox_filterLocked.isChecked() and not overview.locked:
                return False
            if (self.checkBox_filterFailed.isChecked()
                    and not self._result_failed(overview.last_acquisition_result)):
                return False
            return True
        if kind == KIND_GRID:
            grid = self.gm[identifier]
            if self.checkBox_filterActive.isChecked() and not grid.active:
                return False
            if self.checkBox_filterLocked.isChecked() and not grid.locked:
                return False
            if (self.checkBox_filterFailed.isChecked()
                    and not self._result_failed(grid.last_acquisition_result)):
                return False
            return True
        return True

    def _group_has_visible_content(self, group_id, visited=None):
        if not self._filters_active():
            return True
        current_group_id = self._current_filter_group_id()
        if (self.checkBox_filterCurrentGroup.isChecked()
                and group_id == current_group_id):
            return True
        if visited is None:
            visited = set()
        if group_id in visited:
            return False
        visited.add(group_id)
        for ov_index in self._group_direct_overview_indices(group_id):
            if self._item_matches_filters(KIND_OVERVIEW, ov_index):
                return True
        for grid_index in self._group_direct_grid_indices(group_id):
            if self._item_matches_filters(KIND_GRID, grid_index):
                return True
        for child_group_id in self.acq_groups.child_group_ids(group_id):
            if self._group_has_visible_content(child_group_id, visited):
                return True
        return False

    def _create_bucket_item(self, kind, title):
        item = QTreeWidgetItem([title, ''])
        item.setFlags(self._bucket_flags())
        self._register_item(item, kind, kind)
        return item

    def _group_direct_overview_indices(self, group_id):
        return [
            ov_index for ov_index in range(self.ovm.number_ov)
            if self._overview_group_id_cached(ov_index) == group_id
        ]

    def _group_direct_grid_indices(self, group_id):
        return [
            grid_index for grid_index in range(self.gm.number_grids)
            if self._grid_group_id_cached(grid_index) == group_id
        ]

    def _group_check_state(self, group_id):
        total_items = 0
        active_items = 0
        for ov_index in self.acq_groups.grouped_overview_indices(group_id):
            total_items += 1
            if self.ovm[ov_index].active:
                active_items += 1
        for grid_index in self.acq_groups.grouped_grid_indices(group_id):
            total_items += 1
            if self.gm[grid_index].active:
                active_items += 1
        if total_items == 0 or active_items == 0:
            return Qt.Unchecked
        if active_items == total_items:
            return Qt.Checked
        return Qt.PartiallyChecked

    def _create_group_item(self, group_id):
        group = self.acq_groups.group(group_id)
        item = QTreeWidgetItem([group['name'], ''])
        item.setFlags(self._group_flags())
        item.setCheckState(0, self._group_check_state(group_id))
        item.setIcon(0, self._colour_icon(group['colour']))
        item.setToolTip(0, self.acq_groups.group_path_text(group_id))
        self._register_item(item, KIND_GROUP, group_id)
        return item

    def _create_overview_item(self, ov_index):
        overview = self.ovm[ov_index]
        title = f'OV {ov_index}'
        if not overview.active:
            title += ' (inactive)'
        status_state = self._status_state(KIND_OVERVIEW, ov_index)
        item = QTreeWidgetItem([title, ''])
        item.setFlags(self._leaf_flags())
        item.setCheckState(0, Qt.Checked if overview.active else Qt.Unchecked)
        item.setIcon(1, self._status_icon(status_state))
        group_id = self._overview_group_id_cached(ov_index)
        if group_id is not None:
            group = self.acq_groups.group(group_id)
            if group is not None:
                item.setIcon(0, self._colour_icon(group['colour']))
        item.setToolTip(0, self.acq_groups.overview_group_path_text(ov_index))
        item.setToolTip(1, self._status_tooltip(status_state))
        self._register_item(item, KIND_OVERVIEW, ov_index)
        return item

    def _create_grid_item(self, grid_index):
        grid = self.gm[grid_index]
        title = grid.get_label(grid_index)
        if not grid.active:
            title += ' (inactive)'
        status_state = self._status_state(KIND_GRID, grid_index)
        item = QTreeWidgetItem([title, ''])
        item.setFlags(self._leaf_flags())
        item.setCheckState(0, Qt.Checked if grid.active else Qt.Unchecked)
        item.setIcon(1, self._status_icon(status_state))
        group_id = self._grid_group_id_cached(grid_index)
        if group_id is not None:
            group = self.acq_groups.group(group_id)
            if group is not None:
                item.setIcon(0, self._colour_icon(group['colour']))
        item.setToolTip(0, self.acq_groups.grid_group_path_text(grid_index))
        item.setToolTip(1, self._status_tooltip(status_state))
        self._register_item(item, KIND_GRID, grid_index)
        return item

    def _add_group_branch(self, parent_item, group_id):
        if not self._group_has_visible_content(group_id):
            return False
        group_item = self._create_group_item(group_id)
        parent_item.addChild(group_item)
        for child_group_id in self.acq_groups.child_group_ids(group_id):
            self._add_group_branch(group_item, child_group_id)
        for ov_index in self._group_direct_overview_indices(group_id):
            if self._item_matches_filters(KIND_OVERVIEW, ov_index):
                group_item.addChild(self._create_overview_item(ov_index))
        for grid_index in self._group_direct_grid_indices(group_id):
            if self._item_matches_filters(KIND_GRID, grid_index):
                group_item.addChild(self._create_grid_item(grid_index))
        if self.acq_groups.group(group_id)['expanded']:
            self.tree.expandItem(group_item)
        return True

    def refresh_view(self, selected_key=None, filter_group_id_override=None):
        self.acq_groups.sync_inventory()
        if selected_key is None:
            selected_key = self._selected_item_key()
        if (self.checkBox_filterCurrentGroup.isChecked()
                and filter_group_id_override is not None):
            current_group_id = filter_group_id_override
        else:
            current_group_id = self._current_filter_group_id()
        if self._tree_reorder_enabled():
            self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        else:
            self.tree.setDragDropMode(QAbstractItemView.NoDragDrop)

        self._tree_refreshing = True
        self._item_index = {}
        self.tree.clear()

        root = self.tree.invisibleRootItem()
        top_level_groups = (
            [current_group_id]
            if current_group_id is not None
            else self.acq_groups.child_group_ids(None))
        for group_id in top_level_groups:
            if group_id is not None:
                self._add_group_branch(root, group_id)

        if current_group_id is None:
            visible_ungrouped_ov = [
                ov_index for ov_index in range(self.ovm.number_ov)
                if (self._overview_group_id_cached(ov_index) is None
                    and self._item_matches_filters(KIND_OVERVIEW, ov_index))]
            if visible_ungrouped_ov:
                bucket_ov = self._create_bucket_item(
                    KIND_BUCKET_OVERVIEW, 'Ungrouped overviews')
                root.addChild(bucket_ov)
                for ov_index in visible_ungrouped_ov:
                    bucket_ov.addChild(self._create_overview_item(ov_index))
                bucket_ov.setExpanded(True)

            visible_ungrouped_grids = [
                grid_index for grid_index in range(self.gm.number_grids)
                if (self._grid_group_id_cached(grid_index) is None
                    and self._item_matches_filters(KIND_GRID, grid_index))]
            if visible_ungrouped_grids:
                bucket_grid = self._create_bucket_item(
                    KIND_BUCKET_GRID, 'Ungrouped grids')
                root.addChild(bucket_grid)
                for grid_index in visible_ungrouped_grids:
                    bucket_grid.addChild(self._create_grid_item(grid_index))
                bucket_grid.setExpanded(True)

        if selected_key and selected_key in self._item_index:
            self.tree.setCurrentItem(self._item_index[selected_key])
        elif self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self.tree.setCurrentItem(None)
        self._update_top_level_button_state()
        self._update_inspector()
        self._last_current_group_filter_id = self._current_filter_group_id()
        self._tree_refreshing = False

    def _tree_item_changed(self, item, column):
        if self._tree_refreshing or column != 0 or not self._is_mutating_enabled():
            return
        kind = item.data(0, ROLE_KIND)
        identifier = item.data(0, ROLE_IDENTIFIER)
        if kind == KIND_GROUP:
            state = item.checkState(0)
            if state == Qt.PartiallyChecked:
                return
            active = (state == Qt.Checked)
            for ov_index in self.acq_groups.grouped_overview_indices(identifier):
                self.ovm[ov_index].active = active
            for grid_index in self.acq_groups.grouped_grid_indices(identifier):
                self.gm[grid_index].active = active
            self.viewport._notify_acquisition_manager_state_change(
                update_debris=True)
        elif kind == KIND_OVERVIEW:
            self.ovm[identifier].active = (item.checkState(0) == Qt.Checked)
            self.viewport._notify_acquisition_manager_state_change(
                update_debris=True)
        elif kind == KIND_GRID:
            self.gm[identifier].active = (item.checkState(0) == Qt.Checked)
            self.viewport._notify_acquisition_manager_state_change(
                update_debris=True)

    def _tree_current_item_changed(self, current, previous):
        del current, previous
        if self._tree_refreshing:
            return
        current_group_id = self._current_filter_group_id()
        if (self.checkBox_filterCurrentGroup.isChecked()
                and current_group_id != self._last_current_group_filter_id):
            self._last_current_group_filter_id = current_group_id
            self.refresh_view()
            return
        self._update_top_level_button_state()
        self._update_inspector()

    def _tree_selection_changed(self):
        if self._tree_refreshing:
            return
        if self.checkBox_filterCurrentGroup.isChecked():
            current_group_id = self._current_filter_group_id()
            if current_group_id != self._last_current_group_filter_id:
                self._last_current_group_filter_id = current_group_id
                self.refresh_view()
                return
        self._update_top_level_button_state()
        self._update_inspector()

    def _tree_item_expanded(self, item):
        if self._tree_refreshing:
            return
        if item.data(0, ROLE_KIND) == KIND_GROUP:
            self.acq_groups.set_group_expanded(
                item.data(0, ROLE_IDENTIFIER), True)

    def _tree_item_collapsed(self, item):
        if self._tree_refreshing:
            return
        if item.data(0, ROLE_KIND) == KIND_GROUP:
            self.acq_groups.set_group_expanded(
                item.data(0, ROLE_IDENTIFIER), False)

    def _tree_reordered(self):
        if self._tree_refreshing or not self._is_mutating_enabled():
            return
        ordered_pairs = []
        overview_assignments = {}
        grid_assignments = {}

        def walk(parent_item, current_group_id=None):
            for child_index in range(parent_item.childCount()):
                child = parent_item.child(child_index)
                kind = child.data(0, ROLE_KIND)
                identifier = child.data(0, ROLE_IDENTIFIER)
                if kind == KIND_GROUP:
                    ordered_pairs.append((identifier, current_group_id))
                    walk(child, identifier)
                elif kind == KIND_OVERVIEW:
                    overview_assignments[identifier] = current_group_id
                elif kind == KIND_GRID:
                    grid_assignments[identifier] = current_group_id
                else:
                    walk(child, None)

        walk(self.tree.invisibleRootItem(), None)
        self.acq_groups.apply_group_tree_order(ordered_pairs)
        for ov_index in range(self.ovm.number_ov):
            self.acq_groups.assign_overview(
                ov_index, overview_assignments.get(ov_index))
        for grid_index in range(self.gm.number_grids):
            self.acq_groups.assign_grid(
                grid_index, grid_assignments.get(grid_index))
        self.viewport._notify_acquisition_manager_state_change(
            update_debris=False)

    def _update_top_level_button_state(self):
        current = self._selected_item()
        kind = current.data(0, ROLE_KIND) if current is not None else None
        enabled = self._is_mutating_enabled()
        self.button_new_group.setEnabled(enabled)
        self.button_new_subgroup.setEnabled(enabled and kind == KIND_GROUP)
        self.button_delete_group.setEnabled(enabled and kind == KIND_GROUP)

    def _update_inspector(self):
        selected_items = self._selected_items()
        if len(selected_items) > 1:
            summary = self._selection_summary()
            lines = [
                f'Selected rows: {len(selected_items)}',
                f'Groups: {summary[KIND_GROUP]}',
                f'Overviews: {summary[KIND_OVERVIEW]}',
                f'Grids: {summary[KIND_GRID]}',
                '',
                'Use the right-click menu for batch actions such as group assignment, bulk enable/disable, bulk lock/unlock, and batch imaging settings for selected rows.',
            ]
            self.placeholder_title.setText('Multiple selection')
            self.placeholder_body.setText('\n'.join(lines))
            self.inspector_stack.setCurrentWidget(self.page_placeholder)
            return
        current = self._selected_item()
        if current is None:
            self.placeholder_title.setText('Selection')
            self.placeholder_body.setText(
                'Select a group, overview, or grid to inspect and edit it.')
            self.inspector_stack.setCurrentWidget(self.page_placeholder)
            return

        kind = current.data(0, ROLE_KIND)
        identifier = current.data(0, ROLE_IDENTIFIER)
        if kind == KIND_GROUP:
            self._update_group_page(identifier)
            self.inspector_stack.setCurrentWidget(self.page_group)
        elif kind == KIND_OVERVIEW:
            self._update_overview_page(identifier)
            self.inspector_stack.setCurrentWidget(self.page_overview)
        elif kind == KIND_GRID:
            self._update_grid_page(identifier)
            self.inspector_stack.setCurrentWidget(self.page_grid)
        elif kind == KIND_BUCKET_OVERVIEW:
            self.placeholder_title.setText('Ungrouped overviews')
            self.placeholder_body.setText(
                'Drop overviews here to remove them from a group. '
                'Ungrouped overviews keep their existing acquisition behavior.')
            self.inspector_stack.setCurrentWidget(self.page_placeholder)
        elif kind == KIND_BUCKET_GRID:
            self.placeholder_title.setText('Ungrouped grids')
            self.placeholder_body.setText(
                'Drop grids here to remove them from a group. '
                'Ungrouped grids keep their existing acquisition behavior and manual colours.')
            self.inspector_stack.setCurrentWidget(self.page_placeholder)

    def _update_group_page(self, group_id):
        group = self.acq_groups.group(group_id)
        if group is None:
            self.refresh_view()
            return

        self._inspector_refreshing = True
        self.group_title.setText(group['name'])
        self.group_name_edit.setText(group['name'])
        self.group_colour_combo.setCurrentIndex(group['colour'])
        parent_id = group['parent_id']
        self.group_parent_label.setText(
            self.acq_groups.group_path_text(parent_id) if parent_id else 'Top level')
        self.group_path_label.setText(self.acq_groups.group_path_text(group_id))
        summary = self.acq_groups.group_summary(group_id, self.acq.slice_counter)
        self.group_active_ov_label.setText(str(summary['active_overviews']))
        self.group_active_grid_label.setText(str(summary['active_grids']))
        self.group_active_tiles_label.setText(str(summary['active_tiles']))
        self.group_locked_label.setText(str(summary['locked_items']))
        self.group_acquired_label.setText(str(summary['acquired_items']))
        self.group_intervallic_label.setText(str(summary['intervallic_items']))
        self.group_slice_note.setText(summary['current_slice_note'])
        if self.acq.take_overviews:
            note = ('Stack acquisition still runs overviews first, then grids, '
                    'then the cut cycle. Groups do not change execution order.')
        else:
            note = ('Stack acquisition currently skips overview refreshes. '
                    'Groups still only control state and colour; grid and '
                    'cut-cycle timing remains unchanged.')
        self.group_execution_note.setText(note)
        editable = self._is_mutating_enabled()
        self.group_name_edit.setEnabled(editable)
        self.group_colour_combo.setEnabled(editable)
        self.button_group_new_subgroup.setEnabled(editable)
        self.button_group_delete.setEnabled(editable)
        self._inspector_refreshing = False

    def _update_overview_page(self, ov_index):
        overview = self.ovm[ov_index]
        self.ov_title.setText(f'OV {ov_index}')
        self.ov_group_label.setText(
            self.acq_groups.overview_group_path_text(ov_index))
        self.ov_status_label.setText(
            self._status_text(
                overview.active,
                overview.locked,
                overview.acquired,
                overview.last_acquisition_result,
                False))
        self.ov_last_result_label.setText(
            overview.last_acquisition_result or 'not_imaged')
        self.ov_last_timestamp_label.setText(
            overview.last_acquisition_timestamp or '-')
        self.ov_frame_size_label.setText(
            f'{overview.frame_size[0]} x {overview.frame_size[1]} px')
        self.ov_pixel_size_label.setText(f'{overview.pixel_size:.3f} nm')
        self.ov_dwell_time_label.setText(f'{overview.dwell_time}')
        self.ov_interval_label.setText(
            self._interval_text(overview.acq_interval, overview.acq_interval_offset))
        has_image = bool(overview.vp_file_path and os.path.isfile(overview.vp_file_path))
        self.ov_image_label.setText('present' if has_image else 'not loaded')
        editable = self._is_mutating_enabled()
        self.button_ov_open.setEnabled(editable)
        self.button_ov_acquire.setEnabled(editable)
        self.button_ov_clear.setEnabled(editable)
        self.button_ov_lock.setEnabled(editable)
        self.button_ov_delete.setEnabled(editable)
        self.button_ov_lock.setText('Unlock' if overview.locked else 'Lock')

    def _update_grid_page(self, grid_index):
        grid = self.gm[grid_index]
        self._current_grid_for_tile_map = grid_index
        self.grid_title.setText(grid.get_label(grid_index))
        self.grid_group_label.setText(self.acq_groups.grid_group_path_text(grid_index))
        self.grid_status_label.setText(
            self._status_text(
                grid.active,
                grid.locked,
                grid.acquired,
                grid.last_acquisition_result,
                grid.is_deferred_polygon_roi()))
        self.grid_last_result_label.setText(
            grid.last_acquisition_result or 'not_imaged')
        self.grid_last_timestamp_label.setText(
            grid.last_acquisition_timestamp or '-')
        if grid.is_deferred_polygon_roi():
            size_text = (f'Deferred ROI ({grid.roi_estimated_rows} x '
                         f'{grid.roi_estimated_cols} est.)')
        else:
            size_text = f'{grid.size[0]} x {grid.size[1]}'
        self.grid_size_label.setText(size_text)
        self.grid_frame_size_label.setText(
            f'{grid.frame_size[0]} x {grid.frame_size[1]} px')
        self.grid_pixel_size_label.setText(f'{grid.pixel_size:.3f} nm')
        self.grid_dwell_time_label.setText(f'{grid.dwell_time}')
        self.grid_interval_label.setText(
            self._interval_text(grid.acq_interval, grid.acq_interval_offset))
        self.grid_active_tiles_label.setText(
            f'{grid.number_active_tiles()} / {grid.number_tiles}')
        editable = self._is_mutating_enabled()
        self.button_grid_open.setEnabled(editable)
        self.button_grid_acquire.setEnabled(editable)
        self.button_grid_clear.setEnabled(editable)
        self.button_grid_lock.setEnabled(editable)
        self.button_grid_delete.setEnabled(editable)
        self.button_grid_select_all.setEnabled(
            editable and not grid.is_deferred_polygon_roi())
        self.button_grid_deselect_all.setEnabled(
            editable and not grid.is_deferred_polygon_roi())
        self.button_grid_lock.setText('Unlock' if grid.locked else 'Lock')
        self.tile_map.set_grid(grid)
        self.tile_map.set_interactive(editable and not grid.is_deferred_polygon_roi())
        if grid.is_deferred_polygon_roi():
            self.tile_map_note.setText(
                'Deferred polygon ROI. Open grid settings to materialize the tile list before editing it here.')
        else:
            note = ('Click or drag to toggle tile activation. '
                    'The acquisition manager only updates the existing active-tile state.')
            if self.autofocus.tracking_mode == 1:
                note += (' Focus tracking is active, so tile autofocus '
                         'references follow the active tiles in this grid.')
            self.tile_map_note.setText(note)

    def _status_text(self, active, locked, acquired, result_text, deferred):
        parts = [
            'active' if active else 'inactive',
            'locked' if locked else 'unlocked',
            'acquired' if acquired else 'not acquired',
        ]
        if self._result_failed(result_text):
            parts.append('failed')
        if deferred:
            parts.append('deferred')
        return ', '.join(parts)

    def _interval_text(self, interval, offset):
        return f'every {interval} slice(s), offset {offset}'

    def _broadcast_group_change(self, update_debris=False, selected_key=None,
                                filter_group_id_override=None):
        self.viewport._notify_acquisition_manager_state_change(
            update_debris=update_debris)
        if selected_key is not None:
            self.refresh_view(
                selected_key=selected_key,
                filter_group_id_override=filter_group_id_override)

    def _current_group_id(self):
        current = self._selected_item()
        if current is None or current.data(0, ROLE_KIND) != KIND_GROUP:
            return None
        return current.data(0, ROLE_IDENTIFIER)

    def _selected_overview_index(self):
        current = self._selected_item()
        if current is None or current.data(0, ROLE_KIND) != KIND_OVERVIEW:
            return None
        return current.data(0, ROLE_IDENTIFIER)

    def _selected_grid_index(self):
        current = self._selected_item()
        if current is None or current.data(0, ROLE_KIND) != KIND_GRID:
            return None
        return current.data(0, ROLE_IDENTIFIER)

    def _selected_target_indices(self):
        overview_indices = set()
        grid_indices = set()
        for kind, identifier in self._selected_kind_identifier_pairs():
            if kind == KIND_GROUP:
                overview_indices.update(
                    self.acq_groups.grouped_overview_indices(identifier))
                grid_indices.update(
                    self.acq_groups.grouped_grid_indices(identifier))
            elif kind == KIND_OVERVIEW:
                overview_indices.add(identifier)
            elif kind == KIND_GRID:
                grid_indices.add(identifier)
        return sorted(overview_indices), sorted(grid_indices)

    def _overview_imaging_state(self, ov_index):
        ov = self.ovm[ov_index]
        return {
            'frame_size_selector': int(ov.frame_size_selector),
            'pixel_size': float(ov.pixel_size),
            'dwell_time_selector': int(ov.dwell_time_selector),
            'bit_depth_selector': int(ov.bit_depth_selector),
            'acq_interval': int(ov.acq_interval),
            'acq_interval_offset': int(ov.acq_interval_offset),
        }

    def _grid_imaging_state(self, grid_index):
        grid = self.gm[grid_index]
        return {
            'frame_size_selector': int(grid.frame_size_selector),
            'pixel_size': float(grid.pixel_size),
            'dwell_time_selector': int(grid.dwell_time_selector),
            'bit_depth_selector': int(grid.bit_depth_selector),
            'acq_interval': int(grid.acq_interval),
            'acq_interval_offset': int(grid.acq_interval_offset),
            'overlap': int(grid.overlap),
            'row_shift': int(grid.row_shift),
        }

    def _toggle_selected_rows_active(self, active):
        overview_indices, grid_indices = self._selected_target_indices()
        if not overview_indices and not grid_indices:
            return
        for ov_index in overview_indices:
            self.ovm[ov_index].active = bool(active)
        for grid_index in grid_indices:
            self.gm[grid_index].active = bool(active)
        self.viewport._notify_acquisition_manager_state_change(
            update_debris=True)

    def _toggle_selected_rows_lock(self, locked):
        overview_indices, grid_indices = self._selected_target_indices()
        if not overview_indices and not grid_indices:
            return
        if not locked:
            locked_items = [
                f'OV {ov_index}' for ov_index in overview_indices
                if self.ovm[ov_index].locked
            ] + [
                self.gm[grid_index].get_label(grid_index)
                for grid_index in grid_indices
                if self.gm[grid_index].locked
            ]
            if locked_items:
                response = QMessageBox.question(
                    self,
                    'Unlock selected items',
                    'Unlocking acquired items allows moving them and may '
                    'break spatial provenance.\n\nProceed?',
                    QMessageBox.Ok | QMessageBox.Cancel)
                if response != QMessageBox.Ok:
                    return
        for ov_index in overview_indices:
            self.ovm[ov_index].locked = bool(locked)
        for grid_index in grid_indices:
            self.gm[grid_index].locked = bool(locked)
        self.viewport._notify_acquisition_manager_state_change(
            update_debris=False)

    def _batch_target_indices_for_group(self, group_id, kind):
        if kind == KIND_OVERVIEW:
            return self.acq_groups.grouped_overview_indices(group_id)
        return self.acq_groups.grouped_grid_indices(group_id)

    def _validate_grid_batch_changes(self, target_indices, changes):
        for grid_index in target_indices:
            grid = self.gm[grid_index]
            frame_size_selector = changes.get(
                'frame_size_selector', grid.frame_size_selector)
            frame_size = self.viewport.sem.STORE_RES[frame_size_selector]
            tile_width_p = frame_size[0]
            overlap = changes.get('overlap', grid.overlap)
            row_shift = changes.get('row_shift', grid.row_shift)
            if not (-0.3 * tile_width_p <= overlap < 0.3 * tile_width_p):
                return ('Overlap outside of allowed range '
                        '(-30% .. 30% frame width).')
            if not (0 <= row_shift <= tile_width_p):
                return ('Row shift outside of allowed range '
                        '(0 .. frame width).')
        return ''

    def _open_batch_settings_for_targets(self, kind, target_indices, target_label):
        if not target_indices:
            return
        if kind == KIND_OVERVIEW:
            source_values = self._overview_imaging_state(target_indices[0])
        else:
            source_values = self._grid_imaging_state(target_indices[0])
        dialog = BatchImagingSettingsDlg(
            kind, self.viewport.sem, source_values, target_label, self)
        if dialog.exec() != QDialog.Accepted:
            return
        changes = dialog.selected_values()
        if not changes:
            return
        if kind == KIND_GRID:
            error_msg = self._validate_grid_batch_changes(
                target_indices, changes)
            if error_msg:
                QMessageBox.warning(self, 'Error', error_msg, QMessageBox.Ok)
                return
        if kind == KIND_OVERVIEW:
            for ov_index in target_indices:
                self._apply_overview_imaging_settings(ov_index, changes)
            self.viewport._notify_acquisition_manager_state_change(
                update_debris=False)
        else:
            for grid_index in target_indices:
                self._apply_grid_imaging_settings(grid_index, changes)
            self.viewport._notify_acquisition_manager_state_change(
                update_debris=True)

    def _open_batch_settings_for_selected(self, kind):
        target_indices = self._selected_indices(kind)
        if not target_indices:
            return
        label = f'{len(target_indices)} selected {"overview" if kind == KIND_OVERVIEW else "grid"} row(s)'
        self._open_batch_settings_for_targets(kind, target_indices, label)

    def _open_batch_settings_for_group(self, group_id, kind):
        target_indices = self._batch_target_indices_for_group(group_id, kind)
        if not target_indices:
            QMessageBox.information(
                self,
                'No matching items in group',
                'The selected group does not contain any matching items for batch imaging settings.',
                QMessageBox.Ok)
            return
        group_name = self.acq_groups.group_path_text(group_id)
        label = f'"{group_name}" ({len(target_indices)} {"overview" if kind == KIND_OVERVIEW else "grid"} row(s))'
        self._open_batch_settings_for_targets(kind, target_indices, label)

    def _apply_overview_imaging_settings(self, ov_index, payload):
        ov = self.ovm[ov_index]
        ov.frame_size_selector = payload.get(
            'frame_size_selector', ov.frame_size_selector)
        ov.pixel_size = payload.get('pixel_size', ov.pixel_size)
        ov.dwell_time_selector = payload.get(
            'dwell_time_selector', ov.dwell_time_selector)
        ov.bit_depth_selector = payload.get(
            'bit_depth_selector', ov.bit_depth_selector)
        ov.acq_interval = payload.get('acq_interval', ov.acq_interval)
        ov.acq_interval_offset = payload.get(
            'acq_interval_offset', ov.acq_interval_offset)

    def _apply_grid_imaging_settings(self, grid_index, payload):
        grid = self.gm[grid_index]
        frame_size_selector = payload.get(
            'frame_size_selector', grid.frame_size_selector)
        pixel_size = payload.get('pixel_size', grid.pixel_size)
        overlap = payload.get('overlap', grid.overlap)
        row_shift = payload.get('row_shift', grid.row_shift)
        frame_size = self.viewport.sem.STORE_RES[frame_size_selector]
        geometry_changed = any([
            frame_size_selector != grid.frame_size_selector,
            overlap != grid.overlap,
            row_shift != grid.row_shift,
            pixel_size != grid.pixel_size,
        ])
        preserve_rectangular_footprint = (
            geometry_changed and not grid.has_polygon_roi())
        rectangular_layout = None
        polygon_top_left_dx_dy = None
        if grid.has_polygon_roi():
            polygon_top_left_dx_dy = (
                grid.origin_dx_dy[0] - grid.tile_width_d() / 2,
                grid.origin_dx_dy[1] - grid.tile_height_d() / 2)
        elif preserve_rectangular_footprint:
            if (not isinstance(grid.sw_sh, (list, tuple))
                    or len(grid.sw_sh) < 2
                    or grid.sw_sh[0] <= 0
                    or grid.sw_sh[1] <= 0):
                grid.sw_sh = [float(grid.width_d()), float(grid.height_d())]
            rectangular_layout = self.gm.polygon_layout_summary(
                float(grid.sw_sh[0]),
                float(grid.sw_sh[1]),
                frame_size,
                pixel_size,
                overlap,
                row_shift)
        prev_grid_centre = np.array(grid.centre_sx_sy)
        grid.auto_update_tile_positions = False
        if preserve_rectangular_footprint and rectangular_layout is not None:
            grid.size = [
                rectangular_layout['rows'],
                rectangular_layout['cols']]
        grid.frame_size_selector = frame_size_selector
        grid.overlap = overlap
        grid.row_shift = row_shift
        grid.pixel_size = pixel_size
        grid.dwell_time_selector = payload.get(
            'dwell_time_selector', grid.dwell_time_selector)
        grid.bit_depth_selector = payload.get(
            'bit_depth_selector', grid.bit_depth_selector)
        grid.acq_interval = payload.get('acq_interval', grid.acq_interval)
        grid.acq_interval_offset = payload.get(
            'acq_interval_offset', grid.acq_interval_offset)
        if grid.has_polygon_roi():
            if grid.is_deferred_polygon_roi():
                self.gm.update_deferred_polygon_grid(
                    grid_index, top_left_dx_dy=polygon_top_left_dx_dy)
            else:
                self.gm.refresh_polygon_grid(
                    grid_index, top_left_dx_dy=polygon_top_left_dx_dy)
        else:
            grid.update_tile_positions()
            grid.centre_sx_sy = prev_grid_centre
            if preserve_rectangular_footprint:
                grid.sw_sh = [float(grid.sw_sh[0]), float(grid.sw_sh[1])]
            else:
                grid.sw_sh = [float(grid.width_d()), float(grid.height_d())]
        grid.auto_update_tile_positions = True

    def _open_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        if not item.isSelected():
            self.tree.clearSelection()
            item.setSelected(True)
            self.tree.setCurrentItem(item)
        kind = item.data(0, ROLE_KIND)
        identifier = item.data(0, ROLE_IDENTIFIER)
        summary = self._selection_summary()
        overview_indices, grid_indices = self._selected_target_indices()
        selected_rows_total = summary[KIND_OVERVIEW] + summary[KIND_GRID]
        single_overview_selection = summary[KIND_OVERVIEW] == 1 and selected_rows_total == 1
        single_grid_selection = summary[KIND_GRID] == 1 and selected_rows_total == 1
        multi_overview_selection = summary[KIND_OVERVIEW] > 1 and selected_rows_total == summary[KIND_OVERVIEW]
        multi_grid_selection = summary[KIND_GRID] > 1 and selected_rows_total == summary[KIND_GRID]
        editable = self._is_mutating_enabled()
        menu = QMenu(self)

        if overview_indices or grid_indices:
            action_enable_selected = menu.addAction('Enable selected rows')
            action_enable_selected.triggered.connect(
                lambda: self._toggle_selected_rows_active(True))
            action_disable_selected = menu.addAction('Disable selected rows')
            action_disable_selected.triggered.connect(
                lambda: self._toggle_selected_rows_active(False))
            action_lock_selected = menu.addAction('Lock selected rows')
            action_lock_selected.triggered.connect(
                lambda: self._toggle_selected_rows_lock(True))
            action_unlock_selected = menu.addAction('Unlock selected rows')
            action_unlock_selected.triggered.connect(
                lambda: self._toggle_selected_rows_lock(False))
            action_enable_selected.setEnabled(editable)
            action_disable_selected.setEnabled(editable)
            action_lock_selected.setEnabled(editable)
            action_unlock_selected.setEnabled(editable)
            menu.addSeparator()

        if kind == KIND_GROUP:
            action_new_subgroup = menu.addAction('New subgroup')
            action_new_subgroup.triggered.connect(self._create_subgroup)
            action_delete_group = menu.addAction('Delete group')
            action_delete_group.triggered.connect(self._delete_selected_group)
            action_new_subgroup.setEnabled(editable)
            action_delete_group.setEnabled(editable)
            group_overviews = self.acq_groups.grouped_overview_indices(identifier)
            group_grids = self.acq_groups.grouped_grid_indices(identifier)
            if group_overviews or group_grids:
                menu.addSeparator()
                if group_overviews:
                    action_batch_ov = menu.addAction(
                        'Batch overview settings for this group...')
                    action_batch_ov.triggered.connect(
                        lambda _, group_id=identifier:
                            self._open_batch_settings_for_group(
                                group_id, KIND_OVERVIEW))
                    action_batch_ov.setEnabled(editable)
                if group_grids:
                    action_batch_grid = menu.addAction(
                        'Batch grid settings for this group...')
                    action_batch_grid.triggered.connect(
                        lambda _, group_id=identifier:
                            self._open_batch_settings_for_group(
                                group_id, KIND_GRID))
                    action_batch_grid.setEnabled(editable)
        elif kind == KIND_OVERVIEW:
            if single_overview_selection:
                action_open = menu.addAction('Open settings')
                action_open.triggered.connect(
                    self._open_selected_overview_settings)
                action_copy = menu.addAction('Copy OV')
                action_copy.triggered.connect(self._copy_selected_overview_row)
                action_duplicate = menu.addAction('Duplicate OV')
                action_duplicate.triggered.connect(
                    self._duplicate_selected_overview_row)
                action_delete = menu.addAction('Delete OV')
                action_delete.triggered.connect(self._delete_selected_overview)
                action_open.setEnabled(editable)
                action_copy.setEnabled(editable)
                action_duplicate.setEnabled(editable)
                action_delete.setEnabled(editable)
                if identifier == 0 or identifier != self.ovm.number_ov - 1:
                    action_delete.setEnabled(False)
                menu.addSeparator()
            if single_overview_selection or multi_overview_selection:
                action_batch_overviews = menu.addAction(
                    'Batch overview settings for selected rows...')
                action_batch_overviews.triggered.connect(
                    lambda: self._open_batch_settings_for_selected(
                        KIND_OVERVIEW))
                action_batch_overviews.setEnabled(editable)
        elif kind == KIND_GRID:
            if single_grid_selection:
                action_open = menu.addAction('Open settings')
                action_open.triggered.connect(self._open_selected_grid_settings)
                action_copy = menu.addAction('Copy grid')
                action_copy.triggered.connect(self._copy_selected_grid_row)
                action_duplicate = menu.addAction('Duplicate grid')
                action_duplicate.triggered.connect(
                    self._duplicate_selected_grid_row)
                action_delete = menu.addAction('Delete grid')
                action_delete.triggered.connect(self._delete_selected_grid)
                action_open.setEnabled(editable)
                action_copy.setEnabled(editable)
                action_duplicate.setEnabled(editable)
                action_delete.setEnabled(editable)
                if identifier != self.gm.number_grids - 1:
                    action_delete.setEnabled(False)
                menu.addSeparator()
            if single_grid_selection or multi_grid_selection:
                action_batch_grids = menu.addAction(
                    'Batch grid settings for selected rows...')
                action_batch_grids.triggered.connect(
                    lambda: self._open_batch_settings_for_selected(
                        KIND_GRID))
                action_batch_grids.setEnabled(editable)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _create_group(self):
        if not self._is_mutating_enabled():
            return
        group_id = self.acq_groups.create_group()
        filter_group_id_override = None
        if self.checkBox_filterCurrentGroup.isChecked():
            filter_group_id_override = group_id
        self._broadcast_group_change(
            update_debris=False,
            selected_key=self._item_key(KIND_GROUP, group_id),
            filter_group_id_override=filter_group_id_override)

    def _create_subgroup(self):
        if not self._is_mutating_enabled():
            return
        parent_id = self._current_group_id()
        if parent_id is None:
            return
        group_id = self.acq_groups.create_group(parent_id=parent_id)
        self._broadcast_group_change(
            update_debris=False,
            selected_key=self._item_key(KIND_GROUP, group_id))

    def _delete_selected_group(self):
        if not self._is_mutating_enabled():
            return
        group_id = self._current_group_id()
        if group_id is None:
            return
        group_name = self.acq_groups.group_path_text(group_id)
        user_reply = QMessageBox.question(
            self,
            'Delete group',
            f'Dissolve "{group_name}"?\n'
            'Child groups and assigned items will move to the parent group.',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply != QMessageBox.Ok:
            return
        self.acq_groups.delete_group(group_id)
        self._broadcast_group_change(update_debris=False)

    def _group_name_edited(self):
        if self._inspector_refreshing or not self._is_mutating_enabled():
            return
        group_id = self._current_group_id()
        if group_id is None:
            return
        self.acq_groups.rename_group(group_id, self.group_name_edit.text())
        self._broadcast_group_change(
            update_debris=False,
            selected_key=self._item_key(KIND_GROUP, group_id))

    def _group_colour_changed(self, colour_index):
        if self._inspector_refreshing or not self._is_mutating_enabled():
            return
        group_id = self._current_group_id()
        if group_id is None:
            return
        self.acq_groups.set_group_colour(group_id, colour_index)
        self._broadcast_group_change(
            update_debris=False,
            selected_key=self._item_key(KIND_GROUP, group_id))

    def _open_selected_overview_settings(self):
        ov_index = self._selected_overview_index()
        if ov_index is not None:
            self.viewport.main_controls_trigger.transmit(
                'OPEN OV SETTINGS', ov_index)

    def _open_selected_grid_settings(self):
        grid_index = self._selected_grid_index()
        if grid_index is not None:
            self.viewport.main_controls_trigger.transmit(
                'OPEN GRID SETTINGS', grid_index)

    def _copy_selected_overview_row(self):
        ov_index = self._selected_overview_index()
        if ov_index is None:
            return
        previous_ov = self.viewport.selected_ov
        self.viewport.selected_ov = ov_index
        try:
            self.viewport._vp_copy_selected_ov()
        finally:
            self.viewport.selected_ov = previous_ov

    def _duplicate_selected_overview_row(self):
        ov_index = self._selected_overview_index()
        if ov_index is None:
            return
        previous_ov = self.viewport.selected_ov
        self.viewport.selected_ov = ov_index
        try:
            self.viewport._vp_duplicate_selected_ov()
        finally:
            self.viewport.selected_ov = previous_ov

    def _copy_selected_grid_row(self):
        grid_index = self._selected_grid_index()
        if grid_index is None:
            return
        previous_grid = self.viewport.selected_grid
        self.viewport.selected_grid = grid_index
        try:
            self.viewport._vp_copy_selected_grid()
        finally:
            self.viewport.selected_grid = previous_grid

    def _duplicate_selected_grid_row(self):
        grid_index = self._selected_grid_index()
        if grid_index is None:
            return
        previous_grid = self.viewport.selected_grid
        self.viewport.selected_grid = grid_index
        try:
            self.viewport._vp_duplicate_selected_grid()
        finally:
            self.viewport.selected_grid = previous_grid

    def _acquire_selected_overview(self):
        ov_index = self._selected_overview_index()
        if ov_index is not None:
            self.viewport.vp_acquire_specific_overview(ov_index)

    def _acquire_selected_grid(self):
        grid_index = self._selected_grid_index()
        if grid_index is not None:
            self.viewport.vp_acquire_specific_grid(grid_index)

    def _clear_selected_overview(self):
        ov_index = self._selected_overview_index()
        if ov_index is not None:
            self.viewport.vp_clear_overview_image(ov_index)

    def _clear_selected_grid(self):
        grid_index = self._selected_grid_index()
        if grid_index is not None:
            self.viewport.vp_clear_grid_previews(grid_index)

    def _toggle_selected_overview_lock(self):
        ov_index = self._selected_overview_index()
        if ov_index is not None:
            self.viewport._vp_toggle_ov_lock(ov_index)

    def _toggle_selected_grid_lock(self):
        grid_index = self._selected_grid_index()
        if grid_index is not None:
            self.viewport._vp_toggle_grid_lock(grid_index)

    def _delete_selected_overview(self):
        ov_index = self._selected_overview_index()
        if ov_index is not None:
            self.viewport.vp_delete_overview(ov_index)

    def _delete_selected_grid(self):
        grid_index = self._selected_grid_index()
        if grid_index is not None:
            self.viewport.vp_delete_grid(grid_index)

    def _tile_map_changed(self):
        grid_index = self._current_grid_for_tile_map
        if grid_index is None or not (0 <= grid_index < self.gm.number_grids):
            return
        grid = self.gm[grid_index]
        if self.autofocus.tracking_mode == 1:
            for tile_index in range(grid.number_tiles):
                grid[tile_index].autofocus_active = (
                    tile_index in grid.active_tiles)
        self.viewport.vp_update_after_active_tile_selection()

    def _select_all_tiles(self):
        if not self._is_mutating_enabled():
            return
        grid_index = self._selected_grid_index()
        if grid_index is None:
            return
        previous_grid = self.viewport.selected_grid
        self.viewport.selected_grid = grid_index
        try:
            self.viewport.vp_activate_all_tiles()
        finally:
            self.viewport.selected_grid = previous_grid

    def _deselect_all_tiles(self):
        if not self._is_mutating_enabled():
            return
        grid_index = self._selected_grid_index()
        if grid_index is None:
            return
        previous_grid = self.viewport.selected_grid
        self.viewport.selected_grid = grid_index
        try:
            self.viewport.vp_deactivate_all_tiles()
        finally:
            self.viewport.selected_grid = previous_grid
