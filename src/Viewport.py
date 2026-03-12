# -*- coding: utf-8 -*-

# ==============================================================================
#   This source file is part of SBEMimage (github.com/SBEMimage)
#   (c) 2018-2020 Friedrich Miescher Institute for Biomedical Research, Basel,
#   and the SBEMimage developers.
#   This software is licensed under the terms of the MIT License.
#   See LICENSE.txt in the project root folder.
# ==============================================================================

"""This module controls the Viewport window, which consists of three tabs:
    - the Viewport (methods/attributes concerning the Viewport tab are
                    tagged with 'vp_')
    - the Slice-by-Slice Viewer (sv_),
    - the Reslice/Statistics tab (m_ for 'monitoring')
"""

import os
import shutil
import json
import numpy as np
import scipy
from time import time, sleep
from math import log, sqrt, sin, cos, radians
from statistics import mean

from qtpy.uic import loadUi
from qtpy.QtWidgets import QWidget, QApplication, QMessageBox, QMenu, \
                           QFrame, QHBoxLayout, QLabel, QToolButton, \
                           QCheckBox, QPushButton, QSizePolicy, \
                           QFileDialog
from qtpy.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QPen, \
                       QBrush, QKeyEvent, QFontMetrics, QTransform
from qtpy.QtCore import Qt, QObject, QRect, QRectF, QPointF, QSize, QTimer

import acq_func
import constants
import utils
import viewport_polygon_roi as polygon_roi
import stub_overview_workflow as stub_workflow
from image_io import imread
from dialog.viewport.ModifyImagesDlg import ModifyImagesDlg
from dialog.viewport.ImportImageDlg import ImportImageDlg
from dialog.viewport.TemplateRotationDlg import TemplateRotationDlg
from dialog.viewport.GridRotationDlg import GridRotationDlg
from dialog.viewport.FocusGradientTileSelectionDlg import FocusGradientTileSelectionDlg
from dialog.viewport.StubOVDlg import StubOVDlg
from dialog.viewport.AcquisitionManagerDlg import AcquisitionManagerDlg
from dialog.viewport.ov_queue_dlg import OVQueueDlg
from dialog.MotorStatusDlg import MotorStatusDlg


