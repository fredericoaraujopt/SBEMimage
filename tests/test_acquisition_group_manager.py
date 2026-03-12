import sys
from configparser import ConfigParser

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QWidget

from AcquisitionGroupManager import AcquisitionGroupManager
from CoordinateSystem import CoordinateSystem
from GridManager import GridManager
from OverviewManager import OverviewManager
from dialog.viewport.AcquisitionManagerDlg import AcquisitionManagerDlg
from sem.SEM import SEM


APP = QApplication.instance()
if APP is None:
    APP = QApplication(sys.argv)


def _read_default_configs():
    cfg = ConfigParser()
    with open('src/default_cfg/default.ini', 'r') as file_handle:
        cfg.read_file(file_handle)
    syscfg = ConfigParser()
    with open('src/default_cfg/system.cfg', 'r') as file_handle:
        syscfg.read_file(file_handle)
    return cfg, syscfg


@pytest.fixture
def group_env():
    cfg, syscfg = _read_default_configs()
    cs = CoordinateSystem(cfg, syscfg)
    sem = SEM(cfg, syscfg)
    ovm = OverviewManager(cfg, sem, cs)
    gm = GridManager(cfg, sem, cs)
    acq_groups = AcquisitionGroupManager(cfg, gm, ovm)
    return cfg, syscfg, cs, sem, ovm, gm, acq_groups


def test_group_round_trip(group_env):
    cfg, _, _, _, ovm, gm, acq_groups = group_env
    group_id = acq_groups.create_group('Section A')
    child_group_id = acq_groups.create_group('High res', group_id)
    acq_groups.set_group_colour(group_id, 4)
    acq_groups.set_group_expanded(group_id, False)
    acq_groups.assign_overview(0, group_id)
    acq_groups.assign_grid(0, child_group_id)
    acq_groups.save_to_cfg()

    reloaded = AcquisitionGroupManager(cfg, gm, ovm)
    assert reloaded.group(group_id)['name'] == 'Section A'
    assert reloaded.group(group_id)['colour'] == 4
    assert reloaded.group(group_id)['expanded'] is False
    assert reloaded.group(child_group_id)['parent_id'] == group_id
    assert reloaded.overview_group_id(0) == group_id
    assert reloaded.grid_group_id(0) == child_group_id
    assert reloaded.group_path_text(child_group_id) == 'Section A / High res'


def test_sync_inventory_after_add_delete(group_env):
    _, _, _, _, ovm, gm, acq_groups = group_env
    group_id = acq_groups.create_group('Section A')
    acq_groups.assign_overview(0, group_id)
    acq_groups.assign_grid(0, group_id)

    gm.add_new_grid()
    ovm.add_new_overview()
    acq_groups.sync_inventory()
    assert len(acq_groups._grid_group_ids) == gm.number_grids
    assert len(acq_groups._ov_group_ids) == ovm.number_ov
    assert acq_groups.grid_group_id(gm.number_grids - 1) is None
    assert acq_groups.overview_group_id(ovm.number_ov - 1) is None

    gm.delete_grid()
    ovm.delete_overview()
    acq_groups.sync_inventory()
    assert len(acq_groups._grid_group_ids) == gm.number_grids
    assert len(acq_groups._ov_group_ids) == ovm.number_ov


def test_delete_group_dissolves_children(group_env):
    _, _, _, _, _, _, acq_groups = group_env
    parent_id = acq_groups.create_group('Section A')
    child_id = acq_groups.create_group('Subsection', parent_id)
    acq_groups.assign_grid(0, parent_id)
    acq_groups.assign_overview(0, child_id)

    acq_groups.delete_group(parent_id)

    assert acq_groups.has_group(parent_id) is False
    assert acq_groups.group(child_id)['parent_id'] is None
    assert acq_groups.grid_group_id(0) is None
    assert acq_groups.overview_group_id(0) == child_id


