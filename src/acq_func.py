# -*- coding: utf-8 -*-

# ==============================================================================
#   This source file is part of SBEMimage (github.com/SBEMimage)
#   (c) 2018-2020 Friedrich Miescher Institute for Biomedical Research, Basel,
#   and the SBEMimage developers.
#   This software is licensed under the terms of the MIT License.
#   See LICENSE.txt in the project root folder.
# ==============================================================================

"""This module contains four functions that are called manually (by the user)
and not during acquisitions:
(1) Overview acquisition (to refresh the displayed OV in the viewport),
(2) Stub overview acquisition,
(3) Manual sweep command (when the user wants to remove debris),
(4) Manual stage move
"""

import os
import datetime
import cv2
import numpy as np
from time import sleep

import constants
from constants import Error
from image_io import imwrite
import utils
from acq_guardrails import (
    now_timestamp,
    ov_diagnostics_payload,
    recommended_ov_tile_factor,
)


def _log_ov_diagnostics(sem, ov, ov_index):
    payload = ov_diagnostics_payload(sem, ov)
    sem_frame = payload.get('sem_frame', None)
    sem_frame_str = str(sem_frame) if sem_frame is not None else 'unknown'
    utils.log_info(
        'SEM',
        f"OV {ov_index} diagnostics: req_frame={payload['requested_frame']}, "
        f"sem_frame={sem_frame_str}, px={payload['requested_pixel_size_nm']:.2f} nm, "
        f"mag={payload['requested_mag']:.1f}x, dwell={payload['dwell_us']:.3f} us, "
        f"bit_depth_sel={payload['bit_depth_selector']}")


def _mark_ov_result(ov, success):
    ts = now_timestamp()
    if success:
        ov.mark_acquired('success', ts)
    else:
        ov.last_acquisition_result = 'failed'
        ov.last_acquisition_timestamp = ts


def _acquire_ov_tiled_fallback(base_dir, ov_index, sem, stage, ovm, img_inspector, ov_save_path):
    """Fallback path for OV refresh when single-frame grabbing is unreliable."""
    ov = ovm[ov_index]
    min_single_frame_mag = float(
        sem.cfg['overviews'].get('ov_single_frame_min_mag', 80))
    tile_factor = recommended_ov_tile_factor(
        sem,
        ov.frame_size,
        ov.pixel_size,
        min_single_frame_mag=min_single_frame_mag)
    tile_factor = int(np.clip(tile_factor, 2, 6))

    width_px, height_px = ov.width_p(), ov.height_p()
    stitched = None
    tile_pixel_size = ov.pixel_size / tile_factor
    tile_w_d = ov.width_d() / tile_factor
    tile_h_d = ov.height_d() / tile_factor
    centre_dx, centre_dy = ov.centre_dx_dy

    sem.apply_frame_settings(
        ov.frame_size_selector,
        tile_pixel_size,
        ov.dwell_time)
    sem.set_bit_depth(ov.bit_depth_selector)

    utils.log_info(
        'SEM',
        f'OV {ov_index}: falling back to tiled acquisition '
        f'({tile_factor}x{tile_factor}, tile px {tile_pixel_size:.2f} nm).')

    try:
        for row in range(tile_factor):
            for col in range(tile_factor):
                offset_dx = (col + 0.5) * tile_w_d - ov.width_d() / 2
                offset_dy = (row + 0.5) * tile_h_d - ov.height_d() / 2
                target_sx_sy = ov.cs.convert_d_to_s((centre_dx + offset_dx, centre_dy + offset_dy))
                stage.move_to_xy(target_sx_sy)
                if stage.error_state != Error.none:
                    stage.reset_error_state()
                    return False

                temp_path = os.path.join(
                    base_dir,
                    'workspace',
                    f'ov{str(ov_index).zfill(constants.OV_DIGITS)}_tile_{row}_{col}{constants.TEMP_IMAGE_FORMAT}')
                sem.acquire_frame(temp_path, stage)
                tile_img, _, _, load_error, _, grab_incomplete = img_inspector.load_and_inspect(temp_path)
                if load_error or grab_incomplete:
                    sem.acquire_frame(temp_path, stage)
                    tile_img, _, _, load_error, _, grab_incomplete = img_inspector.load_and_inspect(temp_path)
                    if load_error or grab_incomplete:
                        return False

                if stitched is None:
                    if tile_img.ndim == 2:
                        stitched = np.zeros((height_px, width_px), dtype=tile_img.dtype)
                    else:
                        stitched = np.zeros((height_px, width_px, tile_img.shape[2]), dtype=tile_img.dtype)

                x0 = int(round(col * width_px / tile_factor))
                x1 = int(round((col + 1) * width_px / tile_factor))
                y0 = int(round(row * height_px / tile_factor))
                y1 = int(round((row + 1) * height_px / tile_factor))
                target_w = max(1, x1 - x0)
                target_h = max(1, y1 - y0)
                resized = cv2.resize(tile_img, (target_w, target_h), interpolation=cv2.INTER_AREA)
                stitched[y0:y1, x0:x1] = resized
    finally:
        # Restore original OV settings for next operation.
        sem.apply_frame_settings(
            ov.frame_size_selector,
            ov.pixel_size,
            ov.dwell_time)
        sem.set_bit_depth(ov.bit_depth_selector)

    if stitched is None:
        return False
    imwrite(ov_save_path, stitched)
    return True


