import json
import os
import time
from time import sleep

import numpy as np

from constants import Error
from microtome.BFRemover import BFRemover
import utils


try:
    import ftdidio as _ftdidio_module
    _ftdidio_avail = True
except ImportError:
    _ftdidio_module = None
    _ftdidio_avail = False

try:
    from ftdidio import FtdiDio as _ftdi_dio_cls
    _ftdi_dio_avail = True
except ImportError:
    _ftdi_dio_cls = None
    _ftdi_dio_avail = False

try:
    import ftdirelais as _ftdirelais_module
    _ftdirelais_avail = True
except ImportError:
    _ftdirelais_module = None
    _ftdirelais_avail = False

try:
    import ftdirelais.ftdirelais as _ftdirelais_legacy_module
    _ftdirelais_legacy_avail = True
except ImportError:
    _ftdirelais_legacy_module = None
    _ftdirelais_legacy_avail = False

_ftdi_blanking_avail = _ftdidio_avail
_ftdi_relais_avail = _ftdirelais_avail or _ftdirelais_legacy_avail
_lab_gcib_workflow_avail = _ftdi_dio_avail and _ftdi_relais_avail


class GCIB(BFRemover):
    # The legacy GCIB workflow used successfully in the lab runs with a fixed
    # milling cadence and fixed hardware routing. These values intentionally
    # override the configurable defaults when GCIB is instantiated.
    LAB_MILL_CYCLE_SECONDS = 16880.0
    LAB_ROTATION_STEP_DEG = 40
    LAB_ROTATION_DWELL_SECONDS = 60.0
    LAB_SETTLE_SECONDS = 5.0

    ARGON_RELAIS_SERIAL = 'QYEZ248'
    GATE_RELAIS_SERIAL = 'DN7B6BWK'
    CLOSE_SHUTTER_BIT = 1
    OPEN_SHUTTER_BIT = 2

    """
    [WIP]
    Requires stage hook.
    Todo:
        * use consistent error states.
        * remove redundant interface to SEMstage
        * Update full_cut_duration when changing mill_cycle / mill_duration
        * Unify mill_cycle and mill_duration!
    """

    def __init__(self, config: dict, sysconfig: dict, stage):
        """

        Args:
            config:
            sysconfig:
            stage: Stage class must implement XYZ translation, tilt and rotation.
        """
        super().__init__(config, sysconfig)
        self.cfg = config
        self.syscfg = sysconfig
        self.stage = stage
        self.error_state = Error.none
        self.error_info = ''
        self.acq = None
        self.simulation_mode = (
            self.cfg['sys']['simulation_mode'].lower() == 'true')
        self._ftdi_device = None

        # Load device name and other settings from sysconfig. These
        # settings overwrite the settings in config.
        recognized_devices = json.loads(
            self.syscfg['device']['microtome_recognized'])
        self.cfg['microtome']['device'] = self.syscfg['device']['microtome']
        if self.cfg['microtome']['device'] not in recognized_devices:
            self.cfg['microtome']['device'] = 'NOT RECOGNIZED'
        self.device_name = self.cfg['microtome']['device']

        self._pos_prior_mill_mov = None
        # Catch errors that occur while reading configuration and converting
        # the string values into floats or integers
        try:
            # Start from the persisted config, then apply the validated lab
            # workflow constants.
            self.mill_cycle = float(self.cfg['gcib']['mill_cycle'])
            self.mill_cycle = self.LAB_MILL_CYCLE_SECONDS
            self._ftdi_serial = str(self.cfg['gcib']['ftdi_serial'])
            self.continuous_rot = int(self.cfg['gcib']['continuous_rot'])
            self.xyzt_milling = self._parse_xyzt_milling(
                self.cfg['gcib']['xyzt_milling'])
            self.full_cut_duration = self.mill_cycle
            self.base_dir = self.cfg['acq']['base_dir'].rstrip(r'\\\/ ')
        except Exception as e:
            self.error_state = Error.configuration
            self.error_info = str(e)
            return

        self.monitor_path = os.path.join(self.base_dir, 'meta', 'milling')
        os.makedirs(self.monitor_path, exist_ok=True)

        if not self.simulation_mode and not (
                _lab_gcib_workflow_avail or _ftdi_blanking_avail):
            self.error_state = Error.configuration
            self.error_info = (
                f'ImportError: {self} requires either the legacy GCIB FTDI '
                f'shutter/relais stack or the ftdidio blanking module.')
            return

        if _ftdi_blanking_avail and not _lab_gcib_workflow_avail and not self.simulation_mode:
            try:
                self._ftdi_device = _ftdidio_module.Ftdidio()
            except Exception as e:
                self.error_state = Error.configuration
                self.error_info = f'Could not initialize ftdidio: {str(e)}'
                return
            self._connect_blanking()

    def _parse_xyzt_milling(self, raw_value):
        xyzt_milling = np.array(json.loads(raw_value), dtype=float).reshape(-1)
        if xyzt_milling.size not in (4, 5):
            raise ValueError(
                'GCIB xyzt_milling must contain 4 or 5 numeric entries.')
        return xyzt_milling

    def _mill_position_xyz_t(self):
        return self.xyzt_milling[:4]

    def _new_relais_device(self):
        if _ftdirelais_legacy_avail:
            return _ftdirelais_legacy_module.Ftdirelais()
        if _ftdirelais_avail:
            return _ftdirelais_module.Ftdirelais()
        return None

    def _connect_blanking(self):
        if self._ftdi_device is None:
            return
        try:
            self._ftdi_device.open(serial=self._ftdi_serial)
            self._ftdi_device.set_mask(1)
            self._blank_beam()
            msg = f'GCIB: Connected ftdidio.'
            utils.log_info(msg)
        except Exception as e:
            self.error_state = Error.move_init
            self.error_info = str(e)

    def _disconnect_blanking(self):
        """
        Disconnect from ftdi device. Tries to blank beam.
        """
        if self._ftdi_device is None:
            return
        try:
            self._blank_beam()
            self._ftdi_device.close()
        except Exception as e:
            self.error_state = Error.move_init
            self.error_info = str(e)

    def _blank_beam(self):
        if self._ftdi_device is not None:
            self._ftdi_device.set_bit(1)

    def _unblank_beam(self):
        if self._ftdi_device is not None:
            self._ftdi_device.clear_bit(1)

    def _write_monitor_marker(self, prefix, timestamp):
        marker_path = os.path.join(
            self.monitor_path, f'{prefix}_{round(timestamp)}.txt')
        with open(marker_path, 'w') as marker_file:
            marker_file.write(f'{prefix} time: {timestamp}')

    def argon_relais(self, state, relais_serial):
        relais = self._new_relais_device()
        if relais is None:
            self.error_state = Error.configuration
            self.error_info = 'Could not initialize ftdirelais for GCIB.'
            return False
        try:
            relais.open(serial=relais_serial)
            if state:
                relais.set_relais_0()
            else:
                relais.clear_relais_0()
            return True
        except Exception as e:
            self.error_state = Error.configuration
            self.error_info = f'GCIB relais error: {str(e)}'
            return False
        finally:
            try:
                relais.close()
            except Exception:
                pass

    def close_shutter(self):
        if _ftdi_dio_cls is None:
            self.error_state = Error.configuration
            self.error_info = 'Could not initialize FtdiDio for GCIB shutter control.'
            return False
        dev = _ftdi_dio_cls()
        try:
            dev.set_mask(self.CLOSE_SHUTTER_BIT + self.OPEN_SHUTTER_BIT)
            dev.clear_bits(self.OPEN_SHUTTER_BIT)
            dev.set_bits(self.CLOSE_SHUTTER_BIT)
            return True
        except Exception as e:
            self.error_state = Error.configuration
            self.error_info = f'GCIB shutter close error: {str(e)}'
            return False
        finally:
            try:
                dev.close()
            except Exception:
                pass

    def open_shutter(self):
        if _ftdi_dio_cls is None:
            self.error_state = Error.configuration
            self.error_info = 'Could not initialize FtdiDio for GCIB shutter control.'
            return False
        dev = _ftdi_dio_cls()
        try:
            dev.set_mask(self.CLOSE_SHUTTER_BIT + self.OPEN_SHUTTER_BIT)
            dev.clear_bits(self.CLOSE_SHUTTER_BIT)
            dev.set_bits(self.OPEN_SHUTTER_BIT)
            return True
        except Exception as e:
            self.error_state = Error.configuration
            self.error_info = f'GCIB shutter open error: {str(e)}'
            return False
        finally:
            try:
                dev.close()
            except Exception:
                pass

    def save_to_cfg(self):
        self.cfg['microtome']['full_cut_duration'] = str(self.mill_cycle)
        self.cfg['gcib']['ftdi_serial'] = str(self._ftdi_serial)
        self.cfg['gcib']['xyzt_milling'] = str(self.xyzt_milling.tolist())
        self.cfg['gcib']['mill_cycle'] = str(self.mill_cycle)
        self.cfg['gcib']['continuous_rot'] = str(self.continuous_rot)
        self.cfg['gcib']['last_known_z'] = str(self.last_known_z)
        # TODO: why is this called here?
        self.stage.save_to_cfg()

    def do_full_cut(self, **kwargs):
        self.do_full_removal(**kwargs)
        return

    def move_stage_to_millpos(self):
        """
        Sets '_pos_prior_mill_mov' to current stage position. Moves the stage to R=120.


        """
        # move_to_xyzt will set rotation to self.stage.rotation, no need to store r explicitly
        if np.all(self.xyzt_milling == 0):
            self.error_info = 'NotInitializedError: Location parameters for milling have not been set.'
            self.error_state = Error.move_params
            return
        x, y, z, t, r = self.stage.get_stage_xyztr()
        msg = f'GCIB: Start position for milling cycle X={x}, Y={y}, Z={z}, T={t}, R={r}.'
        utils.log_info(msg)
        if not np.isclose(t, 0, atol=1e-4):
            self.error_state = Error.move_unsafe
            self.error_info = (f'UnsafeMovementError: Current t position is supposed to be close to 0,'
                               f'instead got: {t} != 0.')
            return
        # This is pure safety measure - this would be possible
        if not np.isclose(t, 0):
            self.error_info = 'UnsafeMovementError: Current tilt angle is not close to 0. As a safety measure, ' \
                              'this is currently not supported.'
            self.error_state = Error.move_unsafe
            return
        x_mill, y_mill, z_mill, t_mill = self._mill_position_xyz_t()
        if z < z_mill:
            self.error_state = Error.move_unsafe
            self.error_info = (f'UnsafeMovementError: Current z position is smaller than the '
                               f'one given as milling location: {z} < {z_mill}.')
            return
        self._pos_prior_mill_mov = [x, y, z, t, r]
        msg = f'Stored position prior to mill movement: {self._pos_prior_mill_mov}'
        utils.log_info(msg)

        if self.simulation_mode:
            return
        self.stage.move_stage_to_z(z_mill)
        # TODO: maybe tilt at the very end for safety reasons if z_mill is high..
        self.stage.move_stage_to_xyzt(x_mill, y_mill, z_mill, t_mill)
        _, _, _, _, r_current = self.stage.get_stage_xyztr()
        msg = f'GCIB: Reached mill position: X={x_mill}, Y={y_mill}, Z={z_mill}, T={t_mill}, R={r_current}.'
        utils.log_info(msg)

    def move_stage_to_pos_prior_mill_mov(self):
        """
        Sets '_pos_prior_mill_mov' to None.

        """
        if self._pos_prior_mill_mov is None:
            self.error_info = 'UnsafeMovementError: Position prior to mill movement is None.'
            self.error_state = Error.move_params
            return
        x, y, z, t, r = self._pos_prior_mill_mov
        if not np.isclose(t, 0, atol=1e-4):
            self.error_state = Error.move_unsafe
            self.error_info = (f'UnsafeMovementError: Tilt position before milling is supposed to be close to 0,'
                               f'instead got: {t} != 0.')
            return
        x_mill, y_mill, z_mill, t_mill = self._mill_position_xyz_t()
        # move stage to initial position, first tilt to 0 degree
        self.stage.move_stage_to_r(r, no_wait=True)
        # TODO: will still wait for the rotation to finish within move_stage_to_xyztr, as rotating is the slowest part
        self.stage.move_stage_to_xyztr(x_mill, y_mill, z_mill, t, r)
        _, _, _, t_curr, _ = self.stage.get_stage_xyztr()
        # double check tilt position
        if not np.isclose(t_curr, 0, atol=1e-4):
            self.error_state = Error.move_unsafe
            self.error_info = (f'IncosistentMoveError: Target t position is supposed to be close to 0,'
                               f'instead got: {t} != 0.')
            return
        # move XYR
        self.stage.move_stage_to_xyztr(x, y, z_mill, t, r)
        # move Z at the very end
        self.stage.move_stage_to_xyztr(x, y, z, t, r)
        self._pos_prior_mill_mov = None
        # TODO: any check required?
        # _, _, _, _, r_dest = self.stage.get_stage_xyztr()
        # if not np.isclose(r_dest, self.stage.stage_rotation, atol=1e-4):
        #     self.error_state = Error.move_unsafe
        #     self.error_info = (f'IncosistentMoveError: Current r position is supposed to be close to '
        #                        f'self.stage.stage_rotation={self.stage.stage_rotation},'
        #                        f'instead got: {r_dest} != 0.')
        #     return
        msg = f'GCIB: Reached original position after milling cycle: X={x}, Y={y}, Z={z}, T={t}, R={r}.'
        utils.log_info(msg)

    def do_full_removal(self, mill_duration=None, testing=False):
        """Perform a full milling cycle. This is the only removal function
           used during stack acquisitions.
        """
        if mill_duration is None:
            mill_duration = self.mill_cycle
        self.move_stage_to_millpos()
        if self.error_state != Error.none:
            return

        if self.simulation_mode:
            time.sleep(max(mill_duration, 0))
            self._pos_prior_mill_mov = None
            return

        dt_milling = None
        beam_unblanked = False
        shutter_closed = False
        gas_flow_enabled = False

        try:
            if _lab_gcib_workflow_avail:
                time.sleep(self.LAB_SETTLE_SECONDS)
                if not self.close_shutter():
                    return
                shutter_closed = True
                time.sleep(self.LAB_SETTLE_SECONDS)
                if not testing:
                    if not self.argon_relais(True, self.GATE_RELAIS_SERIAL):
                        return
                    if not self.argon_relais(True, self.ARGON_RELAIS_SERIAL):
                        return
                    gas_flow_enabled = True
                    time.sleep(self.LAB_SETTLE_SECONDS)
            elif mill_duration > 0 and self._ftdi_device is not None:
                self._unblank_beam()
                beam_unblanked = True

            dt_milling = time.time()
            self._write_monitor_marker('start', dt_milling)
            self.rotate360(mill_duration)
        finally:
            if dt_milling is not None:
                end_time = time.time()
                self._write_monitor_marker('stopp', end_time)
                utils.log_info(
                    f'GCIB: Milling cycle kept the stage in milling position for '
                    f'{end_time - dt_milling:.1f} s')

            if beam_unblanked:
                self._blank_beam()

            if gas_flow_enabled:
                self.argon_relais(False, self.ARGON_RELAIS_SERIAL)
                self.argon_relais(False, self.GATE_RELAIS_SERIAL)

            if shutter_closed:
                time.sleep(self.LAB_SETTLE_SECONDS)
                self.open_shutter()
                time.sleep(self.LAB_SETTLE_SECONDS)

            self.move_stage_to_pos_prior_mill_mov()

        if testing:
            return
        # TODO: requires further investigation (might disappear with proper gold coating and electron irradiation)
        dt_sleep = 0
        if dt_sleep > 0:
            msg = f'GCIB: Sleeping for {dt_sleep} s to lose charge on sample.'
            utils.log_info(msg)
            sleep(dt_sleep)

    def rotate360(self, mill_duration):
        """
        Args:
            mill_duration: Total mill duration in seconds.
        """
        # Hayworth et al, 2019, Nat. Methods: Three evenly spaced azimuthal
        # directions for 360 deg and 360 s per mill cycle
        if not self.continuous_rot:
            start = time.time()
            while True:  # loop while < mill duration
                start_interval = time.time()
                while True:  # wait between discrete stage rotations
                    dt_interval = time.time() - start_interval
                    dt = time.time() - start
                    if self.acq is not None and self.acq.acq_paused and self.acq.pause_state == 1:
                        break
                    if dt_interval >= self.LAB_ROTATION_DWELL_SECONDS or dt >= mill_duration:
                        break
                    time.sleep(1)
                # pause_state==1 -> pause immediately
                if dt >= mill_duration or (self.acq is not None and self.acq.acq_paused and self.acq.pause_state == 1):
                    break
                self.stage.move_stage_delta_r(self.LAB_ROTATION_STEP_DEG, no_wait=False)
        else:
            dt_per_2deg = mill_duration / 180
            for deg in range(360):
                if self.acq is not None and self.acq.acq_paused and self.acq.pause_state == 1:
                    break
                start = time.time()
                self.stage.move_stage_delta_r(2)
                dt = time.time() - start
                if dt > dt_per_2deg:
                    msg = (
                        f'GCIB: WARNING: Rotation speed was slower '
                        f'({dt:.3f} s) than requested by the target mill cycle '
                        f'({dt_per_2deg:.2f} s).')
                    utils.log_info(msg)
                else:
                    sleep(dt_per_2deg - dt)

    def move_stage_to_z(self, z):
        return self.stage.move_stage_to_z(z)

    def move_stage_to_xy(self, coordinates):
        return self.stage.move_stage_to_xy(coordinates)

    def get_stage_x(self):
        return self.stage.get_stage_x()

    def get_stage_y(self):
        return self.stage.get_stage_y()

    def get_stage_xy(self):
        return self.stage.get_stage_xy()

    def get_stage_xyz(self):
        return self.stage.get_stage_xyz()

    @property
    def last_known_y(self):
        return self.stage.last_known_xy[1]

    @property
    def last_known_x(self):
        return self.stage.last_known_xy[0]

    @property
    def last_known_z(self):
        return self.stage.last_known_z

    def do_sweep(self, z_position):
        return

    def check_cut_cycle_status(self):
        return
