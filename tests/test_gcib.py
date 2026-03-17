from configparser import ConfigParser

import pytest

import microtome.GCIB as gcib_module
from constants import Error
from microtome.GCIB import GCIB


def _read_mock_configs():
    config = ConfigParser()
    with open('tests/resources/mock.ini', 'r') as file_handle:
        config.read_file(file_handle)
    sysconfig = ConfigParser()
    with open('tests/resources/mock.cfg', 'r') as file_handle:
        sysconfig.read_file(file_handle)
    return config, sysconfig


class FakeFtdiDio:
    actions = []

    def set_mask(self, mask):
        self.actions.append(('set_mask', mask))

    def clear_bits(self, bits):
        self.actions.append(('clear_bits', bits))

    def set_bits(self, bits):
        self.actions.append(('set_bits', bits))

    def close(self):
        self.actions.append(('close', None))


class FakeRelais:
    actions = []

    def __init__(self):
        self.serial = None

    def open(self, serial):
        self.serial = serial
        self.actions.append(('open', serial))

    def set_relais_0(self):
        self.actions.append(('set', self.serial))

    def clear_relais_0(self):
        self.actions.append(('clear', self.serial))

    def close(self):
        self.actions.append(('close', self.serial))


class FakeStage:
    def __init__(self):
        self._state = [10.0, 20.0, 100.0, 0.0, 0.0]
        self.history = []

    def get_stage_xyztr(self):
        return tuple(self._state)

    def move_stage_to_z(self, z):
        self._state[2] = z
        self.history.append(('move_stage_to_z', z))

    def move_stage_to_xyzt(self, x, y, z, t):
        self._state[:4] = [x, y, z, t]
        self.history.append(('move_stage_to_xyzt', x, y, z, t))

    def move_stage_to_r(self, r, no_wait=False):
        self._state[4] = r
        self.history.append(('move_stage_to_r', r, no_wait))

    def move_stage_to_xyztr(self, x, y, z, t, r):
        self._state[:] = [x, y, z, t, r]
        self.history.append(('move_stage_to_xyztr', x, y, z, t, r))

    def move_stage_delta_r(self, delta_r, no_wait=False):
        self._state[4] += delta_r
        self.history.append(('move_stage_delta_r', delta_r, no_wait))

    def save_to_cfg(self):
        self.history.append(('save_to_cfg',))

    @property
    def last_known_xy(self):
        return tuple(self._state[:2])

    @property
    def last_known_z(self):
        return self._state[2]


@pytest.fixture
def gcib_legacy_env(monkeypatch, tmp_path):
    config, sysconfig = _read_mock_configs()
    config['acq']['base_dir'] = str(tmp_path)
    config['gcib']['xyzt_milling'] = '[11, 22, 90, 0, 120]'
    config['sys']['simulation_mode'] = 'False'
    config['microtome']['device'] = 'GCIB'
    sysconfig['device']['microtome'] = 'GCIB'

    FakeFtdiDio.actions = []
    FakeRelais.actions = []

    fake_relais_module = type('FakeRelaisModule', (), {'Ftdirelais': FakeRelais})

    monkeypatch.setattr(gcib_module, '_lab_gcib_workflow_avail', True)
    monkeypatch.setattr(gcib_module, '_ftdi_blanking_avail', False)
    monkeypatch.setattr(gcib_module, '_ftdi_dio_cls', FakeFtdiDio)
    monkeypatch.setattr(gcib_module, '_ftdirelais_legacy_avail', True)
    monkeypatch.setattr(gcib_module, '_ftdirelais_avail', False)
    monkeypatch.setattr(gcib_module, '_ftdirelais_legacy_module', fake_relais_module)
    monkeypatch.setattr(gcib_module, 'sleep', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gcib_module.time, 'sleep', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gcib_module.utils, 'log_info', lambda *_args, **_kwargs: None)

    stage = FakeStage()
    microtome = GCIB(config, sysconfig, stage)
    return microtome, stage, tmp_path


def test_gcib_legacy_workflow_controls_hardware_and_restores_stage(gcib_legacy_env):
    microtome, stage, tmp_path = gcib_legacy_env

    assert microtome.error_state == Error.none
    assert microtome.mill_cycle == GCIB.LAB_MILL_CYCLE_SECONDS
    assert microtome.xyzt_milling.tolist() == [11.0, 22.0, 90.0, 0.0, 120.0]

    microtome.do_full_cut(mill_duration=0)

    assert stage.get_stage_xyztr() == (10.0, 20.0, 100.0, 0.0, 0.0)
    assert ('open', GCIB.GATE_RELAIS_SERIAL) in FakeRelais.actions
    assert ('set', GCIB.GATE_RELAIS_SERIAL) in FakeRelais.actions
    assert ('clear', GCIB.GATE_RELAIS_SERIAL) in FakeRelais.actions
    assert ('open', GCIB.ARGON_RELAIS_SERIAL) in FakeRelais.actions
    assert ('set_bits', GCIB.CLOSE_SHUTTER_BIT) in FakeFtdiDio.actions
    assert ('set_bits', GCIB.OPEN_SHUTTER_BIT) in FakeFtdiDio.actions

    marker_dir = tmp_path / 'meta' / 'milling'
    marker_names = sorted(path.name for path in marker_dir.glob('*.txt'))
    assert len(marker_names) == 2
    assert marker_names[0].startswith('start_')
    assert marker_names[1].startswith('stopp_')


def test_gcib_testing_mode_skips_gas_flow(gcib_legacy_env):
    microtome, stage, _ = gcib_legacy_env

    microtome.do_full_cut(mill_duration=0, testing=True)

    assert stage.get_stage_xyztr() == (10.0, 20.0, 100.0, 0.0, 0.0)
    assert FakeRelais.actions == []
    assert ('set_bits', GCIB.CLOSE_SHUTTER_BIT) in FakeFtdiDio.actions
    assert ('set_bits', GCIB.OPEN_SHUTTER_BIT) in FakeFtdiDio.actions
