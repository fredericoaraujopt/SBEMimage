import os
from configparser import ConfigParser
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QDialog, QMessageBox, QCheckBox, QLabel
from qtpy.uic import loadUi

import utils
from constants import VERSION
from dialog.DeviceSelectionDlg import DeviceSelectionDlg


class ConfigDlg(QDialog):
    """Start-up dialog window that lets user select a configuration file.

    The previously used configuration file is preselected in the list widget.
    The option to load the default configuration (default.ini, system.cfg and
    presets) is shown as "Default Configuration".
    When "Default Configuration" is selected, clicking on "SEM/Microtome setup"
    opens a secondary dialog window, in which the user can select device presets
    for different SEM and microtome models including mocks.
    """

    def __init__(self):
        super().__init__()
        self.device_presets_selection = [None, None]
        self.load_presets_enabled = False
        loadUi('gui/config_dlg.ui', self)
        self.setWindowIcon(utils.get_window_icon())
        if 'dev' in VERSION.lower():
            title = f'DEVELOPMENT VERSION ({VERSION})'
        else:
            title = f'Version {VERSION}'
        self.label_version.setText(title)
        self.labelIcon.setPixmap(QPixmap('img/logo.png'))
        self.label_website.setText('<a href="https://github.com/SBEMimage">'
                                   'https://github.com/SBEMimage</a>')
        self.label_website.setOpenExternalLinks(True)
        self.checkBox_useKlabUi = QCheckBox('klab gui')
        self.checkBox_useKlabUi.setToolTip(
            'Toggle experimental KLAB styling for this session startup.')
        self.labelKlabAnim = QLabel('')
        self.labelKlabAnim.setVisible(False)
        self.labelKlabAnim.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.labelKlabAnim.setWordWrap(True)
        self.labelKlabAnim.setStyleSheet('font-family: Consolas, monospace;')
        self.klab_anim_frames = [
            "  \\  /\n<(o )___\n  /  \\",
            "   --\n<(o )___\n   --",
            "  /  \\\n<(o )___\n  \\  /",
            "   --\n<(o )___\n   --",
        ]
        self.klab_anim_index = 0
        self.klab_anim_timer = QTimer(self)
        self.klab_anim_timer.setInterval(150)
        self.klab_anim_timer.timeout.connect(self._animate_klab_label)
        self.checkBox_useKlabUi.toggled.connect(
            self._update_klab_animation_state)
        self.gridLayout.addWidget(self.checkBox_useKlabUi, 6, 0)
        self.gridLayout.addWidget(self.labelKlabAnim, 7, 0)
        self.gridLayout.addWidget(self.buttonBox, 8, 0)
        self.checkBox_useKlabUi.setChecked(False)
        self._update_klab_animation_state(self.checkBox_useKlabUi.isChecked())
        self.adjustSize()
        self.show()
        self.abort = False
        # Connect button to load device selection dialog
        self.pushButton_deviceSelection.clicked.connect(
           self.open_device_selection_dlg)

        # If the 'cfg' folder does not exist yet (first start of SBEMimage),
        # create it and put empty file 'status.dat' into it.
        if not os.path.exists('cfg'):
            os.makedirs('cfg')
            open('cfg/status.dat', 'a').close()

        # Populate the list widget with existing .ini files
        inifile_list = []
        for file in os.listdir('cfg'):
            if file.endswith('.ini'):
                inifile_list.append(file)
        # Create entry "Default Configuration". Selecting it will
        # load default.ini, system.cfg, and presets
        inifile_list.append('Default Configuration')

        self.listWidget_filelist.addItems(inifile_list)
        self.listWidget_filelist.itemSelectionChanged.connect(
            self.ini_file_selection_changed)

        # Which .ini file was used previously? Check in status.dat
        if os.path.isfile('cfg/status.dat'):
            status_file = open('cfg/status.dat', 'r')
            last_inifile = status_file.readline()
            status_file.close()
            try:
                last_item_used = self.listWidget_filelist.findItems(
                    last_inifile, Qt.MatchExactly)[0]
                self.listWidget_filelist.setCurrentItem(last_item_used)
            except:
                # If the file indicated in status.dat does not exist, select the
                # first item of the list
                self.listWidget_filelist.setCurrentRow(0)
        else:
            # If status.dat does not exist, the program must have crashed or a
            # second instance is running. Select the first item of the list
            # and display a warning.
            self.listWidget_filelist.setCurrentRow(0)
            QMessageBox.warning(
                self, 'Warning: Crash occurred or other SBEMimage instance '
                'is running',
                'SBEMimage appears to have crashed during the '
                'previous run, or another instance of SBEMimage is al'
                'ready '
                'running. Please close the other instance or abort this '
                'one.\n\n'
                'If you want to continue an acquisition after a crash, '
                'double-check all settings before restarting!\n\n'
                'You can report a crash here, ideally with the error '
                'message(s) shown in the Console window: '
                'https://github.com/SBEMimage/SBEMimage/issues',
                QMessageBox.Ok)
        self.ini_file_selection_changed()

    def ini_file_selection_changed(self):
        # Enable device presets selection button if default.ini selected
        current_item = self.listWidget_filelist.currentItem()
        if current_item is None:
            return
        if current_item.text() == 'Default Configuration':
            self.pushButton_deviceSelection.setEnabled(True)
        else:
            self.pushButton_deviceSelection.setEnabled(False)
        self._sync_klab_toggle_with_selected_config()

    def _selected_ini_path(self):
        current_item = self.listWidget_filelist.currentItem()
        if current_item is None:
            return None
        if current_item.text() == 'Default Configuration':
            return os.path.join('src', 'default_cfg', 'default.ini')
        return os.path.join('cfg', current_item.text())

    def _sync_klab_toggle_with_selected_config(self):
        selected_path = self._selected_ini_path()
        use_klab_ui = False
        if selected_path and os.path.isfile(selected_path):
            try:
                cfg = ConfigParser()
                with open(selected_path, 'r') as file:
                    cfg.read_file(file)
                if 'sys' in cfg:
                    if 'use_klab_ui' in cfg['sys']:
                        use_klab_ui = (
                            cfg['sys']['use_klab_ui'].strip().lower()
                            == 'true')
                    elif 'use_teal_experiment_gui' in cfg['sys']:
                        # Backward compatibility with earlier experimental key.
                        use_klab_ui = (
                            cfg['sys']['use_teal_experiment_gui'].strip().lower()
                            == 'true')
            except Exception:
                # Keep current default if selected file cannot be parsed.
                pass
        self.checkBox_useKlabUi.setChecked(use_klab_ui)

    def open_device_selection_dlg(self):
        dialog = DeviceSelectionDlg(self.load_presets_enabled,
                                    self.device_presets_selection)
        if dialog.exec():
            self.device_presets_selection = dialog.selected_presets
            self.load_presets_enabled = dialog.presets_enabled

    def _update_klab_animation_state(self, enabled):
        if enabled:
            self.klab_anim_index = 0
            self.labelKlabAnim.setText(self.klab_anim_frames[self.klab_anim_index])
            self.labelKlabAnim.setVisible(True)
            if not self.klab_anim_timer.isActive():
                self.klab_anim_timer.start()
        else:
            self.klab_anim_timer.stop()
            self.labelKlabAnim.clear()
            self.labelKlabAnim.setVisible(False)

    def _animate_klab_label(self):
        self.klab_anim_index = (
            self.klab_anim_index + 1) % len(self.klab_anim_frames)
        self.labelKlabAnim.setText(self.klab_anim_frames[self.klab_anim_index])

    def reject(self):
        self.abort = True
        super().reject()

    def get_ini_file(self):
        if not self.abort:
            return self.listWidget_filelist.currentItem().text()
        else:
            return 'abort'

    def get_use_klab_ui(self):
        return self.checkBox_useKlabUi.isChecked()
