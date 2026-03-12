"""Helpers for stub-overview workflow orchestration."""

import os


STUB_ARCHIVE_SEM = 'stub_archive_sem'
STUB_ARCHIVE_LM = 'stub_archive_lm'
STUB_ARCHIVE_KINDS = {STUB_ARCHIVE_SEM, STUB_ARCHIVE_LM}


def stub_source_kind(lm_mode):
    return STUB_ARCHIVE_LM if lm_mode else STUB_ARCHIVE_SEM


def stub_mode_key(lm_mode):
    return 'stub_lm' if lm_mode else 'stub'


def stub_mode_label(source_kind):
    return 'LM' if source_kind == STUB_ARCHIVE_LM else 'SEM'


def stub_archive_description(image_path, source_kind):
    basename = os.path.basename(image_path)
    return f'Stub archive {stub_mode_label(source_kind)} - {basename}'


def normalize_bbox(bbox):
    x0, y0, x1, y1 = bbox
    min_x = min(x0, x1)
    min_y = min(y0, y1)
    max_x = max(x0, x1)
    max_y = max(y0, y1)
    return (min_x, min_y, max_x, max_y)


def bbox_overlap(bbox_a, bbox_b):
    ax0, ay0, ax1, ay1 = normalize_bbox(bbox_a)
    bx0, by0, bx1, by1 = normalize_bbox(bbox_b)
    return not (
        ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def bbox_from_centre_d(centre_dx_dy, width_um, height_um):
    centre_dx, centre_dy = centre_dx_dy
    half_width = width_um / 2
    half_height = height_um / 2
    return (
        centre_dx - half_width,
        centre_dy - half_height,
        centre_dx + half_width,
        centre_dy + half_height)


def image_dimensions_um(size_px, pixel_size_nm):
    width_um = size_px[0] * pixel_size_nm / 1000
    height_um = size_px[1] * pixel_size_nm / 1000
    return width_um, height_um


def stub_candidate_dimensions_um(grid_size, frame_size, overlap, pixel_size_nm):
    rows, cols = grid_size
    tile_width, tile_height = frame_size
    width_um = (
        cols * tile_width - (cols - 1) * overlap) * pixel_size_nm / 1000
    height_um = (
        rows * tile_height - (rows - 1) * overlap) * pixel_size_nm / 1000
    return width_um, height_um


def stub_candidate_bbox_d(cs, centre_sx_sy, grid_size, frame_size, overlap,
                          pixel_size_nm):
    centre_dx_dy = cs.convert_s_to_d(centre_sx_sy)
    width_um, height_um = stub_candidate_dimensions_um(
        grid_size, frame_size, overlap, pixel_size_nm)
    return bbox_from_centre_d(centre_dx_dy, width_um, height_um)


def imported_image_bbox_d(cs, imported_image):
    width_um, height_um = image_dimensions_um(
        imported_image.size, imported_image.pixel_size)
    centre_dx_dy = cs.convert_s_to_d(imported_image.centre_sx_sy)
    return bbox_from_centre_d(centre_dx_dy, width_um, height_um)


def active_stub_bbox_d(active_stub):
    return normalize_bbox(active_stub.bounding_box())


def _normalized_path(path):
    return os.path.normcase(os.path.abspath(path))


def has_matching_stub_archive(imported_images, image_path, source_kind):
    target = _normalized_path(image_path)
    for imported_image in imported_images:
        if imported_image.source_kind != source_kind:
            continue
        if _normalized_path(imported_image.image_src) == target:
            return True
    return False


def overlapping_stub_regions(cs, imported_images, active_stub, candidate_bbox_d,
                             source_kind):
    overlaps = []

    active_path = getattr(active_stub, 'vp_file_path', '')
    if active_path:
        if bbox_overlap(candidate_bbox_d, active_stub_bbox_d(active_stub)):
            overlaps.append({
                'type': 'active',
                'source_kind': source_kind,
                'label': f'current {stub_mode_label(source_kind)} stub',
            })

    for imported_image in imported_images:
        if imported_image.source_kind != source_kind:
            continue
        if bbox_overlap(candidate_bbox_d, imported_image_bbox_d(cs, imported_image)):
            overlaps.append({
                'type': 'archive',
                'source_kind': source_kind,
                'label': imported_image.description,
            })

    return overlaps
