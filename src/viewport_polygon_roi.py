import math
import os
import re
import xml.etree.ElementTree as ET

import numpy as np


PREDEFINED_SHAPE_TYPES = ('rectangle', 'circle', 'triangle')
CUSTOM_SHAPE_TYPE = 'custom'
IMPORTED_SHAPE_TYPE = 'imported'
DEFAULT_SHAPE_FOV_FRACTION = 0.28
CIRCLE_SEGMENT_COUNT = 24
SVG_DPI = 96.0
UM_PER_INCH = 25400.0
UM_PER_PX = UM_PER_INCH / SVG_DPI


def rectangle_points_norm():
    return [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def triangle_points_norm():
    return [[0.5, 0.0], [1.0, 1.0], [0.0, 1.0]]


def circle_points_norm(segment_count=CIRCLE_SEGMENT_COUNT):
    points = []
    for index in range(segment_count):
        angle = 2 * math.pi * index / segment_count
        points.append([
            0.5 + 0.5 * math.cos(angle),
            0.5 + 0.5 * math.sin(angle),
        ])
    return points


def predefined_points_norm(shape_type):
    if shape_type == 'rectangle':
        return rectangle_points_norm()
    if shape_type == 'circle':
        return circle_points_norm()
    if shape_type == 'triangle':
        return triangle_points_norm()
    raise ValueError(f'Unsupported predefined shape type: {shape_type}')


def normalize_points(points):
    if len(points) < 3:
        raise ValueError('Polygon requires at least 3 points.')
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    normalized = []
    for x_pos, y_pos in points:
        normalized.append([
            float((x_pos - min_x) / width),
            float((y_pos - min_y) / height),
        ])
    return normalized, (float(min_x), float(min_y), float(width), float(height))


def denormalize_points(points_norm, width, height, x_offset=0.0, y_offset=0.0):
    points = []
    for x_pos, y_pos in points_norm:
        points.append([
            float(x_offset + x_pos * width),
            float(y_offset + y_pos * height),
        ])
    return points


def get_bounds(points):
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return float(min_x), float(min_y), float(max_x - min_x), float(max_y - min_y)


def make_default_shape_bounds(centre_dx, centre_dy, vp_width_d, vp_height_d,
                              shape_type):
    base_width = max(1.0, vp_width_d * DEFAULT_SHAPE_FOV_FRACTION)
    base_height = max(1.0, vp_height_d * DEFAULT_SHAPE_FOV_FRACTION)
    if shape_type == 'circle':
        diameter = min(base_width, base_height)
        base_width = diameter
        base_height = diameter
    elif shape_type == 'triangle':
        base_height *= 0.9
    x_pos = centre_dx - base_width / 2
    y_pos = centre_dy - base_height / 2
    return float(x_pos), float(y_pos), float(base_width), float(base_height)


def point_in_polygon(point, polygon):
    x_pos, y_pos = point
    inside = False
    count = len(polygon)
    if count < 3:
        return False
    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]
        if ((y0 > y_pos) != (y1 > y_pos)):
            denom = (y1 - y0)
            if denom == 0:
                continue
            x_intersection = (x1 - x0) * (y_pos - y0) / denom + x0
            if x_pos <= x_intersection:
                inside = not inside
    return inside


def point_in_rect(point, rect):
    x_pos, y_pos = point
    left, top, right, bottom = rect
    return left <= x_pos <= right and top <= y_pos <= bottom


def _orientation(point_a, point_b, point_c):
    value = ((point_b[1] - point_a[1]) * (point_c[0] - point_b[0])
             - (point_b[0] - point_a[0]) * (point_c[1] - point_b[1]))
    if abs(value) < 1e-9:
        return 0
    return 1 if value > 0 else 2


def _on_segment(point_a, point_b, point_c):
    return (
        min(point_a[0], point_c[0]) - 1e-9 <= point_b[0] <= max(point_a[0], point_c[0]) + 1e-9
        and min(point_a[1], point_c[1]) - 1e-9 <= point_b[1] <= max(point_a[1], point_c[1]) + 1e-9
    )