class Viewport(QWidget):

    def __init__(self, config, sem, stage, coordinate_system,
                 ov_manager, grid_manager, imported_images,
                 autofocus, acquisition, img_inspector,
                 main_controls_trigger, template_manager,
                 imaging_condition_store, acq_groups,
                 use_klab_ui=False):
        super().__init__()
        self.cfg = config
        self.sem = sem
        self.stage = stage
        self.cs = coordinate_system
        self.gm = grid_manager
        self.ovm = ov_manager
        self.tm = template_manager
        self.imported = imported_images
        self.autofocus = autofocus
        self.acq = acquisition
        self.img_inspector = img_inspector
        self.main_controls_trigger = main_controls_trigger
        self.imaging_condition_store = imaging_condition_store
        self.acq_groups = acq_groups
        self.use_klab_ui = use_klab_ui

        # Set Viewport zoom parameters depending on which stage is used for XY
        if self.stage.use_microtome_xy:
            self.VP_SCALING = constants.VP_SCALING_MICROTOME_STAGE
        else:
            self.VP_SCALING = constants.VP_SCALING_SEM_STAGE
        # Set limits for viewport panning.
        self.VC_MIN_X, self.VC_MAX_X, self.VC_MIN_Y, self.VC_MAX_Y = (
            self.vp_dx_dy_range())

        # Shared control variables
        self.busy = False    # acquisition or other operation in progress
        self.active = True   # Viewport windows is active.
        # for mouse operations (dragging, measuring)
        self.doubleclick_registered = False
        self.zooming_in_progress = False
        self.drag_origin = (0, 0)
        self.drag_current = (0, 0)
        self.fov_drag_active = False
        self.tile_paint_mode_active = False
        self.measure_p1 = (None, None)
        self.measure_p2 = (None, None)
        self.measure_complete = False
        self.help_panel_visible = False
        self.stub_ov_centre = [None, None]
        self.stub_ov_dialog = None

        # Set up trigger and queue to update viewport from the
        # acquisition thread or dialog windows.
        self.viewport_trigger = utils.Trigger()
        self.viewport_trigger.signal.connect(self._process_signal)

        # Polygon ROI state must exist before _load_gui() builds the toolbar.
        self.polygon_shape_library = []
        self.polygon_tool_buttons = {}
        self.vp_polygon_tool = None
        self.vp_polygon_tool_spec = None
        self.vp_polygon_custom_points = []
        self.vp_polygon_hover_point = None
        self.vp_polygon_handle_drag = None
        self.vp_polygon_vertex_drag = None
        self.vp_polygon_clipboard = None
        self.vp_polygon_context_dx_dy = None

        self._load_gui()
        # Initialize viewport tabs:
        self._vp_initialize()  # Viewport
        self._sv_initialize()  # Slice-by-slice viewer
        self._m_initialize()   # Monitoring tab
        self.setMouseTracking(True)

        self.selected_template = False
        self.selected_grid, self.selected_tile = None, None
        self.selected_ov = None
        self.selected_imported = None
        self.ov_queue_dlg = None
        self.acquisition_manager_dlg = None
        self._acquisition_manager_refresh_pending = False
        self._vp_grid_acq_in_progress = False
        self._vp_grid_acq_index = None
        self._vp_acq_state_backup = None
        self.render_debug_enabled = utils.str_to_bool(
            self.cfg['viewport'].get('render_debug', 'False'))
        self.render_antialias = utils.str_to_bool(
            self.cfg['viewport'].get('render_antialias', 'False'))

    def save_to_cfg(self):
        """Save viewport configuration to ConfigParser object."""
        self.cfg['viewport']['vp_current_grid'] = str(self.vp_current_grid)
        self.cfg['viewport']['vp_current_ov'] = str(self.vp_current_ov)
        self.cfg['viewport']['vp_tile_preview_mode'] = str(
            self.vp_tile_preview_mode)
        self.cfg['viewport']['show_labels'] = str(self.show_labels)
        self.cfg['viewport']['show_axes'] = str(self.show_axes)
        self.cfg['viewport']['show_stub_ov'] = str(self.show_stub_ov)
        self.cfg['viewport']['show_imported'] = str(self.show_imported)
        self.cfg['viewport']['show_grid_lines'] = str(self.show_grid_lines)
        self.cfg['viewport']['show_native_resolution'] = str(
            self.show_native_res)
        self.cfg['viewport']['show_saturated_pixels'] = str(
            self.show_saturated_pixels)
        self.cfg['viewport']['render_debug'] = str(self.render_debug_enabled)
        self.cfg['viewport']['render_antialias'] = str(self.render_antialias)
        self.cfg['viewport']['polygon_shape_library_names'] = json.dumps(
            [shape['name'] for shape in self.polygon_shape_library])
        self.cfg['viewport']['polygon_shape_library_points'] = json.dumps(
            [shape['points_norm'] for shape in self.polygon_shape_library])
        self.cfg['viewport']['polygon_shape_library_size_um'] = json.dumps(
            [shape.get('size_um') for shape in self.polygon_shape_library])

        self.cfg['viewport']['sv_current_grid'] = str(self.sv_current_grid)
        self.cfg['viewport']['sv_current_tile'] = str(self.sv_current_tile)
        self.cfg['viewport']['sv_current_ov'] = str(self.sv_current_ov)

        self.cfg['viewport']['m_current_grid'] = str(self.m_current_grid)
        self.cfg['viewport']['m_current_tile'] = str(self.m_current_tile)
        self.cfg['viewport']['m_current_ov'] = str(self.m_current_ov)

    def _load_gui(self):
        loadUi('gui/viewport.ui', self)
        self.setFocusPolicy(Qt.StrongFocus)
        self.label_mousePos.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._setup_viewport_selector_controls()
        self._setup_viewport_display_controls()
        self._setup_polygon_toolbar()
        self._ensure_viewport_display_space()
        self._layout_viewport_selector_controls()
        self._layout_viewport_display_controls()
        if self.use_klab_ui:
            self.apply_klab_viewport_geometry_tweaks()
        self.setWindowIcon(utils.get_window_icon())
        self.setWindowTitle('SBEMimage - Viewport')
        # Display current settings:
        #self.setFixedSize(self.size())
        self.move(20, 20)
        # Deactivate buttons for imaging if in simulation mode
        if self.sem.simulation_mode:
            self.pushButton_refreshOVs.setEnabled(False)
            self.pushButton_acquireStubOV.setEnabled(False)
            self.checkBox_showStagePos.setEnabled(False)
        # Detect if tab is changed
        self.tabWidget.currentChanged.connect(self.tab_changed)
        self.QLabel_ViewportCanvas.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def _setup_polygon_toolbar(self):
        if hasattr(self, 'frame_polygonTools'):
            return

        toolbar_height = 32
        self.resize(self.width(), self.height() + toolbar_height)
        self.setMinimumHeight(self.minimumHeight() + toolbar_height)
        self.groupBox.setMinimumHeight(self.groupBox.minimumHeight() + toolbar_height)
        self.groupBox.setMaximumHeight(self.groupBox.maximumHeight() + toolbar_height)
        for frame in (self.frame, self.frame_2, self.frame_3):
            frame.move(frame.x(), frame.y() + toolbar_height)

        self.frame_polygonTools = QFrame(self.groupBox)
        self.frame_polygonTools.setFrameShape(QFrame.StyledPanel)
        self.frame_polygonTools.setFrameShadow(QFrame.Raised)
        self.frame_polygonToolsLayout = QHBoxLayout(self.frame_polygonTools)
        self.frame_polygonToolsLayout.setContentsMargins(6, 0, 6, 0)
        self.frame_polygonToolsLayout.setSpacing(4)
        self._layout_polygon_toolbar()
        self._rebuild_polygon_toolbar()

    def _setup_viewport_selector_controls(self):
        return

    def _layout_viewport_selector_controls(self, combo_margin=10, combo_gap=8,
                                           min_selector_width=96,
                                           min_secondary_width=108):
        frame1_width = self.frame.width()
        combo_y = self.comboBox_gridSelectorVP.y()
        combo_height = self.comboBox_gridSelectorVP.height()
        mouse_line_height = self.label_mousePos.fontMetrics().lineSpacing()
        mouse_y = max(self.label_mousePos.y(), combo_y + combo_height + 6)
        mouse_height = min(
            max(18, mouse_line_height + 2),
            max(18, self.frame.height() - mouse_y - 2))
        selector_width = max(
            min_selector_width,
            QFontMetrics(self.comboBox_gridSelectorVP.font()).horizontalAdvance(
                'All grids') + 26)
        selector_width = min(
            selector_width,
            max(min_selector_width, frame1_width - 150))
        selector_x = combo_margin
        tile_x = selector_x + selector_width + combo_gap
        tile_width = max(
            min_secondary_width,
            frame1_width - tile_x - combo_margin)
        self.comboBox_gridSelectorVP.setGeometry(
            selector_x, self.comboBox_gridSelectorVP.y(),
            selector_width, self.comboBox_gridSelectorVP.height())
        self.comboBox_tilePreviewSelectorVP.setGeometry(
            tile_x, self.comboBox_tilePreviewSelectorVP.y(),
            tile_width, self.comboBox_tilePreviewSelectorVP.height())

        if hasattr(self, 'pushButton_acquisitionManager'):
            button_metrics = QFontMetrics(self.pushButton_acquisitionManager.font())
            button_width = max(
                132,
                button_metrics.horizontalAdvance('Acquisition manager') + 24)
            button_width = min(
                button_width,
                max(108, frame1_width - 120))
            button_y = max(
                self.comboBox_gridSelectorVP.y() + self.comboBox_gridSelectorVP.height() + 5,
                self.label_mousePos.y() - 2)
            self.pushButton_acquisitionManager.setGeometry(
                combo_margin, button_y,
                button_width, self.pushButton_acquisitionManager.sizeHint().height())
            mouse_x = self.pushButton_acquisitionManager.x() + button_width + combo_gap
        else:
            mouse_x = combo_margin
        self.label_mousePos.setGeometry(
            mouse_x, mouse_y,
            max(54, frame1_width - mouse_x - combo_margin),
            mouse_height)

    def _format_mouse_position_text(self, sx, sy, dx, dy):
        full_text = (
            'Stage: {0:.1f}, {1:.1f}; SEM: {2:.1f}, {3:.1f}'
            .format(sx, sy, dx, dy))
        variants = [
            full_text,
            'Stg: {0:.1f}, {1:.1f}; SEM: {2:.1f}, {3:.1f}'
            .format(sx, sy, dx, dy),
            'Stg {0:.1f},{1:.1f} | SEM {2:.1f},{3:.1f}'
            .format(sx, sy, dx, dy),
            'Stg {0:.0f},{1:.0f} | SEM {2:.0f},{3:.0f}'
            .format(sx, sy, dx, dy),
        ]
        available_width = max(24, self.label_mousePos.contentsRect().width() - 2)
        metrics = self.label_mousePos.fontMetrics()
        for candidate in variants:
            if metrics.horizontalAdvance(candidate) <= available_width:
                return candidate, full_text
        return metrics.elidedText(variants[-1], Qt.ElideRight, available_width), full_text

    def _setup_viewport_display_controls(self):
        if hasattr(self, 'checkBox_showGridLines'):
            return
        self.checkBox_showGridLines = QCheckBox('Show grid lines', self.frame_3)
        self.checkBox_showGridLines.setObjectName('checkBox_showGridLines')
        self.checkBox_showGridLines.setToolTip(
            'Show or hide grid outlines in the Viewport. Shortcut: H toggles both grid lines and labels.')

    def _layout_viewport_display_controls(self, combo_margin=10):
        if not hasattr(self, 'checkBox_showGridLines'):
            return

        frame3_width = self.frame_3.width()
        help_margin = 8
        metrics = QFontMetrics(self.checkBox_showStagePos.font())
        toggle_width = max(
            metrics.horizontalAdvance('Show grid lines'),
            metrics.horizontalAdvance('Show labels'),
            metrics.horizontalAdvance('Show stage position'),
            metrics.horizontalAdvance('Show axes')) + 28
        toggle_width = min(toggle_width, 156 if self.use_klab_ui else 166)
        row_positions = (6, 24, 42, 60)
        checkbox_height = self.checkBox_showLabels.height()

        self.checkBox_showGridLines.setGeometry(
            combo_margin, row_positions[0], toggle_width, checkbox_height)
        self.checkBox_showLabels.setGeometry(
            combo_margin, row_positions[1], toggle_width, checkbox_height)
        self.checkBox_showStagePos.setGeometry(
            combo_margin, row_positions[2], toggle_width, checkbox_height)
        self.checkBox_showAxes.setGeometry(
            combo_margin, row_positions[3], toggle_width, checkbox_height)

        self.pushButton_helpViewport.move(
            frame3_width - self.pushButton_helpViewport.width() - help_margin,
            row_positions[2] - 2)

        slider_label_x = combo_margin + toggle_width + (18 if self.use_klab_ui else 16)
        slider_x = slider_label_x + 40
        slider_width = max(
            108 if self.use_klab_ui else 118,
            self.pushButton_helpViewport.x() - slider_x - 8)
        self.label_4.move(slider_label_x, row_positions[0] + 2)
        self.horizontalSlider_VP.setGeometry(
            slider_x, row_positions[0] - 1,
            slider_width, self.horizontalSlider_VP.height())
        self.label_6.move(slider_label_x, row_positions[2] + 1)
        self.label_FOVSize.setGeometry(
            slider_label_x + 32, row_positions[2] + 1,
            max(86, self.pushButton_helpViewport.x() - (slider_label_x + 32) - 8),
            self.label_FOVSize.height())

    def _ensure_viewport_display_space(self):
        if getattr(self, '_viewport_display_space_applied', False):
            return
        extra_height = 18
        self._viewport_display_space_applied = True
        self.resize(self.width(), self.height() + extra_height)
        self.setMinimumHeight(self.minimumHeight() + extra_height)
        self.groupBox.setMinimumHeight(self.groupBox.minimumHeight() + extra_height)
        self.groupBox.setMaximumHeight(self.groupBox.maximumHeight() + extra_height)
        self.frame_3.setGeometry(
            self.frame_3.x(), self.frame_3.y(),
            self.frame_3.width(), self.frame_3.height() + extra_height)

    def _layout_polygon_toolbar(self):
        if not hasattr(self, 'frame_polygonTools'):
            return
        self.frame_polygonTools.setGeometry(
            8,
            12,
            max(300, self.groupBox.width() - 16),
            26)

    def apply_klab_viewport_geometry_tweaks(self):
        """Adjust viewport controls for KLAB theme readability."""
        self._ensure_viewport_display_space()
        combo_margin = 10
        combo_gap = 8
        min_selector_width = 96
        min_secondary_width = 108

        self._layout_viewport_selector_controls(
            combo_margin=combo_margin,
            combo_gap=combo_gap,
            min_selector_width=min_selector_width,
            min_secondary_width=min_secondary_width)

        # Frame 2: OV selector + action buttons, keep buttons right with fixed gap.
        frame2_width = self.frame_2.width()
        ov_selector_width = max(
            min_selector_width,
            QFontMetrics(self.comboBox_OVSelectorVP.font()).horizontalAdvance(
                'All OVs') + 26)
        ov_selector_width = min(ov_selector_width, 120)
        self.comboBox_OVSelectorVP.setGeometry(
            combo_margin, self.comboBox_OVSelectorVP.y(),
            ov_selector_width, self.comboBox_OVSelectorVP.height())
        refresh_x = self.comboBox_OVSelectorVP.x() + ov_selector_width + combo_gap
        self.pushButton_refreshOVs.move(refresh_x, self.pushButton_refreshOVs.y())
        acquire_x = self.pushButton_refreshOVs.x() + self.pushButton_refreshOVs.width() + combo_gap
        max_acquire_x = frame2_width - self.pushButton_measureViewport.width() - 2 * combo_gap - self.pushButton_acquireStubOV.width()
        self.pushButton_acquireStubOV.move(
            min(acquire_x, max_acquire_x),
            self.pushButton_acquireStubOV.y())
        measure_x = frame2_width - self.pushButton_measureViewport.width() - combo_margin
        self.pushButton_measureViewport.move(measure_x, self.pushButton_measureViewport.y())
        self.pushButton_updateStagePos.move(measure_x, self.pushButton_updateStagePos.y())

        # Frame 3: display toggles + FOV controls.
        self._layout_viewport_display_controls(combo_margin=combo_margin)

    def _clear_polygon_toolbar_layout(self):
        while self.frame_polygonToolsLayout.count():
            item = self.frame_polygonToolsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_polygon_toolbar(self):
        self.polygon_tool_buttons = {}
        self._clear_polygon_toolbar_layout()

        label = QLabel('ROI')
        label.setFixedWidth(26)
        label.setProperty('klabFixedMetrics', True)
        self.frame_polygonToolsLayout.addWidget(label)

        default_buttons = [
            ('Rectangle', 'rectangle'),
            ('Circle', 'circle'),
            ('Triangle', 'triangle'),
            ('Draw your own', polygon_roi.CUSTOM_SHAPE_TYPE),
        ]
        for text, key in default_buttons:
            button = self._create_fixed_polygon_toolbar_button(
                text, checkable=True)
            button.clicked.connect(
                lambda checked, button_key=key:
                    self._vp_toggle_polygon_tool(button_key, checked))
            self.frame_polygonToolsLayout.addWidget(button)
            self.polygon_tool_buttons[key] = button

        for index, shape in enumerate(self.polygon_shape_library):
            key = f'imported::{index}'
            button = self._create_fixed_polygon_toolbar_button(
                shape['name'], checkable=True)
            button.clicked.connect(
                lambda checked, button_key=key:
                    self._vp_toggle_polygon_tool(button_key, checked))
            self.frame_polygonToolsLayout.addWidget(button)
            self.polygon_tool_buttons[key] = button

        self.frame_polygonToolsLayout.addStretch(1)

        import_button = self._create_fixed_polygon_toolbar_button('Import')
        import_button.clicked.connect(self._vp_import_polygon_shape)
        self.frame_polygonToolsLayout.addWidget(import_button)
        self.pushButton_importPolygon = import_button

        delete_button = self._create_fixed_polygon_toolbar_button('Delete SVG')
        delete_button.clicked.connect(self._vp_delete_imported_polygon_shape)
        delete_button.setEnabled(False)
        delete_button.setToolTip(
            'Delete the currently selected imported SVG shape from the ROI toolbar.')
        self.frame_polygonToolsLayout.addWidget(delete_button)
        self.pushButton_deleteImportedPolygon = delete_button

        self._sync_polygon_toolbar_buttons()

    def _create_fixed_polygon_toolbar_button(self, text, checkable=False):
        button = QToolButton(self.frame_polygonTools)
        button.setText(text)
        button.setCheckable(checkable)
        metrics = QFontMetrics(button.font())
        button_width = max(68, metrics.horizontalAdvance(text) + 22)
        button.setFixedWidth(button_width)
        button.setFixedHeight(24)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button.setProperty('klabFixedMetrics', True)
        return button

    def _sync_polygon_toolbar_buttons(self):
        active_key = None
        if self.vp_polygon_tool_spec is not None:
            active_key = self.vp_polygon_tool_spec.get('key')
        for key, button in self.polygon_tool_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == active_key)
            button.blockSignals(False)
        if hasattr(self, 'pushButton_deleteImportedPolygon'):
            imported_index = self._vp_selected_imported_polygon_index()
            enabled = imported_index is not None
            self.pushButton_deleteImportedPolygon.setEnabled(enabled)
            if enabled:
                shape_name = self.polygon_shape_library[imported_index]['name']
                self.pushButton_deleteImportedPolygon.setToolTip(
                    f'Delete imported SVG shape "{shape_name}" from the ROI toolbar.')
            else:
                self.pushButton_deleteImportedPolygon.setToolTip(
                    'Select an imported SVG shape to delete it from the ROI toolbar.')

    def _vp_selected_imported_polygon_index(self):
        if self.vp_polygon_tool_spec is None:
            return None
        key = self.vp_polygon_tool_spec.get('key')
        if not isinstance(key, str) or not key.startswith('imported::'):
            return None
        try:
            imported_index = int(key.split('::', 1)[1])
        except ValueError:
            return None
        if 0 <= imported_index < len(self.polygon_shape_library):
            return imported_index
        return None

    def _load_polygon_shape_library(self):
        raw_names = self.cfg['viewport'].get('polygon_shape_library_names', '[]')
        raw_points = self.cfg['viewport'].get('polygon_shape_library_points', '[]')
        raw_sizes = self.cfg['viewport'].get('polygon_shape_library_size_um', '[]')
        try:
            names = json.loads(raw_names)
            points_list = json.loads(raw_points)
            size_list = json.loads(raw_sizes)
        except Exception:
            names = []
            points_list = []
            size_list = []
        self.polygon_shape_library = []
        for index, name in enumerate(names):
            points_norm = points_list[index] if index < len(points_list) else []
            if len(points_norm) < 3:
                continue
            size_um = size_list[index] if index < len(size_list) else None
            if (not isinstance(size_um, list)) or len(size_um) != 2:
                size_um = None
            elif size_um[0] <= 0 or size_um[1] <= 0:
                size_um = None
            self.polygon_shape_library.append({
                'name': str(name),
                'points_norm': points_norm,
                'size_um': size_um,
            })

    def _vp_tool_spec_from_key(self, key):
        if key in polygon_roi.PREDEFINED_SHAPE_TYPES:
            return {
                'key': key,
                'shape_type': key,
                'shape_name': key.title(),
                'points_norm': polygon_roi.predefined_points_norm(key),
            }
        if key == polygon_roi.CUSTOM_SHAPE_TYPE:
            return {
                'key': key,
                'shape_type': polygon_roi.CUSTOM_SHAPE_TYPE,
                'shape_name': 'Custom polygon',
                'points_norm': [],
            }
        if key.startswith('imported::'):
            try:
                index = int(key.split('::', 1)[1])
            except ValueError:
                return None
            if index < 0 or index >= len(self.polygon_shape_library):
                return None
            shape = self.polygon_shape_library[index]
            return {
                'key': key,
                'shape_type': polygon_roi.IMPORTED_SHAPE_TYPE,
                'shape_name': shape['name'],
                'points_norm': shape['points_norm'],
                'size_um': shape.get('size_um'),
            }
        return None

    def _vp_toggle_polygon_tool(self, key, checked):
        if not checked:
            if self.vp_polygon_tool_spec is not None and self.vp_polygon_tool_spec.get('key') == key:
                self._vp_disarm_polygon_tool()
            return

        spec = self._vp_tool_spec_from_key(key)
        if spec is None:
            self._vp_disarm_polygon_tool()
            return
        self.vp_polygon_tool = spec['shape_type']
        self.vp_polygon_tool_spec = spec
        self.vp_polygon_custom_points = []
        self.vp_polygon_hover_point = None
        self._sync_polygon_toolbar_buttons()
        self.vp_draw()

    def _vp_disarm_polygon_tool(self):
        self.vp_polygon_tool = None
        self.vp_polygon_tool_spec = None
        self.vp_polygon_custom_points = []
        self.vp_polygon_hover_point = None
        self._sync_polygon_toolbar_buttons()
        self.vp_draw()

    def _vp_import_polygon_shape(self):
        svg_path, _ = QFileDialog.getOpenFileName(
            self,
            'Import polygon SVG',
            '',
            'SVG files (*.svg)')
        if not svg_path:
            return
        try:
            svg_shape = polygon_roi.parse_svg_shape(svg_path)
            shape_name = polygon_roi.svg_shape_name(svg_path)
        except Exception as exception:
            QMessageBox.warning(
                self,
                'Import polygon SVG',
                f'Could not import polygon SVG:\n{exception}',
                QMessageBox.Ok)
            return

        self.polygon_shape_library.append({
            'name': shape_name,
            'points_norm': svg_shape['points_norm'],
            'size_um': [
                float(svg_shape['bounds_um'][2]),
                float(svg_shape['bounds_um'][3]),
            ],
        })
        self._rebuild_polygon_toolbar()
        imported_key = f'imported::{len(self.polygon_shape_library) - 1}'
        self._vp_toggle_polygon_tool(imported_key, True)

    def _vp_delete_imported_polygon_shape(self):
        imported_index = self._vp_selected_imported_polygon_index()
        if imported_index is None:
            return
        shape_name = self.polygon_shape_library[imported_index]['name']
        user_reply = QMessageBox.question(
            self,
            'Delete imported SVG',
            f'Remove imported SVG shape "{shape_name}" from the ROI toolbar?\n'
            'Existing polygon grids already created from this shape will remain unchanged.',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply != QMessageBox.Ok:
            return

        del self.polygon_shape_library[imported_index]
        self.vp_polygon_tool = None
        self.vp_polygon_tool_spec = None
        self.vp_polygon_custom_points = []
        self.vp_polygon_hover_point = None
        self._rebuild_polygon_toolbar()
        self.vp_draw()

    def _vp_visible_sem_dimensions(self):
        return (
            self.cs.vp_width / self.cs.vp_scale,
            self.cs.vp_height / self.cs.vp_scale)

    def _vp_grid_render_flags(self, suppress_previews=False):
        """Return effective grid-layer visibility flags for the viewport."""
        if self.vp_tile_preview_mode == 1:   # Show previews with grid lines
            show_grid, show_previews, with_gaps = True, True, False
        else:
            show_grid, show_previews, with_gaps = True, False, False

        show_grid = show_grid and self.show_grid_lines
        previews_temporarily_suppressed = (
            suppress_previews
            or self.fov_drag_active
            or self.grid_drag_active)
        if previews_temporarily_suppressed and show_previews:
            # Tile previews are intentionally suppressed during interaction for
            # responsiveness. Preserve the user's explicit grid-line toggle
            # state instead of forcing outlines back on during panning.
            show_previews = False
        return show_grid, show_previews, with_gaps

    def tab_changed(self):
        if self.tabWidget.currentIndex() == 2:  # Acquisition monitor
            # Update motor status
            self.m_show_motor_status()

    def restrict_gui(self, busy):
        """Disable several GUI elements while SBEMimage is busy, for example
        when an acquisition is running."""
        self.busy = busy
        idle = not busy
        if hasattr(self, 'pushButton_acquisitionManager'):
            self.pushButton_acquisitionManager.setEnabled(idle)
        self.pushButton_refreshOVs.setEnabled(idle)
        self.pushButton_acquireStubOV.setEnabled(idle)
        if idle:
            self.radioButton_fromStack.setChecked(True)
        self.radioButton_fromSEM.setEnabled(idle)
        self._refresh_acquisition_manager()

    def update_grids(self):
        """Update the grid selectors after grid is added or deleted."""
        self.acq_groups.sync_inventory()
        self.vp_current_grid = -1
        if self.sv_current_grid >= self.gm.number_grids:
            self.sv_current_grid = self.gm.number_grids - 1
            self.sv_current_tile = -1
        if self.m_current_grid >= self.gm.number_grids:
            self.m_current_grid = self.gm.number_grids - 1
            self.m_current_tile = -1
        self.vp_update_grid_selector()
        self.sv_update_grid_selector()
        self.sv_update_tile_selector()
        self.m_update_grid_selector()
        self.m_update_tile_selector()
        self._refresh_acquisition_manager()

    def update_ov(self):
        """Update the overview selectors after overview is added or deleted."""
        self.acq_groups.sync_inventory()
        self.vp_current_ov = -1
        self.vp_update_ov_selector()
        self.sv_update_ov_selector()
        self.m_update_ov_selector()
        self._refresh_ov_queue()
        self._refresh_acquisition_manager()

    def _update_measure_buttons(self):
        """Display the measuring tool buttons as active or inactive."""
        if self.vp_measure_active:
            self.pushButton_measureViewport.setIcon(
                QIcon('img/measure-active.png'))
            self.pushButton_measureViewport.setIconSize(QSize(16, 16))
        else:
            self.pushButton_measureViewport.setIcon(
                QIcon('img/measure.png'))
            self.pushButton_measureViewport.setIconSize(QSize(16, 16))
        if self.sv_measure_active:
            self.pushButton_measureSliceViewer.setIcon(
                QIcon('img/measure-active.png'))
            self.pushButton_measureSliceViewer.setIconSize(QSize(16, 16))
        else:
            self.pushButton_measureSliceViewer.setIcon(
                QIcon('img/measure.png'))
            self.pushButton_measureSliceViewer.setIconSize(QSize(16, 16))

    def _draw_rectangle(self, qp, point0, point1, color, line_style=Qt.SolidLine):
        x0, y0 = point0
        x1, y1 = point1
        if x0 > x1:
            x1, x0 = x0, x1
        if y0 > y1:
            y1, y0 = y0, y1
        w = x1 - x0
        h = y1 - y0
        qp.setPen(QPen(QColor(*color), 1, line_style))
        qp.setBrush(QColor(255, 255, 255, 0))
        qp.drawRect(QRectF(x0, y0, w, h))

    def _draw_measure_labels(self, qp):
        """Draw measure labels QPainter qp. qp must be active when calling this
        method."""
        def draw_measure_point(qp, x, y):
            qp.drawEllipse(QPointF(x, y), 4, 4)
            qp.drawLine(QPointF(x, y - 10), QPointF(x, y + 10))
            qp.drawLine(QPointF(x - 10, y), QPointF(x + 10, y))

        draw_in_vp = (self.tabWidget.currentIndex() == 0)
        tile_display = (self.sv_current_tile >= 0)

        qp.setPen(QPen(QColor(*constants.COLOUR_SELECTOR[13]), 2, Qt.SolidLine))
        qp.setBrush(QColor(0, 0, 0, 0))
        if self.measure_p1[0] is not None:
            if draw_in_vp:
                p1_x, p1_y = self.cs.convert_d_to_v(self.measure_p1)
            else:
                p1_x, p1_y = self.cs.convert_d_to_sv(
                    self.measure_p1, tile_display)
            draw_measure_point(qp, p1_x, p1_y)
        if self.measure_p2[0] is not None:
            if draw_in_vp:
                p2_x, p2_y = self.cs.convert_d_to_v(self.measure_p2)
            else:
                p2_x, p2_y = self.cs.convert_d_to_sv(
                    self.measure_p2, tile_display)
            draw_measure_point(qp, p2_x, p2_y)

        if self.measure_p2[0] is not None:
            # Draw line between p1 and p2
            qp.drawLine(QPointF(p1_x, p1_y), QPointF(p2_x, p2_y))
            distance = sqrt((self.measure_p1[0] - self.measure_p2[0])**2
                            + (self.measure_p1[1] - self.measure_p2[1])**2)
            qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
            qp.setBrush(QColor(0, 0, 0, 255))
            qp.drawRect(QRectF(self.cs.vp_width - 80, self.cs.vp_height - 20, 80, 20))
            font = QFont()
            font.setPixelSize(12)
            qp.setFont(font)
            qp.setPen(QPen(QColor(*constants.COLOUR_SELECTOR[13]), 1, Qt.SolidLine))
            if distance < 1:
                qp.drawText(self.cs.vp_width - 75, self.cs.vp_height - 5,
                            str((int(distance * 1000))) + ' nm')
            else:
                qp.drawText(self.cs.vp_width - 75, self.cs.vp_height - 5,
                            '{0:.2f}'.format(distance) + ' µm')

    def grab_viewport_screenshot(self, save_path_filename):
        viewport_screenshot = self.grab()
        viewport_screenshot.save(save_path_filename)

    def show_in_incident_log(self, message):
        """Show the message in the Viewport's incident log
        (in the monitoring tab).
        """
        self.textarea_incidentLog.appendPlainText(message)

    def _process_signal(self):
        """Process signals from the acquisition thread or from dialog windows.
        """
        cmd = self.viewport_trigger.queue.get()
        msg = cmd['msg']
        args = cmd['args']
        kwargs = cmd['kwargs']
        if msg == 'DRAW VP':
            self.vp_draw()
        elif msg == 'DRAW VP NO LABELS':
            self.vp_draw(suppress_labels=True, suppress_previews=True)
        elif msg == 'UPDATE XY':
            self.main_controls_trigger.transmit(msg)
        elif msg == 'RESTRICT GUI':
            self.restrict_gui(True)
            self.main_controls_trigger.transmit(msg)
        elif msg == 'UNRESTRICT GUI':
            self.restrict_gui(False)
            self.main_controls_trigger.transmit(msg)
        elif msg == 'STATUS IDLE':
            self.main_controls_trigger.transmit(msg)
        elif msg == 'STATUS BUSY STUB':
            self.main_controls_trigger.transmit(msg)
        elif msg == 'STATUS BUSY OV':
            self.main_controls_trigger.transmit(msg)
        elif msg.startswith('ACQ IND OV'):
            self.vp_toggle_ov_acq_indicator(*args, **kwargs)
        elif msg == 'MANUAL MOVE SUCCESS':
            self._vp_manual_stage_move_success(True)
        elif msg == 'MANUAL MOVE FAILURE':
            self._vp_manual_stage_move_success(False)
        elif msg == 'REFRESH OV SUCCESS':
            self._vp_overview_acq_success(True)
        elif msg == 'REFRESH OV FAILURE':
            self._vp_overview_acq_success(False)
        elif msg == 'VP GRID ACQ FINISHED':
            self._vp_grid_acq_finished(*args, **kwargs)
        elif msg == 'STUB OV SUCCESS':
            self._vp_finish_stub_overview('success', *args, **kwargs)
        elif msg == 'STUB OV FAILURE':
            self._vp_finish_stub_overview('failure', *args, **kwargs)
        elif msg == 'STUB OV ABORTED':
            self._vp_finish_stub_overview('aborted', *args, **kwargs)
        elif msg == 'SHOW IMPORTED':
            self.checkBox_showImported.setChecked(True)
        elif msg == 'ARRAY REMOVE IMAGE':
            self.main_controls_trigger.transmit(msg)
        else:
            self._add_to_main_log(msg)

    def _vp_normalize_selection_state(self):
        if (self.selected_grid is not None
                and not (0 <= self.selected_grid < self.gm.number_grids)):
            self.selected_grid = None
            self.selected_tile = None
        elif self.selected_grid is not None and self.selected_tile is not None:
            grid = self.gm[self.selected_grid]
            if not (0 <= self.selected_tile < grid.number_tiles):
                self.selected_tile = None

        if (self.selected_ov is not None
                and not (0 <= self.selected_ov < self.ovm.number_ov)):
            self.selected_ov = None

        if (self.selected_imported is not None
                and not (0 <= self.selected_imported < len(self.imported))):
            self.selected_imported = None

        if (self.vp_current_grid >= 0
                and not (0 <= self.vp_current_grid < self.gm.number_grids)):
            self.vp_current_grid = -1

    def _add_to_main_log(self, msg):
        """Add entry to the log in the main window via main_controls_trigger."""
        self.main_controls_trigger.transmit(utils.format_log_entry(msg))

    def closeEvent(self, event):
        """This overrides the QWidget's closeEvent(). Viewport must be
        deactivated first before the window can be closed."""
        if self.active:
            QMessageBox.information(self, 'Closing Viewport',
                'The Viewport window can only be closed by closing the main '
                'window of the application.', QMessageBox.Ok)
            event.ignore()
        else:
            event.accept()

    # ======================= Below: event-handling methods ========================

    def setMouseTracking(self, flag):
        """Recursively activate or deactive mouse tracking in a widget."""
        def recursive_set(parent):
            for child in parent.findChildren(QObject):
                try:
                    child.setMouseTracking(flag)
                except:
                    pass
                recursive_set(child)
        QWidget.setMouseTracking(self, flag)
        recursive_set(self)

    def mousePressEvent(self, event):
        self.setFocus()
        p = event.pos()
        px, py = p.x() - constants.VP_MARGIN_X, p.y() - constants.VP_MARGIN_Y
        mouse_pos_within_viewer = (
            px in range(self.cs.vp_width) and py in range(self.cs.vp_height))
        mouse_pos_within_plot_area = (
            px in range(445, 940) and py in range(22, 850))

        if self.sem.simulation_mode:
            # update stage position indicator at any click in VP
            self.stage.get_xy()
            self.vp_draw()

        if ((event.button() == Qt.RightButton)
                and self.tabWidget.currentIndex() == 0
                and mouse_pos_within_viewer
                and self.vp_polygon_tool == polygon_roi.CUSTOM_SHAPE_TYPE
                and self.vp_polygon_custom_points):
            self._vp_add_custom_polygon_vertex(
                self.cs.convert_mouse_to_v((px, py)))
            self.vp_polygon_hover_point = list(
                self.cs.convert_mouse_to_v((px, py)))
            self._vp_finalize_custom_polygon()
            return

        if ((event.button() == Qt.LeftButton)
            and (self.tabWidget.currentIndex() < 2)
            and mouse_pos_within_viewer):

            if self.tabWidget.currentIndex() == 0 and self.vp_polygon_tool_spec is not None:
                if self.vp_polygon_tool == polygon_roi.CUSTOM_SHAPE_TYPE:
                    point_d = self.cs.convert_mouse_to_v((px, py))
                    self._vp_add_custom_polygon_vertex(point_d)
                    self.vp_polygon_hover_point = list(point_d)
                    self.vp_draw()
                else:
                    self._vp_place_shape_from_tool(
                        self.cs.convert_mouse_to_v((px, py)))
                return

            if ((self.tabWidget.currentIndex() == 0)
                    and (QApplication.keyboardModifiers() == Qt.NoModifier)
                    and not self.busy):
                hit = self._vp_polygon_handle_hit_test(px, py)
                if hit is not None:
                    self.selected_grid = hit[0]
                    self.selected_tile = None
                    self.selected_ov = None
                    self.selected_imported = None
                    self._vp_begin_polygon_handle_drag(hit[1], hit[2])
                    self.vp_draw()
                    return

            self.selected_grid, self.selected_tile = \
                self._vp_grid_tile_mouse_selection(px, py)
            self.selected_ov = self._vp_ov_mouse_selection(px, py)
            self.selected_imported = (
                self._vp_imported_img_mouse_selection(px, py))

            if ((self.tabWidget.currentIndex() == 0)
                    and (QApplication.keyboardModifiers() == Qt.NoModifier)
                    and not self.busy
                    and self.selected_grid is None
                    and self.selected_ov is None
                    and self.selected_imported is None):
                polygon_grid = self._vp_polygon_body_hit_test(
                    px, py, allow_large_deferred_interior=False)
                if polygon_grid is not None:
                    self.selected_grid = polygon_grid
                    self.selected_tile = None
                    self.vp_draw()
                    return

            if ((self.tabWidget.currentIndex() == 0)
                    and (QApplication.keyboardModifiers() == Qt.NoModifier)
                    and self.selected_grid is not None
                    and self.gm[self.selected_grid].has_polygon_roi()):
                self.selected_tile = None
                self.selected_ov = None
                self.selected_imported = None
                self.vp_draw()
                return

            # Disable self.selected_template for now (causing runtime warnings)
            # TODO (Benjamin / Philipp): look into this
            # self.selected_template = self._vp_template_mouse_selection(px, py)

            # Shift pressed in first tab? Toggle active tiles.
            if ((self.tabWidget.currentIndex() == 0)
               and (QApplication.keyboardModifiers() == Qt.ShiftModifier)):
                if (self.vp_current_grid >= -2
                   and self.selected_grid is not None
                   and self.selected_tile is not None):
                    if self.busy:
                        user_reply = QMessageBox.question(self,
                            'Confirm tile activation',
                            'Stack acquisition in progress! Please confirm '
                            'that you want to activate/deactivate this tile. '
                            'The new selection will take effect after imaging '
                            'of the current slice is completed.',
                            QMessageBox.Ok | QMessageBox.Cancel)
                        if user_reply == QMessageBox.Ok:
                            new_tile_status = self.gm[
                                self.selected_grid].toggle_active_tile(
                                self.selected_tile)
                            if self.autofocus.tracking_mode == 1:
                                self.gm[
                                    self.selected_grid][
                                    self.selected_tile].autofocus_active ^= True
                            self._add_to_main_log(
                                f'CTRL: Tile {self.selected_grid}.'
                                f'{self.selected_tile}{new_tile_status}')
                            self.vp_update_after_active_tile_selection()
                    else:
                        # If no acquisition in progress,
                        # first toggle current tile.
                        self.gm[self.selected_grid].toggle_active_tile(
                            self.selected_tile)
                        if self.autofocus.tracking_mode == 1:
                            self.gm[self.selected_grid][
                                    self.selected_tile].autofocus_active ^= True
                        self.vp_draw()
                        # Then enter paint mode until mouse button released.
                        self.tile_paint_mode_active = True

            # Check if Ctrl key is pressed -> Move OV
            elif ((self.tabWidget.currentIndex() == 0)
                and (QApplication.keyboardModifiers() == Qt.ControlModifier)
                and self.vp_current_ov >= -2
                and not self.busy):
                if self.selected_ov is not None and self.selected_ov >= 0:
                    if self.ovm[self.selected_ov].locked:
                        QMessageBox.information(
                            self, 'Overview locked',
                            f'OV {self.selected_ov} is acquired and locked.\n'
                            'Unlock it from the context menu before moving.',
                            QMessageBox.Ok)
                    else:
                        self.ov_drag_active = True
                        self.drag_origin = (px, py)
                        self.stage_pos_backup = (
                            self.ovm[self.selected_ov].centre_sx_sy)
                else:
                    # Draw OV
                    self.ov_draw_active = True
                    self.drag_origin = px, py
                    self.drag_current = self.drag_origin

            # Ctrl pressed in Array mode: select grid or draw selection box for grids
            #elif ((self.tabWidget.currentIndex() == 0)
            #    and (QApplication.keyboardModifiers() == Qt.ControlModifier)
            #    and not self.busy
            #    and self.gm.array_mode):
            #    # Select grid or draw selection box for grids
            #    self.grid_selection_or_draw_selection_box_active = True
            #    self.drag_origin = px, py
            #    # it is crucial to update drag_current
            #    # otherwise when doing a simple click without dragging
            #    # the drag_current value is taken from the last time
            #    # a drag was performed
            #    self.drag_current = self.drag_origin

            # Check if Alt key is pressed -> Move grid
            elif ((self.tabWidget.currentIndex() == 0)
                and (QApplication.keyboardModifiers() == Qt.AltModifier)
                and self.vp_current_grid >= -2
                and not self.busy):
                if self.selected_grid is None:
                    polygon_grid = self._vp_polygon_body_hit_test(
                        px, py, allow_large_deferred_interior=False)
                    if polygon_grid is not None:
                        self.selected_grid = polygon_grid
                        self.selected_tile = None
                        self.selected_ov = None
                        self.selected_imported = None
                if self.selected_grid is not None and self.selected_grid >= 0:
                    if self.gm[self.selected_grid].locked:
                        QMessageBox.information(
                            self, 'Grid locked',
                            f'{self.gm.get_grid_label(self.selected_grid)} '
                            'is acquired and locked.\nUnlock it from the '
                            'context menu before moving.',
                            QMessageBox.Ok)
                    else:
                        self.grid_drag_active = True
                        self.drag_origin = px, py
                        self.drag_current = self.drag_origin
                        # Save coordinates in case user wants to undo
                        self.stage_pos_backup = (
                            self.gm[self.selected_grid].origin_sx_sy)
                else:
                    # Draw grid
                    self.grid_draw_active = True
                    self.drag_origin = px, py
                    self.drag_current = self.drag_origin

            # Check if ctrl+shift key is pressed -> Move template
            elif ((self.tabWidget.currentIndex() == 0)
                  and (QApplication.keyboardModifiers() == (Qt.ControlModifier | Qt.ShiftModifier))
                  and not self.busy):
                if self.selected_template:
                    self.template_drag_active = True
                    self.drag_origin = px, py
                    self.drag_current = self.drag_origin
                    # Save coordinates in case user wants to undo
                    self.stage_pos_backup = self.tm.template.origin_sx_sy
                else:
                    # Draw template
                    self.template_draw_active = True
                    self.drag_origin = px, py
                    self.drag_current = self.drag_origin

            # Check if Ctrl + Alt keys are pressed -> Move imported image
            elif ((self.tabWidget.currentIndex() == 0)
                and (QApplication.keyboardModifiers()
                    == (Qt.ControlModifier | Qt.AltModifier))):
                if self.selected_imported is not None:
                    self.imported_img_drag_active = True
                    self.drag_origin = px, py
                    self.drag_current = self.drag_origin
                    # Save coordinates in case user wants to undo
                    self.stage_pos_backup = (
                        self.imported[self.selected_imported].centre_sx_sy)
            # No key pressed -> Panning
            elif (QApplication.keyboardModifiers() == Qt.NoModifier):
                # Move the viewport's FOV
                self.fov_drag_active = True
                # For now, disable showing saturated pixels (too slow)
                if self.show_saturated_pixels:
                    self.checkBox_showSaturated.setChecked(False)
                    self.show_saturated_pixels = False
                self.drag_origin = (p.x() - constants.VP_MARGIN_X,
                                    p.y() - constants.VP_MARGIN_Y)
        # Now check right mouse button for context menus and measuring tool
        if ((event.button() == Qt.RightButton)
                and (self.tabWidget.currentIndex() < 2)
                and mouse_pos_within_viewer):
            if self.tabWidget.currentIndex() == 0:
                if self.vp_measure_active:
                    self._vp_set_measure_point(px, py)
                else:
                    self.vp_show_context_menu(p)
            elif self.tabWidget.currentIndex() == 1:
                if self.sv_measure_active:
                    self._sv_set_measure_point(px, py)
                else:
                    self.sv_show_context_menu(p)

        # Left mouse click in statistics tab to select a slice
        if ((event.button() == Qt.LeftButton)
            and (self.tabWidget.currentIndex() == 2)
            and mouse_pos_within_plot_area
            and self.m_tab_populated):
            self.m_selected_plot_slice = np.clip(
                int((px - 445)/3), 0, 164)
            self.m_draw_plots()
            if self.m_selected_slice_number is not None:
                self.m_draw_histogram()
                self.m_draw_reslice()

    def mouseDoubleClickEvent(self, event):
        self.doubleclick_registered = True

    def mouseMoveEvent(self, event):
        p = event.pos()
        px, py = p.x() - constants.VP_MARGIN_X, p.y() - constants.VP_MARGIN_Y
        # Show current stage and SEM coordinates at mouse position
        mouse_pos_within_viewer = (
            px in range(self.cs.vp_width) and py in range(self.cs.vp_height))
        if ((self.tabWidget.currentIndex() == 0)
                and mouse_pos_within_viewer):
            sx, sy = self.cs.convert_mouse_to_s((px, py))
            dx, dy = self.cs.convert_s_to_d([sx, sy])
            display_text, full_text = self._format_mouse_position_text(
                sx, sy, dx, dy)
            self.label_mousePos.setText(display_text)
            self.label_mousePos.setToolTip(
                full_text if display_text != full_text else '')
        else:
            self.label_mousePos.setText('-')
            self.label_mousePos.setToolTip('')

        # Move grid/OV or FOV:
        if self.vp_polygon_handle_drag is not None:
            self.setCursor(Qt.CrossCursor)
            self._vp_update_polygon_resize(px, py)
        elif self.vp_polygon_vertex_drag is not None:
            self.setCursor(Qt.CrossCursor)
            self._vp_update_polygon_vertex(px, py)
        elif (self.tabWidget.currentIndex() == 0
                and mouse_pos_within_viewer
                and self.vp_polygon_tool_spec is not None):
            self.setCursor(Qt.CrossCursor)
            if self.vp_polygon_tool == polygon_roi.CUSTOM_SHAPE_TYPE:
                self.vp_polygon_hover_point = list(
                    self.cs.convert_mouse_to_v((px, py)))
                if self.vp_polygon_custom_points:
                    self.vp_draw()
        elif self.grid_drag_active:
            # Change cursor appearence
            self.setCursor(Qt.SizeAllCursor)
            drag_vector = (px - self.drag_origin[0],
                           py - self.drag_origin[1])
            # Update drag origin
            self.drag_origin = px, py
            self._vp_reposition_grid(drag_vector)
        elif self.ov_drag_active:
            self.setCursor(Qt.SizeAllCursor)
            drag_vector = (px - self.drag_origin[0],
                           py - self.drag_origin[1])
            self.drag_origin = px, py
            self._vp_reposition_ov(drag_vector)
        elif self.template_drag_active:
            self.setCursor(Qt.SizeAllCursor)
            drag_vector = (px - self.drag_origin[0],
                           py - self.drag_origin[1])
            self.drag_origin = px, py
            self._vp_reposition_template(drag_vector)
        elif self.imported_img_drag_active:
            self.setCursor(Qt.SizeAllCursor)
            drag_vector = (px - self.drag_origin[0],
                           py - self.drag_origin[1])
            self.drag_origin = px, py
            self._vp_reposition_imported_img(drag_vector)
        elif self.fov_drag_active:
            self.setCursor(Qt.SizeAllCursor)
            drag_vector = self.drag_origin[0] - px, self.drag_origin[1] - py
            self.drag_origin = px, py
            if self.tabWidget.currentIndex() == 0:
                self._vp_shift_fov(drag_vector)
            if self.tabWidget.currentIndex() == 1:
                self._sv_shift_fov(drag_vector)
        elif self.tile_paint_mode_active:
            # Toggle tiles in "painting" mode.
            prev_selected_grid = self.selected_grid
            prev_selected_tile = self.selected_tile
            self.selected_grid, self.selected_tile = (
                self._vp_grid_tile_mouse_selection(px, py))
            # If mouse has moved to a new tile, toggle it
            if (self.selected_grid is not None
                and self.selected_tile is not None):
                if ((self.selected_grid == prev_selected_grid
                     and self.selected_tile != prev_selected_tile)
                     or self.selected_grid != prev_selected_grid):
                        self.gm[self.selected_grid].toggle_active_tile(
                            self.selected_tile)
                        if self.autofocus.tracking_mode == 1:
                            self.gm[self.selected_grid][
                                    self.selected_tile].autofocus_active ^= True
                        self.vp_draw()
            else:
                # Disable paint mode when mouse moved beyond grid edge.
                self.tile_paint_mode_active = False
        elif (
            self.grid_draw_active
            or self.ov_draw_active
            or self.template_draw_active
            or self.grid_selection_or_draw_selection_box_active
        ):

            # if the modifier key is not held down any more during the operation
            # then stop the operation
            if QApplication.keyboardModifiers()!=Qt.AltModifier:
                self.grid_draw_active = False

            if QApplication.keyboardModifiers()!=Qt.ControlModifier:
                self.ov_draw_active = False

            if not (QApplication.keyboardModifiers()==(Qt.ControlModifier | Qt.ShiftModifier)):
                self.template_draw_active = False

            if QApplication.keyboardModifiers()!=Qt.ControlModifier:
                self.grid_selection_or_draw_selection_box_active = False

            self.drag_current = px, py
            self.vp_draw()

        elif ((self.tabWidget.currentIndex() == 0)
            and mouse_pos_within_viewer
            and self.vp_measure_active):
                # Change cursor appearence
                self.setCursor(Qt.CrossCursor)
                if self.measure_p1[0] is not None and not self.measure_complete:
                    self._vp_set_measure_point(px, py)
        elif ((self.tabWidget.currentIndex() == 1)
            and mouse_pos_within_viewer
            and self.sv_measure_active):
                self.setCursor(Qt.CrossCursor)
                if self.measure_p1[0] is not None and not self.measure_complete:
                    self._sv_set_measure_point(px, py)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if not self.vp_measure_active:
            self.setCursor(Qt.ArrowCursor)
        # Process doubleclick
        if self.doubleclick_registered:
            p = event.pos()
            px, py = p.x() - constants.VP_MARGIN_X, p.y() - constants.VP_MARGIN_Y
            if px in range(self.cs.vp_width) and py in range(self.cs.vp_height):
                if self.tabWidget.currentIndex() == 0:
                    self.selected_grid, self.selected_tile = (
                        self._vp_grid_tile_mouse_selection(px, py))
                    self.selected_ov = self._vp_ov_mouse_selection(px, py)
                    if self.selected_grid is not None:
                        self._vp_open_grid_settings()
                    elif self.selected_ov is not None:
                        self._vp_open_ov_settings()
                    else:
                        self._vp_mouse_zoom(px, py, 2)
                elif self.tabWidget.currentIndex() == 1:
                    # Disable native resolution
                    self.sv_disable_native_resolution()
                    # Zoom in:
                    self._sv_mouse_zoom(px, py, 2)
            self.doubleclick_registered = False

        elif event.button() == Qt.LeftButton:
            if self.vp_polygon_handle_drag is not None:
                self.vp_polygon_handle_drag = None
                self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')
                return
            if self.vp_polygon_vertex_drag is not None:
                self.vp_polygon_vertex_drag = None
                self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')
                return
            if self.grid_drag_active:
                user_reply = QMessageBox.question(
                    self, 'Repositioning grid',
                    'You have moved the selected grid. Please '
                    'confirm the new position. Click "Cancel" to undo.',
                    QMessageBox.Ok | QMessageBox.Cancel)
                if user_reply == QMessageBox.Cancel:
                    # Restore origin coordinates
                    self.gm[self.selected_grid].origin_sx_sy = (
                        self.stage_pos_backup)
                else:
                    self.ovm.update_all_debris_detections_areas(self.gm)

            if self.ov_drag_active:
                user_reply = QMessageBox.question(
                    self, 'Repositioning overview',
                    'You have moved the selected overview. Please '
                    'confirm the new position. Click "Cancel" to undo.',
                    QMessageBox.Ok | QMessageBox.Cancel)
                if user_reply == QMessageBox.Cancel:
                    # Restore centre coordinates
                    self.ovm[self.selected_ov].centre_sx_sy = (
                        self.stage_pos_backup)
                else:
                    # Remove current preview image from file list
                    self.ovm[self.selected_ov].vp_file_path = ''
                    self.ovm.update_all_debris_detections_areas(self.gm)
            if self.template_drag_active:
                self.template_drag_active = False
                user_reply = QMessageBox.question(
                    self, 'Repositioning template',
                    'You have moved the selected template. Please '
                    'confirm the new position. Click "Cancel" to undo.',
                    QMessageBox.Ok | QMessageBox.Cancel)
                if user_reply == QMessageBox.Cancel:
                    # Restore centre coordinates
                    self.tm.template.origin_sx_sy = self.stage_pos_backup

            if (
                self.grid_draw_active
                or self.ov_draw_active
                or self.template_draw_active
                or self.grid_selection_or_draw_selection_box_active
            ):
                x0, y0 = self.cs.convert_mouse_to_v(self.drag_origin)
                x1, y1 = self.cs.convert_mouse_to_v(self.drag_current)
                if x0 > x1:
                    x1, x0 = x0, x1
                if y0 > y1:
                    y1, y0 = y0, y1
                w = x1 - x0
                h = y1 - y0

            if self.grid_draw_active:
                if h != 0 and w != 0:
                    self.grid_draw_active = False
                    layout = self.gm.estimate_grid_layout_for_drag(x0, y0, w, h)
                    creation_mode = (
                        self._vp_prompt_large_rectangular_grid_creation(layout))
                    if creation_mode == 'defer':
                        self._vp_create_deferred_rectangle_roi(
                            (x0, y0), (w, h), layout)
                    elif creation_mode == 'materialize':
                        self.gm.draw_grid(x0, y0, w, h)
                        self.main_controls_trigger.transmit(
                            'GRID SETTINGS CHANGED')

            if self.ov_draw_active:
                if h != 0 and w != 0:
                    self.ov_draw_active = False
                    self.ovm.draw_overview(x0, y0, w, h)
                    self.main_controls_trigger.transmit('OV SETTINGS CHANGED')

            if self.template_draw_active:
                if h != 0 and w != 0:
                    self.template_draw_active = False
                    self.tm.draw_template(x0, y0, w, h)
                    self.main_controls_trigger.transmit('TEMPLATE SETTINGS CHANGED')

            # ---- Array mode ----
            if self.grid_selection_or_draw_selection_box_active:
                self.grid_selection_or_draw_selection_box_active = False

                # checking whether no other action than
                # simple section click was performed
                if not any([
                    self.grid_drag_active,
                    self.ov_drag_active,
                    self.tile_paint_mode_active,
                    self.imported_img_drag_active]):

                    if h != 0 and w != 0:
                        #find grids in the drawn box
                        contained_grid_indexes = []
                        for grid_index in range(self.gm.number_grids):
                            grid_bb = self.gm[grid_index].bounding_box()
                            if all([
                                grid_bb[0] > x0,
                                grid_bb[1] < x0 + w,
                                grid_bb[2] > y0,
                                grid_bb[3] < y0 + h
                            ]):

                                contained_grid_indexes.append(grid_index)
                        if len(contained_grid_indexes)>0:
                            self.main_controls_trigger.transmit(
                                'ARRAY SET SECTION STATE',
                                'toggle',
                                contained_grid_indexes)
                    else:
                        if self.selected_grid is None:
                            # ctrl+click in background: deselect all
                            # ask for confirmation if more than 10 grids already selected
                            if len(self.gm.array_data.selected_sections)>=10:
                                user_reply = QMessageBox.question(
                                    self, 'Large deselection',
                                    'Deselect all '
                                    + str(len(self.gm.array_data.selected_sections))
                                    + ' grids?',
                                    QMessageBox.Ok | QMessageBox.Cancel)
                                if user_reply == QMessageBox.Ok:
                                    self.main_controls_trigger.transmit(
                                        'ARRAY SET SECTION STATE', 'deselectall')
                            else:
                                self.main_controls_trigger.transmit(
                                    'ARRAY SET SECTION STATE', 'deselectall')
                        else:
                            self.main_controls_trigger.transmit(
                                'ARRAY SET SECTION STATE',
                                'toggle',
                                [self.selected_grid])

            if self.tile_paint_mode_active:
                self.vp_update_after_active_tile_selection()
            if self.imported_img_drag_active:
                user_reply = QMessageBox.question(
                    self, 'Repositioning imported image',
                    'You have moved the selected imported image. Please '
                    'confirm the new position. Click "Cancel" to undo.',
                    QMessageBox.Ok | QMessageBox.Cancel)
                imported = self.imported[self.selected_imported]
                if user_reply == QMessageBox.Cancel:
                    # Restore centre coordinates
                    imported.centre_sx_sy = self.stage_pos_backup
                elif imported.is_array:
                    self.gm.array_update_data_image_properties(imported)

            self.fov_drag_active = False
            self.grid_drag_active = False
            self.ov_drag_active = False
            self.tile_paint_mode_active = False
            self.imported_img_drag_active = False

            # Update viewport
            self.vp_draw()
            self._refresh_ov_queue()
            self.main_controls_trigger.transmit('SHOW CURRENT SETTINGS')

        elif event.button() == Qt.RightButton:
            if self.vp_measure_active or self.sv_measure_active:
                self.measure_complete = True

    def wheelEvent(self, event):
        if self.tabWidget.currentIndex() == 1:
            if event.angleDelta().y() > 0:
                self.sv_slice_fwd()
            if event.angleDelta().y() < 0:
                self.sv_slice_bwd()
        if self.tabWidget.currentIndex() == 0:
            p = event.pos()
            px, py = p.x() - constants.VP_MARGIN_X, p.y() - constants.VP_MARGIN_Y
            mouse_pos_within_viewer = (
                px in range(self.cs.vp_width) and py in range(self.cs.vp_height))
            if mouse_pos_within_viewer:
                mouse_delta_factor = 1.1
                if event.angleDelta().y() > 0:
                    self._vp_mouse_zoom(px, py, mouse_delta_factor)
                if event.angleDelta().y() < 0:
                    self._vp_mouse_zoom(px, py, 1 / mouse_delta_factor)

    def keyPressEvent(self, event):
        # Move through slices in slice-by-slice viewer with PgUp/PgDn
        if (type(event) == QKeyEvent) and (self.tabWidget.currentIndex() == 1):
            if event.key() == Qt.Key_PageUp:
                self.sv_slice_fwd()
            elif event.key() == Qt.Key_PageDown:
                self.sv_slice_bwd()
        elif (type(event) == QKeyEvent) and (self.tabWidget.currentIndex() == 0):
            modifiers = event.modifiers()
            if event.key() == Qt.Key_Escape and self.vp_polygon_tool_spec is not None:
                self._vp_disarm_polygon_tool()
            elif modifiers == Qt.NoModifier and event.key() == Qt.Key_H:
                self.vp_toggle_show_grid_lines_shortcut()
            elif modifiers == Qt.NoModifier and event.key() == Qt.Key_G:
                self.vp_toggle_tile_previews_shortcut()
            elif event.key() == Qt.Key_Delete:
                self._vp_delete_selected_grid()
            elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_C:
                self._vp_copy_selected_grid()
            elif modifiers == Qt.ControlModifier and event.key() == Qt.Key_V:
                if self.vp_polygon_clipboard is not None:
                    self._vp_paste_grid_at(self.cs.vp_centre_dx_dy)

    def resizeEvent(self, event):
        """Adjust the Viewport and Slice-by-slice viewer canvas when the window
        is resized.
        """
        self._layout_polygon_toolbar()
        self.cs.vp_width = event.size().width() - constants.VP_WINDOW_DIFF_X
        self.cs.vp_height = event.size().height() - constants.VP_WINDOW_DIFF_Y
        self.cs.update_vp_origin_dx_dy()
        self.vp_canvas = QPixmap(self.cs.vp_width, self.cs.vp_height)
        self.sv_canvas = QPixmap(self.cs.vp_width, self.cs.vp_height)
        if self.use_klab_ui:
            self.apply_klab_viewport_geometry_tweaks()
        else:
            self._layout_viewport_selector_controls()
            self._layout_viewport_display_controls()
        self.vp_draw()
        self.sv_draw()

    def _vp_polygon_layout_summary(self, size):
        if self.gm.template_grid_index >= self.gm.number_grids:
            self.gm.template_grid_index = 0
        template_grid = self.gm[self.gm.template_grid_index]
        return self.gm.polygon_layout_summary(
            float(size[0]),
            float(size[1]),
            template_grid.frame_size,
            template_grid.pixel_size,
            template_grid.overlap,
            template_grid.row_shift)

    def _vp_prompt_large_polygon_creation(self, shape_name, layout):
        guardrail = self.gm.polygon_guardrail_state(layout['tile_count'])
        if not guardrail['warn']:
            return 'materialize'

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Warning)
        message_box.setWindowTitle('Large polygon ROI')
        shape_label = shape_name or 'Polygon ROI'
        message_box.setText(
            f'{shape_label} would create approximately '
            f'{layout["tile_count"]:,} tiles '
            f'({layout["rows"]} x {layout["cols"]}).')
        if guardrail['block_materialize']:
            message_box.setInformativeText(
                'This is above the safe immediate materialization limit for the '
                'viewport. Create it as a deferred ROI instead, then refine '
                'settings before materializing.')
        else:
            message_box.setInformativeText(
                'Large polygon grids can make the GUI slow. '
                'Recommended: create a deferred ROI placeholder first.')
        deferred_button = message_box.addButton(
            'Create Deferred ROI', QMessageBox.AcceptRole)
        if not guardrail['block_materialize']:
            materialize_button = message_box.addButton(
                'Create Full Grid', QMessageBox.ActionRole)
        else:
            materialize_button = None
        cancel_button = message_box.addButton(QMessageBox.Cancel)
        message_box.setDefaultButton(deferred_button)
        message_box.exec()

        clicked_button = message_box.clickedButton()
        if clicked_button == deferred_button:
            return 'defer'
        if materialize_button is not None and clicked_button == materialize_button:
            return 'materialize'
        if clicked_button == cancel_button:
            return 'cancel'
        return 'cancel'

    def _vp_prompt_large_rectangular_grid_creation(self, layout):
        guardrail = self.gm.polygon_guardrail_state(layout['tile_count'])
        if not guardrail['warn']:
            return 'materialize'

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Warning)
        message_box.setWindowTitle('Large rectangular grid')
        message_box.setText(
            f'This rectangular grid would create approximately '
            f'{layout["tile_count"]:,} tiles '
            f'({layout["rows"]} x {layout["cols"]}).')
        if guardrail['block_materialize']:
            message_box.setInformativeText(
                'This is above the safe immediate materialization limit for the '
                'viewport. Create a deferred rectangle ROI instead, then refine '
                'settings before materializing.')
        else:
            message_box.setInformativeText(
                'Large rectangular grids can make the GUI slow. '
                'Recommended: create a deferred rectangle ROI placeholder first.')
        deferred_button = message_box.addButton(
            'Create Deferred ROI', QMessageBox.AcceptRole)
        if not guardrail['block_materialize']:
            materialize_button = message_box.addButton(
                'Create Full Grid', QMessageBox.ActionRole)
        else:
            materialize_button = None
        cancel_button = message_box.addButton(QMessageBox.Cancel)
        message_box.setDefaultButton(deferred_button)
        message_box.exec()

        clicked_button = message_box.clickedButton()
        if clicked_button == deferred_button:
            return 'defer'
        if materialize_button is not None and clicked_button == materialize_button:
            return 'materialize'
        if clicked_button == cancel_button:
            return 'cancel'
        return 'cancel'

    def _vp_create_deferred_rectangle_roi(self, top_left_dx_dy, size,
                                          estimated_layout):
        grid_index = self.gm.add_new_grid_from_polygon(
            top_left_dx_dy=top_left_dx_dy,
            size=size,
            shape_type='rectangle',
            points_norm=polygon_roi.predefined_points_norm('rectangle'),
            shape_name='Rectangle ROI',
            materialize=False,
            estimated_layout=estimated_layout)
        self.selected_grid = grid_index
        self.selected_tile = None
        self.vp_current_grid = grid_index
        self.vp_update_grid_selector()
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')
        self._add_to_main_log(
            f'CTRL: Created deferred ROI placeholder for '
            f'{self.gm.get_grid_label(grid_index)} '
            f'({estimated_layout["tile_count"]:,} estimated tiles).')

    def _vp_create_polygon_grid(self, shape_type, points_norm, top_left_dx_dy,
                                size, shape_name=''):
        layout = self._vp_polygon_layout_summary(size)
        creation_mode = self._vp_prompt_large_polygon_creation(shape_name, layout)
        if creation_mode == 'cancel':
            return
        grid_index = self.gm.add_new_grid_from_polygon(
            top_left_dx_dy=top_left_dx_dy,
            size=size,
            shape_type=shape_type,
            points_norm=points_norm,
            shape_name=shape_name,
            materialize=(creation_mode == 'materialize'),
            estimated_layout=layout)
        self.selected_grid = grid_index
        self.selected_tile = None
        self.vp_current_grid = grid_index
        self.vp_update_grid_selector()
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')
        if creation_mode == 'defer':
            self._add_to_main_log(
                f'CTRL: Created deferred ROI placeholder for '
                f'{self.gm.get_grid_label(grid_index)} '
                f'({layout["tile_count"]:,} estimated tiles).')
        self._vp_disarm_polygon_tool()
        self.vp_draw()

    def _vp_place_shape_from_tool(self, centre_dx_dy):
        if self.vp_polygon_tool_spec is None:
            return
        shape_type = self.vp_polygon_tool_spec['shape_type']
        size_um = self.vp_polygon_tool_spec.get('size_um')
        if (shape_type == polygon_roi.IMPORTED_SHAPE_TYPE
                and isinstance(size_um, list)
                and len(size_um) == 2
                and size_um[0] > 0
                and size_um[1] > 0):
            width = float(size_um[0])
            height = float(size_um[1])
            top_left_x = float(centre_dx_dy[0] - width / 2)
            top_left_y = float(centre_dx_dy[1] - height / 2)
        else:
            vp_width_d, vp_height_d = self._vp_visible_sem_dimensions()
            top_left_x, top_left_y, width, height = (
                polygon_roi.make_default_shape_bounds(
                    centre_dx_dy[0],
                    centre_dx_dy[1],
                    vp_width_d,
                    vp_height_d,
                    shape_type))
        self._vp_create_polygon_grid(
            shape_type=shape_type,
            points_norm=self.vp_polygon_tool_spec['points_norm'],
            top_left_dx_dy=(top_left_x, top_left_y),
            size=(width, height),
            shape_name=self.vp_polygon_tool_spec['shape_name'])

    def _vp_finalize_custom_polygon(self):
        if len(self.vp_polygon_custom_points) < 3:
            QMessageBox.information(
                self,
                'Custom polygon ROI',
                'Add at least 3 vertices before closing the polygon.',
                QMessageBox.Ok)
            return
        points_norm, bounds = polygon_roi.normalize_points(
            self.vp_polygon_custom_points)
        self._vp_create_polygon_grid(
            shape_type=polygon_roi.CUSTOM_SHAPE_TYPE,
            points_norm=points_norm,
            top_left_dx_dy=(bounds[0], bounds[1]),
            size=(bounds[2], bounds[3]),
            shape_name='Custom polygon')

    def _vp_add_custom_polygon_vertex(self, point_d):
        if point_d is None:
            return
        point_d = [float(point_d[0]), float(point_d[1])]
        if self.vp_polygon_custom_points:
            last_point = self.vp_polygon_custom_points[-1]
            if np.linalg.norm(np.array(point_d) - np.array(last_point)) < 1e-9:
                return
        self.vp_polygon_custom_points.append(point_d)

    def _vp_grid_topleft_dx_dy(self, grid_index):
        grid = self.gm[grid_index]
        return (
            grid.origin_dx_dy[0] - grid.tile_width_d() / 2,
            grid.origin_dx_dy[1] - grid.tile_height_d() / 2)

    def _vp_grid_local_to_global_d(self, grid_index, local_point):
        grid = self.gm[grid_index]
        rel_x = local_point[0] - grid.tile_width_d() / 2
        rel_y = local_point[1] - grid.tile_height_d() / 2
        theta = radians(grid.rotation)
        if theta != 0:
            rot_x = rel_x * cos(theta) - rel_y * sin(theta)
            rot_y = rel_x * sin(theta) + rel_y * cos(theta)
            rel_x, rel_y = rot_x, rot_y
        return [grid.origin_dx_dy[0] + rel_x, grid.origin_dx_dy[1] + rel_y]

    def _vp_mouse_to_grid_local_d(self, px, py, grid_index):
        grid = self.gm[grid_index]
        dx, dy = grid.origin_dx_dy
        origin_vx, origin_vy = self.cs.convert_d_to_v((dx, dy))
        x_pos = px - origin_vx
        y_pos = py - origin_vy
        theta = radians(grid.rotation)
        if theta != 0:
            rot_x = x_pos * cos(-theta) - y_pos * sin(-theta)
            rot_y = x_pos * sin(-theta) + y_pos * cos(-theta)
            x_pos, y_pos = rot_x, rot_y
        x_pos = x_pos / self.cs.vp_scale + grid.tile_width_d() / 2
        y_pos = y_pos / self.cs.vp_scale + grid.tile_height_d() / 2
        return [x_pos, y_pos]

    def _vp_polygon_points_v(self, grid_index, local_points=None):
        grid = self.gm[grid_index]
        if local_points is None:
            local_points = grid.roi_local_points_d()
        transform = self._vp_grid_local_transform_v(grid_index)
        viewport_points = []
        for point in local_points:
            mapped = transform.map(
                QPointF(
                    float(point[0] * self.cs.vp_scale),
                    float(point[1] * self.cs.vp_scale)))
            viewport_points.append([mapped.x(), mapped.y()])
        return viewport_points

    def _vp_grid_local_transform_v(self, grid_index):
        grid = self.gm[grid_index]
        dx, dy = grid.origin_dx_dy
        origin_vx, origin_vy = self.cs.convert_d_to_v((dx, dy))
        top_left_dx = dx - grid.tile_width_d() / 2
        top_left_dy = dy - grid.tile_height_d() / 2
        topleft_vx, topleft_vy = self.cs.convert_d_to_v((top_left_dx, top_left_dy))
        transform = QTransform()
        if grid.rotation != 0:
            transform.translate(origin_vx, origin_vy)
            transform.rotate(grid.rotation)
            transform.translate(
                -grid.tile_width_d() / 2 * self.cs.vp_scale,
                -grid.tile_height_d() / 2 * self.cs.vp_scale)
        else:
            transform.translate(topleft_vx, topleft_vy)
        return transform

    def _vp_visible_grid_indices(self):
        if self.vp_current_grid == -2:
            return []
        if self.vp_current_grid == -1:
            return list(reversed(range(self.gm.number_grids)))
        if 0 <= self.vp_current_grid < self.gm.number_grids:
            return [self.vp_current_grid]
        return []

    def _vp_point_segment_distance_sq(self, point, seg_start, seg_end):
        point_x, point_y = point
        start_x, start_y = seg_start
        end_x, end_y = seg_end
        seg_dx = end_x - start_x
        seg_dy = end_y - start_y
        if abs(seg_dx) < 1e-9 and abs(seg_dy) < 1e-9:
            return (point_x - start_x) ** 2 + (point_y - start_y) ** 2
        projection = (
            ((point_x - start_x) * seg_dx + (point_y - start_y) * seg_dy)
            / (seg_dx ** 2 + seg_dy ** 2))
        projection = np.clip(projection, 0.0, 1.0)
        nearest_x = start_x + projection * seg_dx
        nearest_y = start_y + projection * seg_dy
        return (point_x - nearest_x) ** 2 + (point_y - nearest_y) ** 2

    def _vp_point_near_polygon_edge(self, point, polygon_points, tolerance=6.0):
        if len(polygon_points) < 2:
            return False
        tolerance_sq = tolerance ** 2
        for index in range(len(polygon_points)):
            seg_start = polygon_points[index]
            seg_end = polygon_points[(index + 1) % len(polygon_points)]
            if (self._vp_point_segment_distance_sq(
                    point, seg_start, seg_end) <= tolerance_sq):
                return True
        return False

    def _vp_polygon_handle_positions_v(self, grid_index):
        grid = self.gm[grid_index]
        if not grid.has_polygon_roi():
            return []
        if grid.roi_shape_type in polygon_roi.PREDEFINED_SHAPE_TYPES:
            width, height = grid.sw_sh
            local_points = [
                [0.0, 0.0],
                [width, 0.0],
                [width, height],
                [0.0, height],
            ]
        else:
            local_points = grid.roi_local_points_d()
        return self._vp_polygon_points_v(grid_index, local_points)

    def _vp_polygon_handle_hit_test(self, px, py):
        for grid_index in self._vp_visible_grid_indices():
            grid = self.gm[grid_index]
            if not grid.has_polygon_roi():
                continue
            handle_positions = self._vp_polygon_handle_positions_v(grid_index)
            if grid_index == self.selected_grid:
                hit_radius_sq = 20 ** 2
            else:
                hit_radius_sq = 12 ** 2
            for index, point in enumerate(handle_positions):
                if ((point[0] - px) ** 2 + (point[1] - py) ** 2) <= hit_radius_sq:
                    if grid.roi_shape_type in polygon_roi.PREDEFINED_SHAPE_TYPES:
                        return (grid_index, 'resize', index)
                    return (grid_index, 'vertex', index)
        return None

    def _vp_require_explicit_large_deferred_polygon_selection(self, grid_index):
        grid = self.gm[grid_index]
        if not grid.is_deferred_polygon_roi():
            return False
        guardrail = self.gm.polygon_guardrail_state(grid.roi_estimated_tile_count)
        return guardrail['warn']

    def _vp_polygon_body_hit_test(self, px, py,
                                  allow_large_deferred_interior=True):
        point = (px, py)
        for grid_index in self._vp_visible_grid_indices():
            grid = self.gm[grid_index]
            if not grid.has_polygon_roi():
                continue
            polygon_points = self._vp_polygon_points_v(grid_index)
            if len(polygon_points) < 3:
                continue
            if self._vp_point_near_polygon_edge(point, polygon_points):
                return grid_index
            if polygon_roi.point_in_polygon(point, polygon_points):
                if (allow_large_deferred_interior
                        or not self._vp_require_explicit_large_deferred_polygon_selection(
                            grid_index)):
                    return grid_index
        return None

    def _vp_begin_polygon_handle_drag(self, drag_kind, handle_index):
        if self.selected_grid is None:
            return
        grid = self.gm[self.selected_grid]
        if drag_kind == 'resize':
            width, height = grid.sw_sh
            anchor_points = [
                [width, height],
                [0.0, height],
                [0.0, 0.0],
                [width, 0.0],
            ]
            self.vp_polygon_handle_drag = {
                'grid_index': self.selected_grid,
                'handle_index': handle_index,
                'anchor_local': anchor_points[handle_index],
            }
        elif drag_kind == 'vertex':
            self.vp_polygon_vertex_drag = {
                'grid_index': self.selected_grid,
                'vertex_index': handle_index,
            }

    def _vp_update_polygon_resize(self, px, py):
        drag_state = self.vp_polygon_handle_drag
        if drag_state is None:
            return
        grid_index = drag_state['grid_index']
        grid = self.gm[grid_index]
        mouse_local = self._vp_mouse_to_grid_local_d(px, py, grid_index)
        anchor_x, anchor_y = drag_state['anchor_local']
        left = min(mouse_local[0], anchor_x)
        right = max(mouse_local[0], anchor_x)
        top = min(mouse_local[1], anchor_y)
        bottom = max(mouse_local[1], anchor_y)
        width = max(1.0, right - left)
        height = max(1.0, bottom - top)
        top_left_dx_dy = self._vp_grid_local_to_global_d(grid_index, [left, top])
        grid.sw_sh = [width, height]
        if grid.is_deferred_polygon_roi():
            self.gm.update_deferred_polygon_grid(
                grid_index, top_left_dx_dy=top_left_dx_dy)
        else:
            self.gm.refresh_polygon_grid(grid_index, top_left_dx_dy=top_left_dx_dy)
        self.vp_draw()

    def _vp_update_polygon_vertex(self, px, py):
        drag_state = self.vp_polygon_vertex_drag
        if drag_state is None:
            return
        grid_index = drag_state['grid_index']
        grid = self.gm[grid_index]
        local_points = grid.roi_local_points_d()
        if not local_points:
            return
        local_points[drag_state['vertex_index']] = (
            self._vp_mouse_to_grid_local_d(px, py, grid_index))
        points_norm, bounds = polygon_roi.normalize_points(local_points)
        top_left_dx_dy = self._vp_grid_local_to_global_d(
            grid_index,
            [bounds[0], bounds[1]])
        grid.set_polygon_roi(
            grid.roi_shape_type,
            points_norm,
            grid.roi_shape_name)
        grid.sw_sh = [max(1.0, bounds[2]), max(1.0, bounds[3])]
        if grid.is_deferred_polygon_roi():
            self.gm.update_deferred_polygon_grid(
                grid_index, top_left_dx_dy=top_left_dx_dy)
        else:
            self.gm.refresh_polygon_grid(grid_index, top_left_dx_dy=top_left_dx_dy)
        self.vp_draw()

    def _vp_copy_selected_grid(self):
        if self.selected_grid is None:
            return
        grid = self.gm[self.selected_grid]
        self.vp_polygon_clipboard = {
            'has_polygon_roi': grid.has_polygon_roi(),
            'roi_shape_type': grid.roi_shape_type,
            'roi_shape_name': grid.roi_shape_name,
            'roi_points_norm': json.loads(json.dumps(grid.roi_points_norm)),
            'roi_materialized': grid.roi_materialized,
            'roi_estimated_rows': grid.roi_estimated_rows,
            'roi_estimated_cols': grid.roi_estimated_cols,
            'roi_estimated_tile_count': grid.roi_estimated_tile_count,
            'sw_sh': [float(grid.sw_sh[0]), float(grid.sw_sh[1])],
            'active': grid.active,
            'size': [int(grid.size[0]), int(grid.size[1])],
            'active_tiles': list(grid.active_tiles),
            'frame_size': list(grid.frame_size),
            'frame_size_selector': grid.frame_size_selector,
            'overlap': grid.overlap,
            'pixel_size': grid.pixel_size,
            'dwell_time': grid.dwell_time,
            'dwell_time_selector': grid.dwell_time_selector,
            'bit_depth_selector': grid.bit_depth_selector,
            'rotation': grid.rotation,
            'row_shift': grid.row_shift,
            'acq_interval': grid.acq_interval,
            'acq_interval_offset': grid.acq_interval_offset,
            'wd_stig_xy': list(grid.wd_stig_xy),
            'use_wd_gradient': grid.use_wd_gradient,
            'wd_gradient_ref_tiles': list(grid.wd_gradient_ref_tiles),
            'wd_gradient_params': list(grid.wd_gradient_params),
        }

    def _vp_copy_selected_polygon(self):
        self._vp_copy_selected_grid()

    def _vp_paste_grid_at(self, centre_dx_dy):
        if self.vp_polygon_clipboard is None:
            return
        clip = self.vp_polygon_clipboard
        pasted_size = [1, 1] if clip['has_polygon_roi'] else clip['size']
        new_grid = self.gm.add_new_grid(
            origin_sx_sy=self.cs.convert_d_to_s((centre_dx_dy[0], centre_dx_dy[1])),
            sw_sh=clip['sw_sh'],
            active=clip['active'],
            frame_size=clip['frame_size'],
            frame_size_selector=clip['frame_size_selector'],
            overlap=clip['overlap'],
            pixel_size=clip['pixel_size'],
            dwell_time=clip['dwell_time'],
            dwell_time_selector=clip['dwell_time_selector'],
            bit_depth_selector=clip['bit_depth_selector'],
            rotation=clip['rotation'],
            row_shift=clip['row_shift'],
            acq_interval=clip['acq_interval'],
            acq_interval_offset=clip['acq_interval_offset'],
            wd_stig_xy=clip['wd_stig_xy'],
            use_wd_gradient=clip['use_wd_gradient'],
            wd_gradient_ref_tiles=clip['wd_gradient_ref_tiles'],
            wd_gradient_params=clip['wd_gradient_params'],
            size=pasted_size)
        new_index = self.gm.number_grids - 1
        if clip['has_polygon_roi']:
            new_grid.set_polygon_roi(
                clip['roi_shape_type'],
                clip['roi_points_norm'],
                clip['roi_shape_name'])
            new_grid.sw_sh = [float(clip['sw_sh'][0]), float(clip['sw_sh'][1])]
            if clip['roi_materialized']:
                self.gm.refresh_polygon_grid(new_index, centre_dx_dy=centre_dx_dy)
            else:
                self.gm.update_deferred_polygon_grid(
                    new_index, centre_dx_dy=centre_dx_dy)
        else:
            new_grid.centre_sx_sy = self.cs.convert_d_to_s(centre_dx_dy)
            new_grid.sw_sh = [float(clip['sw_sh'][0]), float(clip['sw_sh'][1])]

        new_grid.active_tiles = [
            tile_index for tile_index in clip['active_tiles']
            if tile_index < new_grid.number_tiles]
        self.selected_grid = new_index
        self.selected_tile = None
        self.vp_current_grid = new_index
        self.vp_update_grid_selector()
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')
        self.vp_draw()

    def _vp_paste_polygon_at(self, centre_dx_dy):
        self._vp_paste_grid_at(centre_dx_dy)

    def _vp_duplicate_selected_grid(self):
        if self.selected_grid is None:
            return
        self._vp_copy_selected_grid()
        grid = self.gm[self.selected_grid]
        offset_dx_dy = [
            grid.centre_dx_dy[0] + max(5.0, grid.sw_sh[0] * 0.15),
            grid.centre_dx_dy[1] + max(5.0, grid.sw_sh[1] * 0.15),
        ]
        self._vp_paste_grid_at(offset_dx_dy)

    def _vp_duplicate_selected_polygon(self):
        self._vp_duplicate_selected_grid()

    def _vp_delete_selected_grid(self):
        self.vp_delete_grid(self.selected_grid)

    def _vp_delete_selected_polygon(self):
        self._vp_delete_selected_grid()

    # ====================== Below: Viewport (vp) methods ==========================

    def _vp_initialize(self):
        # self.vp_current_grid and self.vp_current_ov store the grid(s) and
        # OV(s) currently selected in the viewport's drop-down lists in the
        # bottom left. The selection -1 corresponds to 'show all' and
        # -2 corresponds to 'hide all'. Numbers >=0 correspond to grid and
        # overview indices.
        self.vp_current_grid = int(self.cfg['viewport']['vp_current_grid'])
        self.vp_current_ov = int(self.cfg['viewport']['vp_current_ov'])
        self.vp_tile_preview_mode = self._normalize_tile_preview_mode(
            int(self.cfg['viewport']['vp_tile_preview_mode']))
        # display options
        self.show_stub_ov = (
            self.cfg['viewport']['show_stub_ov'].lower() == 'true')
        self.show_imported = (
            self.cfg['viewport']['show_imported'].lower() == 'true')
        self.show_grid_lines = utils.str_to_bool(
            self.cfg['viewport'].get('show_grid_lines', 'True'))
        self.show_labels = (
            self.cfg['viewport']['show_labels'].lower() == 'true')
        self.show_axes = (
            self.cfg['viewport']['show_axes'].lower() == 'true')
        # By default, stage position indicator is not visible. Can be activated
        # by user in GUI
        self.show_stage_pos = False

        # Active user flag (highlighted text in the upper left corner of the
        # Viewport to show that a user is actively using the program.)
        self.active_user_flag_enabled = False
        self.active_user_flag_text = ''

        # The following variables store the tile or OV that is being acquired.
        self.tile_acq_indicator = [None, None]
        self.ov_acq_indicator = None

        # self.selected_grid, self.selected_tile etc. store the elements
        # most recenlty selected with a mouse click.
        self.selected_grid = None
        self.selected_tile = None
        self.selected_ov = None
        self.selected_imported = None
        self._load_polygon_shape_library()
        self._rebuild_polygon_toolbar()
        # The following booleans are set to True when the corresponding
        # user actions are active.
        self.grid_draw_active = False
        self.ov_draw_active = False
        self.template_draw_active = False
        self.grid_drag_active = False
        self.ov_drag_active = False
        self.template_drag_active = False
        self.imported_img_drag_active = False
        self.vp_measure_active = False
        self.vp_polygon_handle_drag = None
        self.vp_polygon_vertex_drag = None
        #---magc---
        self.grid_selection_or_draw_selection_box_active = False
        #----------

        # Canvas
        self.vp_canvas = QPixmap(self.cs.vp_width, self.cs.vp_height)
        # Help panel
        self.vp_help_panel_img = QPixmap(
            os.path.join('..', 'img', 'help-viewport.png'))
        # QPainter object that is used throughout this modult to write to the
        # Viewport canvas
        self.vp_qp = QPainter()

        # Buttons
        if hasattr(self, 'pushButton_acquisitionManager'):
            self.pushButton_acquisitionManager.clicked.connect(
                self.vp_open_acquisition_manager)
        self.pushButton_refreshOVs.clicked.connect(self.vp_acquire_overview)
        self.pushButton_acquireStubOV.clicked.connect(
            self._vp_open_stub_overview_dlg)
        self.pushButton_measureViewport.clicked.connect(self._vp_toggle_measure)
        self.pushButton_measureViewport.setIcon(
            QIcon(os.path.join('..', 'img', 'measure.png')))
        self.pushButton_measureViewport.setIconSize(QSize(16, 16))
        self.pushButton_measureViewport.setToolTip(
            'Measure with right mouse clicks')
        self.pushButton_updateStagePos.setIcon(
            QIcon('img/stage_pos.png'))
        self.pushButton_updateStagePos.setIconSize(QSize(16, 16))
        self.pushButton_measureViewport.setToolTip(
            'Update stage position')
        self.pushButton_updateStagePos.clicked.connect(
            self._vp_update_stage_position)
        self.pushButton_helpViewport.clicked.connect(self.vp_toggle_help_panel)
        self.pushButton_helpSliceViewer.clicked.connect(self.vp_toggle_help_panel)
        # Slider for zoom
        self.horizontalSlider_VP.valueChanged.connect(
            self._vp_adjust_scale_from_slider)
        self.vp_adjust_zoom_slider()
        # Tile Preview selector:
        self.comboBox_tilePreviewSelectorVP.addItems(
            ['Hide tile previews',
             'Show tile previews'])
        self.comboBox_tilePreviewSelectorVP.setCurrentIndex(
            self.vp_tile_preview_mode)
        self.comboBox_tilePreviewSelectorVP.currentIndexChanged.connect(
            self.vp_change_tile_preview_mode)

        # Connect and populate grid/tile/OV comboboxes:
        self.comboBox_gridSelectorVP.currentIndexChanged.connect(
            self.vp_change_grid_selection)
        self.vp_update_grid_selector()
        self.comboBox_OVSelectorVP.currentIndexChanged.connect(
            self.vp_change_ov_selection)
        self.vp_update_ov_selector()

        # Update all checkboxes with current settings
        self.checkBox_showLabels.setChecked(self.show_labels)
        self.checkBox_showLabels.stateChanged.connect(
            self.vp_toggle_show_labels)
        self.checkBox_showAxes.setChecked(self.show_axes)
        self.checkBox_showAxes.stateChanged.connect(self.vp_toggle_show_axes)
        self.checkBox_showImported.setChecked(self.show_imported)
        self.checkBox_showImported.stateChanged.connect(
            self.vp_toggle_show_imported)
        self.checkBox_showGridLines.setChecked(self.show_grid_lines)
        self.checkBox_showGridLines.stateChanged.connect(
            self.vp_toggle_show_grid_lines)
        self.checkBox_showStubOV.setChecked(self.show_stub_ov)
        self.checkBox_showStubOV.stateChanged.connect(
            self.vp_toggle_show_stub_ov)
        self.checkBox_showStagePos.setChecked(self.show_stage_pos)
        self.checkBox_showStagePos.stateChanged.connect(
            self.vp_toggle_show_stage_pos)

    def vp_update_grid_selector(self):
        if self.vp_current_grid >= self.gm.number_grids:
            self.vp_current_grid = -1  # show all
        self.comboBox_gridSelectorVP.blockSignals(True)
        self.comboBox_gridSelectorVP.clear()
        self.comboBox_gridSelectorVP.addItems(
            ['Hide grids', 'All grids'] + self.gm.grid_selector_list())
        self.comboBox_gridSelectorVP.setCurrentIndex(
            self.vp_current_grid + 2)
        self.comboBox_gridSelectorVP.blockSignals(False)

    def vp_update_ov_selector(self):
        if self.vp_current_ov >= self.ovm.number_ov:
            self.vp_current_ov = -1  # show all
        self.comboBox_OVSelectorVP.blockSignals(True)
        self.comboBox_OVSelectorVP.clear()
        self.comboBox_OVSelectorVP.addItems(
            ['Hide OVs', 'All OVs'] + self.ovm.ov_selector_list())
        self.comboBox_OVSelectorVP.setCurrentIndex(
            self.vp_current_ov + 2)
        self.comboBox_OVSelectorVP.blockSignals(False)

    def vp_change_tile_preview_mode(self):
        self.vp_tile_preview_mode = self._normalize_tile_preview_mode(
            self.comboBox_tilePreviewSelectorVP.currentIndex())
        self.vp_draw()

    @staticmethod
    def _normalize_tile_preview_mode(mode):
        return 1 if int(mode) > 0 else 0

    def vp_change_grid_selection(self):
        self.vp_current_grid = self.comboBox_gridSelectorVP.currentIndex() - 2
        self.vp_draw()

    def vp_change_ov_selection(self):
        self.vp_current_ov = self.comboBox_OVSelectorVP.currentIndex() - 2
        self.vp_draw()

    def vp_toggle_show_labels(self):
        self.show_labels = self.checkBox_showLabels.isChecked()
        self.vp_draw()

    def vp_toggle_show_axes(self):
        self.show_axes = self.checkBox_showAxes.isChecked()
        self.vp_draw()

    def vp_toggle_show_grid_lines(self):
        self.show_grid_lines = self.checkBox_showGridLines.isChecked()
        self.vp_draw()

    def vp_toggle_show_grid_lines_shortcut(self):
        if self.tabWidget.currentIndex() != 0:
            return
        new_state = not (self.show_grid_lines or self.show_labels)
        self.show_grid_lines = new_state
        self.show_labels = new_state
        self.checkBox_showGridLines.blockSignals(True)
        self.checkBox_showGridLines.setChecked(self.show_grid_lines)
        self.checkBox_showGridLines.blockSignals(False)
        self.checkBox_showLabels.blockSignals(True)
        self.checkBox_showLabels.setChecked(self.show_labels)
        self.checkBox_showLabels.blockSignals(False)
        self.vp_draw()

    def vp_toggle_tile_previews_shortcut(self):
        if self.tabWidget.currentIndex() != 0:
            return
        self.vp_tile_preview_mode = 1 - self._normalize_tile_preview_mode(
            self.vp_tile_preview_mode)
        self.comboBox_tilePreviewSelectorVP.blockSignals(True)
        self.comboBox_tilePreviewSelectorVP.setCurrentIndex(
            self.vp_tile_preview_mode)
        self.comboBox_tilePreviewSelectorVP.blockSignals(False)
        self.vp_draw()

    def vp_toggle_show_stub_ov(self):
        self.show_stub_ov = self.checkBox_showStubOV.isChecked()
        self.vp_draw()

    def vp_toggle_show_imported(self):
        self.show_imported = self.checkBox_showImported.isChecked()
        self.vp_draw()

    def vp_toggle_tile_acq_indicator(self, grid_index, tile_index):
        if self.tile_acq_indicator[0] is None:
            self.tile_acq_indicator = [grid_index, tile_index]
        else:
            self.tile_acq_indicator = [None, None]
        self.vp_draw()

    def vp_toggle_ov_acq_indicator(self, ov_index):
        if self.ov_acq_indicator is None:
            self.ov_acq_indicator = ov_index
        else:
            self.ov_acq_indicator = None
        self.vp_draw()

    def vp_toggle_show_stage_pos(self):
        self.show_stage_pos ^= True
        self.vp_draw()

    def vp_activate_checkbox_show_stage_pos(self):
        self.show_stage_pos = True
        self.checkBox_showStagePos.blockSignals(True)
        self.checkBox_showStagePos.setChecked(True)
        self.checkBox_showStagePos.blockSignals(False)

    def vp_update_after_active_tile_selection(self):
        """Update debris detection areas, show updated settings and redraw
        Viewport after active tile selection has been changed by user."""
        self.ovm.update_all_debris_detections_areas(self.gm)
        self.main_controls_trigger.transmit('SHOW CURRENT SETTINGS')
        self.vp_draw()
        self._refresh_acquisition_manager()

    def _refresh_ov_queue(self):
        if self.ov_queue_dlg is not None and self.ov_queue_dlg.isVisible():
            self.ov_queue_dlg.refresh_table()

    def _refresh_acquisition_manager(self):
        if (self.acquisition_manager_dlg is None
                or not self.acquisition_manager_dlg.isVisible()
                or self._acquisition_manager_refresh_pending):
            return
        self._acquisition_manager_refresh_pending = True
        QTimer.singleShot(0, self._perform_acquisition_manager_refresh)

    def _perform_acquisition_manager_refresh(self):
        self._acquisition_manager_refresh_pending = False
        if (self.acquisition_manager_dlg is not None
                and self.acquisition_manager_dlg.isVisible()):
            self.acquisition_manager_dlg.refresh_view()

    def vp_open_acquisition_manager(self):
        self.acq_groups.sync_inventory()
        if self.acquisition_manager_dlg is None:
            self.acquisition_manager_dlg = AcquisitionManagerDlg(
                self.acq_groups, self)
            self.acquisition_manager_dlg.destroyed.connect(
                lambda *_: setattr(self, 'acquisition_manager_dlg', None))
        self.acquisition_manager_dlg.show()
        self.acquisition_manager_dlg.raise_()
        self.acquisition_manager_dlg.activateWindow()
        self.acquisition_manager_dlg.refresh_view()

    def vp_open_ov_queue_panel(self):
        if self.ov_queue_dlg is None:
            self.ov_queue_dlg = OVQueueDlg(self.ovm, self)
        self.ov_queue_dlg.show()
        self.ov_queue_dlg.raise_()
        self.ov_queue_dlg.activateWindow()
        self.ov_queue_dlg.refresh_table()

    def _vp_open_ov_settings(self):
        ov_index = self.selected_ov if self.selected_ov is not None else 0
        self.main_controls_trigger.transmit('OPEN OV SETTINGS', ov_index)

    def _vp_toggle_grid_lock(self, grid_index):
        grid = self.gm[grid_index]
        if grid.locked:
            user_reply = QMessageBox.question(
                self, 'Unlock acquired grid',
                f'{grid.get_label(grid_index)} is locked because it was acquired.\n\n'
                'Unlocking allows moving it, which may break spatial provenance.\n'
                'Proceed with unlock?',
                QMessageBox.Ok | QMessageBox.Cancel)
            if user_reply != QMessageBox.Ok:
                return
            grid.locked = False
            self._add_to_main_log(
                f'CTRL: {grid.get_label(grid_index)} unlocked by operator.')
        else:
            grid.locked = True
            self._add_to_main_log(
                f'CTRL: {grid.get_label(grid_index)} locked.')
        self.vp_draw()
        self._refresh_acquisition_manager()

    def _vp_toggle_ov_lock(self, ov_index):
        ov = self.ovm[ov_index]
        if ov.locked:
            user_reply = QMessageBox.question(
                self, 'Unlock acquired overview',
                f'OV {ov_index} is locked because it was acquired.\n\n'
                'Unlocking allows moving it, which may break spatial provenance.\n'
                'Proceed with unlock?',
                QMessageBox.Ok | QMessageBox.Cancel)
            if user_reply != QMessageBox.Ok:
                return
            ov.locked = False
            self._add_to_main_log(f'CTRL: OV {ov_index} unlocked by operator.')
        else:
            ov.locked = True
            self._add_to_main_log(f'CTRL: OV {ov_index} locked.')
        self.vp_draw()
        self._refresh_ov_queue()
        self._refresh_acquisition_manager()

    def _notify_acquisition_manager_state_change(self, update_debris=False):
        self.acq_groups.sync_inventory()
        if update_debris and self.ovm.use_auto_debris_area:
            self.ovm.update_all_debris_detections_areas(self.gm)
        self.main_controls_trigger.transmit('ACQ GROUPS CHANGED')
        self._refresh_ov_queue()
        self._refresh_acquisition_manager()
        self.vp_draw()

    def vp_clear_overview_image(self, ov_index):
        if ov_index is None or not (0 <= ov_index < self.ovm.number_ov):
            return
        self.ovm[ov_index].vp_file_path = ''
        self.ovm[ov_index].mark_not_acquired(result='cleared')
        self._notify_acquisition_manager_state_change()

    def _vp_clear_selected_ov_image(self):
        self.vp_clear_overview_image(self.selected_ov)

    def vp_clear_grid_previews(self, grid_index):
        if grid_index is None or not (0 <= grid_index < self.gm.number_grids):
            return
        user_reply = QMessageBox.question(
            self, 'Reset tile previews',
            f'This will clear all tile preview images in the Viewport for '
            f'{self.gm.get_grid_label(grid_index)}',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply != QMessageBox.Ok:
            return
        self.gm[grid_index].clear_all_tile_previews()
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def vp_delete_overview(self, ov_index):
        if ov_index is None or not (0 <= ov_index < self.ovm.number_ov):
            return
        if ov_index == 0:
            QMessageBox.information(
                self,
                'OV 0 protected',
                'OV 0 is a persistent anchor and cannot be deleted.',
                QMessageBox.Ok)
            return
        if ov_index != self.ovm.number_ov - 1:
            QMessageBox.information(
                self,
                'Delete order',
                'For consistency, only the highest OV index can be deleted.',
                QMessageBox.Ok)
            return
        user_reply = QMessageBox.question(
            self,
            'Delete overview',
            f'Delete OV {ov_index}?',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply != QMessageBox.Ok:
            return
        self.ovm.delete_overview()
        if self.selected_ov == ov_index:
            self.selected_ov = None
        self.main_controls_trigger.transmit('OV SETTINGS CHANGED')

    def vp_delete_grid(self, grid_index):
        if grid_index is None or not (0 <= grid_index < self.gm.number_grids):
            return
        if grid_index != self.gm.number_grids - 1:
            QMessageBox.information(
                self,
                'Delete grid',
                'Only the most recently created grid can be deleted safely.\n'
                'Delete or move later grids first.',
                QMessageBox.Ok)
            return
        grid_label = self.gm.get_grid_label(grid_index)
        user_reply = QMessageBox.question(
            self,
            'Delete grid',
            f'This will delete {grid_label}.\n'
            'Proceed?',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply != QMessageBox.Ok:
            return
        self.gm.delete_grid()
        if self.selected_grid == grid_index:
            self.selected_grid = None
            self.selected_tile = None
        self.vp_current_grid = -1
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def vp_registration_check(self):
        """Quick geometry check between selected tile and selected/containing OV."""
        if self.selected_grid is None or self.selected_tile is None:
            QMessageBox.information(
                self, 'Registration check',
                'Select a tile first (right-click on a tile).',
                QMessageBox.Ok)
            return
        grid = self.gm[self.selected_grid]
        min_dx, max_dx, min_dy, max_dy = grid.tile_bounding_box(self.selected_tile)
        tile_w = max_dx - min_dx
        tile_h = max_dy - min_dy
        candidate_ov = self.selected_ov
        if candidate_ov is None:
            for ov_index in range(self.ovm.number_ov):
                ov_min_dx, ov_min_dy, ov_max_dx, ov_max_dy = self.ovm[ov_index].bounding_box()
                if (min_dx >= ov_min_dx and max_dx <= ov_max_dx
                        and min_dy >= ov_min_dy and max_dy <= ov_max_dy):
                    candidate_ov = ov_index
                    break
        if candidate_ov is None:
            QMessageBox.warning(
                self, 'Registration check',
                'Selected tile is outside all current OV footprints.',
                QMessageBox.Ok)
            return
        ov = self.ovm[candidate_ov]
        ov_min_dx, ov_min_dy, _, _ = ov.bounding_box()
        px_left = int((min_dx - ov_min_dx) * 1000 / ov.pixel_size)
        px_top = int((min_dy - ov_min_dy) * 1000 / ov.pixel_size)
        px_w = int(tile_w * 1000 / ov.pixel_size)
        px_h = int(tile_h * 1000 / ov.pixel_size)
        calibration_note = ''
        if not getattr(self.cs, 'calibration_found', True):
            calibration_note = (
                '\n\nWarning: stage calibration is missing for current EHT, '
                'so OV/tile registration may be unreliable.')
        QMessageBox.information(
            self, 'OV/Grid registration check',
            f'Grid {self.selected_grid} tile {self.selected_tile} expected footprint in '
            f'OV {candidate_ov}:\n'
            f'- top-left: ({px_left}, {px_top}) px\n'
            f'- size: {px_w} x {px_h} px{calibration_note}',
            QMessageBox.Ok)

    def vp_toggle_render_debug(self):
        self.render_debug_enabled = not self.render_debug_enabled
        self.vp_draw()

    def vp_toggle_render_antialias(self):
        self.render_antialias = not self.render_antialias
        self.vp_draw()

    def vp_show_context_menu(self, p):
        """Show context menu after user has right-clicked at position p."""
        px, py = p.x() - constants.VP_MARGIN_X, p.y() - constants.VP_MARGIN_Y
        if px in range(self.cs.vp_width) and py in range(self.cs.vp_height):
            self.selected_grid, self.selected_tile = \
                self._vp_grid_tile_mouse_selection(px, py)
            if self.selected_grid is None:
                polygon_grid = self._vp_polygon_body_hit_test(px, py)
                if polygon_grid is not None:
                    self.selected_grid = polygon_grid
                    self.selected_tile = None
            grid_index, tile_index = self.selected_grid, self.selected_tile
            grid_label = self.gm.get_grid_label(grid_index)
            self.selected_ov = self._vp_ov_mouse_selection(px, py)
            self.selected_imported = (
                self._vp_imported_img_mouse_selection(px, py))
            # Disable self.selected_template for now (causing runtime warnings)
            # TODO (Benjamin / Philipp): look into this
            # self.selected_template = self._vp_template_mouse_selection(px, py)
            sx, sy = self.cs.convert_mouse_to_s((px, py))
            dx, dy = self.cs.convert_s_to_d((sx, sy))
            self.vp_polygon_context_dx_dy = (dx, dy)
            current_pos_str = ('Move stage to X: {0:.3f}, '.format(sx)
                               + 'Y: {0:.3f}'.format(sy))
            self.selected_stage_pos = (sx, sy)
            grid_str = ''
            if grid_index is not None:
                grid_str = f'in {grid_label}'
            selected_for_autofocus = 'Select/deselect as'
            selected_for_gradient = 'Select/deselect as'
            if (grid_index is not None
                and tile_index is not None):
                selected = f'tile {grid_label}.{tile_index}'
                if self.gm[grid_index][
                           tile_index].autofocus_active:
                    selected_for_autofocus = (
                        f'Deselect Tile {grid_label}.'
                        f'{tile_index} as')
                else:
                    selected_for_autofocus = (
                        f'Select Tile {grid_label}.'
                        f'{tile_index} as')
                if self.gm[grid_index][
                           tile_index].wd_grad_active:
                    selected_for_gradient = (
                        f'Deselect Tile {grid_label}.'
                        f'{tile_index} as')
                else:
                    selected_for_gradient = (
                        f'Select Tile {grid_label}.'
                        f'{tile_index} as')
            elif self.selected_ov is not None:
                selected = f'OV {self.selected_ov}'
            else:
                selected = 'Tile/OV'

            menu = QMenu()
            action_sliceViewer = menu.addAction(
                f'Load {selected} in Slice Viewer')
            action_sliceViewer.triggered.connect(self.sv_load_selected)
            action_focusTool = menu.addAction(f'Load {selected} in Focus Tool')
            action_focusTool.triggered.connect(self._vp_load_selected_in_ft)
            action_statistics = menu.addAction(f'Load {selected} statistics')
            action_statistics.triggered.connect(self.m_load_selected)

            menu.addSeparator()
            if grid_index is not None:
                action_openGridSettings = menu.addAction(
                    f'Open settings of {grid_label}'
                    ' | Shortcut &G')
            else:
                action_openGridSettings = menu.addAction(
                    'Open settings of selected grid')
            action_openGridSettings.triggered.connect(
                self._vp_open_grid_settings)
            if self.selected_ov is not None:
                action_openOVSettings = menu.addAction(
                    f'Open settings of OV {self.selected_ov}')
            else:
                action_openOVSettings = menu.addAction(
                    'Open settings of selected OV')
            action_openOVSettings.triggered.connect(self._vp_open_ov_settings)
            action_selectAll = menu.addAction('Select all tiles ' + grid_str)
            action_selectAll.triggered.connect(self.vp_activate_all_tiles)
            action_deselectAll = menu.addAction(
                'Deselect all tiles ' + grid_str)
            action_deselectAll.triggered.connect(self.vp_deactivate_all_tiles)
            if grid_index is not None:
                action_changeRotation = menu.addAction(
                    f'Change rotation of Tile {grid_label} | Shortcut &R')
                action_changeRotation.triggered.connect(
                    self._vp_open_change_grid_rotation_dlg)
            else:
                action_changeRotation = None

            if grid_index is not None:
                menu.addSeparator()
                action_copyGrid = menu.addAction(
                    f'Copy {grid_label}')
                action_copyGrid.triggered.connect(self._vp_copy_selected_grid)
                action_duplicateGrid = menu.addAction(
                    f'Duplicate {grid_label}')
                action_duplicateGrid.triggered.connect(
                    self._vp_duplicate_selected_grid)
                action_deleteGrid = menu.addAction(
                    f'Delete {grid_label}')
                action_deleteGrid.triggered.connect(
                    self._vp_delete_selected_grid)
                if self.selected_grid != self.gm.number_grids - 1:
                    action_deleteGrid.setEnabled(False)
            else:
                action_copyGrid = None
                action_duplicateGrid = None
                action_deleteGrid = None
            action_pasteGrid = menu.addAction('Paste copied grid here')
            action_pasteGrid.triggered.connect(
                lambda: self._vp_paste_grid_at(self.vp_polygon_context_dx_dy))
            action_pasteGrid.setEnabled(self.vp_polygon_clipboard is not None)

            if self.gm.array_mode:
                action_moveGridCurrentStage = menu.addAction(
                    f'Move {grid_label} to current stage position')
                action_moveGridCurrentStage.triggered.connect(
                    self._vp_manual_stage_move)
                if not ((grid_index is not None)
                    and self.gm.array_data.calibrated):
                    action_moveGridCurrentStage.setEnabled(False)

            menu.addSeparator()
            if self.autofocus.method == 2:
                action_selectAutofocus = menu.addAction(
                    selected_for_autofocus + ' focus tracking ref.')
            else:
                action_selectAutofocus = menu.addAction(
                    selected_for_autofocus + ' autofocus ref.')
            action_selectAutofocus.triggered.connect(
                self._vp_toggle_tile_autofocus)
            action_selectGradient = menu.addAction(
                selected_for_gradient + ' focus gradient ref.')
            action_selectGradient.triggered.connect(
                self._vp_toggle_wd_gradient_ref_tile)

            menu.addSeparator()
            action_acquireGrid = None
            action_acquireTile = None
            action_pauseAcq = None
            if grid_index is not None:
                action_acquireGrid = menu.addAction(f'Acquire Grid {grid_label}')
                action_acquireGrid.triggered.connect(self._vp_acquire_grid)
                action_pauseAcq = menu.addAction('Pause acquisition...')
                action_pauseAcq.triggered.connect(self._vp_pause_acquisition)
                if tile_index is not None:
                    action_acquireTile = menu.addAction(
                        f'Acquire Tile {grid_label}.{tile_index}')
                    action_acquireTile.triggered.connect(self._vp_acquire_tile)
                    action_registrationCheck = menu.addAction(
                        f'Registration check for {grid_label}.{tile_index}')
                    action_registrationCheck.triggered.connect(
                        self.vp_registration_check)
                else:
                    action_registrationCheck = None
            else:
                action_registrationCheck = None
            if self.selected_ov is not None:
                action_acquireOV = menu.addAction(
                    f'Acquire OV {self.selected_ov}')
                action_acquireOV.triggered.connect(
                    lambda _, ov_index=self.selected_ov:
                        self.vp_acquire_specific_overview(ov_index))
                action_clearOV = menu.addAction(
                    f'Clear OV {self.selected_ov} image')
                action_clearOV.triggered.connect(self._vp_clear_selected_ov_image)
            else:
                action_acquireOV = None
                action_clearOV = None
            action_move = menu.addAction(current_pos_str)
            action_move.triggered.connect(self._vp_manual_stage_move)
            action_stub = menu.addAction('Acquire stub OV at this position')
            action_stub.triggered.connect(self._vp_set_stub_ov_centre)

            # menu.addSeparator()
            # action_templateMatching = menu.addAction('Run Template Matching')
            # action_templateMatching.triggered.connect(self._vp_place_grids_template_matching)

            menu.addSeparator()
            action_import = menu.addAction('Import and place image')
            action_import.triggered.connect(self.vp_open_import_image_dlg)
            action_modifyImported = menu.addAction('Modify imported images')
            action_modifyImported.triggered.connect(
                self._vp_open_modify_images_dlg)
            action_ovQueue = menu.addAction('Open acquisition manager')
            action_ovQueue.triggered.connect(self.vp_open_acquisition_manager)

            menu.addSeparator()
            if grid_index is not None:
                grid_locked = self.gm[grid_index].locked
                action_gridLock = menu.addAction(
                    f'{"Unlock" if grid_locked else "Lock"} {grid_label}')
                action_gridLock.triggered.connect(
                    lambda _, index=grid_index: self._vp_toggle_grid_lock(index))
            else:
                action_gridLock = None
            if self.selected_ov is not None:
                ov_locked = self.ovm[self.selected_ov].locked
                action_ovLock = menu.addAction(
                    f'{"Unlock" if ov_locked else "Lock"} OV {self.selected_ov}')
                action_ovLock.triggered.connect(
                    lambda _, index=self.selected_ov: self._vp_toggle_ov_lock(index))
            else:
                action_ovLock = None
            action_toggleRenderDebug = menu.addAction(
                'Render diagnostics: '
                + ('on' if self.render_debug_enabled else 'off'))
            action_toggleRenderDebug.triggered.connect(self.vp_toggle_render_debug)
            action_toggleAntialias = menu.addAction(
                'Overlay anti-aliasing: '
                + ('on' if self.render_antialias else 'off'))
            action_toggleAntialias.triggered.connect(self.vp_toggle_render_antialias)

            # ----- Array items -----
            if self.gm.array_mode:
                menu.addSeparator()
                # get closest grid
                self._closest_grid_number = self._vp_get_closest_grid_id(
                    self.selected_stage_pos)
                if len(self.gm.array_data.selected_sections) > 0:
                    array_selected_section = self.gm.array_data.selected_sections[0]

            if (grid_index is not None
                and self.gm[grid_index].roi_index is not None):

                # propagate to all sections
                action_propagateToAll = menu.addAction(
                    f'Array | Propagate properties of {grid_label}'
                    ' to all sections | Shortcut &P')
                action_propagateToAll.triggered.connect(
                    self.array_vp_propagate_grid_to_all_sections)

                # propagate to selected sections
                action_propagateToSelected = menu.addAction(
                    f'Array | Propagate properties of {grid_label}'
                    ' to selected sections | Shortcut &O')
                action_propagateToSelected.triggered.connect(
                    self.array_vp_propagate_grid_to_selected_sections)

                # revert location to file-defined location
                action_revertLocation = menu.addAction(
                    f'Array | Revert location of {grid_label}'
                    ' to original file-defined location | Shortcut &Z')
                action_revertLocation.triggered.connect(
                    self.array_vp_revert_grid_to_file)

                # if self.gm.magc['path'] == '':
                if (self.gm.array_data is None
                        or self.gm.array_data.transform is None
                        or len(self.gm.array_data.transform) == 0):
                    action_propagateToAll.setEnabled(False)
                    action_propagateToSelected.setEnabled(False)
                    action_revertLocation.setEnabled(False)

            #---autofocus points---#
            if self.gm.array_mode and len(self.gm.array_data.selected_sections) == 1:
                array_index, roi_index = array_selected_section
                grid_selected_index = self.gm.find_grid_index(array_index, roi_index)
                if grid_selected_index is not None and self.gm.array_autofocus_points(grid_selected_index):

                    action_removeAutofocusPoint = menu.addAction(
                        'Array | Remove last autofocus point of '
                        f' {grid_label} | Shortcut &E')
                    action_removeAutofocusPoint.triggered.connect(
                        self.vp_remove_autofocus_point)

                    action_removeAllAutofocusPoint = menu.addAction(
                        'Array | Remove all autofocus points of '
                        f' {grid_label} | Shortcut &W')
                    action_removeAllAutofocusPoint.triggered.connect(
                        self.vp_remove_all_autofocus_point)

                action_addAutofocusPoint = menu.addAction(
                    'Array | Add autofocus point to '
                    f' {grid_label} | Shortcut &T')
                action_addAutofocusPoint.triggered.connect(
                    self.vp_add_autofocus_point)
            #----------------------#
            # ----- End of Array items -----

            if (tile_index is None) and (self.selected_ov is None):
                action_sliceViewer.setEnabled(False)
                action_focusTool.setEnabled(False)
                action_statistics.setEnabled(False)
            if grid_index is None:
                action_openGridSettings.setEnabled(False)
                action_selectAll.setEnabled(False)
                action_deselectAll.setEnabled(False)
            if self.selected_ov is None:
                action_openOVSettings.setEnabled(False)
                if action_acquireOV is not None:
                    action_acquireOV.setEnabled(False)
                if action_clearOV is not None:
                    action_clearOV.setEnabled(False)
            if (self.selected_template is None and grid_index is None
                    and action_changeRotation is not None):
                action_changeRotation.setEnabled(False)
            if tile_index is None:
                action_selectAutofocus.setEnabled(False)
                action_selectGradient.setEnabled(False)
            if self.autofocus.tracking_mode == 1:
                action_selectAutofocus.setEnabled(False)
            if self.imported.number_imported == 0:
                action_modifyImported.setEnabled(False)
            if self.busy:
                action_focusTool.setEnabled(False)
                action_openGridSettings.setEnabled(False)
                action_openOVSettings.setEnabled(False)
                if action_changeRotation is not None:
                    action_changeRotation.setEnabled(False)
                action_selectAll.setEnabled(False)
                action_deselectAll.setEnabled(False)
                action_selectGradient.setEnabled(False)
                action_move.setEnabled(False)
                action_stub.setEnabled(False)
                action_import.setEnabled(False)
                if action_acquireOV is not None:
                    action_acquireOV.setEnabled(False)
                if action_registrationCheck is not None:
                    action_registrationCheck.setEnabled(False)
                if action_gridLock is not None:
                    action_gridLock.setEnabled(False)
                if action_ovLock is not None:
                    action_ovLock.setEnabled(False)
            if action_acquireGrid is not None and self.busy:
                action_acquireGrid.setEnabled(False)
            if action_acquireTile is not None and self.busy:
                action_acquireTile.setEnabled(False)
            if action_pauseAcq is not None:
                pause_possible = (
                    self.acq.acq_in_progress
                    and self.acq.pause_state not in [1, 2]
                )
                action_pauseAcq.setEnabled(pause_possible)
            if self.sem.simulation_mode:
                action_move.setEnabled(False)
                action_stub.setEnabled(False)
                if action_acquireOV is not None:
                    action_acquireOV.setEnabled(False)
                if action_acquireGrid is not None:
                    action_acquireGrid.setEnabled(False)
                if action_acquireTile is not None:
                    action_acquireTile.setEnabled(False)
                if action_pauseAcq is not None:
                    action_pauseAcq.setEnabled(False)
            menu.exec_(self.mapToGlobal(p))

    def _vp_get_closest_grid_id(self, sx_sy):
        closest_id = (scipy.spatial.distance.cdist(
            [np.array(sx_sy)],
            [self.gm[id].centre_sx_sy for id in range(self.gm.number_grids)])
            .argmin())
        return closest_id

    def vp_add_autofocus_point(self):
        self.gm.array_add_autofocus_point(
            self.gm.array_data.selected_sections[0],
            self.selected_stage_pos)
        self.gm.array_write()
        self.vp_draw()

    def vp_remove_autofocus_point(self):
        self.gm.array_delete_last_autofocus_point(
            self.gm.array_data.selected_sections[0])
        self.gm.array_write()
        self.vp_draw()

    def vp_remove_all_autofocus_point(self):
        self.gm.array_delete_autofocus_points(
            self.gm.array_data.selected_sections[0])
        self.gm.array_write()
        self.vp_draw()

    def _vp_load_selected_in_ft(self):
        self.main_controls_trigger.transmit('LOAD IN FOCUS TOOL')

    def _vp_pause_acquisition(self):
        if not self.acq.acq_in_progress:
            QMessageBox.information(
                self, 'Pause acquisition',
                'No acquisition is currently in progress.',
                QMessageBox.Ok)
            return
        self.main_controls_trigger.transmit('PAUSE ACQ')

    def _vp_backup_acq_state(self):
        self._vp_acq_state_backup = {
            'pause_state': self.acq.pause_state,
            'acq_paused': self.acq.acq_paused,
            'acq_interrupted': self.acq.acq_interrupted,
            'acq_interrupted_at': list(self.acq.acq_interrupted_at),
            'tiles_acquired': list(self.acq.tiles_acquired),
            'grids_acquired': list(self.acq.grids_acquired),
            'error_state': self.acq.error_state,
            'error_info': self.acq.error_info,
            'acq_in_progress': self.acq.acq_in_progress,
            'acq_run_mode': self.acq.acq_run_mode,
        }

    def _vp_restore_acq_state(self):
        if self._vp_acq_state_backup is None:
            return
        backup = self._vp_acq_state_backup
        self.acq.pause_state = backup['pause_state']
        self.acq.acq_paused = backup['acq_paused']
        self.acq.acq_interrupted = backup['acq_interrupted']
        self.acq.acq_interrupted_at = list(backup['acq_interrupted_at'])
        self.acq.tiles_acquired = list(backup['tiles_acquired'])
        self.acq.grids_acquired = list(backup['grids_acquired'])
        self.acq.error_state = backup['error_state']
        self.acq.error_info = backup['error_info']
        self.acq.acq_in_progress = backup['acq_in_progress']
        self.acq.acq_run_mode = backup['acq_run_mode']
        self._vp_acq_state_backup = None

    def _vp_close_manual_acq_logs(self):
        file_handles = [
            'main_log_file',
            'imagelist_file',
            'imagelist_ov_file',
            'mirror_imagelist_file',
            'mirror_imagelist_ov_file',
            'incident_log_file',
            'metadata_file',
        ]
        for attr in file_handles:
            handle = getattr(self.acq, attr, None)
            if handle is not None and not handle.closed:
                handle.close()

    def _vp_acquire_grid_thread(self, grid_index):
        outcome = 'error'
        self.acq.acq_in_progress = True
        self.acq.acq_run_mode = 'viewport_grid'
        try:
            self.acq.reset_error_state()
            self.acq.pause_state = None
            self.acq.acq_paused = False
            self.acq.init_acquisition()
            self.acq.set_up_acq_subdirectories()
            self.acq.set_up_acq_logs()
            self.acq.set_up_afss_masks()
            if self.acq.error_state == constants.Error.none:
                self.acq.acquire_grid(grid_index, overwrite=True)

            if self.acq.error_state != constants.Error.none:
                outcome = 'error'
            elif self.acq.pause_state in [1, 2]:
                outcome = 'paused'
            else:
                outcome = 'success'
        except Exception:
            utils.log_exception('Viewport grid acquisition exception')
            outcome = 'error'
        finally:
            self.acq.acq_in_progress = False
            self.acq.acq_run_mode = None
            self.viewport_trigger.transmit('VP GRID ACQ FINISHED', outcome, grid_index)

    def _vp_grid_acq_finished(self, outcome, grid_index):
        grid_label = self.gm.get_grid_label(grid_index)
        if outcome == 'success':
            self._add_to_main_log(
                f'CTRL: User-requested acquisition of {grid_label} completed.')
        elif outcome == 'paused':
            self._add_to_main_log(
                f'CTRL: User-requested acquisition of {grid_label} paused.')
        else:
            self._add_to_main_log(
                f'CTRL: ERROR occurred during acquisition of {grid_label}.')
            QMessageBox.warning(
                self, 'Error during grid acquisition',
                f'An error occurred while acquiring {grid_label}. '
                'Please check the log for details.',
                QMessageBox.Ok)

        self._vp_close_manual_acq_logs()
        self._vp_restore_acq_state()
        self._vp_grid_acq_in_progress = False
        self._vp_grid_acq_index = None
        self.main_controls_trigger.transmit('UNRESTRICT GUI')
        self.restrict_gui(False)
        self.main_controls_trigger.transmit('STATUS IDLE')
        self.vp_draw()
        self._refresh_acquisition_manager()

    def vp_acquire_specific_grid(self, grid_index):
        if grid_index is None or not (0 <= grid_index < self.gm.number_grids):
            return
        self.selected_grid = grid_index
        self.selected_tile = None
        if len(self.gm[grid_index].active_tiles) == 0:
            QMessageBox.warning(
                self, 'No active tiles',
                'The currently selected grid has no active tiles',
                QMessageBox.Ok)
            return
        if self.busy or self.acq.acq_in_progress:
            QMessageBox.information(
                self, 'Operation in progress',
                'Another operation is currently running. '
                'Use "Pause acquisition..." from the context menu to pause it first.',
                QMessageBox.Ok)
            return

        grid_label = self.gm.get_grid_label(grid_index)
        self._vp_backup_acq_state()
        self.acq.acq_in_progress = True
        self.acq.acq_run_mode = 'viewport_grid'
        self._vp_grid_acq_in_progress = True
        self._vp_grid_acq_index = grid_index
        self._add_to_main_log(
            f'CTRL: User-requested acquisition of {grid_label} started.')
        self.restrict_gui(True)
        self.main_controls_trigger.transmit('RESTRICT GUI')
        self.main_controls_trigger.transmit('STATUS BUSY GRID')
        utils.run_log_thread(self._vp_acquire_grid_thread, grid_index)

    def _vp_acquire_grid(self):
        self.vp_acquire_specific_grid(self.selected_grid)

    def _vp_acquire_tile(self):
        active_tiles = self.gm[self.selected_grid].active_tiles
        if self.selected_tile not in active_tiles:
            active_tiles.append(self.selected_tile)
        self.acq.init_acquisition()
        self.acq.set_up_acq_subdirectories()
        self.acq.set_scan_rotation(self.selected_grid)
        self.acq.acquire_tile(self.selected_grid, self.selected_tile,
                              adjust_acq_settings=True, overwrite=True)

    def _vp_set_stub_ov_centre(self):
        self.stub_ov_centre = self.selected_stage_pos
        self._vp_open_stub_overview_dlg()

    def vp_dx_dy_range(self):
        x_min, x_max, y_min, y_max = self.stage.limits
        dx, dy = [0, 0, 0, 0], [0, 0, 0, 0]
        dx[0], dy[0] = self.cs.convert_s_to_d((x_min, y_min))
        dx[1], dy[1] = self.cs.convert_s_to_d((x_max, y_min))
        dx[2], dy[2] = self.cs.convert_s_to_d((x_max, y_max))
        dx[3], dy[3] = self.cs.convert_s_to_d((x_min, y_max))
        return min(dx), max(dx), min(dy), max(dy)

    def vp_draw(self, suppress_labels=False, suppress_previews=False):
        """Draw all elements on Viewport canvas"""
        self._vp_normalize_selection_state()
        draw_started = time()
        show_debris_area = (self.ovm.detection_area_visible
                            and self.acq.use_debris_detection)
        if self.ov_drag_active or self.grid_drag_active or self.template_drag_active:
            show_debris_area = False
        # Start with empty black canvas
        self.vp_canvas.fill(Qt.black)
        # Begin painting on canvas
        painter_active = self.vp_qp.begin(self.vp_canvas)
        if not painter_active:
            return
        try:
            self.vp_qp.setRenderHint(QPainter.Antialiasing, self.render_antialias)
            # First, show imported images as the background layer.
            if self.show_imported:
                for imported_img_index in range(len(self.imported)):
                    if self._vp_imported_visible(imported_img_index):
                        self._vp_place_imported_img(imported_img_index)

            # Then, show stub OV if option selected and stub OV image exists:
            if self.show_stub_ov:
                for imported_img_index in range(len(self.imported)):
                    if self._vp_imported_visible(imported_img_index):
                        imported = self.imported[imported_img_index]
                        if imported.is_stub_archive:
                            self._vp_place_stub_archive(imported_img_index)
                self._vp_place_stub_overview(self.ovm['stub_lm'])
                self._vp_place_stub_overview(self.ovm['stub'])
                # self._place_template()
            # Place OV overviews over stub OV:
            if self.vp_current_ov == -1:  # show all
                for ov_index in range(self.ovm.number_ov):
                    self._vp_place_overview(ov_index,
                                            show_debris_area,
                                            suppress_labels)
            if self.vp_current_ov >= 0:  # show only the selected OV
                self._vp_place_overview(self.vp_current_ov,
                                        show_debris_area,
                                        suppress_labels)
            show_grid, show_previews, with_gaps = (
                self._vp_grid_render_flags(suppress_previews))

            if self.vp_current_grid == -2:
                grid_indices = []
            elif self.vp_current_grid >= 0:
                # show only the selected grid
                grid_indices = [self.vp_current_grid]
            else:
                # show all grids
                grid_indices = range(self.gm.number_grids)
            for grid_index in grid_indices:
                self._vp_place_grid(grid_index,
                                    show_grid,
                                    show_previews,
                                    with_gaps,
                                    suppress_labels)
            # Show stage boundaries (motor range limits)
            self._vp_draw_stage_boundaries()
            if self.show_axes:
                self._vp_draw_stage_axes()
            # Show interactive features
            if self.grid_draw_active:
                self._draw_rectangle(self.vp_qp, self.drag_origin, self.drag_current,
                                     constants.COLOUR_SELECTOR[0], line_style=Qt.DashLine)
                self._vp_draw_live_grid_layout()
            if self.ov_draw_active:
                self._draw_rectangle(self.vp_qp, self.drag_origin, self.drag_current,
                                     constants.COLOUR_SELECTOR[10], line_style=Qt.DashLine)
            if self.template_draw_active:
                self._draw_rectangle(self.vp_qp, self.drag_origin, self.drag_current,
                                     constants.COLOUR_SELECTOR[8], line_style=Qt.DashLine)
            self._vp_draw_pending_polygon()

            # --- array mode ---
            if self.grid_selection_or_draw_selection_box_active:
                self._draw_rectangle(self.vp_qp, self.drag_origin, self.drag_current,
                                     constants.COLOUR_SELECTOR[0], line_style=Qt.DashLine)
            self._place_landmarks()

            #-----------------------------------------#

            # ------
            if self.vp_measure_active:
                self._draw_measure_labels(self.vp_qp)
            # Show help panel
            if self.help_panel_visible:
                self.vp_qp.drawPixmap(QPointF(self.cs.vp_width - 200,
                                      self.cs.vp_height - 550),
                                      self.vp_help_panel_img)
            # Simulation mode indicator
            if self.sem.simulation_mode:
                self._show_simulation_mode_indicator()
            # Active user flag
            if self.active_user_flag_enabled:
                self._show_active_user_flag()
            # Show current stage position
            if self.show_stage_pos:
                self._show_stage_position_indicator()
            self._vp_draw_selection_overlay()
            if self.render_debug_enabled:
                self._vp_draw_render_diagnostics((time() - draw_started) * 1000)
        finally:
            if self.vp_qp.isActive():
                self.vp_qp.end()
        # All elements have been drawn on the canvas, now show them in the
        # Viewport window.
        self.QLabel_ViewportCanvas.setPixmap(self.vp_canvas)
        self._refresh_ov_queue()
        # Update text labels (bottom of the Viewport window)
        self.label_FOVSize.setText(
            '{0:.1f}'.format(self.cs.vp_width / self.cs.vp_scale)
            + ' µm × '
            + '{0:.1f}'.format(self.cs.vp_height / self.cs.vp_scale) + ' µm')

    def _place_landmarks(self):
        self.vp_qp.setBrush(QBrush(
            QColor(255, 255, 255, 100),
            Qt.SolidPattern,
        ))
        for landmark_id, landmark in self.gm.get_array_landmarks('stage').items():
            landmark_v = self.cs.convert_d_to_v(self.cs.convert_s_to_d(landmark))
            # draw cross
            cross_length = 100 * self.cs.vp_scale
            self.vp_qp.setPen(QColor(Qt.yellow))
            self.vp_qp.drawLine(
                QPointF(landmark_v[0] - cross_length, landmark_v[1]),
                QPointF(landmark_v[0] + cross_length, landmark_v[1]),
            )
            self.vp_qp.drawLine(
                QPointF(landmark_v[0], landmark_v[1] - cross_length),
                QPointF(landmark_v[0], landmark_v[1] + cross_length),
            )
            # draw landmark label
            font = QFont()
            fontsize = int(self.cs.vp_scale * 8)
            fontsize = max(fontsize, 10)
            font.setPixelSize(fontsize)
            self.vp_qp.setFont(font)
            landmark_rect = QRectF(
                landmark_v[0] - 50 * self.cs.vp_scale,
                landmark_v[1] - 12 * self.cs.vp_scale,
                6 * fontsize,
                4/3 * fontsize
            )
            self.vp_qp.setPen(QColor(255, 255, 255, 100))
            self.vp_qp.drawRect(landmark_rect)
            self.vp_qp.setPen(QColor(Qt.black))
            self.vp_qp.drawText(
                landmark_rect,
                Qt.AlignVCenter | Qt.AlignHCenter,
                f"landmark {landmark_id}",
            )

    def _vp_draw_live_grid_layout(self):
        """Display live rows/cols growth while user drags a new grid ROI."""
        x0, y0 = self.cs.convert_mouse_to_v(self.drag_origin)
        x1, y1 = self.cs.convert_mouse_to_v(self.drag_current)
        if x0 > x1:
            x1, x0 = x0, x1
        if y0 > y1:
            y1, y0 = y0, y1
        w = x1 - x0
        h = y1 - y0
        if w <= 0 or h <= 0:
            return
        layout = self.gm.estimate_grid_layout_for_drag(x0, y0, w, h)
        footprint_w, footprint_h = layout['footprint_um']
        fp0 = self.cs.convert_d_to_v((x0, y0))
        fp1 = self.cs.convert_d_to_v((x0 + footprint_w, y0 + footprint_h))
        self._draw_rectangle(
            self.vp_qp, fp0, fp1, constants.COLOUR_SELECTOR[12], line_style=Qt.DotLine)
        text = (
            f"Grid preview: {layout['rows']} x {layout['cols']} tiles "
            f"({layout['tile_count']} total)")
        text_rect = QRectF(
            min(self.drag_origin[0], self.drag_current[0]) + 8,
            min(self.drag_origin[1], self.drag_current[1]) - 24,
            320,
            18)
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        self.vp_qp.setBrush(QColor(255, 255, 255, 210))
        self.vp_qp.drawRect(text_rect)
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        self.vp_qp.drawText(text_rect, Qt.AlignVCenter | Qt.AlignHCenter, text)

    def _show_simulation_mode_indicator(self):
        """Draw simulation mode indicator on viewport canvas.
        QPainter object self.vp_qp must be active when calling this method.
        """
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        self.vp_qp.setBrush(QColor(0, 0, 0, 255))
        self.vp_qp.drawRect(0, 0, 120, 20)
        self.vp_qp.setPen(QPen(QColor(255, 0, 0), 1, Qt.SolidLine))
        font = QFont()
        font.setPixelSize(12)
        self.vp_qp.setFont(font)
        self.vp_qp.drawText(7, 15, 'SIMULATION MODE')

    def _show_active_user_flag(self):
        custom_text = 'ACTIVE USER: ' + self.active_user_flag_text
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        self.vp_qp.setBrush(QColor(0, 0, 0, 255))
        font = QFont()
        font.setPixelSize(16)
        metrics = QFontMetrics(font)
        self.vp_qp.drawRect(0, 0, metrics.width(custom_text) + 15, 30)
        self.vp_qp.setPen(
            QPen(QColor(*constants.COLOUR_SELECTOR[13]), 1, Qt.SolidLine))
        self.vp_qp.setFont(font)
        self.vp_qp.drawText(7, 21, custom_text)

    def _vp_draw_selection_overlay(self):
        lines = []
        if self.selected_grid is not None:
            grid = self.gm[self.selected_grid]
            grid_label = self.gm.get_grid_label(self.selected_grid)
            selection_line = (
                f'Selected: {grid_label} | active={int(grid.active)} '
                f'locked={int(grid.locked)} acquired={int(grid.acquired)}')
            if grid.is_deferred_polygon_roi():
                selection_line += (
                    f' | deferred est={grid.roi_estimated_tile_count:,} '
                    f'({grid.roi_estimated_rows} x {grid.roi_estimated_cols})')
            lines.append(selection_line)
            min_x, max_x, min_y, max_y = grid.bounding_box()
            top_left_v = self.cs.convert_d_to_v((min_x, min_y))
            bottom_right_v = self.cs.convert_d_to_v((max_x, max_y))
            x0 = min(top_left_v[0], bottom_right_v[0])
            y0 = min(top_left_v[1], bottom_right_v[1])
            width = abs(bottom_right_v[0] - top_left_v[0])
            height = abs(bottom_right_v[1] - top_left_v[1])
            self.vp_qp.setPen(QPen(QColor(255, 210, 0), 2, Qt.DashLine))
            self.vp_qp.setBrush(QColor(0, 0, 0, 0))
            self.vp_qp.drawRect(QRectF(
                x0, y0, width, height))
        if self.selected_ov is not None:
            ov = self.ovm[self.selected_ov]
            lines.append(
                f'Selected: OV {self.selected_ov} | active={int(ov.active)} '
                f'locked={int(ov.locked)} acquired={int(ov.acquired)}')
            min_x, min_y, max_x, max_y = ov.bounding_box()
            top_left_v = self.cs.convert_d_to_v((min_x, min_y))
            bottom_right_v = self.cs.convert_d_to_v((max_x, max_y))
            x0 = min(top_left_v[0], bottom_right_v[0])
            y0 = min(top_left_v[1], bottom_right_v[1])
            width = abs(bottom_right_v[0] - top_left_v[0])
            height = abs(bottom_right_v[1] - top_left_v[1])
            self.vp_qp.setPen(QPen(QColor(255, 255, 120), 2, Qt.DashLine))
            self.vp_qp.setBrush(QColor(0, 0, 0, 0))
            self.vp_qp.drawRect(QRectF(
                x0, y0, width, height))
        if not lines:
            return
        if (self.selected_grid is not None
                and self.gm[self.selected_grid].is_deferred_polygon_roi()):
            width = 620
        else:
            width = 440
        height = 18 * len(lines) + 8
        panel_rect = QRectF(8, 24, width, height)
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        self.vp_qp.setBrush(QColor(40, 40, 40, 190))
        self.vp_qp.drawRect(panel_rect)
        self.vp_qp.setPen(QPen(QColor(230, 230, 230), 1, Qt.SolidLine))
        font = QFont()
        font.setPixelSize(12)
        self.vp_qp.setFont(font)
        for i, line in enumerate(lines):
            self.vp_qp.drawText(
                QRectF(12, 28 + i * 18, width - 8, 16),
                Qt.AlignVCenter | Qt.AlignLeft, line)

    def _vp_draw_render_diagnostics(self, draw_time_ms):
        text = (
            f"Render diagnostics: antialias={int(self.render_antialias)} "
            f"scale={self.cs.vp_scale:.3f} draw={draw_time_ms:.1f} ms "
            f"layers(OV={self.ovm.number_ov}, grid={self.gm.number_grids})")
        panel_width = min(520, max(260, self.cs.vp_width - 16))
        panel_x = max(8, self.cs.vp_width - panel_width - 8)
        panel_y = 8
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        self.vp_qp.setBrush(QColor(255, 255, 255, 215))
        self.vp_qp.drawRect(QRectF(panel_x, panel_y, panel_width, 18))
        self.vp_qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine))
        font = QFont()
        font.setPixelSize(11)
        self.vp_qp.setFont(font)
        self.vp_qp.drawText(QRectF(panel_x + 4, panel_y + 2, panel_width - 8, 16),
                            Qt.AlignVCenter | Qt.AlignLeft, text)

    def _show_stage_position_indicator(self):
        """Draw red bullseye indicator at last known stage position.
        QPainter object self.vp_qp must be active when caling this method.
        """
        try:
            vx, vy = self.cs.convert_d_to_v(
                self.cs.convert_s_to_d(self.stage.last_known_xy))
        except TypeError: # last_known_xy not defined (e.g. simulation mode)
            return
        size = float(np.clip(12 * np.sqrt(max(self.cs.vp_scale, 1e-3)), 6, 36))
        pen_width = int(np.clip(size / 8, 1, 4))
        self.vp_qp.setPen(QPen(QColor(255, 0, 0), pen_width, Qt.SolidLine))
        self.vp_qp.setBrush(QColor(255, 0, 0, 0))
        self.vp_qp.drawEllipse(QPointF(vx, vy), size, size)
        self.vp_qp.setBrush(QColor(255, 0, 0, 0))
        self.vp_qp.drawEllipse(QPointF(vx, vy), size/2, size/2)
        self.vp_qp.drawLine(QPointF(vx - 1.25 * size, vy), QPointF(vx + 1.25 * size, vy))
        self.vp_qp.drawLine(QPointF(vx, vy - 1.25 * size), QPointF(vx, vy + 1.25 * size))

    def _vp_update_stage_position(self):
        """Read the current stage position and show the stage position indicator.
        """
        # Calling stage.get_xy() updates the last known XY stage position
        self.stage.get_xy()
        # Set "Show stage position" option as selected and redraw new
        # view centred on updated stage position
        self.vp_activate_checkbox_show_stage_pos()
        self.cs.vp_centre_dx_dy = self.cs.convert_s_to_d(self.stage.last_known_xy)
        self.vp_draw()

    def _vp_visible_area(self, vx, vy, w_px, h_px, resize_ratio):
        """Determine if an object at position vx, vy (Viewport coordinates) and
        size w_px, h_px at a given resize_ratio is visible in the Viewport and
        calculate its crop_area. Return visible=True if the object is visible,
        and its crop area and the new Viewport coordinates vx_cropped,
        vy_cropped. TODO: What about rotated elements?"""
        crop_area = QRect(0, 0, w_px, h_px)
        vx_cropped, vy_cropped = vx, vy
        visible = self._vp_element_visible(vx, vy, w_px, h_px, resize_ratio)
        if visible:
            if (vx >= 0) and (vy >= 0):
                crop_area = QRect(0, 0,
                                  int((self.cs.vp_width - vx) / resize_ratio + 1),
                                  int(self.cs.vp_height / resize_ratio + 1))
            if (vx >= 0) and (vy < 0):
                crop_area = QRect(0, int(-vy / resize_ratio),
                                  int((self.cs.vp_width - vx) / resize_ratio + 1),
                                  int((self.cs.vp_height) / resize_ratio + 1))
                vy_cropped = 0
            if (vx < 0) and (vy < 0):
                crop_area = QRect(int(-vx / resize_ratio), int(-vy / resize_ratio),
                                  int((self.cs.vp_width) / resize_ratio + 1),
                                  int((self.cs.vp_height) / resize_ratio + 1))
                vx_cropped, vy_cropped = 0, 0
            if (vx < 0) and (vy >= 0):
                crop_area = QRect(int(-vx / resize_ratio), 0,
                                  int((self.cs.vp_width) / resize_ratio + 1),
                                  int((self.cs.vp_height - vy) / resize_ratio + 1))
                vx_cropped = 0
        return visible, crop_area, vx_cropped, vy_cropped

    def _vp_element_visible(self, vx, vy, width, height, resize_ratio,
                            pivot_vx=0, pivot_vy=0, angle=0):
        """Return True if element is visible, otherwise return False."""
        # Calculate the four corners of the unrotated bounding box
        points_x = [vx, vx + width * resize_ratio,
                    vx, vx + width * resize_ratio]
        points_y = [vy, vy, vy + height * resize_ratio,
                    vy + height * resize_ratio]
        if angle > 0:
            angle = radians(angle)
            # Rotate all coordinates with respect to the pivot:
            # (1) Subtract pivot coordinates
            # (2) Rotate corners
            # (3) Add pivot coordinates
            for i in range(4):
                points_x[i] -= pivot_vx
                points_y[i] -= pivot_vy
                x_rot = points_x[i] * cos(angle) - points_y[i] * sin(angle)
                y_rot = points_x[i] * sin(angle) + points_y[i] * cos(angle)
                points_x[i] = x_rot + pivot_vx
                points_y[i] = y_rot + pivot_vy
        # Find the maximum and minimum x and y coordinates:
        max_x, min_x = max(points_x), min(points_x)
        max_y, min_y = max(points_y), min(points_y)
        # Check if bounding box is entirely outside viewport
        if (min_x > self.cs.vp_width or max_x < 0
            or min_y > self.cs.vp_height or max_y < 0):
            return False
        return True

    def _vp_place_stub_overview(self, stub_ovm):
        """Place stub overview image onto the Viewport canvas. Crop and resize
        the image before placing it. QPainter object self.vp_qp must be active
        when calling this method."""

        if stub_ovm.image() is None:
            return

        viewport_pixel_size = 1000 / self.cs.vp_scale
        resize_ratio0 = stub_ovm.pixel_size / viewport_pixel_size
        # calculate size pyramid level to power of 2 value
        mag_level = np.clip(int(2 ** -np.round(np.log2(resize_ratio0))), 1, 16)

        # Compute position of stub overview (upper left corner) and its
        # width and height
        dx, dy = np.array(stub_ovm.origin_dx_dy) - stub_ovm.tile_size_d() / 2
        vx, vy = self.cs.convert_d_to_v((dx, dy))

        width_px, height_px = np.array(stub_ovm.size_p()) // mag_level
        resize_ratio = resize_ratio0 * mag_level
        # Crop and resize stub OV before placing it
        visible, crop_area, vx_cropped, vy_cropped = self._vp_visible_area(
            vx, vy, width_px, height_px, resize_ratio)
        if visible:
            image = stub_ovm.image(mag=mag_level)
            if image is None:
                return
            cropped_img = image.copy(crop_area)
            v_width = cropped_img.size().width()
            cropped_resized_img = cropped_img.scaledToWidth(
                int(v_width * resize_ratio))
            # Draw stub OV on canvas
            self.vp_qp.drawPixmap(QPointF(vx_cropped, vy_cropped),
                                  cropped_resized_img)
            # Draw dark grey rectangle around stub OV
            pen = QPen(QColor(*constants.COLOUR_SELECTOR[11]), 2, Qt.SolidLine)
            self.vp_qp.setPen(pen)
            self.vp_qp.drawRect(QRectF(vx - 1, vy - 1,
                                width_px * resize_ratio + 1,
                                height_px * resize_ratio + 1))

    def _vp_place_stub_archive(self, index):
        imported = self.imported[index]
        if (not imported.enabled
                or not imported.is_stub_archive
                or imported.image is None):
            return
        if imported.rotation != 0 or imported.flipped:
            self._vp_place_imported_img(index)
            return

        viewport_pixel_size = 1000 / self.cs.vp_scale
        resize_ratio0 = imported.pixel_size / viewport_pixel_size
        mag_level = np.clip(int(2 ** -np.round(np.log2(resize_ratio0))), 1, 16)
        image = imported.pyramid_image(mag=mag_level)
        if image is None:
            return

        width_px, height_px = np.array(imported.size) // mag_level
        centre_dx_dy = self.cs.convert_s_to_d(imported.centre_sx_sy)
        dx = centre_dx_dy[0] - (imported.size[0] * imported.pixel_size / 1000) / 2
        dy = centre_dx_dy[1] - (imported.size[1] * imported.pixel_size / 1000) / 2
        vx, vy = self.cs.convert_d_to_v((dx, dy))

        resize_ratio = resize_ratio0 * mag_level
        visible, crop_area, vx_cropped, vy_cropped = self._vp_visible_area(
            vx, vy, width_px, height_px, resize_ratio)
        if not visible:
            return

        cropped_img = image.copy(crop_area)
        v_width = cropped_img.size().width()
        cropped_resized_img = cropped_img.scaledToWidth(
            int(v_width * resize_ratio))
        self.vp_qp.setOpacity(1 - imported.transparency / 100)
        self.vp_qp.drawPixmap(QPointF(vx_cropped, vy_cropped),
                              cropped_resized_img)
        self.vp_qp.setOpacity(1)

    def _vp_place_imported_img0(self, index):
        """Place imported image specified by index onto the viewport canvas."""
        imported = self.imported[index]
        if imported.enabled and imported.image is not None:
            viewport_pixel_size = 1000 / self.cs.vp_scale
            image_pixel_size = imported.pixel_size
            resize_ratio = image_pixel_size / viewport_pixel_size

            # Compute position of image in viewport:
            dx, dy = self.cs.convert_s_to_d(
                imported.centre_sx_sy)
            # Get width and height of the imported QPixmap:
            width = imported.image.width()
            height = imported.image.height()
            pixel_size = imported.pixel_size
            dx -= (width * pixel_size / 1000) / 2
            dy -= (height * pixel_size / 1000) / 2
            vx, vy = self.cs.convert_d_to_v((dx, dy))
            # Crop and resize image before placing it into viewport:
            visible, crop_area, vx_cropped, vy_cropped = self._vp_visible_area(
                vx, vy, width, height, resize_ratio)
            if visible:
                cropped_img = imported.image.copy(crop_area)
                v_width = cropped_img.size().width()
                cropped_resized_img = cropped_img.scaledToWidth(
                    int(v_width * resize_ratio))
                self.vp_qp.setOpacity(
                    1 - imported.transparency / 100)
                self.vp_qp.drawPixmap(QPointF(vx_cropped, vy_cropped),
                                      cropped_resized_img)
                self.vp_qp.setOpacity(1)

    def _vp_place_imported_img(self, index):
        """Place imported image specified by index onto the viewport canvas."""
        imported = self.imported[index]
        if imported.enabled and imported.image is not None:
            viewport_pixel_size = 1000 / self.cs.vp_scale
            image_pixel_size = imported.pixel_size
            resize_ratio = image_pixel_size / viewport_pixel_size

            # Compute position of image in viewport:
            transform_s_d = self.cs.get_s_to_d_transform()
            center_position = utils.apply_transform(imported.centre_sx_sy, transform_s_d)
            image = imported.image.transformed(utils.transform_to_QTransform(transform_s_d))

            width, height = image.width(), image.height()
            position = center_position - np.array([width, height]) / 2 * image_pixel_size / 1000
            #transform_d_v = self.cs.get_d_to_v_transform()
            #vx, vy = utils.apply_transform(position, transform_d_v)
            vx, vy = self.cs.convert_d_to_v(position)

            # Get width and height of the imported QPixmap:
            # Crop and resize image before placing it into viewport:
            visible, crop_area, vx_cropped, vy_cropped = self._vp_visible_area(
                vx, vy, width, height, resize_ratio)
            if visible:
                cropped_img = image.copy(crop_area)
                v_width = cropped_img.size().width()
                cropped_resized_img = cropped_img.scaledToWidth(
                    int(v_width * resize_ratio))
                self.vp_qp.setOpacity(
                    1 - imported.transparency / 100)
                self.vp_qp.drawPixmap(QPointF(vx_cropped, vy_cropped),
                                      cropped_resized_img)
                self.vp_qp.setOpacity(1)

    def _vp_imported_visible(self, index):
        imported = self.imported[index]
        if not imported.enabled:
            return False
        if imported.is_stub_archive:
            return self.show_stub_ov
        return self.show_imported

    def _vp_place_overview(self, ov_index,
                           show_debris_area=False, suppress_labels=False):
        """Place OV overview image specified by ov_index onto the viewport
        canvas. Crop and resize the image before placing it.
        """
        # Load, resize and crop OV for display.
        viewport_pixel_size = 1000 / self.cs.vp_scale
        ov_pixel_size = self.ovm[ov_index].pixel_size
        resize_ratio = ov_pixel_size / viewport_pixel_size
        accent_rgb = self.acq_groups.overview_accent_colour(ov_index)
        # Load OV centre in SEM coordinates.
        dx, dy = self.ovm[ov_index].centre_dx_dy
        # First, calculate origin of OV image with respect to
        # SEM coordinate system.
        dx -= self.ovm[ov_index].width_d() / 2
        dy -= self.ovm[ov_index].height_d() / 2
        width_px = self.ovm[ov_index].width_p()
        height_px = self.ovm[ov_index].height_p()
        # Convert to viewport window coordinates.
        vx, vy = self.cs.convert_d_to_v((dx, dy))

        if not suppress_labels:
            # Suppress the display of labels for performance reasons.
            # TODO: Reconsider this after refactoring complete.
            suppress_labels = (
                (self.gm.number_grids + self.ovm.number_ov) > 10
                and self.cs.vp_scale < 1.0)

        # Crop and resize OV before placing it.
        visible, crop_area, vx_cropped, vy_cropped = self._vp_visible_area(
            vx, vy, width_px, height_px, resize_ratio)

        if not visible:
            return

        # Show OV label in upper left corner
        if self.show_labels and not suppress_labels:
            font_size = int(self.cs.vp_scale * 8)
            if font_size < 12:
                font_size = 12
            self.vp_qp.setPen(QColor(*constants.COLOUR_SELECTOR[10]))
            self.vp_qp.setBrush(QColor(*constants.COLOUR_SELECTOR[10]))
            if self.ovm[ov_index].active:
                width_factor = 3.6
            else:
                width_factor = 9
            ov_label_rect = QRectF(
                vx, vy - 4/3 * font_size,
                width_factor * font_size, 4/3 * font_size)
            self.vp_qp.drawRect(ov_label_rect)
            if accent_rgb is not None:
                chip_size = max(6, int(font_size * 0.55))
                chip_rect = QRectF(
                    ov_label_rect.right() - chip_size - 3,
                    ov_label_rect.top() + 2,
                    chip_size,
                    chip_size)
                self.vp_qp.setPen(QColor(*accent_rgb))
                self.vp_qp.setBrush(QColor(*accent_rgb))
                self.vp_qp.drawRect(chip_rect)
            self.vp_qp.setPen(QColor(255, 255, 255))
            font = QFont()
            font.setPixelSize(font_size)
            self.vp_qp.setFont(font)
            ov_label_text = f'OV {ov_index}'
            if not self.ovm[ov_index].active:
                ov_label_text += ' (inactive)'
            self.vp_qp.drawText(ov_label_rect,
                                Qt.AlignVCenter | Qt.AlignHCenter,
                                ov_label_text)

        if self.ovm[ov_index].active:
            cropped_img = self.ovm[ov_index].image.copy(crop_area)
            v_width = cropped_img.size().width()
            cropped_resized_img = cropped_img.scaledToWidth(
                int(v_width * resize_ratio))
            if not (self.ov_drag_active and ov_index == self.selected_ov):
                # Draw OV
                self.vp_qp.drawPixmap(QPointF(vx_cropped, vy_cropped),
                                      cropped_resized_img)
        pen_style = Qt.SolidLine if self.ovm[ov_index].active else Qt.DashLine
        pen_width = 2
        if self.ovm[ov_index].locked:
            pen_width = 3
        if ov_index == self.selected_ov:
            pen_width = max(3, pen_width)
        # Draw blue rectangle around OV (for active and inactive OVs).
        self.vp_qp.setPen(
            QPen(QColor(*constants.COLOUR_SELECTOR[10]), pen_width, pen_style))
        if ((self.ov_acq_indicator is not None)
            and self.ov_acq_indicator == ov_index):
            self.vp_qp.setBrush(QColor(*constants.COLOUR_SELECTOR[12]))
        elif self.ovm[ov_index].active:
            self.vp_qp.setBrush(QColor(0, 0, 0, 0))
        else:
            # Keep inactive OV footprints visible without requiring activation.
            self.vp_qp.setBrush(QColor(0, 0, 255, 25))
        self.vp_qp.drawRect(QRectF(vx, vy,
                            width_px * resize_ratio,
                            height_px * resize_ratio))
        if accent_rgb is not None:
            accent_pen = QPen(QColor(*accent_rgb), max(2, pen_width + 1), Qt.SolidLine)
            self.vp_qp.setPen(accent_pen)
            self.vp_qp.drawLine(
                QPointF(vx + 2, vy + 2),
                QPointF(vx + min(18, width_px * resize_ratio * 0.18), vy + 2))
            self.vp_qp.drawLine(
                QPointF(vx + 2, vy + 2),
                QPointF(vx + 2, vy + min(18, height_px * resize_ratio * 0.18)))

        if show_debris_area and self.ovm[ov_index].active:
            # w3, w4 are fudge factors for clearer display
            w3 = np.clip(self.cs.vp_scale/2, 1, 3)
            w4 = np.clip(self.cs.vp_scale, 5, 9)

            area = self.ovm[ov_index].debris_detection_area
            if area:
                (top_left_dx, top_left_dy,
                 bottom_right_dx, bottom_right_dy) = area
                width = bottom_right_dx - top_left_dx
                height = bottom_right_dy - top_left_dy
                if width == self.ovm[ov_index].width_p():
                    w3, w4 = 3, 6

                pen = QPen(
                    QColor(*constants.COLOUR_SELECTOR[10]), 2, Qt.DashDotLine)
                self.vp_qp.setPen(pen)
                self.vp_qp.setBrush(QColor(0, 0, 0, 0))
                self.vp_qp.drawRect(QRectF(vx + top_left_dx * resize_ratio - w3,
                                    vy + top_left_dy * resize_ratio - w3,
                                    width * resize_ratio + w4,
                                    height * resize_ratio + w4))

    def _vp_draw_polygon_overlay(self, grid_index):
        grid = self.gm[grid_index]
        if not grid.has_polygon_roi():
            return

        polygon_points = grid.roi_local_points_d()
        if len(polygon_points) < 3:
            return

        selected = (grid_index == self.selected_grid)
        overlay_colour = QColor(255, 255, 255, 220 if selected else 140)
        self.vp_qp.setPen(QPen(overlay_colour, 2 if selected else 1, Qt.DashLine))
        self.vp_qp.setBrush(QColor(255, 255, 255, 0))
        polygon_points_v = [
            QPointF(point[0] * self.cs.vp_scale, point[1] * self.cs.vp_scale)
            for point in polygon_points]
        for index, point in enumerate(polygon_points_v):
            next_point = polygon_points_v[(index + 1) % len(polygon_points_v)]
            self.vp_qp.drawLine(point, next_point)

        if grid.is_deferred_polygon_roi():
            note_rect = QRectF(
                0,
                max(6, grid.sw_sh[1] * self.cs.vp_scale * 0.5 - 12),
                max(120, grid.sw_sh[0] * self.cs.vp_scale),
                24)
            self.vp_qp.setPen(QPen(QColor(255, 255, 255), 1, Qt.SolidLine))
            self.vp_qp.setBrush(QColor(20, 20, 20, 170))
            self.vp_qp.drawRect(note_rect)
            deferred_text = (
                f'Deferred ROI: {grid.roi_estimated_tile_count:,} est. tiles')
            self.vp_qp.drawText(
                note_rect,
                Qt.AlignVCenter | Qt.AlignHCenter,
                deferred_text)

        if not selected:
            return

        if grid.roi_shape_type in polygon_roi.PREDEFINED_SHAPE_TYPES:
            handle_points = [
                QPointF(0, 0),
                QPointF(grid.sw_sh[0] * self.cs.vp_scale, 0),
                QPointF(grid.sw_sh[0] * self.cs.vp_scale, grid.sw_sh[1] * self.cs.vp_scale),
                QPointF(0, grid.sw_sh[1] * self.cs.vp_scale),
            ]
        else:
            handle_points = polygon_points_v

        handle_size = 8
        self.vp_qp.setPen(QPen(QColor(255, 255, 255), 1, Qt.SolidLine))
        if self.use_klab_ui:
            self.vp_qp.setBrush(QColor(8, 76, 97, 220))
        else:
            self.vp_qp.setBrush(QColor(20, 20, 20, 220))
        for point in handle_points:
            self.vp_qp.drawRect(QRectF(
                point.x() - handle_size / 2,
                point.y() - handle_size / 2,
                handle_size,
                handle_size))

    def _vp_draw_pending_polygon(self):
        if self.vp_polygon_tool != polygon_roi.CUSTOM_SHAPE_TYPE:
            return
        if not self.vp_polygon_custom_points:
            return

        self.vp_qp.setPen(QPen(QColor(255, 255, 255), 2, Qt.DashLine))
        self.vp_qp.setBrush(QColor(255, 255, 255))
        for index in range(len(self.vp_polygon_custom_points) - 1):
            point0 = self.cs.convert_d_to_v(self.vp_polygon_custom_points[index])
            point1 = self.cs.convert_d_to_v(self.vp_polygon_custom_points[index + 1])
            self.vp_qp.drawLine(
                QPointF(float(point0[0]), float(point0[1])),
                QPointF(float(point1[0]), float(point1[1])))
        if self.vp_polygon_hover_point is not None:
            point0 = self.cs.convert_d_to_v(self.vp_polygon_custom_points[-1])
            point1 = self.cs.convert_d_to_v(self.vp_polygon_hover_point)
            self.vp_qp.drawLine(
                QPointF(float(point0[0]), float(point0[1])),
                QPointF(float(point1[0]), float(point1[1])))
        for point in self.vp_polygon_custom_points:
            vx, vy = self.cs.convert_d_to_v(point)
            self.vp_qp.drawEllipse(QPointF(vx, vy), 4, 4)

    def _vp_place_grid(self, grid_index,
                       show_grid=True, show_previews=False, with_gaps=False,
                       suppress_labels=False):
        """Place grid specified by grid_index onto the viewport canvas
        (including tile previews if option selected).
        """
        grid = self.gm[grid_index]
        grid_label = grid.get_label(grid_index)
        viewport_pixel_size = 1000 / self.cs.vp_scale
        grid_pixel_size = grid.pixel_size
        resize_ratio = grid_pixel_size / viewport_pixel_size

        # Calculate coordinates of grid origin with respect to Viewport canvas
        dx, dy = grid.origin_dx_dy
        origin_vx, origin_vy = self.cs.convert_d_to_v((dx, dy))

        # Calculate top-left corner of the (unrotated) grid
        dx -= grid.tile_width_d() / 2
        dy -= grid.tile_height_d() / 2
        topleft_vx, topleft_vy = self.cs.convert_d_to_v((dx, dy))

        width_px = grid.width_p()
        height_px = grid.height_p()
        theta = grid.rotation
        use_rotation = (theta != 0)

        font = QFont()
        effective_display_colour = (
            self.acq_groups.effective_grid_display_colour(grid_index))
        grid_colour_rgb = self.acq_groups.effective_grid_colour_rgb(grid_index)
        if len(grid_colour_rgb) < 4:
            grid_colour_rgba = grid_colour_rgb + [255]
        else:
            grid_colour_rgba = grid_colour_rgb
        grid_colour = QColor(*grid_colour_rgba)
        indicator_colour = QColor(*constants.COLOUR_SELECTOR[12])

        # In dense array mode, labels remain suppressed when zoomed far out.
        if self.gm.array_mode and self.cs.vp_scale < 1:
            suppress_labels = True

        if grid.is_deferred_polygon_roi():
            min_x, max_x, min_y, max_y = grid.bounding_box()
            top_left_v = self.cs.convert_d_to_v((min_x, min_y))
            bottom_right_v = self.cs.convert_d_to_v((max_x, max_y))
            visible = not (
                min(top_left_v[0], bottom_right_v[0]) > self.cs.vp_width
                or max(top_left_v[0], bottom_right_v[0]) < 0
                or min(top_left_v[1], bottom_right_v[1]) > self.cs.vp_height
                or max(top_left_v[1], bottom_right_v[1]) < 0)
        else:
            visible = self._vp_element_visible(
                topleft_vx, topleft_vy, width_px, height_px, resize_ratio,
                origin_vx, origin_vy, theta)

        # Proceed only if at least a part of the grid is visible
        if not visible:
            return

        # Rotate the painter if grid has a rotation angle <> 0
        if use_rotation:
            # Translate painter to coordinates of grid origin, then rotate
            self.vp_qp.translate(origin_vx, origin_vy)
            self.vp_qp.rotate(theta)
            # Translate to top-left corner
            self.vp_qp.translate(
                -grid.tile_width_d() / 2 * self.cs.vp_scale,
                -grid.tile_height_d() / 2 * self.cs.vp_scale)
            # Enable anti-aliasing
            self.vp_qp.setRenderHint(QPainter.Antialiasing, self.render_antialias)
        else:
            # Translate painter to coordinates of top-left corner
            self.vp_qp.translate(topleft_vx, topleft_vy)

        # Show grid label in upper left corner
        if self.show_labels and not suppress_labels:
            fontsize = int(self.cs.vp_scale * 8)
            if fontsize < 12:
                fontsize = 12
            font.setPixelSize(fontsize)
            self.vp_qp.setFont(font)
            self.vp_qp.setPen(grid_colour)
            self.vp_qp.setBrush(grid_colour)
            if grid.active:
                width_factor = 5.3
            else:
                width_factor = 10.5
            if grid.is_deferred_polygon_roi():
                width_factor = max(width_factor, 12.5)
            grid_label_rect = QRect(0,
                                    -int(4/3 * fontsize),
                                    int(width_factor * fontsize),
                                    int(4/3 * fontsize))
            self.vp_qp.drawRect(grid_label_rect)
            if effective_display_colour in [1, 2, 3]:
            # Use black for light and white for dark background colour
                self.vp_qp.setPen(QColor(0, 0, 0))
            else:
                self.vp_qp.setPen(QColor(255, 255, 255))
            # Show the grid label in different versions, depending on
            # whether grid is active
            grid_label_text = grid_label
            if grid.is_deferred_polygon_roi():
                grid_label_text += ' (deferred)'
            if not grid.active:
                grid_label_text += ' (inactive)'
            self.vp_qp.drawText(grid_label_rect,
                                Qt.AlignVCenter | Qt.AlignHCenter,
                                grid_label_text)

        # Deferred polygon ROIs draw only the polygon overlay and skip
        # full tile materialization in the viewport.
        if grid.is_deferred_polygon_roi():
            if show_grid:
                self._vp_draw_polygon_overlay(grid_index)
            self.vp_qp.resetTransform()
            return

        # Inactive grids still need a lightweight footprint so they remain
        # visible when labels are temporarily suppressed during interaction.
        if not grid.active:
            if show_grid:
                inactive_pen_width = 2 if grid_index == self.selected_grid else 1
                inactive_pen = QPen(
                    grid_colour, inactive_pen_width, Qt.DashLine)
                inactive_fill = QColor(grid_colour)
                inactive_fill.setAlpha(25)
                self.vp_qp.setPen(inactive_pen)
                self.vp_qp.setBrush(inactive_fill)
                self.vp_qp.drawRect(QRectF(
                    0, 0,
                    width_px * resize_ratio,
                    height_px * resize_ratio))
                self._vp_draw_polygon_overlay(grid_index)
            self.vp_qp.resetTransform()
            return

        if with_gaps:
            # Use gapped tile grid in pixels (coordinates not rotated)
            tile_map = grid.gapped_tile_positions_p()
        else:
            # Tile grid in pixels (coordinates not rotated)
            tile_map = grid.tile_positions_p()

        tile_width_v = grid.tile_width_d() * self.cs.vp_scale
        tile_height_v = grid.tile_height_d() * self.cs.vp_scale

        font_size1 = int(tile_width_v/5)
        font_size1 = np.clip(font_size1, 2, 120)
        font_size2 = int(tile_width_v/11)
        font_size2 = np.clip(font_size2, 1, 40)

        if (show_previews
                and not self.fov_drag_active
                and not self.grid_drag_active):
            # Previews are disabled when FOV or grid are being dragged
            width_px = grid.tile_width_p()
            height_px = grid.tile_height_p()

            for tile_index in grid.active_tiles:
                vx = tile_map[tile_index][0] * resize_ratio
                vy = tile_map[tile_index][1] * resize_ratio
                tile_visible = self._vp_element_visible(
                    topleft_vx + vx, topleft_vy + vy,
                    width_px, height_px, resize_ratio,
                    origin_vx, origin_vy, theta)
                if not tile_visible:
                    continue
                # Show tile preview
                preview_img = grid[tile_index].preview_img
                if preview_img is not None:
                    tile_img = preview_img.scaledToWidth(int(tile_width_v))
                    self.vp_qp.drawPixmap(QPointF(vx, vy), tile_img)

        # Display grid lines
        rows, cols = grid.size
        grid_pen = QPen(grid_colour, 1, Qt.SolidLine)
        if len(grid_colour_rgb) < 4:
            grid_colour_rgba = grid_colour_rgb + [40]
        else:
            grid_colour_rgba = grid_colour_rgb
        grid_brush_active_tile = QBrush(QColor(*grid_colour_rgba),
                                        Qt.SolidPattern)
        grid_brush_transparent = QBrush(QColor(255, 255, 255, 0),
                                        Qt.SolidPattern)

        # In dense array mode, tile labels remain suppressed when zoomed far out.
        if self.gm.array_mode and self.cs.vp_scale < 0.5:
            suppress_labels = True

        if ((tile_width_v * cols > 2 or tile_height_v * rows > 2)
                and 'multisem' not in self.sem.device_name.lower()):
            # Draw grid if at least 3 pixels wide or high.
            for tile_index in range(rows * cols):
                self.vp_qp.setPen(grid_pen)
                if grid[tile_index].tile_active:
                    self.vp_qp.setBrush(grid_brush_active_tile)
                else:
                    self.vp_qp.setBrush(grid_brush_transparent)
                if (self.tile_acq_indicator[0] is not None and
                    (self.tile_acq_indicator == [grid_index, tile_index])):
                    self.vp_qp.setBrush(indicator_colour)
                # Draw tile rectangles.
                if show_grid:
                    self.vp_qp.drawRect(QRectF(
                        tile_map[tile_index][0] * resize_ratio,
                        tile_map[tile_index][1] * resize_ratio,
                        tile_width_v, tile_height_v))
                if self.show_labels and not suppress_labels:
                    if grid[tile_index].tile_active:
                        self.vp_qp.setPen(QColor(255, 255, 255))
                        font.setBold(True)
                    else:
                        self.vp_qp.setPen(grid_colour)
                        font.setBold(False)
                    pos_x = (tile_map[tile_index][0] * resize_ratio
                             + tile_width_v / 2)
                    pos_y = (tile_map[tile_index][1] * resize_ratio
                             + tile_height_v / 2)
                    position_rect = QRect(int(pos_x - tile_width_v / 2),
                                          int(pos_y - tile_height_v / 2),
                                          int(tile_width_v), int(tile_height_v))
                    # Show tile indices.
                    font.setPixelSize(int(font_size1))
                    self.vp_qp.setFont(font)
                    self.vp_qp.drawText(
                        position_rect, Qt.AlignVCenter | Qt.AlignHCenter,
                        str(tile_index))

                    # Show autofocus/gradient labels and working distance.
                    font = QFont()
                    font.setPixelSize(int(font_size2))
                    font.setBold(True)
                    self.vp_qp.setFont(font)
                    position_rect = QRect(
                        int(pos_x - tile_width_v),
                        int(pos_y - tile_height_v - tile_height_v/4),
                        int(2 * tile_width_v), int(2 * tile_height_v))
                    show_grad_label = (
                        grid[tile_index].wd_grad_active
                        and grid.use_wd_gradient)
                    show_autofocus_label = (
                        grid[tile_index].autofocus_active
                        and self.acq.use_autofocus
                        and self.autofocus.method in (0, 1, 3, 4))
                    show_tracking_label = (
                        grid[tile_index].autofocus_active
                        and self.acq.use_autofocus
                        and self.autofocus.method == 2)

                    if show_grad_label and show_autofocus_label:
                        self.vp_qp.drawText(position_rect,
                                            Qt.AlignVCenter | Qt.AlignHCenter,
                                            'GRAD + AF')
                    elif show_grad_label and show_tracking_label:
                        self.vp_qp.drawText(position_rect,
                                            Qt.AlignVCenter | Qt.AlignHCenter,
                                            'GRAD + TRACK')
                    elif show_grad_label:
                        self.vp_qp.drawText(position_rect,
                                            Qt.AlignVCenter | Qt.AlignHCenter,
                                            'GRADIENT')
                    elif show_autofocus_label:
                        self.vp_qp.drawText(position_rect,
                                            Qt.AlignVCenter | Qt.AlignHCenter,
                                            'AUTOFOCUS')
                    elif show_tracking_label:
                        self.vp_qp.drawText(position_rect,
                                            Qt.AlignVCenter | Qt.AlignHCenter,
                                            'TRACKED FOCUS')

                    font.setBold(False)
                    self.vp_qp.setFont(font)
                    if (grid[tile_index].wd > 0
                        and (grid[tile_index].tile_active
                             or show_grad_label
                             or show_autofocus_label
                             or show_tracking_label)):
                        position_rect = QRect(
                            int(pos_x - tile_width_v),
                            int(pos_y - tile_height_v + tile_height_v / 4),
                            int(2 * tile_width_v), int(2 * tile_height_v))
                        self.vp_qp.drawText(
                            position_rect,
                            Qt.AlignVCenter | Qt.AlignHCenter,
                            'WD: {0:.6f}'.format(
                                self.gm[grid_index][tile_index].wd * 1000))
        else:
            # Show the grid as a single pixel (for performance reasons when
            # zoomed out).
            if show_grid:
                self.vp_qp.setPen(grid_pen)
                self.vp_qp.drawPoint(int(tile_map[0][0] * resize_ratio),
                                     int(tile_map[0][1] * resize_ratio))

        # Reset painter (undo translation and rotation).
        if show_grid:
            self._vp_draw_polygon_overlay(grid_index)
        self.vp_qp.resetTransform()

        # ---- Autofocus points in Array mode ---- #
        if self.gm.array_mode:
            self.vp_qp.setBrush(QBrush(
                QColor(Qt.red),
                Qt.SolidPattern))
            for autofocus_point in self.gm.array_autofocus_points(grid_index):
                autofocus_point_v = self.cs.convert_d_to_v(autofocus_point)
                diameter = 2 * self.cs.vp_scale
                self.vp_qp.drawEllipse(
                    autofocus_point_v[0]-diameter/2,
                    autofocus_point_v[1]-diameter/2,
                    diameter,
                    diameter)
        #-----------------------------------------#

    def _place_template(self):
        if np.prod(self.tm.template.frame_size) == 0:
            return
        viewport_pixel_size = 1000 / self.cs.vp_scale
        grid_pixel_size = self.tm.pixel_size
        resize_ratio = grid_pixel_size / viewport_pixel_size

        # Calculate coordinates of grid origin with respect to Viewport canvas
        dx, dy = self.tm.template.origin_dx_dy
        origin_vx, origin_vy = self.cs.convert_d_to_v((dx, dy))

        # Calculate top-left corner of the (unrotated) grid
        dx -= self.tm.template.tile_width_d() / 2
        dy -= self.tm.template.tile_height_d() / 2
        topleft_vx, topleft_vy = self.cs.convert_d_to_v((dx, dy))

        width_px = self.tm.template.width_p()
        height_px = self.tm.template.height_p()
        theta = self.tm.template.rotation
        use_rotation = (theta != 0)

        font = QFont()
        grid_colour_rgb = self.tm.template.display_colour_rgb()
        if len(grid_colour_rgb) < 4:
            grid_colour_rgba = grid_colour_rgb + [255]
        else:
            grid_colour_rgba = grid_colour_rgb
        grid_colour = QColor(*grid_colour_rgba)

        visible = self._vp_element_visible(
            topleft_vx, topleft_vy, width_px, height_px, resize_ratio,
            origin_vx, origin_vy, theta)

        # Proceed only if at least a part of the grid is visible
        if not visible:
            return

        # Rotate the painter if grid has a rotation angle <> 0
        if use_rotation:
            # Translate painter to coordinates of grid origin, then rotate
            self.vp_qp.translate(origin_vx, origin_vy)
            self.vp_qp.rotate(theta)
            # Translate to top-left corner
            self.vp_qp.translate(
                -self.tm.template.tile_width_d() / 2 * self.cs.vp_scale,
                -self.tm.template.tile_height_d() / 2 * self.cs.vp_scale)
            # Enable anti-aliasing in this case:
            # self.vp_qp.setRenderHint(QPainter.Antialiasing)
            # TODO: Try Antialiasing again - advantageous or not? What about
            # Windows 7 vs Windows 10?
        else:
            # Translate painter to coordinates of top-left corner
            self.vp_qp.translate(topleft_vx, topleft_vy)

        # Show grid label in upper left corner
        if self.show_labels:
            fontsize = int(self.cs.vp_scale * 8)
            if fontsize < 12:
                fontsize = 12
            font.setPixelSize(fontsize)
            self.vp_qp.setFont(font)
            self.vp_qp.setPen(grid_colour)
            self.vp_qp.setBrush(grid_colour)
            if self.tm.template.active:
                width_factor = 5.3
            else:
                width_factor = 10.5
            grid_label_rect = QRectF(0,
                                    -4/3 * fontsize,
                                    width_factor * fontsize,
                                    4/3 * fontsize)
            self.vp_qp.drawRect(grid_label_rect)
            if self.tm.template.display_colour in [1, 2, 3]:
            # Use black for light and white for dark background colour
                self.vp_qp.setPen(QColor(0, 0, 0))
            else:
                self.vp_qp.setPen(QColor(255, 255, 255))

            self.vp_qp.drawText(grid_label_rect,
                                Qt.AlignVCenter | Qt.AlignHCenter,
                                'TEMPLATE')

        # Tile grid in pixels (coordinates not rotated)
        tile_map = self.tm.template.tile_positions_p()

        tile_width_v = self.tm.template.tile_width_d() * self.cs.vp_scale
        tile_height_v = self.tm.template.tile_height_d() * self.cs.vp_scale

        # Display grid lines
        rows, cols = self.tm.template.size
        grid_pen = QPen(grid_colour, 1, Qt.SolidLine)
        if len(grid_colour_rgb) < 4:
            grid_colour_rgba = grid_colour_rgb + [40]
        else:
            grid_colour_rgba = grid_colour_rgb
        grid_brush_active_tile = QBrush(QColor(*grid_colour_rgba),
                                        Qt.SolidPattern)
        if tile_width_v * cols > 2 or tile_height_v * rows > 2:
            # Draw grid if at least 3 pixels wide or high.
            for tile_index in range(rows * cols):
                self.vp_qp.setPen(grid_pen)
                self.vp_qp.setBrush(grid_brush_active_tile)
                # Draw tile rectangles.
                self.vp_qp.drawRect(QRectF(
                    tile_map[tile_index][0] * resize_ratio,
                    tile_map[tile_index][1] * resize_ratio,
                    tile_width_v, tile_height_v))
        else:
            # Show the grid as a single pixel (for performance reasons when
            # zoomed out).
            self.vp_qp.setPen(grid_pen)
            self.vp_qp.drawPoint(tile_map[0][0] * resize_ratio,
                                 tile_map[0][1] * resize_ratio)

        # Reset painter (undo translation and rotation).
        self.vp_qp.resetTransform()

    def _vp_draw_stage_boundaries(self):
        """Calculate and show bounding box around the area accessible to the
        stage motors."""
        x_min, x_max, y_min, y_max = self.stage.limits
        b_left = self.cs.convert_d_to_v(self.cs.convert_s_to_d((x_min, y_min)))
        b_top = self.cs.convert_d_to_v(self.cs.convert_s_to_d((x_max, y_min)))
        b_right = self.cs.convert_d_to_v(self.cs.convert_s_to_d((x_max, y_max)))
        b_bottom = self.cs.convert_d_to_v(self.cs.convert_s_to_d((x_min, y_max)))
        self.vp_qp.setPen(QColor(255, 255, 255))
        self.vp_qp.drawLine(QPointF(*b_left), QPointF(*b_top))
        self.vp_qp.drawLine(QPointF(*b_top), QPointF(*b_right))
        self.vp_qp.drawLine(QPointF(*b_right), QPointF(*b_bottom))
        self.vp_qp.drawLine(QPointF(*b_bottom), QPointF(*b_left))
        if self.show_labels:
            # Show coordinates of stage corners.
            font = QFont()
            font.setPixelSize(12)
            self.vp_qp.setFont(font)
            self.vp_qp.drawText(QPointF(b_left[0] - 75, b_left[1]),
                                f'X: {x_min:.0f} µm')
            self.vp_qp.drawText(QPointF(b_left[0] - 75, b_left[1] + 15),
                                f'Y: {y_min:.0f} µm')
            self.vp_qp.drawText(QPointF(b_top[0] - 20, b_top[1] - 25),
                                f'X: {x_max:.0f} µm')
            self.vp_qp.drawText(QPointF(b_top[0] - 20, b_top[1] - 10),
                                f'Y: {y_min:.0f} µm')
            self.vp_qp.drawText(QPointF(b_right[0] + 10, b_right[1]),
                                f'X: {x_max:.0f} µm')
            self.vp_qp.drawText(QPointF(b_right[0] + 10, b_right[1] + 15),
                                f'Y: {y_max:.0f} µm')
            self.vp_qp.drawText(QPointF(b_bottom[0] - 20, b_bottom[1] + 15),
                                f'X: {x_min:.0f} µm')
            self.vp_qp.drawText(QPointF(b_bottom[0] - 20, b_bottom[1] + 30),
                                f'Y: {y_max:.0f} µm')

    def _vp_draw_stage_axes(self):
        """Calculate and show the x axis and the y axis of the stage."""
        x_min, x_max, y_min, y_max = self.stage.limits
        x_axis_start = self.cs.convert_d_to_v(
            self.cs.convert_s_to_d((x_min - 100, 0)))
        x_axis_end = self.cs.convert_d_to_v(
            self.cs.convert_s_to_d((x_max + 100, 0)))
        y_axis_start = self.cs.convert_d_to_v(
            self.cs.convert_s_to_d((0, y_min - 100)))
        y_axis_end = self.cs.convert_d_to_v(
            self.cs.convert_s_to_d((0, y_max + 100)))
        self.vp_qp.setPen(QPen(QColor(255, 255, 255), 1, Qt.DashLine))
        self.vp_qp.drawLine(QPointF(*x_axis_start), QPointF(*x_axis_end))
        self.vp_qp.drawLine(QPointF(*y_axis_start), QPointF(*y_axis_end))
        if self.show_labels:
            font = QFont()
            font.setPixelSize(12)
            self.vp_qp.drawText(QPointF(x_axis_end[0] + 10, x_axis_end[1]),
                                'stage x-axis')
            self.vp_qp.drawText(QPointF(y_axis_end[0] + 10, y_axis_end[1] + 10),
                                'stage y-axis')

    def _vp_set_measure_point(self, px, py):
        """Convert pixel coordinates where mouse was clicked to SEM coordinates
        in Viewport for starting or end point of measurement."""
        if self.measure_p1[0] is None or self.measure_complete:
            self.measure_p1 = self.cs.convert_mouse_to_v((px, py))
            self.measure_complete = False
            self.measure_p2 = (None, None)
        else:
            self.measure_p2 = self.cs.convert_mouse_to_v((px, py))
        self.vp_draw()

    def _vp_draw_zoom_delay(self):
        """Redraw the viewport without suppressing labels/previews after at
        least 0.3 seconds have passed since last mouse/slider zoom action."""
        finish_trigger = utils.Trigger()
        finish_trigger.signal.connect(self.vp_draw)
        current_time = self.time_of_last_zoom_action
        while current_time - self.time_of_last_zoom_action < 0.3:
            sleep(0.1)
            current_time += 0.1
        self.zooming_in_progress = False
        finish_trigger.signal.emit()

    def vp_adjust_zoom_slider(self):
        """Adjust the position of the viewport sliders according to the current
        viewport scaling."""
        self.horizontalSlider_VP.blockSignals(True)
        self.horizontalSlider_VP.setValue(
            int(log(self.cs.vp_scale / self.VP_SCALING[0], self.VP_SCALING[1])))
        self.horizontalSlider_VP.blockSignals(False)

    def _vp_adjust_scale_from_slider(self):
        """Adjust the viewport scale according to the value currently set with
        the viewport slider. Recalculate the scaling factor and redraw the
        canvas."""
        self.time_of_last_zoom_action = time()
        if not self.zooming_in_progress:
            # Start thread to ensure viewport is drawn with labels and previews
            # after zooming completed.
            self.zooming_in_progress = True
            utils.run_log_thread(self._vp_draw_zoom_delay)
        # Recalculate scaling factor.
        self.cs.vp_scale = (
                self.VP_SCALING[0]
                * (self.VP_SCALING[1]) ** self.horizontalSlider_VP.value())
        # Redraw viewport with labels and previews suppressed.
        self.vp_draw(suppress_labels=True, suppress_previews=True)

    def _vp_mouse_zoom(self, px, py, factor):
        """Zoom with factor after user double-clicks at position px, py."""
        self.time_of_last_zoom_action = time()
        if not self.zooming_in_progress and not self.doubleclick_registered:
            # Start thread to ensure viewport is drawn with labels and previews
            # after zooming completed.
            self.zooming_in_progress = True
            utils.run_log_thread(self._vp_draw_zoom_delay)
        # Recalculate scaling factor.
        old_vp_scale = self.cs.vp_scale
        self.cs.vp_scale = np.clip(
            factor * old_vp_scale,
            self.VP_SCALING[0],
            self.VP_SCALING[0] * (self.VP_SCALING[1]) ** 99)  # 99 is max slider value
        self.vp_adjust_zoom_slider()
        # Recentre, so that mouse position is preserved.
        current_centre_dx, current_centre_dy = self.cs.vp_centre_dx_dy
        x_shift = px - self.cs.vp_width // 2
        y_shift = py - self.cs.vp_height // 2
        scale_diff = 1 / self.cs.vp_scale - 1 / old_vp_scale
        new_centre_dx = current_centre_dx - x_shift * scale_diff
        new_centre_dy = current_centre_dy - y_shift * scale_diff
        new_centre_dx = np.clip(
            new_centre_dx, self.VC_MIN_X, self.VC_MAX_X)
        new_centre_dy = np.clip(
            new_centre_dy, self.VC_MIN_Y, self.VC_MAX_Y)
        # Set new vp_centre coordinates.
        self.cs.vp_centre_dx_dy = [new_centre_dx, new_centre_dy]
        # Redraw viewport.
        if self.doubleclick_registered:
            # Doubleclick is (usually) a single event: draw with labels/previews
            self.vp_draw()
        else:
            # Continuous zoom with the mouse wheel: Suppress previews
            # for smoother redrawing.
            self.vp_draw(suppress_labels=False, suppress_previews=True)

    def _vp_shift_fov(self, shift_vector):
        """Shift the Viewport's field of view (FOV) by shift_vector."""
        dx, dy = shift_vector
        current_centre_dx, current_centre_dy = self.cs.vp_centre_dx_dy
        new_centre_dx = current_centre_dx + dx / self.cs.vp_scale
        new_centre_dy = current_centre_dy + dy / self.cs.vp_scale
        new_centre_dx = np.clip(
            new_centre_dx, self.VC_MIN_X, self.VC_MAX_X)
        new_centre_dy = np.clip(
            new_centre_dy, self.VC_MIN_Y, self.VC_MAX_Y)
        self.cs.vp_centre_dx_dy = [new_centre_dx, new_centre_dy]
        self.vp_draw()

    def _vp_reposition_ov(self, shift_vector):
        """Shift the OV selected by the mouse click (self.selected_ov) by
        shift_vector."""
        dx, dy = shift_vector
        old_ov_dx, old_ov_dy = self.ovm[self.selected_ov].centre_dx_dy
        # Move OV along shift vector.
        new_ov_dx = old_ov_dx + dx / self.cs.vp_scale
        new_ov_dy = old_ov_dy + dy / self.cs.vp_scale
        # Set new OV centre and redraw.
        self.ovm[self.selected_ov].centre_sx_sy = self.cs.convert_d_to_s(
            (new_ov_dx, new_ov_dy))
        self.vp_draw()

    def _vp_reposition_template(self, shift_vector):
        """Shift the template by the mouse click (self.selected_ov) by
        shift_vector."""
        dx, dy = shift_vector
        old_ov_dx, old_ov_dy = self.tm.template.origin_dx_dy
        # Move OV along shift vector.
        new_ov_dx = old_ov_dx + dx / self.cs.vp_scale
        new_ov_dy = old_ov_dy + dy / self.cs.vp_scale
        # Set new OV centre and redraw.

        self.tm.template.origin_sx_sy = self.cs.convert_d_to_s(
            (new_ov_dx, new_ov_dy))
        self.vp_draw()

    def _vp_place_grids_template_matching(self):
        """Find candidate locations and place grids in VP using template matching."""
        self.tm.place_grids_template_matching(self.gm)
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def _vp_reposition_imported_img(self, shift_vector):
        """Shift the imported image selected by the mouse click
        (self.selected_imported) by shift_vector."""
        dx, dy = shift_vector
        old_origin_dx, old_origin_dy = self.cs.convert_s_to_d(
            self.imported[self.selected_imported].centre_sx_sy)
        new_origin_dx = old_origin_dx + dx / self.cs.vp_scale
        new_origin_dy = old_origin_dy + dy / self.cs.vp_scale
        # Set new centre coordinates.
        self.imported[self.selected_imported].centre_sx_sy = (
            self.cs.convert_d_to_s((new_origin_dx, new_origin_dy)))
        self.vp_draw()

    def _vp_reposition_grid(self, shift_vector):
        """Shift the grid selected by the mouse click (self.selected_grid)
        by shift_vector."""
        dx, dy = shift_vector
        old_grid_origin_dx, old_grid_origin_dy = (
            self.gm[self.selected_grid].origin_dx_dy)
        new_grid_origin_dx = old_grid_origin_dx + dx / self.cs.vp_scale
        new_grid_origin_dy = old_grid_origin_dy + dy / self.cs.vp_scale
        # Set new grid origin and redraw.
        self.gm[self.selected_grid].origin_sx_sy = (
            self.cs.convert_d_to_s((new_grid_origin_dx, new_grid_origin_dy)))
        self.vp_draw()

    def _vp_grid_tile_mouse_selection(self, px, py):
        """Get the grid index and tile index at the position in the viewport
        where user has clicked.
        """
        if self.vp_current_grid == -2:  # grids are hidden
            grid_range = []
            selected_grid, selected_tile = None, None
        elif self.vp_current_grid == -1:  # all grids visible
            grid_range = reversed(range(self.gm.number_grids))
            selected_grid, selected_tile = None, None
        elif self.vp_current_grid >= 0:  # one selected grid visible
            grid_range = range(self.vp_current_grid, self.vp_current_grid + 1)
            selected_grid, selected_tile = self.vp_current_grid, None

        # Go through all visible grids to check for overlap with mouse click
        # position. Check grids with a higher grid index first.
        for grid_index in grid_range:
            # Calculate origin of the grid with respect to viewport canvas
            dx, dy = self.gm[grid_index].origin_dx_dy
            grid_origin_vx, grid_origin_vy = self.cs.convert_d_to_v((dx, dy))
            pixel_size = self.gm[grid_index].pixel_size
            # Calculate top-left corner of unrotated grid
            dx -= self.gm[grid_index].tile_width_d() / 2
            dy -= self.gm[grid_index].tile_height_d() / 2
            grid_topleft_vx, grid_topleft_vy = self.cs.convert_d_to_v((dx, dy))
            cols = self.gm[grid_index].number_cols()
            rows = self.gm[grid_index].number_rows()
            overlap = self.gm[grid_index].overlap
            tile_width_p = self.gm[grid_index].tile_width_p()
            tile_height_p = self.gm[grid_index].tile_height_p()
            # Tile width in viewport pixels taking overlap into account
            tile_width_v = ((tile_width_p - overlap) * pixel_size
                            / 1000 * self.cs.vp_scale)
            tile_height_v = ((tile_height_p - overlap) * pixel_size
                             / 1000 * self.cs.vp_scale)
            overlap_v = overlap * pixel_size / 1000 * self.cs.vp_scale
            # Row shift in viewport pixels
            shift_v = (self.gm[grid_index].row_shift * pixel_size
                       / 1000 * self.cs.vp_scale)
            # Mouse click position relative to top-left corner of grid
            x, y = px - grid_topleft_vx, py - grid_topleft_vy
            theta = radians(self.gm[grid_index].rotation)
            if theta != 0:
                # Rotate the mouse click coordinates if grid is rotated.
                # Use grid origin as pivot.
                x, y = px - grid_origin_vx, py - grid_origin_vy
                # Inverse rotation for (x, y).
                x_rot = x * cos(-theta) - y * sin(-theta)
                y_rot = x * sin(-theta) + y * cos(-theta)
                x, y = x_rot, y_rot
                # Correction for top-left corner.
                x += tile_width_p / 2 * pixel_size / 1000 * self.cs.vp_scale
                y += tile_height_p / 2 * pixel_size / 1000 * self.cs.vp_scale

            if self.gm[grid_index].is_deferred_polygon_roi():
                continue

            if not 'multisem' in self.sem.device_name.lower():
                # Check if mouse click position is within current grid's tile area
                # if the current grid is active
                if all([
                    self.gm[grid_index].active,
                    # we can include + shift_v here and handle
                    # the following 2 peculiar cases later:
                    # 1. click at the left of a shifted row
                    # 2. click at the right of a non-shifted row
                    0 <= x <= cols * tile_width_v + overlap_v + shift_v, # = grid_width + shift_v
                    0 <= y <= rows * tile_height_v + overlap_v]):

                    # with tile_width_p = 10; tile_width_v = 9; overlap = 1
                    # Intervals of x coordinates for each column
                    # column 1: [0,10]
                    # column 2: [9,19]
                    # column 3: [18,28]
                    tile_intervals_y = [
                        [r * tile_height_v,
                        (r+1) * tile_height_v + overlap_v]
                        for r in range(rows)]

                    r = [interval[0] <= y <= interval[1]
                        for interval in tile_intervals_y].index(True)

                    if shift_v!=0 and r%2==1:
                        tile_intervals_x = [
                            [c * tile_width_v + shift_v,
                            (c+1) * tile_width_v + overlap_v + shift_v]
                            for c in range(cols)]
                    else:
                        tile_intervals_x = [
                            [c * tile_width_v,
                            (c+1) * tile_width_v + overlap_v]
                            for c in range(cols)]

                    try:
                        c = [interval[0] <= x <= interval[1]
                            for interval in tile_intervals_x].index(True)
                    except ValueError:
                        # the click_x is outside of the intervals
                        # when click at the left of a shifted row
                        # or at the right of a non-shifted row
                        break

                    selected_tile = int(c + r * cols)
                    selected_grid = grid_index
                    break

            else: # Check if mouse click position is within current ROI.
                pass
                # polyroi_s = self.gm.magc_polyroi_points(grid_index)
                # if len(polyroi_s) > 2:
                    # polyroi_v = [
                        # self.cs.convert_d_to_v(point)
                        # for point in polyroi_s]
                    # if magc_utils.is_point_inside_polygon((px, py), polyroi_v):
                        # selected_grid = grid_index
                        # break

            # Also check whether grid label clicked. This selects only the grid
            # and not a specific tile.
            suppress_labels = ((self.gm.number_grids + self.ovm.number_ov) > 10
                               and self.cs.vp_scale < 1.0)

            if self.show_labels and (not suppress_labels):
                f = int(self.cs.vp_scale * 8)
                if f < 12:
                    f = 12
                # Active and inactive grids have different label widths
                if self.gm[grid_index].active:
                    width_factor = 5.3
                else:
                    width_factor = 10.5
                label_width = int(width_factor * f)
                label_height = int(4/3 * f)
                l_y = y + label_height
                if x >= 0 and l_y >= 0 and selected_grid is None:
                    if x < label_width and l_y < label_height:
                        selected_grid = grid_index
                        selected_tile = None
                        break

        return selected_grid, selected_tile

    def _vp_ov_mouse_selection(self, px, py):
        """Return the index of the OV at the position in the viewport
        where user has clicked."""
        if self.vp_current_ov == -2:
            selected_ov = None
        elif self.vp_current_ov == -1:
            selected_ov = None
            for ov_index in reversed(range(self.ovm.number_ov)):
                # Calculate origin of the overview with respect to mosaic viewer
                dx, dy = self.ovm[ov_index].centre_dx_dy
                dx -= self.ovm[ov_index].width_d() / 2
                dy -= self.ovm[ov_index].height_d() / 2
                pixel_offset_x, pixel_offset_y = self.cs.convert_d_to_v((dx, dy))
                p_width = self.ovm[ov_index].width_d() * self.cs.vp_scale
                p_height = self.ovm[ov_index].height_d() * self.cs.vp_scale
                x, y = px - pixel_offset_x, py - pixel_offset_y
                # Check if mouse click position is within OV area
                if x >= 0 and y >= 0:
                    if x < p_width and y < p_height:
                        selected_ov = ov_index
                        break
                    else:
                        selected_ov = None
                # Also check whether label clicked.
                f = int(self.cs.vp_scale * 8)
                if f < 12:
                    f = 12
                if self.ovm[ov_index].active:
                    width_factor = 3.6
                else:
                    width_factor = 9
                label_width = int(f * width_factor)
                label_height = int(4/3 * f)
                l_y = y + label_height
                if x >= 0 and l_y >= 0 and selected_ov is None:
                    if x < label_width and l_y < label_height:
                        selected_ov = ov_index
                        break
        elif self.vp_current_ov >= 0:
            selected_ov = self.vp_current_ov
        return selected_ov

    def _vp_imported_img_mouse_selection(self, px, py):
        """Return the index of the imported image at the position in the
        viewport where user has clicked."""
        for i in reversed(range(len(self.imported))):
            if not self._vp_imported_visible(i):
                continue
            # Calculate origin of the image with respect to the viewport.
            # Use width and height of the QPixmap (may be rotated and
            # therefore larger than original image).
            if self.imported[i].image is not None:
                dx, dy = self.cs.convert_s_to_d(
                    self.imported[i].centre_sx_sy)
                pixel_size = self.imported[i].pixel_size
                width_d = (self.imported[i].image.size().width()
                           * pixel_size / 1000)
                height_d = (self.imported[i].image.size().height()
                            * pixel_size / 1000)
                dx -= width_d / 2
                dy -= height_d / 2
                pixel_offset_x, pixel_offset_y = self.cs.convert_d_to_v(
                    (dx, dy))
                p_width = width_d * self.cs.vp_scale
                p_height = height_d * self.cs.vp_scale
                x, y = px - pixel_offset_x, py - pixel_offset_y
                if x >= 0 and y >= 0:
                    if x < p_width and y < p_height:
                        return i
        return None

    def _vp_template_mouse_selection(self, px, py):
        if self.tm.template.origin_sx_sy is None:  # no template exists
            return False
        # Calculate origin of the grid with respect to viewport canvas
        selected_template = False
        template = self.tm.template
        dx, dy = template.origin_dx_dy
        grid_origin_vx, grid_origin_vy = self.cs.convert_d_to_v((dx, dy))
        pixel_size = template.pixel_size
        # Calculate top-left corner of unrotated grid
        dx -= template.tile_width_d() / 2
        dy -= template.tile_height_d() / 2
        grid_topleft_vx, grid_topleft_vy = self.cs.convert_d_to_v((dx, dy))
        cols = template.number_cols()
        rows = template.number_rows()
        overlap = template.overlap
        tile_width_p = template.tile_width_p()
        tile_height_p = template.tile_height_p()
        # Tile width in viewport pixels taking overlap into account
        tile_width_v = ((tile_width_p - overlap) * pixel_size
                        / 1000 * self.cs.vp_scale)
        tile_height_v = ((tile_height_p - overlap) * pixel_size
                         / 1000 * self.cs.vp_scale)
        # Row shift in viewport pixels
        shift_v = (template.row_shift * pixel_size
                   / 1000 * self.cs.vp_scale)
        # Mouse click position relative to top-left corner of grid
        x, y = px - grid_topleft_vx, py - grid_topleft_vy
        theta = radians(template.rotation)
        if theta != 0:
            # Rotate the mouse click coordinates if grid is rotated.
            # Use grid origin as pivot.
            x, y = px - grid_origin_vx, py - grid_origin_vy
            # Inverse rotation for (x, y).
            x_rot = x * cos(-theta) - y * sin(-theta)
            y_rot = x * sin(-theta) + y * cos(-theta)
            x, y = x_rot, y_rot
            # Correction for top-left corner.
            x += tile_width_p / 2 * pixel_size / 1000 * self.cs.vp_scale
            y += tile_height_p / 2 * pixel_size / 1000 * self.cs.vp_scale
        # Check if mouse click position is within current grid's tile area
        # if the current grid is active
        if template.active and x >= 0 and y >= 0:
            j = y // tile_height_v
            if j % 2 == 0:
                i = x // tile_width_v
            elif x > shift_v:
                # Subtract shift for odd rows.
                i = (x - shift_v) // tile_width_v
            else:
                i = cols
            if (i < cols) and (j < rows):
                selected_template = True

        # Also check whether template label clicked. This selects only the grid
        # and not a specific tile.
        f = int(self.cs.vp_scale * 8)
        if f < 12:
            f = 12
        # Active and inactive grids have different label widths
        if template.active:
            width_factor = 5.3
        else:
            width_factor = 10.5
        label_width = int(width_factor * f)
        label_height = int(4/3 * f)
        l_y = y + label_height
        if x >= 0 and l_y >= 0 and not selected_template:
            if x < label_width and l_y < label_height:
                selected_template = True

        return selected_template

    def vp_activate_all_tiles(self):
        """Activate all tiles in the selected grid (mouse selection)."""
        if self.selected_grid is not None:
            grid_label = self.gm.get_grid_label(self.selected_grid)
            user_reply = QMessageBox.question(
                self, 'Set all tiles in grid to "active"',
                f'This will activate all tiles in {grid_label}. '
                f'Proceed?',
                QMessageBox.Ok | QMessageBox.Cancel)
            if user_reply == QMessageBox.Ok:
                self.gm[self.selected_grid].activate_all_tiles()
                if self.autofocus.tracking_mode == 1:
                    self.gm.make_all_active_tiles_autofocus_ref_tiles()
                self._add_to_main_log(f'CTRL: All tiles in {grid_label} activated.')
                self.vp_update_after_active_tile_selection()

    def vp_deactivate_all_tiles(self):
        """Deactivate all tiles in the selected grid (mouse selection)."""
        if self.selected_grid is not None:
            grid_label = self.gm.get_grid_label(self.selected_grid)
            user_reply = QMessageBox.question(
                self, 'Deactivating all tiles in grid',
                f'This will deactivate all tiles in {grid_label}. '
                f'Proceed?',
                QMessageBox.Ok | QMessageBox.Cancel)
            if user_reply == QMessageBox.Ok:
                self.gm[self.selected_grid].deactivate_all_tiles()
                if self.autofocus.tracking_mode == 1:
                    self.gm.delete_all_autofocus_ref_tiles()
                self._add_to_main_log(f'CTRL: All tiles in grid {grid_label} deactivated.')
                self.vp_update_after_active_tile_selection()

    def _vp_open_grid_settings(self):
        self.main_controls_trigger.transmit(
            'OPEN GRID SETTINGS', self.selected_grid)

    def _vp_move_grid_to_current_stage_position(self):
        """Move the selected grid to the current stage position (MagC)."""
        if self.gm[self.selected_grid].locked:
            QMessageBox.information(
                self, 'Grid locked',
                f'{self.gm.get_grid_label(self.selected_grid)} is locked.\n'
                'Unlock it first to change location.',
                QMessageBox.Ok)
            return
        x, y = self.stage.get_xy()
        self.gm[self.selected_grid].centre_sx_sy = [x, y]
        self.gm[self.selected_grid].update_tile_positions()
        self.gm.array_write()
        self.vp_draw()

    def _vp_toggle_tile_autofocus(self):
        """Toggle the autofocus reference status of the currently selected
        tile."""
        if self.selected_grid is not None and self.selected_tile is not None:
            self.gm[self.selected_grid][
                    self.selected_tile].autofocus_active ^= True
            self.vp_draw()

    def _vp_toggle_wd_gradient_ref_tile(self):
        """Toggle the wd gradient reference status of the currently selected
        tile."""
        if self.selected_grid is not None and self.selected_tile is not None:
            ref_tiles = self.gm[self.selected_grid].wd_gradient_ref_tiles
            if self.selected_tile in ref_tiles:
                ref_tiles[ref_tiles.index(self.selected_tile)] = -1
            else:
                # Let user choose the intended relative position of the tile:
                dialog = FocusGradientTileSelectionDlg(ref_tiles)
                if dialog.exec():
                    if dialog.selected is not None:
                        ref_tiles[dialog.selected] = self.selected_tile
            self.gm[self.selected_grid].wd_gradient_ref_tiles = ref_tiles
            self.main_controls_trigger.transmit('UPDATE FT TILE SELECTOR')
            self.vp_draw()

    def _vp_toggle_measure(self):
        self.vp_measure_active = not self.vp_measure_active
        if self.vp_measure_active:
            self.sv_measure_active = False
        self.measure_p1 = (None, None)
        self.measure_p2 = (None, None)
        self.measure_complete = False
        self._update_measure_buttons()
        self.vp_draw()

    def vp_toggle_help_panel(self):
        self.help_panel_visible ^= True
        if self.help_panel_visible:
            self.pushButton_helpViewport.setStyleSheet(
                'QPushButton {color: #FF6A22;}')
            self.pushButton_helpSliceViewer.setStyleSheet(
                'QPushButton {color: #FF6A22;}')
        else:
            self.pushButton_helpViewport.setStyleSheet(
                'QPushButton {color: #000000;}')
            self.pushButton_helpSliceViewer.setStyleSheet(
                'QPushButton {color: #000000;}')
        self.vp_draw()
        self.sv_draw()

    def _vp_manual_stage_move(self):
        utils.log_info('CTRL', 'Performing user-requested stage move.')
        self.main_controls_trigger.transmit('STATUS BUSY STAGE MOVE')
        self.main_controls_trigger.transmit('RESTRICT GUI')
        self.restrict_gui(True)
        QApplication.processEvents()
        utils.run_log_thread(acq_func.manual_stage_move,
                             self.stage,
                             self.selected_stage_pos,
                             self.viewport_trigger)

    def _vp_manual_stage_move_success(self, success):
        # Show new stage position in Main Controls GUI
        self.main_controls_trigger.transmit('UPDATE XY')
        if success:
            utils.log_info('CTRL', 'User-requested stage move completed.')
        else:
            utils.log_error('CTRL', 'ERROR ocurred during manual stage move.')
            QMessageBox.warning(
                self, 'Error during stage move',
                'An error occurred during the requested stage move: '
                'The target position could not be reached after two attempts. '
                'Please check the status of your microtome or SEM stage.',
                QMessageBox.Ok)
        self.vp_draw()
        self.restrict_gui(False)
        self.main_controls_trigger.transmit('UNRESTRICT GUI')
        self.main_controls_trigger.transmit('STATUS IDLE')

    def _vp_start_ov_acquisition(self, selection):
        self._add_to_main_log(
            'CTRL: User-requested acquisition of OV image(s) started.')
        self.restrict_gui(True)
        self.main_controls_trigger.transmit('RESTRICT GUI')
        self.main_controls_trigger.transmit('STATUS BUSY OV')
        # Start OV acquisition thread
        utils.run_log_thread(acq_func.acquire_ov,
                             self.acq.base_dir, selection,
                             self.sem, self.stage, self.ovm, self.img_inspector,
                             self.main_controls_trigger, self.viewport_trigger)

    def vp_acquire_specific_overview(self, ov_index):
        if ov_index is None or ov_index < 0 or ov_index >= self.ovm.number_ov:
            QMessageBox.information(
                self, 'Acquire overview',
                'Please select a valid overview first.',
                QMessageBox.Ok)
            return
        self.vp_current_ov = ov_index
        self.vp_update_ov_selector()
        self._vp_start_ov_acquisition(ov_index)

    def vp_acquire_overview(self):
        """Acquire one selected or all overview images."""
        if self.vp_current_ov <= -2:
            QMessageBox.information(
                self, 'Acquisition of overview image(s)',
                'Please select "All OVs" or a single OV from the '
                'pull-down menu.',
                QMessageBox.Ok)
            return
        user_reply = None
        if (self.vp_current_ov == -1) and (self.ovm.number_ov > 1):
            user_reply = QMessageBox.question(
                self, 'Acquisition of all overview images',
                'This will acquire all active overview images.\n\n'
                'Do you wish to proceed?',
                QMessageBox.Ok | QMessageBox.Cancel)
        if (user_reply == QMessageBox.Ok or self.vp_current_ov >= 0
                or (self.ovm.number_ov == 1 and self.vp_current_ov == -1)):
            self._vp_start_ov_acquisition(self.vp_current_ov)

    def _vp_overview_acq_success(self, success):
        if success:
            self._add_to_main_log(
                'CTRL: User-requested acquisition of overview(s) completed.')
        else:
            self._add_to_main_log(
                'CTRL: ERROR ocurred during acquisition of overview(s).')
            QMessageBox.warning(
                self, 'Error during overview acquisition',
                'An error occurred during the acquisition of the overview(s) '
                'at the current location(s). Please check the log for more '
                'information. If the stage failed to move to the target OV '
                'position, the most likely causes are incorrect XY stage '
                'limits or incorrect motors speeds.', QMessageBox.Ok)
        self.main_controls_trigger.transmit('UNRESTRICT GUI')
        self.restrict_gui(False)
        self.main_controls_trigger.transmit('STATUS IDLE')
        self._refresh_ov_queue()
        self._refresh_acquisition_manager()

    def _vp_open_stub_overview_dlg(self):
        centre_sx_sy = self.stub_ov_centre
        if centre_sx_sy[0] is None:
            # Use the last known position
            centre_sx_sy = self.ovm['stub'].centre_sx_sy
        if self.stub_ov_dialog is not None and self.stub_ov_dialog.isVisible():
            self.stub_ov_dialog.raise_()
            self.stub_ov_dialog.activateWindow()
            return
        self.stub_ov_dialog = StubOVDlg(
            centre_sx_sy,
            self.sem,
            self.stage,
            self.ovm,
            self.imported,
            self.acq,
            self.img_inspector,
            self.viewport_trigger,
            self.imaging_condition_store)
        self.stub_ov_dialog.destroyed.connect(
            lambda *_: setattr(self, 'stub_ov_dialog', None))
        self.stub_ov_dialog.show()
        self.stub_ov_dialog.raise_()
        self.stub_ov_dialog.activateWindow()

    def _vp_archive_previous_stub(self, previous_state):
        if previous_state is None:
            return
        previous_path = previous_state.get('vp_file_path', '')
        if not previous_path or not os.path.isfile(previous_path):
            return
        source_kind = previous_state.get('source_kind', 'imported')
        if stub_workflow.has_matching_stub_archive(
                self.imported, previous_path, source_kind):
            return
        centre_sx_sy = previous_state.get('centre_sx_sy')
        if centre_sx_sy is None:
            return
        image_size_px = previous_state.get('image_size_px')
        pixel_size = previous_state.get('pixel_size')
        if image_size_px is None or pixel_size is None:
            return
        self.imported.add_image(
            previous_path,
            stub_workflow.stub_archive_description(previous_path, source_kind),
            centre_sx_sy,
            0,
            False,
            image_size_px,
            pixel_size,
            True,
            0,
            False,
            source_kind)

    def _vp_finish_stub_overview(self, outcome, mode_key=None,
                                 previous_state=None):
        self.acq.acq_in_progress = False
        self.acq.acq_run_mode = None
        self.restrict_gui(False)
        self.main_controls_trigger.transmit('UNRESTRICT GUI')
        if outcome == 'success':
            self._add_to_main_log(
                'CTRL: Acquisition of stub overview image completed.')
            self._vp_archive_previous_stub(previous_state)
            self.vp_show_new_stub_overview()
            self.stub_ov_centre = [None, None]
            if self.acq.use_mirror_drive and mode_key in ('stub', 'stub_lm'):
                stub_path = self.ovm[mode_key].vp_file_path
                if stub_path:
                    mirror_path = os.path.join(
                        self.acq.mirror_drive,
                        self.acq.base_dir[2:], 'overviews', 'stub')
                    if not os.path.exists(mirror_path):
                        try:
                            os.makedirs(mirror_path)
                        except Exception as e:
                            self._add_to_main_log(
                                'CTRL: Creating directory on mirror drive failed: '
                                + str(e))
                    try:
                        shutil.copy(stub_path, mirror_path)
                    except Exception as e:
                        self._add_to_main_log(
                            'CTRL: Copying stub overview image to mirror drive '
                            'failed: ' + str(e))
        elif outcome == 'failure':
            self._add_to_main_log(
                'CTRL: ERROR ocurred during stub overview acquisition.')
        elif outcome == 'aborted':
            self._add_to_main_log(
                'CTRL: Stub overview acquisition aborted by user.')
        self.main_controls_trigger.transmit('STATUS IDLE')
        self.vp_draw()

    def _vp_open_change_grid_rotation_dlg(self):
        if self.selected_template:
            dialog = TemplateRotationDlg(self.tm, self.viewport_trigger)
        else:
            dialog = GridRotationDlg(self.selected_grid, self.gm,
                                     self.viewport_trigger, self.sem.magc_mode)
        if dialog.exec():
            if self.ovm.use_auto_debris_area:
                self.ovm.update_all_debris_detections_areas(self.gm)
                self.vp_draw()

    def vp_open_import_image_dlg(self, start_path=None, on_success_function=None):
        dialog = ImportImageDlg(self.imported, self.viewport_trigger, self.stage, start_path=start_path)
        if dialog.exec():
            if on_success_function:
                on_success_function()
            self.vp_draw()

    def _vp_open_modify_images_dlg(self):
        dialog = ModifyImagesDlg(self.imported, self.gm, self.stage, self.viewport_trigger)
        dialog.exec()

    def vp_show_new_stub_overview(self):
        self.checkBox_showStubOV.setChecked(True)
        self.show_stub_ov = True
        self.vp_draw()

    def vp_show_overview_for_user_inspection(self, ov_index):
        """Show the overview image with ov_index in the centre of the Viewport
        with no grids, tile previews or other objects obscuring it.
        """
        # Switch to Viewport tab
        self.tabWidget.setCurrentIndex(0)
        # Preserve previous display settings
        vp_current_ov_prev = self.vp_current_ov
        vp_current_grid_prev = self.vp_current_grid
        vp_centre_dx_dy_prev = self.cs.vp_centre_dx_dy
        vp_scale_prev = self.cs.vp_scale
        # Show ov_index only and hide the grids
        self.vp_current_ov = ov_index
        self.vp_current_grid = -2
        # Position the viewing window and adjust the scale to show the full OV
        self.cs.vp_centre_dx_dy = self.ovm[ov_index].centre_dx_dy
        self.cs.vp_scale = (self.cs.vp_width - 100) / self.ovm[ov_index].width_d()
        self.vp_draw(suppress_labels=False, suppress_previews=True)
        # Revert to previous settings
        self.vp_current_ov = vp_current_ov_prev
        self.vp_current_grid = vp_current_grid_prev
        self.cs.vp_centre_dx_dy = vp_centre_dx_dy_prev
        self.cs.vp_scale = vp_scale_prev

    # ---------------------- Array methods in Viewport --------------------------

    def array_vp_propagate_grid_to_selected_sections(self):
        self.gm.array_propagate_source_grid_to_target_grid(
            self.selected_grid,
            self.gm.array_data.selected_sections,
            self.imported.find_array_image())
        self.gm.array_write()
        self.vp_draw()
        self.main_controls_trigger.transmit('SHOW CURRENT SETTINGS') # update statistics in GUI
        grid_label = self.gm.get_grid_label(self.selected_grid)
        utils.log_info(
            'Array-CTRL',
            f'Properties of {grid_label}'
            ' have been propagated to the selected sections')

    def array_vp_propagate_grid_to_all_sections(self):
        self.gm.array_propagate_source_grid_to_target_grid(
            self.selected_grid,
            range(self.gm.number_grids),
            self.imported.find_array_image())

        self.gm.array_write()

        self.vp_draw()
        self.main_controls_trigger.transmit('SHOW CURRENT SETTINGS') # update statistics in GUI
        grid_label = self.gm.get_grid_label(self.selected_grid)
        utils.log_info(
            'Array-CTRL',
            f'Properties of {grid_label}'
            ' have been propagated to all sections')

    def array_vp_revert_grid_to_file(self):
        self.gm.array_revert_grid(self.selected_grid, self.imported.find_array_image())
        self.gm.array_write()
        self.vp_draw()
        self.main_controls_trigger.transmit('SHOW CURRENT SETTINGS') # update statistics in GUI

    # -------------------- End of Array methods in Viewport ---------------------

    # ================= Below: Slice-by-Slice Viewer (sv) methods ==================

    def _sv_initialize(self):
        self.slice_view_images = []
        self.slice_view_index = 0    # slice_view_index: 0..max_slices
        self.max_slices = 10         # default 10, can be increased by user
        # sv_current_grid, sv_current_tile and sv_current_ov stored the
        # indices currently selected in the drop-down lists.
        self.sv_current_grid = int(self.cfg['viewport']['sv_current_grid'])
        self.sv_current_tile = int(self.cfg['viewport']['sv_current_tile'])
        self.sv_current_ov = int(self.cfg['viewport']['sv_current_ov'])
        # display options
        self.show_native_res = (
            self.cfg['viewport']['show_native_resolution'].lower() == 'true')
        self.show_saturated_pixels = (
            self.cfg['viewport']['show_saturated_pixels'].lower() == 'true')

        self.sv_measure_active = False
        self.sv_canvas = QPixmap(self.cs.vp_width, self.cs.vp_height)
        # Help panel:
        self.sv_help_panel_img = QPixmap('img/help-sliceviewer.png')
        self.sv_qp = QPainter()

        self.pushButton_reloadSV.clicked.connect(self.sv_load_slices)
        self.pushButton_measureSliceViewer.clicked.connect(
            self.sv_toggle_measure)
        self.pushButton_measureSliceViewer.setIcon(
            QIcon('img/measure.png'))
        self.pushButton_measureSliceViewer.setIconSize(QSize(16, 16))
        self.pushButton_measureSliceViewer.setToolTip(
            'Measure with right mouse clicks')
        self.pushButton_sliceBWD.clicked.connect(self.sv_slice_bwd)
        self.pushButton_sliceFWD.clicked.connect(self.sv_slice_fwd)

        self.horizontalSlider_SV.valueChanged.connect(
            self._sv_adjust_scale_from_slider)
        self._sv_adjust_zoom_slider()

        self.comboBox_gridSelectorSV.currentIndexChanged.connect(
            self.sv_change_grid_selection)
        self.sv_update_grid_selector()
        self.comboBox_tileSelectorSV.currentIndexChanged.connect(
            self.sv_change_tile_selection)
        self.sv_update_tile_selector()
        self.comboBox_OVSelectorSV.currentIndexChanged.connect(
            self.sv_change_ov_selection)
        self.sv_update_ov_selector()

        self.checkBox_setNativeRes.setChecked(self.show_native_res)
        self.checkBox_setNativeRes.stateChanged.connect(
            self.sv_toggle_show_native_resolution)
        if self.show_native_res:
            self.horizontalSlider_SV.setEnabled(False)
            self.sv_set_native_resolution()
        self.checkBox_showSaturated.setChecked(self.show_saturated_pixels)
        self.checkBox_showSaturated.stateChanged.connect(
            self.sv_toggle_show_saturated_pixels)

        self.lcdNumber_sliceIndicator.display(0)
        self.spinBox_maxSlices.setRange(1, 20)
        self.spinBox_maxSlices.setSingleStep(1)
        self.spinBox_maxSlices.setValue(self.max_slices)
        self.spinBox_maxSlices.valueChanged.connect(self.sv_update_max_slices)
        # Show empty slice viewer canvas with instructions.
        self.sv_canvas.fill(Qt.black)
        self.sv_qp.begin(self.sv_canvas)
        self.sv_qp.setPen(QColor(255, 255, 255))
        position_rect = QRect(150, 380, 700, 40)
        self.sv_qp.drawRect(position_rect)
        self.sv_qp.drawText(
            position_rect, Qt.AlignVCenter | Qt.AlignHCenter,
            'Select tile or overview from controls below and click "(Re)load" '
            'to display the images from the most recent slices.')
        self.sv_instructions_displayed = True
        self.sv_qp.end()
        self.QLabel_SliceViewerCanvas.setPixmap(self.sv_canvas)

    def sv_update_grid_selector(self):
        if self.sv_current_grid >= self.gm.number_grids:
            self.sv_current_grid = 0
        self.comboBox_gridSelectorSV.blockSignals(True)
        self.comboBox_gridSelectorSV.clear()
        self.comboBox_gridSelectorSV.addItems(self.gm.grid_selector_list())
        self.comboBox_gridSelectorSV.setCurrentIndex(self.sv_current_grid)
        self.comboBox_gridSelectorSV.blockSignals(False)

    def sv_update_tile_selector(self):
        self.comboBox_tileSelectorSV.blockSignals(True)
        self.comboBox_tileSelectorSV.clear()
        self.comboBox_tileSelectorSV.addItems(
            ['Select tile']
            + self.gm[self.sv_current_grid].tile_selector_list())
        if self.sv_current_tile >= self.gm[self.sv_current_grid].number_tiles:
            self.sv_current_tile = -1
        self.comboBox_tileSelectorSV.setCurrentIndex(self.sv_current_tile + 1)
        self.comboBox_tileSelectorSV.blockSignals(False)

    def sv_update_ov_selector(self):
        if self.sv_current_ov >= self.ovm.number_ov:
            self.sv_current_ov = -1
        self.comboBox_OVSelectorSV.blockSignals(True)
        self.comboBox_OVSelectorSV.clear()
        self.comboBox_OVSelectorSV.addItems(
            ['Select OV'] + self.ovm.ov_selector_list())
        self.comboBox_OVSelectorSV.setCurrentIndex(self.sv_current_ov + 1)
        self.comboBox_OVSelectorSV.blockSignals(False)

    def sv_slice_fwd(self):
        if self.slice_view_index < 0:
            self.slice_view_index += 1
            self.lcdNumber_sliceIndicator.display(self.slice_view_index)
            # For now, disable showing saturated pixels (too slow)
            self.sv_disable_saturated_pixels()
            self.sv_draw()

    def sv_slice_bwd(self):
        if (self.slice_view_index > (-1) * (self.max_slices-1)) and \
           ((-1) * self.slice_view_index < len(self.slice_view_images)-1):
            self.slice_view_index -= 1
            self.lcdNumber_sliceIndicator.display(self.slice_view_index)
            self.sv_disable_saturated_pixels()
            self.sv_draw()

    def sv_update_max_slices(self):
        self.max_slices = self.spinBox_maxSlices.value()

    def _sv_adjust_scale_from_slider(self):
        # Recalculate scale factor
        # This depends on whether OV or a tile is displayed.
        if self.sv_current_ov >= 0:
            self.cs.sv_scale_ov = (
                    constants.SV_SCALING_OV[0]
                    * constants.SV_SCALING_OV[1] ** self.horizontalSlider_SV.value())
        else:
            self.cs.sv_scale_tile = (
                    constants.SV_SCALING_TILE[0]
                    * constants.SV_SCALING_TILE[1] ** self.horizontalSlider_SV.value())
        self.sv_disable_saturated_pixels()
        self.sv_draw()

    def _sv_adjust_zoom_slider(self):
        self.horizontalSlider_SV.blockSignals(True)
        if self.sv_current_ov >= 0:
            self.horizontalSlider_SV.setValue(
                int(log(self.cs.sv_scale_ov / constants.SV_SCALING_OV[0],
                        constants.SV_SCALING_OV[1])))
        else:
            self.horizontalSlider_SV.setValue(
                int(log(self.cs.sv_scale_tile / constants.SV_SCALING_TILE[0],
                        constants.SV_SCALING_TILE[1])))
        self.horizontalSlider_SV.blockSignals(False)

    def _sv_mouse_zoom(self, px, py, factor):
        """Zoom in by specified factor and preserve the relative location of
        where user double-clicked."""
        if self.sv_current_ov >= 0:
            old_sv_scale_ov = self.cs.sv_scale_ov
            current_vx, current_vy = self.cs.sv_ov_vx_vy
            # Recalculate scaling factor.
            self.cs.sv_scale_ov = np.clip(
                factor * old_sv_scale_ov,
                constants.SV_SCALING_OV[0],
                constants.SV_SCALING_OV[0] * constants.SV_SCALING_OV[1] ** 99)
                # 99 is max slider value
            ratio = self.cs.sv_scale_ov / old_sv_scale_ov
            # Preserve mouse click position.
            new_vx = int(ratio * current_vx - (ratio - 1) * px)
            new_vy = int(ratio * current_vy - (ratio - 1) * py)
            self.cs.sv_ov_vx_vy = [new_vx, new_vy]
        elif self.sv_current_tile >= 0:
            old_sv_scale_tile = self.cs.sv_scale_tile
            current_vx, current_vy = self.cs.sv_tile_vx_vy
            self.cs.sv_scale_tile = np.clip(
                factor * old_sv_scale_tile,
                constants.SV_SCALING_TILE[0],
                constants.SV_SCALING_TILE[0] * constants.SV_SCALING_TILE[1] ** 99)
            ratio = self.cs.sv_scale_tile / old_sv_scale_tile
            # Preserve mouse click position.
            new_vx = int(ratio * current_vx - (ratio - 1) * px)
            new_vy = int(ratio * current_vy - (ratio - 1) * py)
            self.cs.sv_tile_vx_vy = [new_vx, new_vy]
        self._sv_adjust_zoom_slider()
        self.sv_draw()

    def sv_change_grid_selection(self):
        self.sv_current_grid = self.comboBox_gridSelectorSV.currentIndex()
        self.sv_update_tile_selector()

    def sv_change_tile_selection(self):
        self.sv_current_tile = self.comboBox_tileSelectorSV.currentIndex() - 1
        if self.sv_current_tile >= 0:
            self.slice_view_index = 0
            self.lcdNumber_sliceIndicator.display(0)
            self.sv_current_ov = -1
            self.comboBox_OVSelectorSV.blockSignals(True)
            self.comboBox_OVSelectorSV.setCurrentIndex(self.sv_current_ov + 1)
            self.comboBox_OVSelectorSV.blockSignals(False)
            self._sv_adjust_zoom_slider()
            self.sv_load_slices()
        else:
            self.slice_view_images = []
            self.slice_view_index = 0
            self.sv_draw()

    def sv_change_ov_selection(self):
        self.sv_current_ov = self.comboBox_OVSelectorSV.currentIndex() - 1
        if self.sv_current_ov >= 0:
            self.slice_view_index = 0
            self.lcdNumber_sliceIndicator.display(0)
            self.sv_current_tile = -1
            self.comboBox_tileSelectorSV.blockSignals(True)
            self.comboBox_tileSelectorSV.setCurrentIndex(
                self.sv_current_tile + 1)
            self.comboBox_tileSelectorSV.blockSignals(False)
            self._sv_adjust_zoom_slider()
            self.sv_load_slices()
        else:
            self.slice_view_images = []
            self.slice_view_index = 0
            self.sv_draw()

    def sv_load_selected(self):
        if self.gm.array_mode:
            roi_index = self.gm[self.selected_grid].roi_index
            template_grid_index = self.gm.find_grid_index(roi_index)
            if template_grid_index is not None:
                self.selected_grid = template_grid_index
        if self.selected_grid is not None and self.selected_tile is not None:
            self.sv_current_grid = self.selected_grid
            self.sv_current_tile = self.selected_tile
            self.comboBox_gridSelectorSV.blockSignals(True)
            self.comboBox_gridSelectorSV.setCurrentIndex(self.selected_grid)
            self.comboBox_gridSelectorSV.blockSignals(False)
            self.sv_update_tile_selector()
            self.comboBox_OVSelectorSV.blockSignals(True)
            self.comboBox_OVSelectorSV.setCurrentIndex(0)
            self.comboBox_OVSelectorSV.blockSignals(False)
            self.sv_current_ov = -1
        elif self.selected_ov is not None:
            self.sv_current_ov = self.selected_ov
            self.comboBox_OVSelectorSV.blockSignals(True)
            self.comboBox_OVSelectorSV.setCurrentIndex(self.sv_current_ov + 1)
            self.comboBox_OVSelectorSV.blockSignals(False)
            self.sv_current_tile = -1
            self.sv_update_tile_selector()
        self.tabWidget.setCurrentIndex(1)
        QApplication.processEvents()
        self.sv_load_slices()

    def sv_img_within_boundaries(self, vx, vy, w_px, h_px, resize_ratio):
        visible = not ((-vx >= w_px * resize_ratio - 80)
                       or (-vy >= h_px * resize_ratio - 80)
                       or (vx >= self.cs.vp_width - 80)
                       or (vy >= self.cs.vp_height - 80))
        return visible

    def sv_load_slices(self):
        if self.sv_current_grid is None and self.sv_current_ov is None:
            QMessageBox('No tile or overview selected for slice-by-slice '
                        'display.')
            return
        # Reading the tiff files from SmartSEM generates warnings. They
        # are suppressed in the code below.
        # First show a "waiting" info, since loading the images may take a
        # while.
        self.sv_qp.begin(self.sv_canvas)
        self.sv_qp.setBrush(QColor(0, 0, 0))
        if self.sv_instructions_displayed:
            # Erase initial explanatory message.
            position_rect = QRect(150, 380, 700, 40)
            self.sv_qp.setPen(QColor(0, 0, 0))
            self.sv_qp.drawRect(position_rect)
            self.sv_instructions_displayed = False

        self.sv_qp.setPen(QColor(255, 255, 255))
        position_rect = QRect(350, 380, 300, 40)
        self.sv_qp.drawRect(position_rect)
        self.sv_qp.drawText(position_rect, Qt.AlignVCenter | Qt.AlignHCenter,
                            'Loading slices...')
        self.sv_qp.end()
        self.QLabel_SliceViewerCanvas.setPixmap(self.sv_canvas)
        QApplication.processEvents()
        self.slice_view_images = []
        self.slice_view_index = 0
        self.lcdNumber_sliceIndicator.display(0)
        start_slice = self.acq.slice_counter

        if self.gm.array_mode:
            n = self.gm.array_data.get_nsections()
        else:
            n = self.max_slices

        for index in range(n):
            filename = None
            if self.gm.array_mode and self.sv_current_tile >= 0:
                grid = self.gm[self.sv_current_grid]
                filename = os.path.join(
                    self.acq.base_dir, utils.tile_relative_save_path(
                        self.acq.stack_name, self.sv_current_grid,
                        n - 1 - index, grid.roi_index,
                        self.sv_current_tile))
            elif self.sv_current_ov >= 0:
                filename = utils.ov_save_path(
                    self.acq.base_dir, self.acq.stack_name,
                    self.sv_current_ov, start_slice - index)
            elif self.sv_current_tile >= 0:
                grid = self.gm[self.sv_current_grid]
                filename = os.path.join(
                    self.acq.base_dir, utils.tile_relative_save_path(
                        self.acq.stack_name, self.sv_current_grid,
                        grid.array_index, grid.roi_index,
                        self.sv_current_tile, start_slice - index))
            if filename and os.path.isfile(filename):
                self.slice_view_images.append(utils.image_to_QPixmap(imread(filename)))
                #utils.suppress_console_warning()
        self.sv_set_native_resolution()
        self.sv_draw()

        if not self.slice_view_images:
            self.sv_qp.begin(self.sv_canvas)
            self.sv_qp.setPen(QColor(255, 255, 255))
            self.sv_qp.setBrush(QColor(0, 0, 0))
            position_rect = QRect(350, 380, 300, 40)
            self.sv_qp.drawRect(position_rect)
            self.sv_qp.drawText(position_rect,
                                Qt.AlignVCenter | Qt.AlignHCenter,
                                'No images found')
            self.sv_qp.end()
            self.QLabel_SliceViewerCanvas.setPixmap(self.sv_canvas)

    def sv_set_native_resolution(self):
        if self.sv_current_ov >= 0:
            previous_scaling_ov = self.cs.sv_scale_ov
            ov_pixel_size = self.ovm[self.sv_current_ov].pixel_size
            self.cs.sv_scale_ov = 1000 / ov_pixel_size
            ratio = self.cs.sv_scale_ov / previous_scaling_ov
            current_vx, current_vy = self.cs.sv_ov_vx_vy
            dx = self.cs.vp_width // 2 - current_vx
            dy = self.cs.vp_height // 2 - current_vy
            new_vx = int(current_vx - ratio * dx + dx)
            new_vy = int(current_vy - ratio * dy + dy)
        elif self.sv_current_tile >= 0:
            previous_scaling = self.cs.sv_scale_tile
            tile_pixel_size = self.gm[self.sv_current_grid].pixel_size
            self.cs.sv_scale_tile = self.cs.vp_width / tile_pixel_size
            ratio = self.cs.sv_scale_tile / previous_scaling
            current_vx, current_vy = self.cs.sv_tile_vx_vy
            dx = self.cs.vp_width // 2 - current_vx
            dy = self.cs.vp_height // 2 - current_vy
            new_vx = int(current_vx - ratio * dx + dx)
            new_vy = int(current_vy - ratio * dy + dy)
            # Todo:
            # Check if out of bounds.
            self.horizontalSlider_SV.setValue(
                int(log(self.cs.sv_scale_tile / constants.SV_SCALING_TILE[0],
                        constants.SV_SCALING_TILE[1])))
        self._sv_adjust_zoom_slider()
        self.sv_draw()

    def sv_toggle_show_native_resolution(self):
        if self.checkBox_setNativeRes.isChecked():
            self.show_native_res = True
            # Lock zoom slider.
            self.horizontalSlider_SV.setEnabled(False)
            self.sv_set_native_resolution()
        else:
            self.show_native_res = False
            self.horizontalSlider_SV.setEnabled(True)

    def sv_disable_native_resolution(self):
        if self.show_native_res:
            self.show_native_res = False
            self.checkBox_setNativeRes.setChecked(False)
            self.horizontalSlider_SV.setEnabled(True)

    def sv_toggle_show_saturated_pixels(self):
        self.show_saturated_pixels = self.checkBox_showSaturated.isChecked()
        self.sv_draw()

    def sv_disable_saturated_pixels(self):
        if self.show_saturated_pixels:
            self.show_saturated_pixels = False
            self.checkBox_showSaturated.setChecked(False)

    def sv_draw(self):
        # Empty black canvas for slice viewer
        self.sv_canvas.fill(Qt.black)
        self.sv_qp.begin(self.sv_canvas)
        if self.sv_current_ov >= 0:
            viewport_pixel_size = 1000 / self.cs.sv_scale_ov
            ov_pixel_size = self.ovm[self.sv_current_ov].pixel_size
            resize_ratio = ov_pixel_size / viewport_pixel_size
        else:
            viewport_pixel_size = 1000 / self.cs.sv_scale_tile
            tile_pixel_size = self.gm[self.sv_current_grid].pixel_size
            resize_ratio = tile_pixel_size / viewport_pixel_size

        if len(self.slice_view_images) > 0:
            if self.sv_current_ov >= 0:
                vx, vy = self.cs.sv_ov_vx_vy
            else:
                vx, vy = self.cs.sv_tile_vx_vy

            current_image = self.slice_view_images[-self.slice_view_index]

            w_px = current_image.size().width()
            h_px = current_image.size().height()

            visible, crop_area, cropped_vx, cropped_vy = self._vp_visible_area(
                vx, vy, w_px, h_px, resize_ratio)
            display_img = current_image.copy(crop_area)

            if visible:
                # Resize according to scale factor:
                current_width = display_img.size().width()
                display_img = display_img.scaledToWidth(
                    int(current_width * resize_ratio))

                # Show saturated pixels?
                if self.show_saturated_pixels:
                    width = display_img.size().width()
                    height = display_img.size().height()
                    img = display_img.toImage()
                    # Show black pixels as blue and white pixels as red.
                    black_pixels = [QColor(0, 0, 0).rgb(),
                                    QColor(1, 1, 1).rgb()]
                    white_pixels = [QColor(255, 255, 255).rgb(),
                                    QColor(254, 254, 254).rgb()]
                    blue_pixel = QColor(0, 0, 255).rgb()
                    red_pixel = QColor(255, 0, 0).rgb()
                    for x in range(width):
                        for y in range(height):
                            pixel_value = img.pixel(x, y)
                            if pixel_value in black_pixels:
                                img.setPixel(x, y, blue_pixel)
                            if pixel_value in white_pixels:
                                img.setPixel(x, y, red_pixel)
                    display_img = QPixmap(img)

                self.sv_qp.drawPixmap(QPointF(cropped_vx, cropped_vy), display_img)
        # Measuring tool:
        if self.sv_measure_active:
            self._draw_measure_labels(self.sv_qp)
        # Help panel:
        if self.help_panel_visible:
            self.sv_qp.drawPixmap(QPointF(self.cs.vp_width - 200,
                                  self.cs.vp_height - 325),
                                  self.sv_help_panel_img)

        self.sv_qp.end()
        self.QLabel_SliceViewerCanvas.setPixmap(self.sv_canvas)
        # Update scaling label
        if self.sv_current_ov >= 0:
            self.label_FOVSize_sliceViewer.setText(
                '{0:.2f} µm × '.format(self.cs.vp_width / self.cs.sv_scale_ov)
                + '{0:.2f} µm'.format(self.cs.vp_height / self.cs.sv_scale_ov))
        else:
            self.label_FOVSize_sliceViewer.setText(
                '{0:.2f} µm × '.format(self.cs.vp_width / self.cs.sv_scale_tile)
                + '{0:.2f} µm'.format(self.cs.vp_height / self.cs.sv_scale_tile))

    def _sv_shift_fov(self, shift_vector):
        dx, dy = shift_vector
        if self.sv_current_ov >= 0:
            vx, vy = self.cs.sv_ov_vx_vy
            width, height = self.ovm[self.sv_current_ov].frame_size
            viewport_pixel_size = 1000 / self.cs.sv_scale_ov
            ov_pixel_size = self.ovm[self.sv_current_ov].pixel_size
            resize_ratio = ov_pixel_size / viewport_pixel_size
            new_vx = vx - dx
            new_vy = vy - dy
            if self.sv_img_within_boundaries(new_vx, new_vy,
                                             width, height, resize_ratio):
                self.cs.sv_ov_vx_vy = [new_vx, new_vy]
        else:
            vx, vy = self.cs.sv_tile_vx_vy
            width, height = self.gm[self.sv_current_grid].frame_size
            viewport_pixel_size = 1000 / self.cs.sv_scale_tile
            tile_pixel_size = self.gm[self.sv_current_grid].pixel_size
            resize_ratio = tile_pixel_size / viewport_pixel_size
            new_vx = vx - dx
            new_vy = vy - dy
            if self.sv_img_within_boundaries(new_vx, new_vy,
                                             width, height, resize_ratio):
                self.cs.sv_tile_vx_vy = [new_vx, new_vy]
        self.sv_draw()

    def sv_toggle_measure(self):
        self.sv_measure_active = not self.sv_measure_active
        if self.sv_measure_active:
            self.vp_measure_active = False
        self.measure_p1 = (None, None)
        self.measure_p2 = (None, None)
        self.measure_complete = False
        self._update_measure_buttons()
        self.sv_draw()

    def _sv_set_measure_point(self, px, py):
        """Convert pixel coordinates where mouse was clicked to SEM coordinates
        relative to the origin of the image displayed in the Slice-by-Slice
        Viewer, for starting or end point of measurement."""
        if self.sv_current_ov >= 0:
            px -= self.cs.sv_ov_vx_vy[0]
            py -= self.cs.sv_ov_vx_vy[1]
            scale = self.cs.sv_scale_ov
        elif self.sv_current_tile >= 0:
            px -= self.cs.sv_tile_vx_vy[0]
            py -= self.cs.sv_tile_vx_vy[1]
            scale = self.cs.sv_scale_tile
        else:
            # Measuring tool cannot be used when no image displayed.
            return
        if self.measure_p1[0] is None or self.measure_complete:
            self.measure_p1 = px / scale, py / scale
            self.measure_complete = False
            self.measure_p2 = None, None
        else:
            self.measure_p2 = px / scale, py / scale
        self.sv_draw()

    def sv_reset_view(self):
        """Zoom out completely and centre current image."""
        if self.sv_current_ov >= 0:
            self.cs.sv_scale_ov = constants.SV_SCALING_OV[0]
            width, height = self.ovm[self.sv_current_ov].frame_size
            viewport_pixel_size = 1000 / self.cs.sv_scale_ov
            ov_pixel_size = self.ovm[self.sv_current_ov].pixel_size
            resize_ratio = ov_pixel_size / viewport_pixel_size
            new_vx = int(self.cs.vp_width // 2 - (width // 2) * resize_ratio)
            new_vy = int(self.cs.vp_height // 2 - (height // 2) * resize_ratio)
        elif self.sv_current_tile >= 0:
            self.cs.sv_scale_tile = constants.SV_SCALING_TILE[0]
            width, height = self.gm[self.sv_current_grid].frame_size
            viewport_pixel_size = 1000 / self.cs.sv_scale_tile
            tile_pixel_size = self.gm[self.sv_current_grid].pixel_size
            resize_ratio = tile_pixel_size / viewport_pixel_size
            new_vx = int(self.cs.vp_width // 2 - (width // 2) * resize_ratio)
            new_vy = int(self.cs.vp_height // 2 - (height // 2) * resize_ratio)
        # Disable native resolution
        self.sv_disable_native_resolution()
        self._sv_adjust_zoom_slider()
        self.sv_draw()

    def sv_show_context_menu(self, p):
        px, py = p.x() - constants.VP_MARGIN_X, p.y() - constants.VP_MARGIN_Y
        if px in range(self.cs.vp_width) and py in range(self.cs.vp_height):
            menu = QMenu()
            action1 = menu.addAction('Reset view for current image')
            action1.triggered.connect(self.sv_reset_view)
            menu.exec_(self.mapToGlobal(p))

    # ================ Below: Monitoring tab (m) functions =================

    def _m_initialize(self):
        # Currently selected grid/tile/OV in the drop-down lists
        self.m_current_grid = int(self.cfg['viewport']['m_current_grid'])
        self.m_current_tile = int(self.cfg['viewport']['m_current_tile'])
        self.m_current_ov = int(self.cfg['viewport']['m_current_ov'])
        self.m_from_stack = True

        self.histogram_canvas_template = QPixmap(400, 170)
        self.reslice_canvas_template = QPixmap(400, 560)
        self.plots_canvas_template = QPixmap(550, 560)
        self.m_tab_populated = False
        self.m_qp = QPainter()
        if self.cfg['sys']['simulation_mode'].lower() == 'true':
            self.radioButton_fromSEM.setEnabled(False)

        self.radioButton_fromStack.toggled.connect(self._m_source_update)
        self.pushButton_reloadM.clicked.connect(self.m_show_statistics)
        self.pushButton_showMotorStatusDlg.clicked.connect(
            self._m_open_motor_status_dlg)
        self.comboBox_gridSelectorM.currentIndexChanged.connect(
            self.m_change_grid_selection)
        self.m_update_grid_selector()
        self.comboBox_tileSelectorM.currentIndexChanged.connect(
            self.m_change_tile_selection)
        self.m_update_tile_selector()
        self.comboBox_OVSelectorM.currentIndexChanged.connect(
            self.m_change_ov_selection)
        self.m_update_ov_selector()

        # Empty histogram
        self.histogram_canvas_template.fill(QColor(255, 255, 255))
        self.m_qp.begin(self.histogram_canvas_template)
        self.m_qp.setPen(QColor(0, 0, 0))
        self.m_qp.drawRect(10, 9, 257, 151)

        self.m_qp.drawText(280, 30, 'Data source:')
        self.m_qp.drawText(280, 90, 'Mean: ')
        self.m_qp.drawText(280, 110, 'SD: ')
        self.m_qp.drawText(280, 130, 'Peak at: ')
        self.m_qp.drawText(280, 150, 'Peak count: ')
        self.m_qp.end()
        self.QLabel_histogramCanvas.setPixmap(self.histogram_canvas_template)

        # Empty reslice canvas:
        self.reslice_canvas_template.fill(QColor(0, 0, 0))
        self.m_qp.begin(self.reslice_canvas_template)
        pen = QPen(QColor(255, 255, 255))
        self.m_qp.setPen(pen)
        position_rect = QRect(50, 260, 300, 40)
        self.m_qp.drawRect(position_rect)
        self.m_qp.drawText(position_rect, Qt.AlignVCenter | Qt.AlignHCenter,
                           'Select image source from controls below.')
        pen.setWidth(2)
        self.m_qp.setPen(pen)
        # Two arrows to show x and z direction
        self.m_qp.drawLine(12, 513, 12, 543)
        self.m_qp.drawLine(12, 543,  9, 540)
        self.m_qp.drawLine(12, 543, 15, 540)
        self.m_qp.drawLine(12, 513, 42, 513)
        self.m_qp.drawLine(42, 513, 39, 510)
        self.m_qp.drawLine(42, 513, 39, 516)
        self.m_qp.drawText(10, 554, 'z')
        self.m_qp.drawText(48, 516, 'x')
        self.m_qp.end()
        self.QLabel_resliceCanvas.setPixmap(self.reslice_canvas_template)
        # Plots:
        self.m_selected_plot_slice = None
        # Empty plots canvas:
        self.plots_canvas_template.fill(QColor(255, 255, 255))
        self.m_qp.begin(self.plots_canvas_template)
        # Four plot areas, draw axes:
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(2)
        self.m_qp.setPen(pen)
        self.m_qp.drawLine(0, 0, 0, 120)
        self.m_qp.drawLine(0, 146, 0, 266)
        self.m_qp.drawLine(0, 292, 0, 412)
        self.m_qp.drawLine(0, 438, 0, 558)
        # Labels:
        self.m_qp.setPen(QColor(25, 25, 112))
        self.m_qp.drawText(500, 15, 'Mean')
        self.m_qp.drawText(500, 161, 'ΔMean')
        self.m_qp.setPen(QColor(139, 0, 0))
        self.m_qp.drawText(500, 307, 'SD')
        self.m_qp.drawText(500, 453, 'ΔSD')
        # Midlines, dashed:
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        self.m_qp.setPen(pen)
        self.m_qp.drawLine(0, 60, 520, 60)
        self.m_qp.drawLine(0, 206, 520, 206)
        self.m_qp.drawLine(0, 352, 520, 352)
        self.m_qp.drawLine(0, 498, 520, 498)
        self.m_qp.setPen(QColor(25, 25, 112))
        self.m_qp.drawText(523, 210, '0.00')
        self.m_qp.setPen(QColor(139, 0, 0))
        self.m_qp.drawText(523, 502, '0.00')
        self.m_qp.end()
        self.QLabel_plotCanvas.setPixmap(self.plots_canvas_template)

    def _m_source_update(self):
        self.m_from_stack = self.radioButton_fromStack.isChecked()
        # Choice of tile or OV is only enabled when using images from stack
        self.comboBox_gridSelectorM.setEnabled(self.m_from_stack)
        self.comboBox_tileSelectorM.setEnabled(self.m_from_stack)
        self.comboBox_OVSelectorM.setEnabled(self.m_from_stack)
        self.m_show_statistics()

    def m_update_grid_selector(self):
        if self.m_current_grid >= self.gm.number_grids:
            self.m_current_grid = 0
        self.comboBox_gridSelectorM.blockSignals(True)
        self.comboBox_gridSelectorM.clear()
        self.comboBox_gridSelectorM.addItems(self.gm.grid_selector_list())
        self.comboBox_gridSelectorM.setCurrentIndex(self.m_current_grid)
        self.comboBox_gridSelectorM.blockSignals(False)

    def m_update_tile_selector(self, current_tile=-1):
        self.m_current_tile = current_tile
        self.comboBox_tileSelectorM.blockSignals(True)
        self.comboBox_tileSelectorM.clear()
        self.comboBox_tileSelectorM.addItems(
            ['Select tile']
            + self.gm[self.m_current_grid].tile_selector_list())
        self.comboBox_tileSelectorM.setCurrentIndex(self.m_current_tile + 1)
        self.comboBox_tileSelectorM.blockSignals(False)

    def m_update_ov_selector(self):
        if self.m_current_ov > self.ovm.number_ov:
            self.m_current_ov = 0
        self.comboBox_OVSelectorM.blockSignals(True)
        self.comboBox_OVSelectorM.clear()
        self.comboBox_OVSelectorM.addItems(
            ['Select OV'] + self.ovm.ov_selector_list())
        self.comboBox_OVSelectorM.setCurrentIndex(self.m_current_ov + 1)
        self.comboBox_OVSelectorM.blockSignals(False)

    def m_change_grid_selection(self):
        self.m_current_grid = self.comboBox_gridSelectorM.currentIndex()
        self.m_update_tile_selector()

    def m_change_tile_selection(self):
        self.m_current_tile = self.comboBox_tileSelectorM.currentIndex() - 1
        if self.m_current_tile >= 0:
            self.m_current_ov = -1
        elif self.m_current_tile == -1: # no tile selected
            # Select OV 0 by default:
            self.m_current_ov = 0
        self.comboBox_OVSelectorM.blockSignals(True)
        self.comboBox_OVSelectorM.setCurrentIndex(self.m_current_ov + 1)
        self.comboBox_OVSelectorM.blockSignals(False)
        self.m_show_statistics()

    def m_change_ov_selection(self):
        self.m_current_ov = self.comboBox_OVSelectorM.currentIndex() - 1
        if self.m_current_ov >= 0:
            self.m_current_tile = -1
            self.comboBox_tileSelectorM.blockSignals(True)
            self.comboBox_tileSelectorM.setCurrentIndex(
                self.m_current_tile + 1)
            self.comboBox_tileSelectorM.blockSignals(False)
            self.m_show_statistics()

    def m_show_statistics(self):
        self.m_selected_plot_slice = None
        self.m_selected_slice_number = None
        if self.m_from_stack:
            self.m_tab_populated = True
            self.m_draw_reslice()
            self.m_draw_plots()
        self.m_draw_histogram()

    def m_reset_view(self):
        canvas = self.reslice_canvas_template.copy()
        self.m_qp.begin(canvas)
        self.m_qp.setBrush(QColor(0, 0, 0))
        self.m_qp.setPen(QColor(255, 255, 255))
        position_rect = QRect(50, 260, 300, 40)
        self.m_qp.drawRect(position_rect)
        self.m_qp.drawText(position_rect,
                           Qt.AlignVCenter | Qt.AlignHCenter,
                           'No reslice image available.')
        self.m_qp.end()
        self.QLabel_resliceCanvas.setPixmap(canvas)
        self.QLabel_plotCanvas.setPixmap(self.plots_canvas_template)
        self.QLabel_histogramCanvas.setPixmap(self.histogram_canvas_template)

    def m_load_selected(self):
        self.m_from_stack = True
        self.radioButton_fromStack.setChecked(True)
        if self.selected_grid is not None and self.selected_tile is not None:
            self.m_current_grid = self.selected_grid
            self.m_current_tile = self.selected_tile
            self.comboBox_gridSelectorM.blockSignals(True)
            self.comboBox_gridSelectorM.setCurrentIndex(self.m_current_grid)
            self.comboBox_gridSelectorM.blockSignals(False)
            self.m_update_tile_selector(self.m_current_tile)
            self.m_current_ov = -1
            self.comboBox_OVSelectorM.blockSignals(True)
            self.comboBox_OVSelectorM.setCurrentIndex(0)
            self.comboBox_OVSelectorM.blockSignals(False)

        elif self.selected_ov is not None:
            self.m_current_ov = self.selected_ov
            self.comboBox_OVSelectorM.blockSignals(True)
            self.comboBox_OVSelectorM.setCurrentIndex(self.m_current_ov + 1)
            self.comboBox_OVSelectorM.blockSignals(False)
            self.m_current_tile = -1
            self.comboBox_tileSelectorM.blockSignals(True)
            self.comboBox_tileSelectorM.setCurrentIndex(0)
            self.comboBox_tileSelectorM.blockSignals(False)
        else:
            self.m_reset_view()

        # Switch to Monitoring tab:
        self.tabWidget.setCurrentIndex(2)
        QApplication.processEvents()
        self.m_show_statistics()

    def m_draw_reslice(self):
        """Draw the reslice of the selected tile or OV."""
        filename = None
        if self.m_current_ov >= 0:
            filename = utils.ov_reslice_save_path(self.acq.base_dir, self.m_current_ov)
        elif self.m_current_tile >= 0:
            grid = self.gm[self.m_current_grid]
            filename = utils.tile_reslice_save_path(self.acq.base_dir, self.m_current_grid,
                                                    grid.array_index, grid.roi_index,
                                                    self.m_current_tile)
        canvas = self.reslice_canvas_template.copy()
        if filename is not None and os.path.isfile(filename):
            current_reslice = utils.image_to_QPixmap(imread(filename))
            self.m_qp.begin(canvas)
            self.m_qp.setPen(QColor(0, 0, 0))
            self.m_qp.setBrush(QColor(0, 0, 0))
            self.m_qp.drawRect(QRect(30, 260, 340, 40))
            h = current_reslice.height()
            if h > 500:
                # Crop it to last 500:
                rect = QRect(0, h-500, 400, 500)
                current_reslice = current_reslice.copy(rect)
                h = 500
            self.m_qp.drawPixmap(0, 0, current_reslice)
            # Draw red line on currently selected slice:
            if self.m_selected_slice_number is not None:
                most_recent_slice = int(self.acq.slice_counter)
                self.m_qp.setPen(QColor(255, 0, 0))
                slice_y = most_recent_slice - self.m_selected_slice_number
                self.m_qp.drawLine(0, h - slice_y,
                                   400, h - slice_y)

            self.m_qp.setPen(QColor(255, 255, 255))
            if self.m_current_ov >= 0:
                self.m_qp.drawText(260, 523, 'OV ' + str(self.m_current_ov))
            else:
                self.m_qp.drawText(260, 523,
                    'Tile ' + str(self.m_current_grid)
                    + '.' + str(self.m_current_tile))
            self.m_qp.drawText(260, 543, 'Showing past ' + str(h) + ' slices')
            self.m_qp.end()
            self.QLabel_resliceCanvas.setPixmap(canvas)
        else:
            # Clear reslice canvas:
            self.m_qp.begin(canvas)
            self.m_qp.setBrush(QColor(0, 0, 0))
            self.m_qp.setPen(QColor(255, 255, 255))
            position_rect = QRect(50, 260, 300, 40)
            self.m_qp.drawRect(position_rect)
            self.m_qp.drawText(position_rect,
                               Qt.AlignVCenter | Qt.AlignHCenter,
                               'No reslice image available.')
            self.m_qp.end()
            self.QLabel_resliceCanvas.setPixmap(canvas)
            self.m_tab_populated = False

    def m_draw_plots(self):
        x_delta = 3
        # y coordinates for x-axes:
        mean_y_offset = 60
        mean_diff_y_offset = 206
        stddev_y_offset = 352
        stddev_diff_y_offset = 498
        slice_number_list = []
        mean_list = []
        stddev_list = []
        filename = None
        if self.m_current_ov >= 0:
            # get current data:
            filename = os.path.join(
                self.acq.base_dir, 'meta', 'stats',
                'OV' + str(self.m_current_ov).zfill(constants.OV_DIGITS) + '.dat')
        elif self.m_current_tile >= 0:
            tile_key = ('g' + str(self.m_current_grid).zfill(constants.GRID_DIGITS)
                        + '_t'
                        + str(self.m_current_tile).zfill(constants.TILE_DIGITS))
            filename = os.path.join(
                self.acq.base_dir, 'meta', 'stats',
                tile_key + '.dat')
        else:
            filename = None
        if filename is not None and os.path.isfile(filename):
            with open(filename, 'r') as file:
                for line in file:
                    values_str = line.split(';')
                    values = [x for x in values_str]
                    slice_number_list.append(int(values[0]))
                    mean_list.append(float(values[1]))
                    stddev_list.append(float(values[2]))
            # Shorten the lists to last 165 entries if larger than 165:
            N = len(mean_list)
            if N > 165:
                mean_list = mean_list[-165:]
                stddev_list = stddev_list[-165:]
                slice_number_list = slice_number_list[-165:]
                N = 165
            # Get average of the entries
            mean_avg = mean(mean_list)
            stddev_avg = mean(stddev_list)

            mean_diff_list = []
            stddev_diff_list = []

            for i in range(0, N-1):
                mean_diff_list.append(mean_list[i + 1] - mean_list[i])
                stddev_diff_list.append(stddev_list[i + 1] - stddev_list[i])

            max_mean_delta = 3
            for entry in mean_list:
                delta = abs(entry - mean_avg)
                if delta > max_mean_delta:
                    max_mean_delta = delta
            mean_scaling = 60 / max_mean_delta
            max_stddev_delta = 1
            for entry in stddev_list:
                delta = abs(entry - stddev_avg)
                if delta > max_stddev_delta:
                    max_stddev_delta = delta
            stddev_scaling = 60 / max_stddev_delta
            max_mean_diff = 3
            for entry in mean_diff_list:
                if abs(entry) > max_mean_diff:
                    max_mean_diff = abs(entry)
            mean_diff_scaling = 60 / max_mean_diff
            max_stddev_diff = 1
            for entry in stddev_diff_list:
                if abs(entry) > max_stddev_diff:
                    max_stddev_diff = abs(entry)
            stddev_diff_scaling = 60 / max_stddev_diff

            canvas = self.plots_canvas_template.copy()
            self.m_qp.begin(canvas)

            # Selected slice:
            if self.m_selected_plot_slice is not None:
                max_slices = len(slice_number_list)
                if self.m_selected_plot_slice >= max_slices:
                    self.m_selected_slice_number = slice_number_list[-1]
                    self.m_selected_plot_slice = max_slices - 1
                else:
                    self.m_selected_slice_number = slice_number_list[
                        self.m_selected_plot_slice]
                pen = QPen(QColor(105, 105, 105))
                pen.setWidth(1)
                pen.setStyle(Qt.DashLine)
                self.m_qp.setPen(pen)
                self.m_qp.drawLine(4 + self.m_selected_plot_slice * 3, 0,
                                   4 + self.m_selected_plot_slice * 3, 558)
                # Slice:
                self.m_qp.drawText(500, 550, 'Slice '
                    + str(self.m_selected_slice_number))
                # Data for selected slice:
                if self.m_selected_plot_slice < len(mean_list):
                    sel_mean = '{0:.2f}'.format(
                        mean_list[self.m_selected_plot_slice])
                else:
                    sel_mean = '-'
                if self.m_selected_plot_slice < len(mean_diff_list):
                    sel_mean_diff = '{0:.2f}'.format(
                        mean_diff_list[self.m_selected_plot_slice])
                else:
                    sel_mean_diff = '-'
                if self.m_selected_plot_slice < len(stddev_list):
                    sel_stddev = '{0:.2f}'.format(
                        stddev_list[self.m_selected_plot_slice])
                else:
                    sel_stddev = '-'
                if self.m_selected_plot_slice < len(stddev_diff_list):
                    sel_stddev_diff = '{0:.2f}'.format(
                        stddev_diff_list[self.m_selected_plot_slice])
                else:
                    sel_stddev_diff = '-'

                self.m_qp.drawText(500, 30, sel_mean)
                self.m_qp.drawText(500, 176, sel_mean_diff)
                self.m_qp.drawText(500, 322, sel_stddev)
                self.m_qp.drawText(500, 468, sel_stddev_diff)

            # Show axis means:
            self.m_qp.setPen(QColor(25, 25, 112))
            self.m_qp.drawText(523, 64, '{0:.2f}'.format(mean_avg))
            self.m_qp.setPen(QColor(139, 0, 0))
            self.m_qp.drawText(523, 356, '{0:.2f}'.format(stddev_avg))

            pen = QPen(QColor(25, 25, 112))
            pen.setWidth(1)
            self.m_qp.setPen(pen)
            previous_entry = -1
            x_pos = 4
            for entry in mean_list:
                if previous_entry > -1:
                    d1 = (previous_entry - mean_avg) * mean_scaling
                    d1 = np.clip(d1, -60, 60)
                    d2 = (entry - mean_avg) * mean_scaling
                    d2 = np.clip(d2, -60, 60)
                    self.m_qp.drawLine(QPointF(x_pos, mean_y_offset - d1),
                                       QPointF(x_pos + x_delta, mean_y_offset - d2))
                    x_pos += x_delta
                previous_entry = entry

            pen = QPen(QColor(119, 0, 0))
            pen.setWidth(1)
            self.m_qp.setPen(pen)
            previous_entry = -1
            x_pos = 4
            for entry in stddev_list:
                if previous_entry > -1:
                    d1 = (previous_entry - stddev_avg) * stddev_scaling
                    d1 = np.clip(d1, -60, 60)
                    d2 = (entry - stddev_avg) * stddev_scaling
                    d2 = np.clip(d2, -60, 60)
                    self.m_qp.drawLine(QPointF(x_pos, stddev_y_offset - d1),
                                       QPointF(x_pos + x_delta, stddev_y_offset - d2))
                    x_pos += x_delta
                previous_entry = entry

            pen = QPen(QColor(25, 25, 112))
            pen.setWidth(1)
            self.m_qp.setPen(pen)
            x_pos = 4
            for i in range(1, N-1):
                d1 = mean_diff_list[i-1] * mean_diff_scaling
                d1 = np.clip(d1, -60, 60)
                d2 = mean_diff_list[i] * mean_diff_scaling
                d2 = np.clip(d2, -60, 60)
                self.m_qp.drawLine(QPointF(x_pos, mean_diff_y_offset - d1),
                                   QPointF(x_pos + x_delta, mean_diff_y_offset - d2))
                x_pos += x_delta

            pen = QPen(QColor(119, 0, 0))
            pen.setWidth(1)
            self.m_qp.setPen(pen)
            x_pos = 4
            for i in range(1, N-1):
                d1 = stddev_diff_list[i-1] * stddev_diff_scaling
                d1 = np.clip(d1, -60, 60)
                d2 = stddev_diff_list[i] * stddev_diff_scaling
                d2 = np.clip(d2, -60, 60)
                self.m_qp.drawLine(QPointF(x_pos, stddev_diff_y_offset - d1),
                                   QPointF(x_pos + x_delta, stddev_diff_y_offset - d2))
                x_pos += x_delta

            self.m_qp.end()
            self.QLabel_plotCanvas.setPixmap(canvas)
        else:
            self.QLabel_plotCanvas.setPixmap(self.plots_canvas_template)
            self.m_tab_populated = False

    def m_draw_histogram(self):
        selected_file = ''
        slice_number = None
        canvas = self.histogram_canvas_template.copy()

        if self.m_from_stack:
            path = None
            if self.m_current_ov >= 0:
                path = os.path.join(
                    self.acq.base_dir, 'overviews',
                    'ov' + str(self.m_current_ov).zfill(constants.OV_DIGITS))
            elif self.m_current_tile >= 0:
                path = os.path.join(
                    self.acq.base_dir, 'tiles',
                    'g' + str(self.m_current_grid).zfill(constants.GRID_DIGITS)
                    + '\\t' + str(self.m_current_tile).zfill(constants.TILE_DIGITS))

            if path is not None and os.path.exists(path):
                filenames = next(os.walk(path))[2]
                if len(filenames) > 165:
                    filenames = filenames[-165:]
                if filenames:
                    if self.m_selected_slice_number is None:
                        selected_file = os.path.join(path, filenames[-1])
                    else:
                        slice_number_str = (
                            's' + str(self.m_selected_slice_number).zfill(
                                constants.SLICE_DIGITS))
                        for filename in filenames:
                            if slice_number_str in filename:
                                selected_file = os.path.join(path, filename)
                                break

        else:
            # Use current image from SEM
            selected_file = os.path.join(
                self.acq.base_dir, 'workspace', 'current_frame' + constants.TEMP_IMAGE_FORMAT)
            self.sem.save_frame(selected_file, self.acq.stage)
            self.m_reset_view()
            self.m_tab_populated = False

        if os.path.isfile(selected_file):
            img = imread(selected_file)

            # calculate mean and SD:
            mean = np.mean(img)
            stddev = np.std(img)
            #Full histogram:
            hist, bin_edges = np.histogram(img, 256, [0, 256])

            hist_max = hist.max()
            peak = -1
            self.m_qp.begin(canvas)
            self.m_qp.setPen(QColor(25, 25, 112))

            for x in range(0, 256):
                gv_normalized = hist[x]/hist_max
                if gv_normalized == 1:
                    peak = x
                self.m_qp.drawLine(QPointF(x + 11, 160),
                                   QPointF(x + 11, 160 - gv_normalized * 147))
            if self.m_from_stack:
                try:
                    idx = selected_file.rfind('s')
                    slice_number = int(selected_file[idx+1:idx+6])
                except:
                    slice_number = -1
                if self.m_current_ov >= 0:
                    self.m_qp.drawText(
                        280, 50,
                        'OV ' + str(self.m_current_ov)
                        + ', slice ' + str(slice_number))
                elif self.m_current_grid >= 0:
                    self.m_qp.drawText(
                        280, 50,
                        'Tile ' + str(self.m_current_grid)
                        + '.' + str(self.m_current_tile)
                        + ', slice ' + str(slice_number))

            else:
                self.m_qp.drawText(280, 50, 'Current SmartSEM image')
            self.m_qp.drawText(345, 90, '{0:.2f}'.format(mean))
            self.m_qp.drawText(345, 110, '{0:.2f}'.format(stddev))
            self.m_qp.drawText(345, 130, str(peak))
            self.m_qp.drawText(345, 150, str(hist_max))

            self.m_qp.end()
            self.QLabel_histogramCanvas.setPixmap(canvas)
        else:
            self.m_qp.begin(canvas)
            self.m_qp.setPen(QColor(25, 25, 112))
            self.m_qp.drawText(50, 90, 'No image found for selected source   ')
            self.m_qp.end()
            self.QLabel_histogramCanvas.setPixmap(canvas)

    def _m_open_motor_status_dlg(self):
        dialog = MotorStatusDlg(self.stage)
        dialog.exec()

    def m_show_motor_status(self):
        """Show recent motor warnings or errors if there are any."""
        self.label_xMotorStatus.setStyleSheet("color: black")
        self.label_xMotorStatus.setText('No recent warnings')
        self.label_yMotorStatus.setStyleSheet("color: black")
        self.label_yMotorStatus.setText('No recent warnings')
        self.label_zMotorStatus.setStyleSheet("color: black")
        self.label_zMotorStatus.setText('No recent warnings')

        if sum(self.stage.slow_xy_move_warnings) > 0:
            self.label_xMotorStatus.setStyleSheet("color: orange")
            self.label_xMotorStatus.setText('Recent warnings')
            self.label_yMotorStatus.setStyleSheet("color: orange")
            self.label_yMotorStatus.setText('Recent warnings')
        if sum(self.stage.failed_x_move_warnings) > 0:
            self.label_xMotorStatus.setStyleSheet("color: red")
            self.label_xMotorStatus.setText('Recent errors')
        if sum(self.stage.failed_y_move_warnings) > 0:
            self.label_yMotorStatus.setStyleSheet("color: red")
            self.label_yMotorStatus.setText('Recent errors')
        if sum(self.stage.failed_z_move_warnings) > 0:
            self.label_zMotorStatus.setStyleSheet("color: red")
            self.label_zMotorStatus.setText('Recent errors')