def acquire_ov(base_dir, selection, sem, stage, ovm, img_inspector,
               main_controls_trigger, viewport_trigger):
    check_ov_acceptance = utils.str_to_bool(sem.cfg['overviews']['check_acceptance'])
    # Update current XY stage position
    stage.get_xy()
    success = True
    if selection == -1:
        # acquire all OVs
        start = 0
        end = ovm.number_ov
    else:
        # acquire only one OV
        start = selection
        end = selection + 1
    # Acquisition loop
    for ov_index in range(start, end):
        if not ovm[ov_index].active:
            continue
        #main_controls_trigger.transmit(utils.format_log_entry('STAGE: Moving to OV %d position.' % ov_index))
        utils.log_info('STAGE', f'Moving to OV {ov_index} position.')
        # Move to OV stage coordinates
        stage.move_to_xy(ovm[ov_index].centre_sx_sy)
        # Check to see if error ocurred
        if stage.error_state != Error.none:
            stage.reset_error_state()
            sleep(1)
            # Try again
            stage.move_to_xy(ovm[ov_index].centre_sx_sy)
            if stage.error_state != Error.none:
                stage.reset_error_state()
                #main_controls_trigger.transmit(utils.format_log_entry('STAGE: Second attempt to move to OV %d position failed.' % ov_index))
                utils.log_info('STAGE', f'Second attempt to move to OV {ov_index} position failed.')
                success = False
        if success:
            # Update stage position in Main Controls GUI and Viewport
            actual_xy = stage.get_xy()
            tol = max(float(getattr(stage, 'xy_tolerance', 0.0)), 0.5)
            dx = actual_xy[0] - ovm[ov_index].centre_sx_sy[0]
            dy = actual_xy[1] - ovm[ov_index].centre_sx_sy[1]
            if abs(dx) > tol or abs(dy) > tol:
                success = False
                utils.log_error(
                    'STAGE',
                    f'OV {ov_index}: stage mismatch after move. '
                    f'delta=({dx:.3f}, {dy:.3f}) um, tol={tol:.3f} um.')
                break
            main_controls_trigger.transmit('UPDATE XY')
            sleep(0.1)
            main_controls_trigger.transmit('DRAW VP')
            # Use custom focus settings for this OV if available
            ov_wd = ovm[ov_index].wd_stig_xy[0]
            if ov_wd > 0:
                sem.set_wd(ov_wd)
                stig_x, stig_y = ovm[ov_index].wd_stig_xy[1:3]
                sem.set_stig_xy(stig_x, stig_y)
                #main_controls_trigger.transmit(utils.format_log_entry('SEM: Using specified ' + utils.format_wd_stig(ov_wd, stig_x, stig_y)))
                utils.log_info('SEM', 'Using specified ' + utils.format_wd_stig(ov_wd, stig_x, stig_y))
            # Set specified OV frame settings
            sem.apply_frame_settings(ovm[ov_index].frame_size_selector,
                                     ovm[ov_index].pixel_size,
                                     ovm[ov_index].dwell_time)
            # Set bit depth
            sem.set_bit_depth(ovm[ov_index].bit_depth_selector)
            _log_ov_diagnostics(sem, ovm[ov_index], ov_index)
            save_path = os.path.join(
                base_dir, 'workspace',
                utils.get_ov_filename(None, ov_index))
            #main_controls_trigger.transmit(utils.format_log_entry('SEM: Acquiring OV %d.' % ov_index))
            utils.log_info('SEM', f'Acquiring OV {ov_index}.')
            # Indicate the overview being acquired in the viewport
            viewport_trigger.transmit('ACQ IND OV', ov_index)
            success = sem.acquire_frame(save_path, stage)
            # Remove indicator colour
            viewport_trigger.transmit('ACQ IND OV', ov_index)
            _, _, _, load_error, _, grab_incomplete = (
                img_inspector.load_and_inspect(save_path))
            if load_error or grab_incomplete and check_ov_acceptance:
                # Try again
                sleep(0.5)
                #main_controls_trigger.transmit(utils.format_log_entry('SEM: Second attempt: Acquiring OV %d.' % ov_index))
                utils.log_info('SEM', f'Second attempt: Acquiring OV {ov_index}.')
                viewport_trigger.transmit('ACQ IND OV', ov_index)
                success = sem.acquire_frame(save_path, stage)
                viewport_trigger.transmit('ACQ IND OV', ov_index)
                sleep(1)
                _, _, _, load_error, _, grab_incomplete = (
                    img_inspector.load_and_inspect(save_path))
                if load_error or grab_incomplete:
                    cause = 'load error' if load_error else 'grab incomplete'
                    utils.log_info(
                        'SEM',
                        f'Second attempt to acquire OV {ov_index} failed ({cause}).')
                    fallback_enabled = utils.str_to_bool(
                        sem.cfg['overviews'].get('auto_tile_ov_fallback', 'True'))
                    if fallback_enabled:
                        success = _acquire_ov_tiled_fallback(
                            base_dir, ov_index, sem, stage, ovm, img_inspector, save_path)
                        if success:
                            utils.log_info('SEM', f'OV {ov_index}: tiled fallback succeeded.')
                    if not success:
                        success = False
            if success:
                ovm[ov_index].vp_file_path = save_path
            _mark_ov_result(ovm[ov_index], success)
            # Show updated OV
            viewport_trigger.transmit('DRAW VP')
        if not success:
            _mark_ov_result(ovm[ov_index], False)
            break # leave loop if error has occured
    if success:
        viewport_trigger.transmit('REFRESH OV SUCCESS')
    else:
        viewport_trigger.transmit('REFRESH OV FAILURE')


