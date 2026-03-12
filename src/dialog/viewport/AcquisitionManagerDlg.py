import os

from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QColor, QIcon, QPixmap
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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
from dialog.viewport.TileActivationMap import TileActivationMap


ROLE_KIND = Qt.UserRole
ROLE_IDENTIFIER = Qt.UserRole + 1

KIND_GROUP = 'group'
KIND_OVERVIEW = 'overview'
KIND_GRID = 'grid'
KIND_BUCKET_OVERVIEW = 'bucket_ov'
KIND_BUCKET_GRID = 'bucket_grid'


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
        self._item_index = {}
        self._current_grid_for_tile_map = None

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

        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.tree = AcquisitionTreeWidget(left_panel)
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        left_layout.addWidget(self.tree, 1)
        tree_hint = QLabel(
            'Drag grids or overviews onto a group to assign them. '
            'Drop them onto an ungrouped bucket to remove the assignment.')
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
        self.tree.itemChanged.connect(self._tree_item_changed)
        self.tree.currentItemChanged.connect(self._tree_current_item_changed)
        self.tree.itemExpanded.connect(self._tree_item_expanded)
        self.tree.itemCollapsed.connect(self._tree_item_collapsed)
        self.tree.set_drop_callback(self._tree_reordered)

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

    def _selected_item_key(self):
        item = self._selected_item()
        if item is None:
            return None
        return self._item_key(
            item.data(0, ROLE_KIND),
            item.data(0, ROLE_IDENTIFIER))

    def _register_item(self, item, kind, identifier):
        item.setData(0, ROLE_KIND, kind)
        item.setData(0, ROLE_IDENTIFIER, identifier)
        self._item_index[self._item_key(kind, identifier)] = item

    def _is_mutating_enabled(self):
        return not (self.viewport.busy or self.acq.acq_in_progress)

    def _bucket_flags(self):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._is_mutating_enabled():
            flags |= Qt.ItemIsDropEnabled
        return flags

    def _group_flags(self):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._is_mutating_enabled():
            flags |= (Qt.ItemIsUserCheckable
                      | Qt.ItemIsDragEnabled
                      | Qt.ItemIsDropEnabled)
        return flags

    def _leaf_flags(self):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self._is_mutating_enabled():
            flags |= Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled
        return flags

    def _create_bucket_item(self, kind, title):
        item = QTreeWidgetItem([title])
        item.setFlags(self._bucket_flags())
        self._register_item(item, kind, kind)
        return item

    def _group_direct_overview_indices(self, group_id):
        return [
            ov_index for ov_index in range(self.ovm.number_ov)
            if self.acq_groups.overview_group_id(ov_index) == group_id
        ]

    def _group_direct_grid_indices(self, group_id):
        return [
            grid_index for grid_index in range(self.gm.number_grids)
            if self.acq_groups.grid_group_id(grid_index) == group_id
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
        item = QTreeWidgetItem([group['name']])
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
        item = QTreeWidgetItem([title])
        item.setFlags(self._leaf_flags())
        item.setCheckState(0, Qt.Checked if overview.active else Qt.Unchecked)
        group_id = self.acq_groups.overview_group_id(ov_index)
        if group_id is not None:
            group = self.acq_groups.group(group_id)
            if group is not None:
                item.setIcon(0, self._colour_icon(group['colour']))
        item.setToolTip(0, self.acq_groups.overview_group_path_text(ov_index))
        self._register_item(item, KIND_OVERVIEW, ov_index)
        return item

    def _create_grid_item(self, grid_index):
        grid = self.gm[grid_index]
        title = grid.get_label(grid_index)
        if not grid.active:
            title += ' (inactive)'
        item = QTreeWidgetItem([title])
        item.setFlags(self._leaf_flags())
        item.setCheckState(0, Qt.Checked if grid.active else Qt.Unchecked)
        group_id = self.acq_groups.grid_group_id(grid_index)
        if group_id is not None:
            group = self.acq_groups.group(group_id)
            if group is not None:
                item.setIcon(0, self._colour_icon(group['colour']))
        item.setToolTip(0, self.acq_groups.grid_group_path_text(grid_index))
        self._register_item(item, KIND_GRID, grid_index)
        return item

    def _add_group_branch(self, parent_item, group_id):
        group_item = self._create_group_item(group_id)
        parent_item.addChild(group_item)
        for child_group_id in self.acq_groups.child_group_ids(group_id):
            self._add_group_branch(group_item, child_group_id)
        for ov_index in self._group_direct_overview_indices(group_id):
            group_item.addChild(self._create_overview_item(ov_index))
        for grid_index in self._group_direct_grid_indices(group_id):
            group_item.addChild(self._create_grid_item(grid_index))
        if self.acq_groups.group(group_id)['expanded']:
            self.tree.expandItem(group_item)

    def refresh_view(self, selected_key=None):
        self.acq_groups.sync_inventory()
        if selected_key is None:
            selected_key = self._selected_item_key()
        if self._is_mutating_enabled():
            self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        else:
            self.tree.setDragDropMode(QAbstractItemView.NoDragDrop)

        self._tree_refreshing = True
        self._item_index = {}
        self.tree.clear()

        root = self.tree.invisibleRootItem()
        for group_id in self.acq_groups.child_group_ids(None):
            self._add_group_branch(root, group_id)

        bucket_ov = self._create_bucket_item(
            KIND_BUCKET_OVERVIEW, 'Ungrouped overviews')
        root.addChild(bucket_ov)
        for ov_index in range(self.ovm.number_ov):
            if self.acq_groups.overview_group_id(ov_index) is None:
                bucket_ov.addChild(self._create_overview_item(ov_index))
        bucket_ov.setExpanded(True)

        bucket_grid = self._create_bucket_item(
            KIND_BUCKET_GRID, 'Ungrouped grids')
        root.addChild(bucket_grid)
        for grid_index in range(self.gm.number_grids):
            if self.acq_groups.grid_group_id(grid_index) is None:
                bucket_grid.addChild(self._create_grid_item(grid_index))
        bucket_grid.setExpanded(True)

        self._tree_refreshing = False
        if selected_key and selected_key in self._item_index:
            self.tree.setCurrentItem(self._item_index[selected_key])
        elif self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self.tree.setCurrentItem(None)
        self._update_top_level_button_state()
        self._update_inspector()

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
            self._status_text(overview.active, overview.locked, overview.acquired))
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
            self._status_text(grid.active, grid.locked, grid.acquired))
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

    def _status_text(self, active, locked, acquired):
        return (
            ('active' if active else 'inactive')
            + ', '
            + ('locked' if locked else 'unlocked')
            + ', '
            + ('acquired' if acquired else 'not acquired'))

    def _interval_text(self, interval, offset):
        return f'every {interval} slice(s), offset {offset}'

    def _broadcast_group_change(self, update_debris=False, selected_key=None):
        self.viewport._notify_acquisition_manager_state_change(
            update_debris=update_debris)
        if selected_key is not None:
            self.refresh_view(selected_key=selected_key)

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

    def _create_group(self):
        if not self._is_mutating_enabled():
            return
        group_id = self.acq_groups.create_group()
        self._broadcast_group_change(
            update_debris=False,
            selected_key=self._item_key(KIND_GROUP, group_id))

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
