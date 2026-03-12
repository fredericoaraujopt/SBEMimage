from queue import Queue

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
)
from qtpy.uic import loadUi

import acq_func
import stub_overview_workflow as stub_workflow
import utils
from dialog.ImagingConditionSupport import (
    ImagingConditionController,
    StubImagingConditionAdapter,
)


class StubOVDlg(QDialog):
    """Acquire a stub overview image.

    The dialog remains modeless so the viewport can still be panned while the
    acquisition is running.
    """

    def __init__(self, centre_sx_sy, sem, stage, ovm, imported_images, acq,
                 img_inspector, viewport_trigger, imaging_condition_store):
        super().__init__()
        loadUi('gui/stub_ov_dlg.ui', self)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowIcon(utils.get_window_icon())

        self.sem = sem
        self.stage = stage
        self.ovm = ovm
        self.imported = imported_images
        self.acq = acq
        self.img_inspector = img_inspector
        self.viewport_trigger = viewport_trigger
        self.imaging_condition_store = imaging_condition_store

        self.acq_in_progress = False
        self.error_msg_from_acq_thread = ''
        self._syncing_stub_resolution = False
        self.current_stub_mode_key = None
        self.current_stub_previous_state = None
        self._pending_stub_settings = {}

        self.stub_dlg_trigger = utils.Trigger()
        self.stub_dlg_trigger.signal.connect(self.process_thread_signal)
        self.abort_queue = Queue()

        self._setup_imaging_condition_controls()

        self.pushButton_acquire.clicked.connect(self.start_stub_ov_acquisition)
        self.pushButton_abort.clicked.connect(self.abort)
        self.pushButton_abort.setEnabled(False)
        self.pushButton_centreCurrentStage.clicked.connect(
            self.set_centre_to_current_stage_coordinates)

        self.checkBox_LmMode.setEnabled(self.sem.has_lm_mode())
        self.checkBox_LmMode.stateChanged.connect(self.update_settings_from_ovm)

        self.spinBox_rows.valueChanged.connect(
            self.update_dimension_and_duration_display)
        self.spinBox_cols.valueChanged.connect(
            self.update_dimension_and_duration_display)
        self.comboBox_frameSize.currentIndexChanged.connect(
            self._sync_pixel_size_from_magnification)
        self.comboBox_frameSize.currentIndexChanged.connect(
            self.update_dimension_and_duration_display)
        self.comboBox_dwellTime.currentIndexChanged.connect(
            self.update_dimension_and_duration_display)
        self.spinBox_magnification.valueChanged.connect(self.set_magnification)
        self.doubleSpinBox_pixelSize.valueChanged.connect(self.set_pixel_size)

        initial_mode_key = self._stub_mode_key(False)
        self._pending_stub_settings[initial_mode_key] = (
            self._build_settings_from_stub_ovm(
                initial_mode_key,
                centre_override=centre_sx_sy))
        if self.sem.has_lm_mode():
            self._pending_stub_settings[self._stub_mode_key(True)] = (
                self._build_settings_from_stub_ovm(self._stub_mode_key(True)))
        self.current_stub_mode_key = initial_mode_key
        self._apply_widget_settings(self._pending_stub_settings[initial_mode_key])

        self.setFixedSize(self.size())

    def _shift_widgets_y(self, widgets, delta):
        for widget in widgets:
            widget.move(widget.x(), widget.y() + delta)

    def _setup_imaging_condition_controls(self):
        lower_block_delta = 202
        resolution_delta = 30
        self._shift_widgets_y(
            [
                self.label_4,
                self.spinBox_magnification,
                self.label_5,
                self.doubleSpinBox_pixelSize,
            ],
            resolution_delta)
        self._shift_widgets_y(
            [
                self.label_dimension,
                self.label_6,
                self.label_2,
                self.label_duration,
                self.line_2,
                self.progressBar,
                self.pushButton_acquire,
                self.pushButton_abort,
                self.buttonBox,
            ],
            lower_block_delta)
        self.resize(self.width(), self.height() + lower_block_delta)

        row_label_x = 10
        row_input_x = 170
        frame_row_y = 130
        self.label_frameSizeSelector = QLabel('Frame size (px):', self)
        self.label_frameSizeSelector.setGeometry(row_label_x, frame_row_y, 111, 16)
        self.comboBox_frameSize = QComboBox(self)
        self.comboBox_frameSize.setGeometry(row_input_x, frame_row_y - 2, 131, 22)
        self.comboBox_frameSize.addItems(
            [f'{res[0]} x {res[1]}' for res in self.sem.STORE_RES])

        dwell_row_y = 220
        self.label_dwellTimeSelector = QLabel('Dwell time (us):', self)
        self.label_dwellTimeSelector.setGeometry(row_label_x, dwell_row_y, 111, 16)
        self.comboBox_dwellTime = QComboBox(self)
        self.comboBox_dwellTime.setGeometry(row_input_x, dwell_row_y - 2, 131, 22)
        self.comboBox_dwellTime.addItems([str(value) for value in self.sem.DWELL_TIME])

        full_width = self.progressBar.width()
        left_x = self.progressBar.x()
        sem_button_y = 250
        self.pushButton_getFromSEM = QPushButton(
            'Get current settings from SEM', self)
        self.pushButton_getFromSEM.setGeometry(left_x, sem_button_y, full_width, 23)
        self.label_savedImagingCondition = QLabel(
            'Saved imaging condition:', self)
        self.label_savedImagingCondition.setGeometry(
            left_x, sem_button_y + 31, full_width, 18)
        self.comboBox_savedImagingCondition = QComboBox(self)
        self.comboBox_savedImagingCondition.setGeometry(
            left_x, sem_button_y + 51, full_width, 22)
        self.pushButton_applySavedImagingCondition = QPushButton(
            'Apply saved settings', self)
        self.pushButton_applySavedImagingCondition.setGeometry(
            left_x, sem_button_y + 81, 184, 23)
        self.pushButton_manageImagingConditions = QPushButton(
            'Manage...', self)
        self.pushButton_manageImagingConditions.setGeometry(
            left_x + 190, sem_button_y + 81, 101, 23)
        self.pushButton_saveCurrentImagingConditionAs = QPushButton(
            'Save current settings as...', self)
        self.pushButton_saveCurrentImagingConditionAs.setGeometry(
            left_x, sem_button_y + 111, full_width, 23)

        adapter = StubImagingConditionAdapter(self, self.sem)
        self.imaging_condition_controller = ImagingConditionController(
            self,
            self.imaging_condition_store,
            adapter,
            self.comboBox_savedImagingCondition,
            self.pushButton_applySavedImagingCondition,
            self.pushButton_manageImagingConditions,
            self.pushButton_saveCurrentImagingConditionAs,
            self.pushButton_getFromSEM)

    def _stub_mode_key(self, lm_mode=None):
        if lm_mode is None:
            lm_mode = self.checkBox_LmMode.isChecked()
        return stub_workflow.stub_mode_key(lm_mode)

    def _current_frame_size_selector(self):
        return max(0, self.comboBox_frameSize.currentIndex())

    def _current_dwell_time_selector(self):
        return max(0, self.comboBox_dwellTime.currentIndex())

    def _current_frame_size(self):
        return self.sem.STORE_RES[self._current_frame_size_selector()]

    def _current_magnification_from_widgets(self):
        return max(1, self.spinBox_magnification.value())

    def _build_settings_from_stub_ovm(self, mode_key, centre_override=None):
        stub_ovm = self.ovm[mode_key]
        frame_size_selector = int(stub_ovm.frame_size_selector)
        frame_width_px = self.sem.STORE_RES[frame_size_selector][0]
        magnification = max(
            1,
            int(round(
                self.sem.MAG_PX_SIZE_FACTOR
                / (frame_width_px * stub_ovm.pixel_size))))
        return {
            'centre_sx_sy': list(
                centre_override if centre_override is not None
                else stub_ovm.centre_sx_sy),
            'grid_size': list(stub_ovm.size),
            'frame_size_selector': frame_size_selector,
            'pixel_size': float(stub_ovm.pixel_size),
            'dwell_time_selector': int(stub_ovm.dwell_time_selector),
            'magnification': magnification,
        }

    def _current_widget_settings(self):
        return {
            'centre_sx_sy': [self.spinBox_X.value(), self.spinBox_Y.value()],
            'grid_size': [self.spinBox_rows.value(), self.spinBox_cols.value()],
            'frame_size_selector': self._current_frame_size_selector(),
            'pixel_size': float(self.doubleSpinBox_pixelSize.value()),
            'dwell_time_selector': self._current_dwell_time_selector(),
            'magnification': self._current_magnification_from_widgets(),
        }

    def _apply_widget_settings(self, settings):
        frame_size_selector = int(settings['frame_size_selector'])
        pixel_size = float(settings['pixel_size'])
        magnification = int(settings.get('magnification', 1))
        if magnification <= 0:
            frame_width_px = self.sem.STORE_RES[frame_size_selector][0]
            magnification = max(
                1,
                int(round(
                    self.sem.MAG_PX_SIZE_FACTOR
                    / (frame_width_px * pixel_size))))
        self._syncing_stub_resolution = True
        try:
            self.spinBox_X.setValue(int(round(settings['centre_sx_sy'][0])))
            self.spinBox_Y.setValue(int(round(settings['centre_sx_sy'][1])))
            self.spinBox_rows.setValue(int(settings['grid_size'][0]))
            self.spinBox_cols.setValue(int(settings['grid_size'][1]))
            self.comboBox_frameSize.setCurrentIndex(frame_size_selector)
            self.spinBox_magnification.setValue(magnification)
            self.doubleSpinBox_pixelSize.setValue(pixel_size)
            self.comboBox_dwellTime.setCurrentIndex(
                int(settings['dwell_time_selector']))
        finally:
            self._syncing_stub_resolution = False
        self.update_dimension_and_duration_display()

    def get_selected_stub_ovm(self, lm_mode=None):
        return self.ovm[self._stub_mode_key(lm_mode)]

    def _set_dialog_controls_enabled(self, enabled):
        self.pushButton_acquire.setEnabled(enabled)
        self.pushButton_abort.setEnabled(not enabled)
        self.buttonBox.setEnabled(enabled)
        self.pushButton_centreCurrentStage.setEnabled(enabled)
        self.checkBox_LmMode.setEnabled(enabled and self.sem.has_lm_mode())
        self.spinBox_X.setEnabled(enabled)
        self.spinBox_Y.setEnabled(enabled)
        self.spinBox_rows.setEnabled(enabled)
        self.spinBox_cols.setEnabled(enabled)
        self.comboBox_frameSize.setEnabled(enabled)
        self.spinBox_magnification.setEnabled(enabled)
        self.doubleSpinBox_pixelSize.setEnabled(enabled)
        self.comboBox_dwellTime.setEnabled(enabled)
        self.comboBox_savedImagingCondition.setEnabled(enabled)
        self.pushButton_applySavedImagingCondition.setEnabled(enabled)
        self.pushButton_manageImagingConditions.setEnabled(enabled)
        self.pushButton_saveCurrentImagingConditionAs.setEnabled(enabled)
        if enabled:
            self.imaging_condition_controller.update_live_sem_button_state()
        else:
            self.pushButton_getFromSEM.setEnabled(False)

    def process_thread_signal(self):
        """Process commands from the acquisition worker thread."""
        cmd = self.stub_dlg_trigger.queue.get()
        msg = cmd['msg']
        args = cmd['args']
        kwargs = cmd['kwargs']
        if msg == 'UPDATE XY':
            self.viewport_trigger.transmit('UPDATE XY')
        elif msg == 'DRAW VP':
            self.viewport_trigger.transmit('DRAW VP')
        elif msg == 'UPDATE PROGRESS':
            percentage = int(str(args[0]))
            self.progressBar.setValue(percentage)
        elif msg == 'STUB OV SUCCESS':
            self.viewport_trigger.transmit(
                'STUB OV SUCCESS',
                self.current_stub_mode_key,
                self.current_stub_previous_state)
            self._set_dialog_controls_enabled(True)
            QMessageBox.information(
                self, 'Stub Overview acquisition complete',
                'The stub overview was completed successfully.',
                QMessageBox.Ok)
            self.acq_in_progress = False
            self.close()
        elif msg == 'STUB OV FAILURE':
            self._restore_previous_stub_state()
            self.viewport_trigger.transmit(
                'STUB OV FAILURE',
                self.current_stub_mode_key)
            self._set_dialog_controls_enabled(True)
            QMessageBox.warning(
                self, 'Error during stub overview acquisition',
                'An error occurred during the acquisition of the stub '
                'overview mosaic: ' + self.error_msg_from_acq_thread,
                QMessageBox.Ok)
            self.error_msg_from_acq_thread = ''
            self.acq_in_progress = False
            self.close()
        elif msg == 'STUB OV ABORT':
            self._restore_previous_stub_state()
            self.viewport_trigger.transmit(
                'STUB OV ABORTED',
                self.current_stub_mode_key)
            self._set_dialog_controls_enabled(True)
            QMessageBox.information(
                self, 'Stub Overview acquisition aborted',
                'The stub overview acquisition was aborted.',
                QMessageBox.Ok)
            self.acq_in_progress = False
            self.close()
        else:
            self.error_msg_from_acq_thread = msg

    def _capture_previous_stub_state(self, stub_ovm, mode_key):
        return {
            'mode_key': mode_key,
            'source_kind': stub_workflow.stub_source_kind(
                mode_key == 'stub_lm'),
            'vp_file_path': stub_ovm.vp_file_path,
            'centre_sx_sy': list(stub_ovm.centre_sx_sy),
            'grid_size': list(stub_ovm.size),
            'frame_size_selector': int(stub_ovm.frame_size_selector),
            'pixel_size': stub_ovm.pixel_size,
            'dwell_time_selector': int(stub_ovm.dwell_time_selector),
            'image_size_px': list(stub_ovm.size_p()),
        }

    def _restore_previous_stub_state(self):
        if self.current_stub_previous_state is None:
            return
        prev_state = self.current_stub_previous_state
        stub_ovm = self.ovm[prev_state['mode_key']]
        stub_ovm.size = prev_state['grid_size']
        stub_ovm.centre_sx_sy = prev_state['centre_sx_sy']
        stub_ovm.frame_size_selector = prev_state['frame_size_selector']
        stub_ovm.pixel_size = prev_state['pixel_size']
        stub_ovm.dwell_time_selector = prev_state['dwell_time_selector']
        stub_ovm.vp_file_path = prev_state['vp_file_path']
        self.viewport_trigger.transmit('DRAW VP')

    def _confirm_stub_overlap(self, overlaps):
        if not overlaps:
            return True
        overlap_lines = '\n'.join(f'- {entry["label"]}' for entry in overlaps)
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle('Stub overlap detected')
        msg_box.setText(
            f'The requested stub overlaps {len(overlaps)} existing stub region(s).')
        msg_box.setInformativeText(
            overlap_lines + '\n\nProceed with acquisition anyway?')
        proceed_button = msg_box.addButton('Proceed', QMessageBox.AcceptRole)
        cancel_button = msg_box.addButton('Cancel', QMessageBox.RejectRole)
        msg_box.setDefaultButton(cancel_button)
        msg_box.exec()
        return msg_box.clickedButton() == proceed_button

    def set_centre_to_current_stage_coordinates(self):
        try:
            current_stage_xy = self.stage.get_xy()
        except Exception:
            utils.log_exception(
                'Failed to read current stage coordinates for stub overview.')
            QMessageBox.warning(
                self, 'Stage position unavailable',
                'Could not read the current stage coordinates from the '
                'microscope.',
                QMessageBox.Ok)
            return

        try:
            stage_x, stage_y = current_stage_xy[:2]
        except (TypeError, ValueError, IndexError):
            QMessageBox.warning(
                self, 'Stage position unavailable',
                'The microscope did not return a valid X/Y stage position.',
                QMessageBox.Ok)
            return

        if stage_x is None or stage_y is None:
            QMessageBox.warning(
                self, 'Stage position unavailable',
                'The microscope did not return a valid X/Y stage position.',
                QMessageBox.Ok)
            return

        self.spinBox_X.setValue(int(round(stage_x)))
        self.spinBox_Y.setValue(int(round(stage_y)))

    def _sync_pixel_size_from_magnification(self):
        if self._syncing_stub_resolution:
            return
        frame_width_px = self._current_frame_size()[0]
        magnification = self._current_magnification_from_widgets()
        pixel_size = (
            self.sem.MAG_PX_SIZE_FACTOR
            / (magnification * frame_width_px))
        self._syncing_stub_resolution = True
        try:
            self.doubleSpinBox_pixelSize.setValue(pixel_size)
        finally:
            self._syncing_stub_resolution = False
        self.update_dimension_and_duration_display()

    def set_magnification(self):
        self._sync_pixel_size_from_magnification()

    def set_pixel_size(self):
        if self._syncing_stub_resolution:
            return
        pixel_size = self.doubleSpinBox_pixelSize.value()
        if pixel_size <= 0:
            return
        frame_width_px = self._current_frame_size()[0]
        magnification = max(
            1,
            int(round(
                self.sem.MAG_PX_SIZE_FACTOR / (frame_width_px * pixel_size))))
        self._syncing_stub_resolution = True
        try:
            self.spinBox_magnification.setValue(magnification)
        finally:
            self._syncing_stub_resolution = False
        self.update_dimension_and_duration_display()

    def update_settings_from_ovm(self):
        if self.current_stub_mode_key is not None:
            self._pending_stub_settings[self.current_stub_mode_key] = (
                self._current_widget_settings())
        next_mode_key = self._stub_mode_key()
        if next_mode_key not in self._pending_stub_settings:
            self._pending_stub_settings[next_mode_key] = (
                self._build_settings_from_stub_ovm(next_mode_key))
        self.current_stub_mode_key = next_mode_key
        self._apply_widget_settings(self._pending_stub_settings[next_mode_key])
        self.imaging_condition_controller.update_live_sem_button_state()

    def update_dimension_and_duration_display(self):
        rows = self.spinBox_rows.value()
        cols = self.spinBox_cols.value()
        frame_size = self._current_frame_size()
        tile_width = frame_size[0]
        tile_height = frame_size[1]
        overlap = self.get_selected_stub_ovm().overlap
        pixel_size = self.doubleSpinBox_pixelSize.value()
        frame_size_selector = self._current_frame_size_selector()
        dwell_time_selector = self._current_dwell_time_selector()
        cycle_time = (
            self.sem.CYCLE_TIME[frame_size_selector][dwell_time_selector]
            + 0.2)
        motor_move_time = 0
        try:
            if cols >= 2:
                step_x = (tile_width - overlap) * pixel_size / 1000
                motor_move_time = self.stage.stage_move_duration(
                    0, 0, step_x, 0)
            elif rows >= 2:
                step_y = (tile_height - overlap) * pixel_size / 1000
                motor_move_time = self.stage.stage_move_duration(
                    0, 0, 0, step_y)
        except Exception:
            motor_move_time = 0
        width = int(
            (cols * tile_width - (cols - 1) * overlap) * pixel_size / 1000)
        height = int(
            (rows * tile_height - (rows - 1) * overlap) * pixel_size / 1000)
        duration = int(round(
            (rows * cols * (cycle_time + motor_move_time) + 30) / 60))
        self.label_dimension.setText(f'{width} um x {height} um')
        self.label_duration.setText(f'Up to ~{duration} min')

    def start_stub_ov_acquisition(self):
        """Acquire the stub overview. Acquisition routine runs in a thread."""
        if self.acq.acq_in_progress:
            QMessageBox.information(
                self, 'Operation in progress',
                'Another operation is currently running. Please wait for it '
                'to finish before starting a stub overview acquisition.',
                QMessageBox.Ok)
            return

        lm_mode = self.checkBox_LmMode.isChecked()
        if not (lm_mode or self.sem.is_eht_on()):
            QMessageBox.warning(
                self, 'EHT off',
                'EHT / high voltage is off. Please turn '
                'it on before starting the acquisition.',
                QMessageBox.Ok)
            return

        requested_settings = self._current_widget_settings()
        centre_sx_sy = tuple(requested_settings['centre_sx_sy'])
        grid_size = list(requested_settings['grid_size'])
        frame_size_selector = int(requested_settings['frame_size_selector'])
        frame_size = self.sem.STORE_RES[frame_size_selector]
        pixel_size = float(requested_settings['pixel_size'])
        dwell_time_selector = int(requested_settings['dwell_time_selector'])
        mode_key = self._stub_mode_key(lm_mode)
        stub_ovm = self.get_selected_stub_ovm(lm_mode)
        candidate_bbox_d = stub_workflow.stub_candidate_bbox_d(
            stub_ovm.cs,
            centre_sx_sy,
            grid_size,
            frame_size[:2],
            stub_ovm.overlap,
            pixel_size)
        overlaps = stub_workflow.overlapping_stub_regions(
            stub_ovm.cs,
            self.imported,
            stub_ovm,
            candidate_bbox_d,
            stub_workflow.stub_source_kind(lm_mode))
        if not self._confirm_stub_overlap(overlaps):
            return

        self.acq_in_progress = True
        self.current_stub_mode_key = mode_key
        self.current_stub_previous_state = self._capture_previous_stub_state(
            stub_ovm, mode_key)

        stub_ovm.frame_size_selector = frame_size_selector
        stub_ovm.pixel_size = pixel_size
        stub_ovm.dwell_time_selector = dwell_time_selector
        stub_ovm.size = grid_size
        stub_ovm.centre_sx_sy = centre_sx_sy

        if lm_mode:
            self.sem.set_em_mode(lm_mode=True)
            self.sem.apply_frame_settings(
                stub_ovm.frame_size_selector,
                stub_ovm.pixel_size,
                stub_ovm.dwell_time)
            stub_ovm.pixel_size = self.sem.get_pixel_size()
            requested_settings['pixel_size'] = float(stub_ovm.pixel_size)
            frame_width_px = self.sem.STORE_RES[frame_size_selector][0]
            requested_settings['magnification'] = max(
                1,
                int(round(
                    self.sem.MAG_PX_SIZE_FACTOR
                    / (frame_width_px * stub_ovm.pixel_size))))
            self._pending_stub_settings[mode_key] = requested_settings
            self._apply_widget_settings(requested_settings)
        else:
            self._pending_stub_settings[mode_key] = requested_settings

        self.acq.acq_in_progress = True
        self.acq.acq_run_mode = 'stub_overview'
        self.viewport_trigger.transmit(
            'CTRL: Acquisition of stub overview image started.')
        self._set_dialog_controls_enabled(False)
        self.progressBar.setValue(0)
        self.viewport_trigger.transmit('RESTRICT GUI')
        self.viewport_trigger.transmit('STATUS BUSY STUB')
        QApplication.processEvents()
        utils.run_log_thread(
            acq_func.acquire_stub_ov,
            self.sem,
            self.stage,
            stub_ovm,
            self.acq,
            self.img_inspector,
            self.stub_dlg_trigger,
            self.abort_queue)

    def abort(self):
        if self.abort_queue.empty():
            self.abort_queue.put('ABORT')
            self.pushButton_abort.setEnabled(False)

    def closeEvent(self, event):
        if not self.acq_in_progress:
            event.accept()
        else:
            event.ignore()