def acquire_stub_ov(sem, stage, stub_ovm, acq, img_inspector,
                    stub_dlg_trigger, abort_queue):
    """Acquire a large tiled overview image of user-defined size that covers a
    part of or the entire stub (SEM sample holder).

    This function, which acquires the tiles one by one and combines them into
    one large image, is called in a thread from StubOVDlg.
    """
    success = True      # Set to False if an error occurs during acq process
    aborted = False     # Set to True when user clicks the 'Abort' button
    prev_vp_file_path = stub_ovm.vp_file_path

    # Update current XY position and display it in Main Controls GUI
    stage.get_xy()
    stub_dlg_trigger.transmit('UPDATE XY')

    if stage.use_microtome_xy:
        # When using the microtome for XY moves, make sure the correct motor 
        # speeds are being set. This is currently only relevant for Gatan 3View.
        success = stage.update_motor_speed()

    if success:
        image_counter = 0
        first_tile = True
        number_cols = stub_ovm.size[1]
        tile_width, tile_height = stub_ovm.tile_width_p(), stub_ovm.tile_height_p()
        overlap = stub_ovm.overlap
        metadata = None

        # Activate all tiles, which will automatically sort active tiles to
        # minimize motor move durations
        stub_ovm.activate_all_tiles()

        # NumPy array for final stitched image
        temp_save_path = os.path.join(
            acq.base_dir, 'workspace', 'temp_stub_ov' + constants.TEMP_IMAGE_FORMAT)
        stub_ovm.vp_file_path = temp_save_path
        is_single_tile = (len(stub_ovm.active_tiles) == 1)
        if not is_single_tile:
            shape = [stub_ovm.height_p(), stub_ovm.width_p()]
            depth = stub_ovm.tile_depth()
            if depth > 1:
                shape += [depth]
            full_stub_image = np.zeros(shape, dtype=np.uint8)
            # Save current stub image to temp_save_path to show live preview
            # during the acquisition
            imwrite(temp_save_path, full_stub_image, npyramid_add=4, pyramid_downsample=2)
        else:
            full_stub_image = None

        for tile_index in stub_ovm.active_tiles:
            if not abort_queue.empty():
                # Check if user has clicked 'Abort' button in dialog GUI
                if abort_queue.get() == 'ABORT':
                    stub_dlg_trigger.transmit('STUB OV ABORT')
                    sleep(0.5)
                    success = False
                    aborted = True
                    break
            target_x, target_y = stub_ovm[tile_index].sx_sy
            # Only acquire tile if it is within stage limits
            if stage.pos_within_limits((target_x, target_y)):
                stage.move_to_xy((target_x, target_y))
                if stage.error_state != Error.none:
                    stage.reset_error_state()
                    # Try once more
                    sleep(3)
                    stage.move_to_xy((target_x, target_y))
                    if stage.error_state != Error.none:
                        success = False
                        stage.reset_error_state()
                        stub_dlg_trigger.transmit(
                            f'The stage could not reach the target position of '
                            f'tile {tile_index} after two attempts. Please '
                            f'make sure that the XY stage limits and the XY '
                            f'motor speeds are set correctly.')

                if success:
                    # Show new stage coordinates in main control window
                    # and in Viewport (if stage position indicator active)
                    stub_dlg_trigger.transmit('UPDATE XY')
                    sleep(0.1)
                    stub_dlg_trigger.transmit('DRAW VP')
                    save_path = os.path.join(
                        acq.base_dir, 'workspace',
                        'stub' + str(tile_index).zfill(2) + constants.TEMP_IMAGE_FORMAT)
                    if first_tile:
                        # Set acquisition parameters
                        sem.apply_frame_settings(
                            stub_ovm.frame_size_selector,
                            stub_ovm.pixel_size,
                            stub_ovm.dwell_time)
                        sem.set_bit_depth(stub_ovm.bit_depth_selector)
                        first_tile = False
                    if stub_ovm.lm_mode:
                        success = sem.acquire_frame_lm(save_path, stage)
                    else:
                        success = sem.acquire_frame(save_path, stage)
                    sleep(0.5)
                    tile_img, _, _, load_error, _, grab_incomplete = (
                        img_inspector.load_and_inspect(save_path))
                    if load_error or grab_incomplete:
                        # Try again
                        sem.reset_error_state()
                        if stub_ovm.lm_mode:
                            success = sem.acquire_frame_lm(save_path, stage)
                        else:
                            success = sem.acquire_frame(save_path, stage)
                        sleep(1.5)
                        tile_img, _, _, load_error, _, grab_incomplete = (
                            img_inspector.load_and_inspect(save_path))
                        if load_error:
                            success = False
                            if load_error:
                                cause = 'load error'
                            elif grab_incomplete:
                                cause = 'grab incomplete'
                            else:
                                cause = 'acquisition error'
                            sem.reset_error_state()
                            stub_dlg_trigger.transmit(
                                f'Tile {tile_index} could not be successfully '
                                f'acquired after two attempts ({cause}).')
                    if success:
                        # Paste NumPy array of acquired tile (tile_img) into
                        # full_stub_image at the tile XY position
                        x = tile_index % number_cols
                        y = tile_index // number_cols
                        x_pos = x * (tile_width - overlap)
                        y_pos = y * (tile_height - overlap)
                        if is_single_tile:
                            full_stub_image = tile_img
                        else:
                            full_stub_image[y_pos:y_pos + tile_height,
                                            x_pos:x_pos + tile_width] = tile_img
                        # Save current stitched image and show it in Viewport
                        metadata = {'pixel_size': [stub_ovm.pixel_size * 1e-3] * 2,
                                    'position': stub_ovm.centre_sx_sy,
                                    'rotation': stub_ovm.rotation}
                        imwrite(temp_save_path, full_stub_image, metadata=metadata, npyramid_add=4, pyramid_downsample=2)
                        # Setting vp_file_path to temp_save_path reloads the current file
                        stub_ovm.vp_file_path = temp_save_path
                        stub_dlg_trigger.transmit('DRAW VP')
                        sleep(0.1)

            if not success:
                break

            # Update progress bar in dialog window
            image_counter += 1
            percentage_done = int(
                image_counter / stub_ovm.number_tiles * 100)
            stub_dlg_trigger.transmit(
                'UPDATE PROGRESS', percentage_done)

        # Write final full stub overview image and downsampled copies to disk
        # only if the acquisition completed successfully.
        if success and not aborted:
            stub_dir = os.path.join(acq.base_dir, 'overviews', 'stub')
            if not os.path.exists(stub_dir):
                os.makedirs(stub_dir)
            timestamp = str(datetime.datetime.now())
            # Remove some characters from timestap to get a valid file name
            timestamp = timestamp[:19].translate({ord(c): None for c in ' :-.'})
            stub_overview_file_name = os.path.join(
                acq.base_dir, 'overviews', 'stub',
                acq.stack_name + '_stubOV_s'
                + str(acq.slice_counter).zfill(5)
                + '_' + timestamp + constants.STUBOV_IMAGE_FORMAT)

            imwrite(stub_overview_file_name, full_stub_image, metadata=metadata, npyramid_add=4, pyramid_downsample=2)
            stub_ovm.vp_file_path = stub_overview_file_name
        else:
            # Restore previous stub OV
            stub_ovm.vp_file_path = prev_vp_file_path
            stub_dlg_trigger.transmit('DRAW VP')

    if success:
        # Signal to dialog window that stub OV acquisition was successful
        stub_dlg_trigger.transmit('STUB OV SUCCESS')
    elif not aborted:
        # Signal to dialog window that stub OV acquisition failed
        stub_dlg_trigger.transmit('STUB OV FAILURE')


