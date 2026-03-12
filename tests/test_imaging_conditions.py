import sys
from types import SimpleNamespace

import pytest

from CoordinateSystem import CoordinateSystem
from GridManager import GridManager
from ImagingConditions import (
    ImagingConditionDuplicateNameError,
    ImagingConditionPreset,
    ImagingConditionStore,
)
from OverviewManager import OverviewManager
from Stage import Stage
from dialog.GridSettingsDlg import GridSettingsDlg
from dialog.OVSettingsDlg import OVSettingsDlg
from dialog.viewport.StubOVDlg import StubOVDlg
from microtome.Microtome_Mock import Microtome_Mock
from qtpy.QtWidgets import QApplication, QInputDialog
from sem.SEM_Mock import SEM_Mock
from test_utils import init_log, init_read_configs


APP = QApplication.instance()
if APP is None:
    APP = QApplication(sys.argv)


class DummyTrigger:
    def __init__(self):
        self.messages = []

    def transmit(self, *args, **kwargs):
        self.messages.append((args, kwargs))


@pytest.fixture
def mock_context(tmp_path):
    init_log()
    config, sysconfig = init_read_configs('mock.ini', 'mock.cfg')
    config['acq']['base_dir'] = str(tmp_path)
    config['acq']['mock_prev_acq_dir'] = str(tmp_path)
    sem = SEM_Mock(config, sysconfig)
    microtome = Microtome_Mock(config, sysconfig)
    cs = CoordinateSystem(config, sysconfig)
    gm = GridManager(config, sem, cs)
    ovm = OverviewManager(config, sem, cs)
    stage = Stage(sem, microtome, use_microtome=True)
    return {
        'config': config,
        'sysconfig': sysconfig,
        'sem': sem,
        'cs': cs,
        'gm': gm,
        'ovm': ovm,
        'stage': stage,
    }


def test_imaging_condition_store_crud_and_invalid_file(tmp_path):
    storage_dir = tmp_path / 'imaging_conditions'
    store = ImagingConditionStore(str(storage_dir))
    preset = ImagingConditionPreset(
        name='ignored',
        source_dialog='grid',
        source_sem_device='Mock SEM',
        frame_size_px=[1024, 768],
        pixel_size_nm=4.2,
        dwell_time_us=0.8,
    )

    saved = store.save_new_preset('Preset A', preset)
    assert saved.name == 'Preset A'
    assert len(store.list_presets()) == 1
    assert store.get_preset(saved.preset_id).frame_size_px == [1024, 768]
    assert list(storage_dir.glob('*.tmp')) == []

    with pytest.raises(ImagingConditionDuplicateNameError):
        store.save_new_preset('preset a', preset)

    invalid_file = storage_dir / 'broken.json'
    invalid_file.write_text('{invalid', encoding='utf-8')
    presets = store.list_presets()
    assert len(presets) == 1
    assert presets[0].name == 'Preset A'


def test_grid_dialog_saved_preset_applies_to_widgets_only(
        tmp_path, mock_context, monkeypatch):
    store = ImagingConditionStore(str(tmp_path / 'grid_presets'))
    trigger = DummyTrigger()
    dialog = GridSettingsDlg(
        mock_context['gm'],
        mock_context['sem'],
        0,
        trigger,
        store,
        False)

    original_grid = mock_context['gm'][0]
    original_state = (
        original_grid.frame_size_selector,
        original_grid.pixel_size,
        original_grid.dwell_time_selector,
    )
    dialog.comboBox_tileSize.setCurrentIndex(0)
    dialog.doubleSpinBox_pixelSize.setValue(33.3)
    dialog.comboBox_dwellTime.setCurrentIndex(1)

    monkeypatch.setattr(
        QInputDialog,
        'getText',
        staticmethod(lambda *args, **kwargs: ('Grid preset', True)))
    dialog.pushButton_saveCurrentImagingConditionAs.click()

    presets = store.list_presets()
    assert [preset.name for preset in presets] == ['Grid preset']

    dialog.comboBox_tileSize.setCurrentIndex(2)
    dialog.doubleSpinBox_pixelSize.setValue(12.5)
    dialog.comboBox_dwellTime.setCurrentIndex(0)
    dialog.comboBox_savedImagingCondition.setCurrentIndex(1)
    dialog.pushButton_applySavedImagingCondition.click()

    assert dialog.comboBox_tileSize.currentIndex() == 0
    assert dialog.doubleSpinBox_pixelSize.value() == pytest.approx(33.3)
    assert dialog.comboBox_dwellTime.currentIndex() == 1
    assert (
        original_grid.frame_size_selector,
        original_grid.pixel_size,
        original_grid.dwell_time_selector,
    ) == original_state

    dialog.save_current_settings()
    assert original_grid.frame_size_selector == 0
    assert original_grid.pixel_size == pytest.approx(33.3)
    assert original_grid.dwell_time_selector == 1
    dialog.close()