def segments_intersect(seg1_start, seg1_end, seg2_start, seg2_end):
    orientation_1 = _orientation(seg1_start, seg1_end, seg2_start)
    orientation_2 = _orientation(seg1_start, seg1_end, seg2_end)
    orientation_3 = _orientation(seg2_start, seg2_end, seg1_start)
    orientation_4 = _orientation(seg2_start, seg2_end, seg1_end)

    if orientation_1 != orientation_2 and orientation_3 != orientation_4:
        return True

    if orientation_1 == 0 and _on_segment(seg1_start, seg2_start, seg1_end):
        return True
    if orientation_2 == 0 and _on_segment(seg1_start, seg2_end, seg1_end):
        return True
    if orientation_3 == 0 and _on_segment(seg2_start, seg1_start, seg2_end):
        return True
    if orientation_4 == 0 and _on_segment(seg2_start, seg1_end, seg2_end):
        return True
    return False


def polygon_intersects_rect(polygon, rect):
    left, top, right, bottom = rect
    rect_points = [
        [left, top],
        [right, top],
        [right, bottom],
        [left, bottom],
    ]
    rect_edges = [
        (rect_points[0], rect_points[1]),
        (rect_points[1], rect_points[2]),
        (rect_points[2], rect_points[3]),
        (rect_points[3], rect_points[0]),
    ]

    for point in polygon:
        if point_in_rect(point, rect):
            return True

    for point in rect_points:
        if point_in_polygon(point, polygon):
            return True

    for index in range(len(polygon)):
        edge_start = polygon[index]
        edge_end = polygon[(index + 1) % len(polygon)]
        for rect_start, rect_end in rect_edges:
            if segments_intersect(edge_start, edge_end, rect_start, rect_end):
                return True
    return False


def rotate_points(points, centre, angle_deg):
    if abs(angle_deg) < 1e-9:
        return [list(point) for point in points]
    angle_rad = math.radians(angle_deg)
    cos_theta = math.cos(angle_rad)
    sin_theta = math.sin(angle_rad)
    centre_x, centre_y = centre
    rotated = []
    for x_pos, y_pos in points:
        rel_x = x_pos - centre_x
        rel_y = y_pos - centre_y
        rotated.append([
            centre_x + rel_x * cos_theta - rel_y * sin_theta,
            centre_y + rel_x * sin_theta + rel_y * cos_theta,
        ])
    return rotated