def manual_sweep(microtome, main_controls_trigger):
    """Perform sweep requested by user in Main Controls window."""
    z_position = microtome.get_stage_z(wait_interval=1)
    if (z_position is not None) and (z_position >= 0):
        microtome.do_sweep(z_position)
    if microtome.error_state != Error.none:
        microtome.reset_error_state()
        main_controls_trigger.transmit('MANUAL SWEEP FAILURE')
    else:
        main_controls_trigger.transmit('MANUAL SWEEP SUCCESS')


def manual_stage_move(stage, target_position, viewport_trigger):
    """Move stage to target_position (X, Y), requested by user in Viewport.
    This function is run in a thread started in Viewport.py.
    """
    # Read current XY stage position to make sure that stage.last_known_xy
    # is up-to-date. Expected duration of the move is calculated with
    # stage.last_known_xy as the starting point.
    stage.get_xy()
    stage.move_to_xy(target_position)
    if stage.error_state != Error.none:
        stage.reset_error_state()
        sleep(1)
        # Try again
        stage.move_to_xy(target_position)
        if stage.error_state != Error.none:
            stage.reset_error_state()
            viewport_trigger.transmit('MANUAL MOVE FAILURE')
            return
    viewport_trigger.transmit('MANUAL MOVE SUCCESS')