def test_effective_grid_colour_prefers_group_except_special_13(group_env):
    _, _, _, _, _, gm, acq_groups = group_env
    group_id = acq_groups.create_group('Section A')
    acq_groups.set_group_colour(group_id, 5)
    gm[0].display_colour = 2
    acq_groups.assign_grid(0, group_id)
    assert acq_groups.effective_grid_display_colour(0) == 5

    gm[0].display_colour = 13
    assert acq_groups.effective_grid_display_colour(0) == 13


def test_group_summary_counts_intervallic_items(group_env):
    _, _, _, _, ovm, gm, acq_groups = group_env
    group_id = acq_groups.create_group('Section A')
    acq_groups.assign_overview(0, group_id)
    acq_groups.assign_grid(0, group_id)
    ovm[0].active = True
    ovm[0].acq_interval = 2
    ovm[0].acq_interval_offset = 1
    gm[0].active = True
    gm[0].acq_interval = 3
    gm[0].acq_interval_offset = 0

    summary = acq_groups.group_summary(group_id, 3)
    assert summary['active_overviews'] == 1
    assert summary['active_grids'] == 1
    assert summary['active_tiles'] == gm[0].number_active_tiles()
    assert summary['intervallic_items'] == 2
    assert '1 overview(s)' in summary['current_slice_note']
    assert '1 grid(s)' in summary['current_slice_note']


class DummyTrigger:
    def __init__(self):
        self.calls = []

    def transmit(self, msg, *args, **kwargs):
        self.calls.append((msg, args, kwargs))


class DummyViewport(QWidget):
    def __init__(self, gm, ovm, acq_groups):
        super().__init__()
        self.gm = gm
        self.ovm = ovm
        self.acq_groups = acq_groups
        self.busy = False
        self.selected_grid = None
        self.selected_ov = None
        self.main_controls_trigger = DummyTrigger()
        self.refresh_notifications = []
        self.tile_updates = 0
        self.acq = type(
            'AcqState',
            (),
            {'acq_in_progress': False, 'slice_counter': 0, 'take_overviews': True},
        )()
        self.autofocus = type('AutofocusState', (), {'tracking_mode': 0})()
        self.dialog = None

    def _notify_acquisition_manager_state_change(self, update_debris=False):
        self.refresh_notifications.append(update_debris)
        if self.dialog is not None:
            self.dialog.refresh_view()

    def vp_update_after_active_tile_selection(self):
        self.tile_updates += 1
        if self.dialog is not None:
            self.dialog.refresh_view()

    def vp_activate_all_tiles(self):
        self.gm[self.selected_grid].activate_all_tiles()
        self.vp_update_after_active_tile_selection()

    def vp_deactivate_all_tiles(self):
        self.gm[self.selected_grid].deactivate_all_tiles()
        self.vp_update_after_active_tile_selection()


def test_acquisition_manager_dialog_smoke(group_env):
    _, _, _, _, ovm, gm, acq_groups = group_env
    viewport = DummyViewport(gm, ovm, acq_groups)
    dialog = AcquisitionManagerDlg(acq_groups, viewport)
    viewport.dialog = dialog

    dialog.button_new_group.click()
    assert acq_groups.groups()
    group_id = acq_groups.groups()[0]['id']
    acq_groups.assign_grid(0, group_id)
    dialog.refresh_view(selected_key='grid:0')

    grid_item = dialog._item_index['grid:0']
    dialog.tree.setCurrentItem(grid_item)
    grid_item.setCheckState(0, Qt.Unchecked)
    assert gm[0].active is False
    assert viewport.refresh_notifications

    grid_item = dialog._item_index['grid:0']
    dialog.tree.setCurrentItem(grid_item)
    grid_item.setCheckState(0, Qt.Checked)
    assert gm[0].active is True

    dialog.refresh_view(selected_key='grid:0')
    dialog.tile_map.set_grid(gm[0])
    dialog.tile_map._pending_active_tiles = set(gm[0].active_tiles)
    tile_index = gm[0].active_tiles[0]
    dialog.tile_map._pending_active_tiles.remove(tile_index)
    dialog.tile_map.grid.active_tiles = list(dialog.tile_map._pending_active_tiles)
    dialog._tile_map_changed()
    assert tile_index not in gm[0].active_tiles
    assert viewport.tile_updates == 1