def test_overview_dialog_saved_preset_applies_to_widgets_only(
        tmp_path, mock_context):
    store = ImagingConditionStore(str(tmp_path / 'overview_presets'))
    trigger = DummyTrigger()
    dialog = OVSettingsDlg(
        mock_context['ovm'],
        mock_context['sem'],
        0,
        trigger,
        store)

    preset = ImagingConditionPreset(
        name='Overview preset',
        source_dialog='overview',
        source_sem_device='Mock SEM',
        frame_size_px=list(mock_context['sem'].STORE_RES[0][:2]),
        pixel_size_nm=42.0,
        dwell_time_us=float(mock_context['sem'].DWELL_TIME[1]),
    )
    saved = store.save_new_preset('Overview preset', preset)
    dialog.imaging_condition_controller.refresh_presets(saved.preset_id)
    overview = mock_context['ovm'][0]
    original_state = (
        overview.frame_size_selector,
        overview.magnification,
        overview.dwell_time_selector,
    )

    dialog.comboBox_savedImagingCondition.setCurrentIndex(1)
    assert dialog.comboBox_savedImagingCondition.currentData() == saved.preset_id
    dialog.pushButton_applySavedImagingCondition.click()

    expected_mag = int(round(
        mock_context['sem'].MAG_PX_SIZE_FACTOR
        / (mock_context['sem'].STORE_RES[0][0] * 42.0)))
    assert dialog.comboBox_frameSize.currentIndex() == 0
    assert dialog.spinBox_magnification.value() == max(1, expected_mag)
    assert dialog.doubleSpinBox_pixelSize.value() == pytest.approx(42.0, abs=0.01)
    assert (
        overview.frame_size_selector,
        overview.magnification,
        overview.dwell_time_selector,
    ) == original_state

    dialog.save_current_settings()
    assert overview.frame_size_selector == 0
    assert overview.pixel_size == pytest.approx(42.0, abs=0.01)
    assert overview.dwell_time_selector == 1
    dialog.close()


def test_stub_dialog_saved_preset_updates_widgets_and_not_model(
        tmp_path, mock_context):
    store = ImagingConditionStore(str(tmp_path / 'stub_presets'))
    trigger = DummyTrigger()
    sem = mock_context['sem']
    sem.has_lm_mode = lambda: True
    dialog = StubOVDlg(
        (0, 0),
        sem,
        mock_context['stage'],
        mock_context['ovm'],
        [],
        SimpleNamespace(acq_in_progress=False),
        object(),
        trigger,
        store)

    preset = ImagingConditionPreset(
        name='Stub preset',
        source_dialog='stub',
        source_sem_device='Mock SEM',
        frame_size_px=list(sem.STORE_RES[0][:2]),
        pixel_size_nm=55.0,
        dwell_time_us=float(sem.DWELL_TIME[1]),
    )
    saved = store.save_new_preset('Stub preset', preset)
    dialog.imaging_condition_controller.refresh_presets(saved.preset_id)
    stub_ov = mock_context['ovm']['stub']
    original_state = (
        stub_ov.frame_size_selector,
        stub_ov.pixel_size,
        stub_ov.dwell_time_selector,
    )

    dialog.comboBox_savedImagingCondition.setCurrentIndex(1)
    assert dialog.comboBox_savedImagingCondition.currentData() == saved.preset_id
    dialog.pushButton_applySavedImagingCondition.click()

    assert dialog.comboBox_frameSize.currentIndex() == 0
    assert dialog.doubleSpinBox_pixelSize.value() == pytest.approx(55.0, abs=0.02)
    assert dialog.comboBox_dwellTime.currentIndex() == 1
    assert (
        stub_ov.frame_size_selector,
        stub_ov.pixel_size,
        stub_ov.dwell_time_selector,
    ) == original_state

    dialog.checkBox_LmMode.setChecked(True)
    assert dialog.pushButton_getFromSEM.isEnabled() is False
    dialog.checkBox_LmMode.setChecked(False)
    assert dialog.pushButton_getFromSEM.isEnabled() is True
    dialog.close()


def test_stub_overview_selector_keys_round_trip(mock_context):
    config = mock_context['config']
    sem = mock_context['sem']
    cs = mock_context['cs']
    ovm = mock_context['ovm']

    ovm['stub'].frame_size_selector = 1
    ovm['stub'].dwell_time_selector = 2
    ovm['stub_lm'].frame_size_selector = 0
    ovm['stub_lm'].dwell_time_selector = 1
    ovm.save_to_cfg()

    reloaded = OverviewManager(config, sem, cs)
    assert reloaded['stub'].frame_size_selector == 1
    assert reloaded['stub'].dwell_time_selector == 2
    assert reloaded['stub_lm'].frame_size_selector == 0
    assert reloaded['stub_lm'].dwell_time_selector == 1
