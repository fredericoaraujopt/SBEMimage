import numpy as np

from qtpy.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from ImagingConditions import (
    ImagingConditionCompatibilityError,
    ImagingConditionDuplicateNameError,
    ImagingConditionPreset,
)
from dialog.ImagingConditionManagerDlg import ImagingConditionManagerDlg


class BaseImagingConditionAdapter:
    source_dialog = ''

    def __init__(self, dialog, sem):
        self.dialog = dialog
        self.sem = sem

    def supports_live_sem_read(self):
        return (
            self.sem.device_name == 'Mock SEM'
            or (
                self.sem.device_name.startswith('ZEISS')
                and 'MultiSEM' not in self.sem.device_name))

    def _capture_preset(self, frame_size_selector, pixel_size_nm,
                        dwell_time_selector):
        return ImagingConditionPreset(
            source_dialog=self.source_dialog,
            source_sem_device=self.sem.device_name,
            frame_size_px=list(self.sem.STORE_RES[frame_size_selector][:2]),
            pixel_size_nm=float(pixel_size_nm),
            dwell_time_us=float(self.sem.DWELL_TIME[dwell_time_selector]),
        )

    def _resolve_frame_size_selector(self, preset):
        target_frame = [int(preset.frame_size_px[0]), int(preset.frame_size_px[1])]
        for index, frame_size in enumerate(self.sem.STORE_RES):
            if list(frame_size[:2]) == target_frame:
                return index
        raise ImagingConditionCompatibilityError(
            f'Frame size {target_frame[0]} x {target_frame[1]} is not '
            f'available on {self.sem.device_name}.')

    def _resolve_dwell_time_selector(self, preset):
        for index, dwell_time in enumerate(self.sem.DWELL_TIME):
            if np.isclose(float(dwell_time), float(preset.dwell_time_us)):
                return index
        raise ImagingConditionCompatibilityError(
            f'Dwell time {preset.dwell_time_us} us is not available on '
            f'{self.sem.device_name}.')

    def load_from_sem(self):
        if not self.supports_live_sem_read():
            raise ImagingConditionCompatibilityError(
                'Live SEM imaging-condition readback is not available for '
                f'{self.sem.device_name}.')
        frame_size_selector = self.sem.get_frame_size_selector()
        dwell_time_selector = self.sem.get_scan_rate()
        if frame_size_selector is False or dwell_time_selector is False:
            raise ImagingConditionCompatibilityError(
                'Current SEM imaging conditions could not be read.')
        frame_size_selector = int(frame_size_selector)
        dwell_time_selector = int(dwell_time_selector)
        if not (0 <= frame_size_selector < len(self.sem.STORE_RES)):
            raise ImagingConditionCompatibilityError(
                'Current SEM frame size is not supported.')
        if not (0 <= dwell_time_selector < len(self.sem.DWELL_TIME)):
            raise ImagingConditionCompatibilityError(
                'Current SEM dwell time is not supported.')
        return self._capture_preset(
            frame_size_selector,
            self.sem.get_pixel_size(),
            dwell_time_selector)


class GridImagingConditionAdapter(BaseImagingConditionAdapter):
    source_dialog = 'grid'

    def capture_from_widgets(self):
        return self._capture_preset(
            self.dialog.comboBox_tileSize.currentIndex(),
            self.dialog.doubleSpinBox_pixelSize.value(),
            self.dialog.comboBox_dwellTime.currentIndex())

    def apply_to_widgets(self, preset):
        frame_size_selector = self._resolve_frame_size_selector(preset)
        dwell_time_selector = self._resolve_dwell_time_selector(preset)
        self.dialog.comboBox_tileSize.setCurrentIndex(frame_size_selector)
        self.dialog.doubleSpinBox_pixelSize.setValue(preset.pixel_size_nm)
        self.dialog.comboBox_dwellTime.setCurrentIndex(dwell_time_selector)
        self.dialog.show_frame_size_and_dose()


class OverviewImagingConditionAdapter(BaseImagingConditionAdapter):
    source_dialog = 'overview'

    def capture_from_widgets(self):
        return self._capture_preset(
            self.dialog.comboBox_frameSize.currentIndex(),
            self.dialog.doubleSpinBox_pixelSize.value(),
            self.dialog.comboBox_dwellTime.currentIndex())

    def apply_to_widgets(self, preset):
        frame_size_selector = self._resolve_frame_size_selector(preset)
        dwell_time_selector = self._resolve_dwell_time_selector(preset)
        frame_width_px = self.sem.STORE_RES[frame_size_selector][0]
        magnification = max(
            1,
            int(round(
                self.sem.MAG_PX_SIZE_FACTOR
                / (frame_width_px * preset.pixel_size_nm))))
        self.dialog.comboBox_frameSize.setCurrentIndex(frame_size_selector)
        self.dialog.spinBox_magnification.setValue(magnification)
        self.dialog.comboBox_dwellTime.setCurrentIndex(dwell_time_selector)
        self.dialog.update_pixel_size()