def parse_svg_shape(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    namespace_prefix = ''
    if root.tag.startswith('{'):
        namespace_prefix = root.tag.split('}')[0] + '}'

    polygon_element = root.find(f'.//{namespace_prefix}polygon')
    if polygon_element is not None:
        points = _parse_svg_polygon_points(polygon_element.attrib.get('points', ''))
    else:
        path_element = root.find(f'.//{namespace_prefix}path')
        if path_element is not None:
            points = _parse_svg_path_points(path_element.attrib.get('d', ''))
        else:
            raise ValueError('SVG must contain a polygon or a straight-line path.')

    scaled_points = _scale_svg_points_to_um(root, points)
    points_norm, bounds = normalize_points(scaled_points)
    return {
        'points': scaled_points,
        'points_norm': points_norm,
        'bounds_um': bounds,
    }


def parse_svg_points(svg_path):
    return parse_svg_shape(svg_path)['points']


def svg_shape_name(svg_path):
    return os.path.splitext(os.path.basename(svg_path))[0]


def _parse_svg_viewbox(viewbox_text):
    if not viewbox_text:
        return None
    values = re.split(r'[\s,]+', viewbox_text.strip())
    if len(values) != 4:
        return None
    try:
        return tuple(float(value) for value in values)
    except ValueError:
        return None


def _parse_svg_length(length_text):
    if not length_text:
        return None
    match = re.fullmatch(
        r'\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*([A-Za-z%]*)\s*',
        str(length_text))
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower() or 'px'
    if unit == '%':
        return None
    return value, unit


def _svg_length_to_px(length_text):
    parsed = _parse_svg_length(length_text)
    if parsed is None:
        return None
    value, unit = parsed
    if unit == 'px':
        return value
    if unit == 'in':
        return value * SVG_DPI
    if unit == 'cm':
        return value * SVG_DPI / 2.54
    if unit == 'mm':
        return value * SVG_DPI / 25.4
    if unit == 'q':
        return value * SVG_DPI / (25.4 * 4)
    if unit == 'pt':
        return value * SVG_DPI / 72.0
    if unit == 'pc':
        return value * SVG_DPI / 6.0
    return None


def _svg_length_to_um(length_text):
    parsed = _parse_svg_length(length_text)
    if parsed is None:
        return None
    value, unit = parsed
    if unit == 'px':
        return value * UM_PER_PX
    if unit == 'in':
        return value * UM_PER_INCH
    if unit == 'cm':
        return value * 10000.0
    if unit == 'mm':
        return value * 1000.0
    if unit == 'q':
        return value * 250.0
    if unit == 'pt':
        return value * UM_PER_INCH / 72.0
    if unit == 'pc':
        return value * UM_PER_INCH / 6.0
    return None


def _svg_viewport_size(root, bounds):
    width_attr = root.attrib.get('width')
    height_attr = root.attrib.get('height')
    width_px = _svg_length_to_px(width_attr)
    height_px = _svg_length_to_px(height_attr)
    width_um = _svg_length_to_um(width_attr)
    height_um = _svg_length_to_um(height_attr)

    viewbox = _parse_svg_viewbox(root.attrib.get('viewBox'))
    if viewbox is not None:
        origin_x, origin_y, coord_width, coord_height = viewbox
    else:
        origin_x, origin_y = 0.0, 0.0
        coord_width = width_px if width_px is not None else bounds[2]
        coord_height = height_px if height_px is not None else bounds[3]

    coord_width = max(float(coord_width), 1e-9)
    coord_height = max(float(coord_height), 1e-9)
    if width_um is None:
        width_um = coord_width * UM_PER_PX
    if height_um is None:
        height_um = coord_height * UM_PER_PX

    return {
        'origin': (float(origin_x), float(origin_y)),
        'coord_size': (coord_width, coord_height),
        'physical_size_um': (float(width_um), float(height_um)),
    }


def _scale_svg_points_to_um(root, points):
    bounds = get_bounds(points)
    viewport = _svg_viewport_size(root, bounds)
    origin_x, origin_y = viewport['origin']
    coord_width, coord_height = viewport['coord_size']
    width_um, height_um = viewport['physical_size_um']
    scale_x = width_um / max(coord_width, 1e-9)
    scale_y = height_um / max(coord_height, 1e-9)

    scaled_points = []
    for x_pos, y_pos in points:
        scaled_points.append([
            float((x_pos - origin_x) * scale_x),
            float((y_pos - origin_y) * scale_y),
        ])
    return scaled_points


def _parse_svg_polygon_points(points_text):
    tokens = re.split(r'[\s,]+', points_text.strip())
    values = [token for token in tokens if token]
    if len(values) < 6 or len(values) % 2 != 0:
        raise ValueError('SVG polygon points are invalid.')
    points = []
    for index in range(0, len(values), 2):
        points.append([float(values[index]), float(values[index + 1])])
    return points


def _parse_svg_path_points(path_text):
    tokens = re.findall(r'[MmLlHhVvZz]|-?\d+(?:\.\d+)?', path_text)
    points = []
    command = None
    cursor = [0.0, 0.0]
    start_point = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r'[MmLlHhVvZz]', token):
            command = token
            index += 1
            if command in ('Z', 'z'):
                break
            continue
        if command is None:
            raise ValueError('SVG path must start with a move command.')
        if command in ('M', 'L'):
            if index + 1 >= len(tokens):
                raise ValueError('SVG path is truncated.')
            cursor = [float(tokens[index]), float(tokens[index + 1])]
            index += 2
        elif command in ('m', 'l'):
            if index + 1 >= len(tokens):
                raise ValueError('SVG path is truncated.')
            cursor = [
                cursor[0] + float(tokens[index]),
                cursor[1] + float(tokens[index + 1]),
            ]
            index += 2
        elif command == 'H':
            cursor = [float(tokens[index]), cursor[1]]
            index += 1
        elif command == 'h':
            cursor = [cursor[0] + float(tokens[index]), cursor[1]]
            index += 1
        elif command == 'V':
            cursor = [cursor[0], float(tokens[index])]
            index += 1
        elif command == 'v':
            cursor = [cursor[0], cursor[1] + float(tokens[index])]
            index += 1
        else:
            raise ValueError('Unsupported SVG path command.')
        if start_point is None:
            start_point = list(cursor)
        points.append(list(cursor))
    if len(points) < 3:
        raise ValueError('SVG path must describe a closed polygon.')
    if start_point is not None and np.linalg.norm(np.array(points[-1]) - np.array(start_point)) < 1e-9:
        points.pop()
    return points
