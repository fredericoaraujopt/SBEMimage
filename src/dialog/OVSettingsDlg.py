from qtpy.QtCore import Qt
from qtpy.QtWidgets import QComboBox, QDialog, QGroupBox, QPushButton
from qtpy.uic import loadUi

import utils
from dialog.ImagingConditionSupport import (
    ImagingConditionController,
    OverviewImagingConditionAdapter,
)


class OVSettingsDlg(QDialog):
    """Dialog window to adjust settings for overview images, and to add/delete
    overview images.
    """

    def __init__(self, ovm, sem, current_ov, main_controls_trigger,
                 imaging_condition_store):
        super().__init__()
        self.ovm = ovm
        self.sem = sem
        self.current_ov = current_ov
        self.main_controls_trigger = main_controls_trigger
        self.imaging_condition_store = imaging_condition_store
        loadUi('gui/overview_settings_dlg.ui', self)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowIcon(utils.get_window_icon())
        # Set up OV selector
        self.comboBox_OVSelector.addItems(self.ovm.ov_selector_list())
        self.comboBox_OVSelector.setCurrentIndex(self.current_ov)
        self.comboBox_OVSelector.currentIndexChanged.connect(self.change_ov)
        if self.ovm[self.current_ov].active:
            self.radioButton_active.setChecked(True)
        else:
            self.radioButton_inactive.setChecked(True)
        self.radioButton_active.toggled.connect(self.update_active_status)
        self.update_active_status()
        # Set up other comboboxes
        store_res_list = [
            '%d × %d' % (res[0], res[1]) for res in self.sem.STORE_RES]
        self.comboBox_frameSize.addItems(store_res_list)
        self.comboBox_frameSize.currentIndexChanged.connect(
            self.update_pixel_size)
        self.comboBox_dwellTime.addItems(map(str, self.sem.DWELL_TIME))
        self.comboBox_bitDepth.addItems(['8 bit', '16 bit'])
        # Update pixel size when mag changed
        self.spinBox_magnification.valueChanged.connect(self.update_pixel_size)
        # Button to clear OV image in Viewport
        self.pushButton_clearViewportImage.clicked.connect(
            self.clear_viewport_image)
        # Save, add and delete buttons
        self.pushButton_save.clicked.connect(self.save_current_settings)
        self.pushButton_addOV.clicked.connect(self.add_ov)
        self.pushButton_deleteOV.clicked.connect(self.delete_ov)
        self.update_buttons()
        self.show_current_settings()
        self.show_frame_size()
        self._setup_imaging_condition_controls()
        self.setFixedSize(self.size())
        self.show()

    def _shift_widgets_y(self, widgets, delta):
        for widget in widgets:
            widget.move(widget.x(), widget.y() + delta)

    def _setup_imaging_condition_controls(self):
        dialog_width = max(self.width(), 248)
        panel_left = 10
        full_width = dialog_width - 20
        panel_top = self.comboBox_bitDepth.y() + self.comboBox_bitDepth.height() + 10
        panel_height = 138
        shift_delta = panel_top + panel_height + 10 - self.label_oi.y()
        self.resize(dialog_width, self.height() + shift_delta)

        self.groupBox_savedImagingSettings = QGroupBox(
            'Saved imaging settings', self)
        self.groupBox_savedImagingSettings.setGeometry(
            panel_left, panel_top, full_width, panel_height)
        inner_left = 10
        inner_width = full_width - 20
        apply_width = 118
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
        self.pushButton_getFromSEM = QPushButton(
            'Get current settings from SEM', self.groupBox_savedImagingSettings)
        self.pushButton_getFromSEM.setGeometry(
            inner_left, 108, inner_width, 23)

        self._shift_widgets_y(
            [
                self.label_oi,
                self.spinBox_acqInterval,
                self.label_oi_2,
                self.spinBox_acqIntervalOffset,
                self.label_expl1,
                self.label_expl2,
                self.radioButton_active,
                self.radioButton_inactive,
                self.pushButton_clearViewportImage,
                self.line,
                self.pushButton_save,
                self.pushButton_addOV,
                self.pushButton_deleteOV,
                self.buttonBox,
            ],
            shift_delta)

        self.label_expl1.setGeometry(10, self.label_expl1.y(), full_width, self.label_expl1.height())
        self.label_expl2.setGeometry(10, self.label_expl2.y(), full_width, self.label_expl2.height())
        self.pushButton_clearViewportImage.setGeometry(
            10, self.pushButton_clearViewportImage.y(), full_width,
            self.pushButton_clearViewportImage.height())
        self.line.setGeometry(10, self.line.y(), full_width, self.line.height())
        self.pushButton_save.setGeometry(
            10, self.pushButton_save.y(), full_width, self.pushButton_save.height())
        half_width = int((full_width - 8) / 2)
        self.pushButton_addOV.setGeometry(
            10, self.pushButton_addOV.y(), half_width, self.pushButton_addOV.height())
        self.pushButton_deleteOV.setGeometry(
            18 + half_width, self.pushButton_deleteOV.y(),
            full_width - half_width - 8, self.pushButton_deleteOV.height())
        self.buttonBox.move(int((dialog_width - self.buttonBox.width()) / 2),
                            self.buttonBox.y())

        adapter = OverviewImagingConditionAdapter(self, self.sem)
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
        # If current OV is inactive, disable GUI elements
        b = self.radioButton_active.isChecked()
        self.comboBox_frameSize.setEnabled(b)
        self.spinBox_magnification.setEnabled(b)
        self.comboBox_dwellTime.setEnabled(b)
        self.spinBox_acqInterval.setEnabled(b)
        self.spinBox_acqIntervalOffset.setEnabled(b)

    def show_current_settings(self):
        self.comboBox_frameSize.setCurrentIndex(
            self.ovm[self.current_ov].frame_size_selector)
        self.spinBox_magnification.setValue(
            int(self.ovm[self.current_ov].magnification))
        self.doubleSpinBox_pixelSize.setValue(
            self.ovm[self.current_ov].pixel_size)
        self.comboBox_dwellTime.setCurrentIndex(
            self.ovm[self.current_ov].dwell_time_selector)
        self.comboBox_bitDepth.setCurrentIndex(
            self.ovm[self.current_ov].bit_depth_selector)
        self.spinBox_acqInterval.setValue(
            self.ovm[self.current_ov].acq_interval)
        self.spinBox_acqIntervalOffset.setValue(
            self.ovm[self.current_ov].acq_interval_offset)

    def update_pixel_size(self):
        """Calculate pixel size from current magnification and display it."""
        pixel_size = (
            self.sem.MAG_PX_SIZE_FACTOR
            / (self.sem.STORE_RES[self.comboBox_frameSize.currentIndex()][0]
            * self.spinBox_magnification.value()))
        self.doubleSpinBox_pixelSize.setValue(pixel_size)
        self.show_frame_size()

    def show_frame_size(self):
        """Calculate and show physical frame size depending on current frame resolution and pixel size."""
        frame_size_selector = self.comboBox_frameSize.currentIndex()
        pixel_size = self.doubleSpinBox_pixelSize.value()
        width = self.sem.STORE_RES[frame_size_selector][0] * pixel_size / 1000
        height = self.sem.STORE_RES[frame_size_selector][1] * pixel_size / 1000
        self.label_frameSize.setText(f'{width:.1f} × {height:.1f}')

    def change_ov(self):
        self.current_ov = self.comboBox_OVSelector.currentIndex()
        if self.ovm[self.current_ov].active:
            self.radioButton_active.setChecked(True)
        else:
            self.radioButton_inactive.setChecked(True)
        self.update_active_status()
        self.update_buttons()
        self.show_current_settings()
        self.show_frame_size()

    def update_buttons(self):
        """Update labels on buttons and disable/enable delete button depending
        on which OV is selected. OV 0 cannot be deleted. Only the last OV (with
        the highest index) can be deleted. Reason: preserve identities of
        overviews during stack acq.
        """
        if self.current_ov == 0:
            self.pushButton_deleteOV.setEnabled(False)
        else:
            self.pushButton_deleteOV.setEnabled(
                self.current_ov == self.ovm.number_ov - 1)
        # Show current OV number on delete and save buttons
        self.pushButton_save.setText(
            f'Save settings for OV {self.current_ov}')
        self.pushButton_deleteOV.setText(
            f'Delete OV {self.current_ov}')

    def clear_viewport_image(self):
        self.ovm[self.current_ov].vp_file_path = ''
        self.main_controls_trigger.transmit('OV SETTINGS CHANGED')

    def save_current_settings(self):
        self.ovm[self.current_ov].active = self.radioButton_active.isChecked()
        # Save previous values of frame size and magnification. If the new
        # values are different from the previous ones, reset current OV image
        # shown in Viewport.
        self.prev_frame_size = self.ovm[self.current_ov].frame_size_selector
        self.prev_mag = self.ovm[self.current_ov].magnification
        self.ovm[self.current_ov].frame_size_selector = (
            self.comboBox_frameSize.currentIndex())
        self.ovm[self.current_ov].magnification = (
            self.spinBox_magnification.value())
        self.ovm[self.current_ov].dwell_time_selector = (
            self.comboBox_dwellTime.currentIndex())
        self.ovm[self.current_ov].bit_depth_selector = (
            self.comboBox_bitDepth.currentIndex())
        self.ovm[self.current_ov].acq_interval = (
            self.spinBox_acqInterval.value())
        self.ovm[self.current_ov].acq_interval_offset = (
            self.spinBox_acqIntervalOffset.value())
        if ((self.comboBox_frameSize.currentIndex() != self.prev_frame_size)
            or (self.spinBox_magnification.value() != self.prev_mag)):
            # Reset path to current overview image in Viewport
            self.ovm[self.current_ov].vp_file_path = ''
        self.main_controls_trigger.transmit('OV SETTINGS CHANGED')

    def add_ov(self):
        frame_size_selector = self.comboBox_frameSize.currentIndex()
        frame_size = self.comboBox_frameSize.currentText()
        pixel_size = self.doubleSpinBox_pixelSize.value()
        dwell_time_selector = self.comboBox_dwellTime.currentIndex()
        dwell_time = self.comboBox_dwellTime.currentText()
        bit_depth_selector = self.comboBox_bitDepth.currentIndex()
        acq_interval = self.spinBox_acqInterval.value()
        acq_interval_offset = self.spinBox_acqIntervalOffset.value()
        self.ovm.add_new_overview(frame_size=frame_size, frame_size_selector=frame_size_selector, pixel_size=pixel_size,
                                  dwell_time=dwell_time, dwell_time_selector=dwell_time_selector,
                                  bit_depth_selector=bit_depth_selector,
                                  acq_interval=acq_interval, acq_interval_offset=acq_interval_offset)
        self.current_ov = self.ovm.number_ov - 1
        # Update OV selector:
        self.comboBox_OVSelector.blockSignals(True)
        self.comboBox_OVSelector.clear()
        self.comboBox_OVSelector.addItems(self.ovm.ov_selector_list())
        self.comboBox_OVSelector.setCurrentIndex(self.current_ov)
        self.comboBox_OVSelector.blockSignals(False)
        self.change_ov()
        self.main_controls_trigger.transmit('OV SETTINGS CHANGED')

    def delete_ov(self):
        self.ovm.delete_overview()
        self.current_ov = self.ovm.number_ov - 1
        # Update OV selector:
        self.comboBox_OVSelector.blockSignals(True)
        self.comboBox_OVSelector.clear()
        self.comboBox_OVSelector.addItems(self.ovm.ov_selector_list())
        self.comboBox_OVSelector.setCurrentIndex(self.current_ov)
        self.comboBox_OVSelector.blockSignals(False)
        self.change_ov()
        self.main_controls_trigger.transmit('OV SETTINGS CHANGED')
