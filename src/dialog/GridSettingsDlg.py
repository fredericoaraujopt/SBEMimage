import numpy as np

from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap, QColor, QIcon
from qtpy.QtWidgets import QComboBox, QDialog, QGroupBox, QMessageBox, QPushButton
from qtpy.uic import loadUi

import constants
import utils
from dialog.ImagingConditionSupport import (
    GridImagingConditionAdapter,
    ImagingConditionController,
)
from dialog.FocusGradientSettingsDlg import FocusGradientSettingsDlg


class GridSettingsDlg(QDialog):
    """Dialog for changing grid settings and for adding/deleting grids."""

    def __init__(self, grid_manager, sem, selected_grid, main_controls_trigger,
                 imaging_condition_store, magc_mode=False, acq_groups=None):
        super().__init__()
        self.gm = grid_manager
        self.sem = sem
        self.current_grid = selected_grid
        self.main_controls_trigger = main_controls_trigger
        self.imaging_condition_store = imaging_condition_store
        self.magc_mode = magc_mode
        self.acq_groups = acq_groups
        loadUi('gui/grid_settings_dlg.ui', self)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowIcon(utils.get_window_icon())
        # Set up grid selector:
        self.comboBox_gridSelector.addItems(self.gm.grid_selector_list())
        self.comboBox_gridSelector.setCurrentIndex(self.current_grid)
        self.comboBox_gridSelector.currentIndexChanged.connect(
            self.change_grid)
        # Set up colour selector:
        for i in range(len(constants.COLOUR_SELECTOR)):
            rgb = constants.COLOUR_SELECTOR[i]
            colour_icon = QPixmap(20, 10)
            colour_icon.fill(QColor(*rgb))
            self.comboBox_colourSelector.addItem(QIcon(colour_icon), '')
        if self.gm[self.current_grid].active:
            self.radioButton_active.setChecked(True)
        else:
            self.radioButton_inactive.setChecked(True)
        self.radioButton_active.toggled.connect(self.update_active_status)
        self.update_active_status()
        store_res_list = [
            f'{res[0]} × {res[1]}' for res in self.sem.STORE_RES]
        self.comboBox_tileSize.addItems(store_res_list)
        self.comboBox_tileSize.currentIndexChanged.connect(
            self.show_frame_size_and_dose)
        self.comboBox_dwellTime.addItems(map(str, self.sem.DWELL_TIME))
        self.comboBox_dwellTime.currentIndexChanged.connect(
            self.show_frame_size_and_dose)
        self.doubleSpinBox_pixelSize.valueChanged.connect(
            self.show_frame_size_and_dose)
        self.comboBox_bitDepth.addItems(['8 bit', '16 bit'])
        # Focus gradient feature, disabled for TESCAN SEMs
        self.toolButton_focusGradient.clicked.connect(
            self.open_focus_gradient_dlg)
        if sem.device_name.startswith("TESCAN"):
            self.checkBox_focusGradient.setEnabled(False)
            self.toolButton_focusGradient.setEnabled(False)
        # Buttons to reset tile previews and wd/stig parameters
        self.pushButton_resetTilePreviews.clicked.connect(
            self.reset_tile_previews)
        self.pushButton_resetFocusParams.clicked.connect(
            self.reset_wd_stig_params)
        # Save, add, and delete buttons
        self.pushButton_save.clicked.connect(self.save_current_settings)
        self.pushButton_addGrid.clicked.connect(self.add_grid)
        self.pushButton_deleteGrid.clicked.connect(self.delete_grid)
        self.update_buttons()
        self.show_current_settings()
        self.show_frame_size_and_dose()
        self.update_polygon_mode()
        self._setup_imaging_condition_controls()
        if 'multisem' in self.sem.device_name.lower():
            # in multisem ROIs are used instead of grids
            # the smallest possible grid is kept for compatibility
            self.spinBox_rows.setEnabled(False)
            self.spinBox_rows.setValue(1)
            self.spinBox_cols.setEnabled(False)
            self.spinBox_cols.setValue(1)
            self.comboBox_tileSize.setEnabled(False)
            self.comboBox_tileSize.setCurrentIndex(0)
            self.spinBox_shift.setEnabled(False)
        self.setFixedSize(self.size())
        self.show()

    def _shift_widgets_y(self, widgets, delta):
        for widget in widgets:
            widget.move(widget.x(), widget.y() + delta)

    def _setup_imaging_condition_controls(self):
        panel_top = self.groupBox_geometry.y() + self.groupBox_geometry.height() + 8
        panel_height = 138
        shift_delta = panel_top + panel_height + 10 - self.groupBox_2.y()
        self.resize(self.width(), self.height() + shift_delta)

        self.groupBox_savedImagingSettings = QGroupBox(
            'Saved imaging settings', self)
        self.groupBox_savedImagingSettings.setGeometry(
            10, panel_top, self.groupBox_geometry.width(), panel_height)
        inner_left = 10
        inner_width = self.groupBox_savedImagingSettings.width() - 20
        apply_width = 136
        manage_width = inner_width - apply_width - 8

        self.pushButton_saveCurrentImagingConditionAs = QPushButton(
            'Save current settings as...', self.groupBox_savedImagingSettings)
        self.pushButton_saveCurrentImagingConditionAs.setGeometry(
            inner_left, 22, inner_width, 23)
        self.comboBox_savedImagingCondition = QComboBox(
            self.groupBox_savedImagingSettings)
        self.comboBox_savedImagingCondition.setGeometry(
            inner_left, 51, inner_width, 22)
        self.pushButton_applySavedImagingCondition = QPushButton(
            'Apply saved settings', self.groupBox_savedImagingSettings)
        self.pushButton_applySavedImagingCondition.setGeometry(
            inner_left, 79, apply_width, 23)
        self.pushButton_manageImagingConditions = QPushButton(
            'Manage...', self.groupBox_savedImagingSettings)
        self.pushButton_manageImagingConditions.setGeometry(
            inner_left + apply_width + 8, 79, manage_width, 23)
        self.pushButton_getFromSEM.setParent(self.groupBox_savedImagingSettings)
        self.pushButton_getFromSEM.setGeometry(
            inner_left, 108, inner_width, self.pushButton_getFromSEM.height())

        self._shift_widgets_y(
            [
                self.groupBox_2,
                self.radioButton_active,
                self.radioButton_inactive,
                self.pushButton_save,
                self.pushButton_addGrid,
                self.pushButton_deleteGrid,
                self.buttonBox,
            ],
            shift_delta)
        self.buttonBox.move(int((self.width() - self.buttonBox.width()) / 2),
                            self.buttonBox.y())

        adapter = GridImagingConditionAdapter(self, self.sem)
        self.imaging_condition_controller = ImagingConditionController(
            self,
            self.imaging_condition_store,
            adapter,
            self.comboBox_savedImagingCondition,
            self.pushButton_applySavedImagingCondition,
            self.pushButton_manageImagingConditions,
            self.pushButton_saveCurrentImagingConditionAs,
            self.pushButton_getFromSEM)

    def update_active_status(self):
        # If current grid is inactive, disable GUI elements
        b = self.radioButton_active.isChecked()
        tescan_sem = self.sem.device_name.startswith("TESCAN")
        polygon_grid = self.gm[self.current_grid].has_polygon_roi()
        self.spinBox_rows.setEnabled(b and not polygon_grid)
        self.spinBox_cols.setEnabled(b and not polygon_grid)
        self.spinBox_overlap.setEnabled(b)
        self.spinBox_shift.setEnabled(b)
        self.doubleSpinBox_rotation.setEnabled(b)
        self.comboBox_tileSize.setEnabled(b)
        self.comboBox_dwellTime.setEnabled(b)
        self.doubleSpinBox_pixelSize.setEnabled(b)
        self.checkBox_focusGradient.setEnabled(b and not tescan_sem)
        self.toolButton_focusGradient.setEnabled(b and not tescan_sem)
        self.pushButton_resetFocusParams.setEnabled(b)
        self.spinBox_acqInterval.setEnabled(b)
        self.spinBox_acqIntervalOffset.setEnabled(b)
        self.update_polygon_mode()

    def update_polygon_mode(self):
        grid = self.gm[self.current_grid]
        polygon_grid = grid.has_polygon_roi()
        tooltip = ''
        if polygon_grid:
            tooltip = 'Rows and columns are auto-derived from the polygon ROI.'
            if grid.is_deferred_polygon_roi():
                tooltip += ' This ROI is currently deferred and has not been materialized yet.'
        self.spinBox_rows.setToolTip(tooltip)
        self.spinBox_cols.setToolTip(tooltip)

    def get_settings_from_sem(self):
        """Load current SEM settings for frame size, pixel size, and
        dwell time, and set the spin box and the combo boxes to these values.
        """
        current_frame_size_selector = self.sem.get_frame_size_selector()
        current_pixel_size = self.sem.get_pixel_size()
        current_scan_rate = self.sem.get_scan_rate()
        self.comboBox_tileSize.setCurrentIndex(current_frame_size_selector)
        self.comboBox_dwellTime.setCurrentIndex(current_scan_rate)
        self.doubleSpinBox_pixelSize.setValue(current_pixel_size)

    def show_current_settings(self):
        grid = self.gm[self.current_grid]
        self.comboBox_colourSelector.setCurrentIndex(
            grid.display_colour)
        self._update_colour_selector_state()
        self.checkBox_focusGradient.setChecked(
            grid.use_wd_gradient)
        if grid.is_deferred_polygon_roi():
            self.spinBox_rows.setValue(max(1, grid.roi_estimated_rows))
            self.spinBox_cols.setValue(max(1, grid.roi_estimated_cols))
        else:
            self.spinBox_rows.setValue(grid.number_rows())
            self.spinBox_cols.setValue(grid.number_cols())
        self.spinBox_overlap.setValue(int(grid.overlap))
        self.doubleSpinBox_rotation.setValue(
            grid.rotation)
        self.spinBox_shift.setValue(grid.row_shift)
        self.doubleSpinBox_pixelSize.setValue(
            grid.pixel_size)
        self.comboBox_tileSize.setCurrentIndex(
            grid.frame_size_selector)
        self.comboBox_dwellTime.setCurrentIndex(
            grid.dwell_time_selector)
        self.comboBox_bitDepth.setCurrentIndex(
            grid.bit_depth_selector)
        self.spinBox_acqInterval.setValue(
            grid.acq_interval)
        self.spinBox_acqIntervalOffset.setValue(
            grid.acq_interval_offset)

    def _prompt_polygon_materialization_choice(self, layout, currently_deferred):
        guardrail = self.gm.polygon_guardrail_state(layout['tile_count'])
        if not currently_deferred and not guardrail['warn']:
            return 'materialize'

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Warning)
        if currently_deferred:
            message_box.setWindowTitle('Deferred polygon ROI')
            message_box.setText(
                f'This ROI currently stays deferred. With the current settings it '
                f'would create approximately {layout["tile_count"]:,} tiles '
                f'({layout["rows"]} x {layout["cols"]}).')
            if guardrail['block_materialize']:
                message_box.setInformativeText(
                    'This exceeds the safe immediate materialization limit. '
                    'Keep the ROI deferred and refine the settings further.')
            else:
                message_box.setInformativeText(
                    'You can materialize it now or keep it deferred.')
        else:
            message_box.setWindowTitle('Large polygon ROI')
            message_box.setText(
                f'These settings would create approximately '
                f'{layout["tile_count"]:,} tiles '
                f'({layout["rows"]} x {layout["cols"]}).')
            if guardrail['block_materialize']:
                message_box.setInformativeText(
                    'This exceeds the safe immediate materialization limit. '
                    'Save the ROI in deferred mode instead.')
            else:
                message_box.setInformativeText(
                    'Large polygon grids can make the GUI slow. '
                    'Recommended: save this ROI in deferred mode.')

        deferred_button = message_box.addButton(
            'Keep Deferred', QMessageBox.AcceptRole)
        if not guardrail['block_materialize']:
            materialize_button = message_box.addButton(
                'Materialize Grid', QMessageBox.ActionRole)
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

    def show_frame_size_and_dose(self):
        """Calculate and display the tile size and the dose for the current
        settings. Updated in real-time as user changes dwell time, frame
        resolution and pixel size.
        """
        frame_size_selector = self.comboBox_tileSize.currentIndex()
        pixel_size = self.doubleSpinBox_pixelSize.value()
        width = self.sem.STORE_RES[frame_size_selector][0] * pixel_size / 1000
        height = self.sem.STORE_RES[frame_size_selector][1] * pixel_size / 1000
        self.label_tileSize.setText(f'{width:.1f} × {height:.1f}')
        current = self.sem.target_beam_current
        dwell_time = float(self.comboBox_dwellTime.currentText())
        pixel_size = self.doubleSpinBox_pixelSize.value()
        # Show electron dose in electrons per square nanometre.
        self.label_dose.setText('{0:.1f}'.format(
            utils.calculate_electron_dose(current, dwell_time, pixel_size)))

    def change_grid(self):
        self.current_grid = self.comboBox_gridSelector.currentIndex()
        if self.gm[self.current_grid].active:
            self.radioButton_active.setChecked(True)
        else:
            self.radioButton_inactive.setChecked(True)
        self.update_active_status()
        self.update_buttons()
        self.show_current_settings()
        self.show_frame_size_and_dose()
        self.update_polygon_mode()

    def _update_colour_selector_state(self):
        grouped = (
            self.acq_groups is not None
            and self.acq_groups.grid_group_id(self.current_grid) is not None)
        self.comboBox_colourSelector.setEnabled(not grouped)
        if grouped:
            group_path = self.acq_groups.grid_group_path_text(self.current_grid)
            self.label_6.setText('Grid colour: group-managed')
            self.comboBox_colourSelector.setToolTip(
                f'This grid is grouped under "{group_path}". '
                'The viewport colour comes from the acquisition manager.')
        else:
            self.label_6.setText('Grid colour:')
            self.comboBox_colourSelector.setToolTip(
                'Choose the viewport colour for this ungrouped grid.')

    def update_buttons(self):
        """Update labels on buttons and disable/enable delete button
        depending on which grid is selected. Grid 0 cannot be deleted.
        Only the last grid can be deleted. Reason: preserve identities of
        grids and tiles within grids.
        """
        grid_label = self.gm.get_grid_label(self.current_grid)
        if self.current_grid == 0:
            self.pushButton_deleteGrid.setEnabled(False)
        else:
            self.pushButton_deleteGrid.setEnabled(
                self.current_grid == (self.gm.number_grids - 1))
        self.pushButton_save.setText(
            f'Save settings for {grid_label}')
        self.pushButton_deleteGrid.setText(
            f'Delete {grid_label}')

    def add_grid(self):
        active = self.radioButton_active.isChecked()
        frame_size_selector = self.comboBox_tileSize.currentIndex()
        frame_size = self.comboBox_tileSize.currentText()
        input_overlap = self.spinBox_overlap.value()
        pixel_size = self.doubleSpinBox_pixelSize.value()
        dwell_time_selector = self.comboBox_dwellTime.currentIndex()
        dwell_time = self.comboBox_dwellTime.currentText()
        bit_depth_selector = self.comboBox_bitDepth.currentIndex()
        rotation = self.doubleSpinBox_rotation.value()
        input_shift = self.spinBox_shift.value()
        acq_interval = self.spinBox_acqInterval.value()
        acq_interval_offset = self.spinBox_acqIntervalOffset.value()
        size = [self.spinBox_rows.value(), self.spinBox_cols.value()]
        self.gm.add_new_grid(active=active,
                             frame_size=frame_size, frame_size_selector=frame_size_selector,
                             overlap=input_overlap, pixel_size=pixel_size,
                             dwell_time=dwell_time, dwell_time_selector=dwell_time_selector,
                             bit_depth_selector=bit_depth_selector,
                             rotation=rotation, row_shift=input_shift,
                             acq_interval=acq_interval, acq_interval_offset=acq_interval_offset,
                             size=size)
        self.current_grid = self.gm.number_grids - 1
        # Update grid selector:
        self.comboBox_gridSelector.blockSignals(True)
        self.comboBox_gridSelector.clear()
        self.comboBox_gridSelector.addItems(self.gm.grid_selector_list())
        self.comboBox_gridSelector.setCurrentIndex(self.current_grid)
        self.comboBox_gridSelector.blockSignals(False)
        self.change_grid()
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def delete_grid(self):
        user_reply = QMessageBox.question(
                        self, 'Delete grid',
                        'This will delete grid %d.\n\n'
                        'Do you wish to proceed?' % self.current_grid,
                        QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply == QMessageBox.Ok:
            self.gm.delete_grid()
            self.current_grid = self.gm.number_grids - 1
            # Update grid selector:
            self.comboBox_gridSelector.blockSignals(True)
            self.comboBox_gridSelector.clear()
            self.comboBox_gridSelector.addItems(self.gm.grid_selector_list())
            self.comboBox_gridSelector.setCurrentIndex(self.current_grid)
            self.comboBox_gridSelector.blockSignals(False)
            self.change_grid()
            self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def reset_tile_previews(self):
        user_reply = QMessageBox.question(
            self, 'Reset tile previews',
            f'This will clear all tile preview images in the Viewport for '
            f'{self.gm.get_grid_label(self.current_grid)}',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply == QMessageBox.Ok:
            self.gm[self.current_grid].clear_all_tile_previews()
            self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def reset_wd_stig_params(self):
        user_reply = QMessageBox.question(
            self, 'Reset focus/astigmatism parameters',
            f'This will reset the focus and astigmatism parameters for '
            f'all tiles in grid {self.current_grid}.\n'
            f'Proceed?',
            QMessageBox.Ok | QMessageBox.Cancel)
        if user_reply == QMessageBox.Ok:
            self.gm[self.current_grid].set_wd_for_all_tiles(0)
            self.gm[self.current_grid].set_stig_xy_for_all_tiles([0, 0])
            self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def save_current_settings(self):
        error_msg = ''
        grid = self.gm[self.current_grid]
        polygon_grid = grid.has_polygon_roi()
        polygon_top_left_dx_dy = None
        polygon_save_mode = 'materialize'
        preserve_rectangular_footprint = False
        rectangular_layout = None
        prev_rectangular_top_left_dx_dy = None
        prev_rectangular_centre_dx_dy = None
        frame_size_selector = self.comboBox_tileSize.currentIndex()
        input_overlap = self.spinBox_overlap.value()
        input_shift = self.spinBox_shift.value()
        pixel_size = self.doubleSpinBox_pixelSize.value()
        frame_size = self.sem.STORE_RES[frame_size_selector]
        geometry_changed = any([
            frame_size_selector != grid.frame_size_selector,
            input_overlap != grid.overlap,
            input_shift != grid.row_shift,
            pixel_size != grid.pixel_size,
        ])
        requested_size = [self.spinBox_rows.value(), self.spinBox_cols.value()]
        if polygon_grid:
            polygon_top_left_dx_dy = (
                grid.origin_dx_dy[0] - grid.tile_width_d() / 2,
                grid.origin_dx_dy[1] - grid.tile_height_d() / 2)
        else:
            preserve_rectangular_footprint = geometry_changed
            if preserve_rectangular_footprint:
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
                    input_overlap,
                    input_shift)
                prev_rectangular_top_left_dx_dy = np.array(
                    grid.rectangular_roi_top_left_dx_dy(), dtype=float)
                prev_rectangular_centre_dx_dy = np.array(
                    grid.rectangular_roi_centre_dx_dy(), dtype=float)

        prev_grid_centre = np.array(grid.centre_sx_sy)

        tile_width_p = frame_size[0]
        if -0.3 * tile_width_p <= input_overlap < 0.3 * tile_width_p:
            pass
        else:
            error_msg = ('Overlap outside of allowed '
                         'range (-30% .. 30% frame width).')
        if 0 <= input_shift <= tile_width_p:
            pass
        else:
            error_msg = ('Row shift outside of allowed '
                         'range (0 .. frame width).')
        if error_msg:
            QMessageBox.warning(self, 'Error', error_msg, QMessageBox.Ok)
            return

        if polygon_grid:
            layout = self.gm.polygon_layout_summary(
                grid.sw_sh[0],
                grid.sw_sh[1],
                frame_size,
                pixel_size,
                input_overlap,
                input_shift)
            polygon_save_mode = self._prompt_polygon_materialization_choice(
                layout,
                grid.is_deferred_polygon_roi())
            if polygon_save_mode == 'cancel':
                return

        # Update tile positions only once after updating all grid attributes
        grid.auto_update_tile_positions = False

        grid.active = self.radioButton_active.isChecked()
        if not polygon_grid:
            if preserve_rectangular_footprint:
                grid.size = [
                    rectangular_layout['rows'],
                    rectangular_layout['cols']]
            else:
                grid.size = requested_size
        grid.frame_size_selector = frame_size_selector
        grid.overlap = input_overlap
        grid.row_shift = input_shift
        if (self.acq_groups is None
                or self.acq_groups.grid_group_id(self.current_grid) is None):
            grid.display_colour = (
                self.comboBox_colourSelector.currentIndex())
        grid.use_wd_gradient = (
            self.checkBox_focusGradient.isChecked())
        if self.checkBox_focusGradient.isChecked():
            grid.calculate_wd_gradient()
        # Acquisition parameters:
        grid.pixel_size = pixel_size
        grid.dwell_time_selector = (
            self.comboBox_dwellTime.currentIndex())
        grid.bit_depth_selector = (
            self.comboBox_bitDepth.currentIndex())
        grid.acq_interval = (
            self.spinBox_acqInterval.value())
        grid.acq_interval_offset = (
            self.spinBox_acqIntervalOffset.value())
        # Recalculate tile positions after all parameter updates, except rotation (see below)
        if polygon_grid:
            if polygon_save_mode == 'defer':
                self.gm.defer_polygon_grid(
                    self.current_grid,
                    layout['rows'],
                    layout['cols'],
                    layout['tile_count'])
            else:
                self.gm.refresh_polygon_grid(
                    self.current_grid,
                    top_left_dx_dy=polygon_top_left_dx_dy)
        else:
            grid.update_tile_positions()
            if preserve_rectangular_footprint:
                grid.set_rectangular_roi_top_left_dx_dy(
                    prev_rectangular_top_left_dx_dy)
                grid.update_tile_positions()
                grid.sw_sh = [float(grid.sw_sh[0]), float(grid.sw_sh[1])]
            else:
                grid.centre_sx_sy = prev_grid_centre
                grid.sw_sh = [float(grid.width_d()), float(grid.height_d())]

        # Now apply rotation if the rotation angle was changed.
        new_rotation = self.doubleSpinBox_rotation.value()
        if new_rotation != grid.rotation:
            # Keep the existing ROI centred while applying rotation.
            centre_dx, centre_dy = grid.centre_dx_dy
            if (not polygon_grid and preserve_rectangular_footprint
                    and prev_rectangular_centre_dx_dy is not None):
                centre_dx, centre_dy = prev_rectangular_centre_dx_dy
            grid.rotation = new_rotation
            if polygon_grid and polygon_save_mode == 'defer':
                grid.update_tile_positions()
            elif not polygon_grid and preserve_rectangular_footprint:
                grid.set_rectangular_roi_centre_dx_dy((centre_dx, centre_dy))
                grid.update_tile_positions()
            else:
                grid.rotate_around_grid_centre(centre_dx, centre_dy)
                grid.update_tile_positions()
            if polygon_grid and not grid.is_deferred_polygon_roi():
                grid.active_tiles = (
                    self.gm.polygon_active_tiles(grid))

        grid.auto_update_tile_positions = True

        if self.magc_mode:
            if preserve_rectangular_footprint and prev_rectangular_centre_dx_dy is not None:
                grid.set_rectangular_roi_centre_dx_dy(
                    prev_rectangular_centre_dx_dy)
            else:
                grid.centre_sx_sy = prev_grid_centre
            self.gm.array_write()
        # Restore default behaviour for updating tile positions
        self.show_current_settings()
        self.show_frame_size_and_dose()
        self.main_controls_trigger.transmit('GRID SETTINGS CHANGED')

    def open_focus_gradient_dlg(self):
        sub_dialog = FocusGradientSettingsDlg(self.gm, self.current_grid)
        sub_dialog.exec()