class StubImagingConditionAdapter(BaseImagingConditionAdapter):
    @property
    def source_dialog(self):
        if self.dialog.checkBox_LmMode.isChecked():
            return 'stub_lm'
        return 'stub'

    def supports_live_sem_read(self):
        return (
            super().supports_live_sem_read()
            and not self.dialog.checkBox_LmMode.isChecked())

    def capture_from_widgets(self):
        return self._capture_preset(
            self.dialog.comboBox_frameSize.currentIndex(),
            self.dialog.doubleSpinBox_pixelSize.value(),
            self.dialog.comboBox_dwellTime.currentIndex())

    def apply_to_widgets(self, preset):
        frame_size_selector = self._resolve_frame_size_selector(preset)
        dwell_time_selector = self._resolve_dwell_time_selector(preset)
        frame_width_px = self.sem.STORE_RES[frame_size_selector][0]
        magnification = max(
            1,
            int(round(
                self.sem.MAG_PX_SIZE_FACTOR
                / (frame_width_px * preset.pixel_size_nm))))
        self.dialog.comboBox_frameSize.setCurrentIndex(frame_size_selector)
        self.dialog.spinBox_magnification.setValue(magnification)
        self.dialog.comboBox_dwellTime.setCurrentIndex(dwell_time_selector)
        self.dialog.update_dimension_and_duration_display()


class ImagingConditionController:
    def __init__(self, dialog, store, adapter, combo_box, apply_button,
                 manage_button, save_as_button, live_sem_button=None):
        self.dialog = dialog
        self.store = store
        self.adapter = adapter
        self.combo_box = combo_box
        self.apply_button = apply_button
        self.manage_button = manage_button
        self.save_as_button = save_as_button
        self.live_sem_button = live_sem_button

        self.apply_button.clicked.connect(self.apply_selected_preset)
        self.manage_button.clicked.connect(self.open_manager)
        self.save_as_button.clicked.connect(self.save_current_as)
        if self.live_sem_button is not None:
            self.live_sem_button.clicked.connect(self.apply_live_sem_settings)
        self.refresh_presets()
        self.update_live_sem_button_state()

    def refresh_presets(self, selected_preset_id=None):
        if selected_preset_id is None:
            selected_preset_id = self.combo_box.currentData()
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        self.combo_box.addItem('Select saved settings...', None)
        select_index = 0
        for index, preset in enumerate(self.store.list_presets(), start=1):
            self.combo_box.addItem(preset.name, preset.preset_id)
            if preset.preset_id == selected_preset_id:
                select_index = index
        self.combo_box.setCurrentIndex(select_index)
        self.combo_box.blockSignals(False)

    def update_live_sem_button_state(self):
        if self.live_sem_button is None:
            return
        self.live_sem_button.setEnabled(self.adapter.supports_live_sem_read())

    def _warn(self, title, message):
        QMessageBox.warning(self.dialog, title, message, QMessageBox.Ok)

    def apply_selected_preset(self):
        preset_id = self.combo_box.currentData()
        if preset_id is None:
            self._warn(
                'No saved imaging condition selected',
                'Please choose a saved imaging condition first.')
            return
        try:
            preset = self.store.get_preset(preset_id)
            self.adapter.apply_to_widgets(preset)
        except ImagingConditionCompatibilityError as exc:
            self._warn('Preset incompatible', str(exc))
        except Exception as exc:
            self._warn('Preset could not be applied', str(exc))

    def apply_live_sem_settings(self):
        try:
            preset = self.adapter.load_from_sem()
            self.adapter.apply_to_widgets(preset)
        except ImagingConditionCompatibilityError as exc:
            self._warn('SEM readback unavailable', str(exc))
        except Exception as exc:
            self._warn('SEM readback failed', str(exc))

    def _prompt_for_name(self, initial_name=''):
        name, ok = QInputDialog.getText(
            self.dialog,
            'Save imaging condition',
            'Preset name:',
            QLineEdit.Normal,
            initial_name)
        if not ok:
            return None
        name = name.strip()
        if not name:
            self._warn(
                'Preset name required',
                'Please provide a name for the imaging condition.')
            return None
        return name

    def save_current_as(self):
        name = self._prompt_for_name()
        if name is None:
            return
        preset = self.adapter.capture_from_widgets()
        try:
            saved_preset = self.store.save_new_preset(name, preset)
        except ImagingConditionDuplicateNameError:
            existing = self.store.find_preset_by_name(name)
            result = QMessageBox.question(
                self.dialog,
                'Overwrite imaging condition',
                f'A saved imaging condition named "{name}" already exists.\n'
                'Overwrite it?',
                QMessageBox.Ok | QMessageBox.Cancel)
            if result != QMessageBox.Ok:
                return
            preset.name = name
            saved_preset = self.store.update_preset(existing.preset_id, preset)
        except Exception as exc:
            self._warn('Preset could not be saved', str(exc))
            return
        self.refresh_presets(saved_preset.preset_id)

    def open_manager(self):
        dialog = ImagingConditionManagerDlg(self.store, self.dialog)
        dialog.exec()
        self.refresh_presets()
