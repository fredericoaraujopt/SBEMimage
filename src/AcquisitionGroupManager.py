import json

import constants


class AcquisitionGroupManager:
    """Own acquisition-manager hierarchy, assignments, and effective colours."""

    SECTION = 'acquisition_manager'
    UI_DEFAULTS = {
        'ui_view_preset': 'All items',
        'ui_filter_active_only': 'False',
        'ui_filter_locked_only': 'False',
        'ui_filter_failed_only': 'False',
        'ui_filter_current_group_only': 'False',
    }

    def __init__(self, cfg, grid_manager, overview_manager):
        self.cfg = cfg
        self.gm = grid_manager
        self.ovm = overview_manager
        if not self.cfg.has_section(self.SECTION):
            self.cfg.add_section(self.SECTION)
        self._group_nodes = {}
        self._grid_group_ids = []
        self._ov_group_ids = []
        self._load_from_cfg()
        self.sync_inventory()

    def _load_json(self, key, default):
        try:
            return json.loads(self.cfg[self.SECTION].get(key, json.dumps(default)))
        except Exception:
            return default

    def _load_from_cfg(self):
        raw_nodes = self._load_json('group_nodes', [])
        seen_ids = set()
        nodes = {}
        for index, raw_node in enumerate(raw_nodes):
            if not isinstance(raw_node, dict):
                continue
            group_id = str(raw_node.get('id', '')).strip()
            if not group_id or group_id in seen_ids:
                continue
            seen_ids.add(group_id)
            colour = raw_node.get('colour', 0)
            try:
                colour = int(colour)
            except Exception:
                colour = 0
            colour = min(9, max(0, colour))
            parent_id = raw_node.get('parent_id')
            if parent_id in ['', 'null']:
                parent_id = None
            elif parent_id is not None:
                parent_id = str(parent_id)
            try:
                sort_index = int(raw_node.get('sort_index', index))
            except Exception:
                sort_index = index
            nodes[group_id] = {
                'id': group_id,
                'name': str(raw_node.get('name', 'Group')).strip() or 'Group',
                'parent_id': parent_id,
                'colour': colour,
                'sort_index': sort_index,
                'expanded': bool(raw_node.get('expanded', True)),
            }
        self._group_nodes = nodes
        self._remove_invalid_group_links()
        self._grid_group_ids = self._sanitize_assignment_list(
            self._load_json('grid_group_ids', []))
        self._ov_group_ids = self._sanitize_assignment_list(
            self._load_json('ov_group_ids', []))

    def _sanitize_assignment_list(self, values):
        assignments = []
        valid_ids = set(self._group_nodes)
        for value in values:
            if value in [None, '', 'null']:
                assignments.append(None)
            else:
                value = str(value)
                assignments.append(value if value in valid_ids else None)
        return assignments

    def _remove_invalid_group_links(self):
        valid_ids = set(self._group_nodes)
        for group_id, node in self._group_nodes.items():
            parent_id = node['parent_id']
            if parent_id not in valid_ids or parent_id == group_id:
                node['parent_id'] = None
        for group_id in list(self._group_nodes):
            if self._would_create_cycle(group_id, self._group_nodes[group_id]['parent_id']):
                self._group_nodes[group_id]['parent_id'] = None
        self._normalize_all_sort_indices()

    def _would_create_cycle(self, group_id, parent_id):
        visited = set()
        while parent_id is not None:
            if parent_id == group_id:
                return True
            if parent_id in visited:
                return True
            visited.add(parent_id)
            node = self._group_nodes.get(parent_id)
            if node is None:
                return False
            parent_id = node['parent_id']
        return False

    def sync_inventory(self):
        self._remove_invalid_group_links()
        valid_ids = set(self._group_nodes)
        self._grid_group_ids = [
            group_id if group_id in valid_ids else None
            for group_id in self._grid_group_ids[:self.gm.number_grids]
        ]
        while len(self._grid_group_ids) < self.gm.number_grids:
            self._grid_group_ids.append(None)
        self._ov_group_ids = [
            group_id if group_id in valid_ids else None
            for group_id in self._ov_group_ids[:self.ovm.number_ov]
        ]
        while len(self._ov_group_ids) < self.ovm.number_ov:
            self._ov_group_ids.append(None)

    def _normalize_all_sort_indices(self):
        for parent_id in [None] + list(self._group_nodes):
            self._normalize_sort_indices(parent_id)

    def _normalize_sort_indices(self, parent_id):
        children = self.child_group_ids(parent_id)
        for sort_index, group_id in enumerate(children):
            self._group_nodes[group_id]['sort_index'] = sort_index

    def _generate_group_id(self):
        next_index = 1
        existing = set(self._group_nodes)
        while True:
            group_id = f'group-{next_index}'
            if group_id not in existing:
                return group_id
            next_index += 1

    def _next_sort_index(self, parent_id):
        return len(self.child_group_ids(parent_id))

    def child_group_ids(self, parent_id):
        return [
            node['id'] for node in sorted(
                self._group_nodes.values(),
                key=lambda item: (
                    item['parent_id'] is not None,
                    item['sort_index'],
                    item['name'].lower(),
                    item['id']))
            if node['parent_id'] == parent_id
        ]

    def groups(self):
        ordered = []

        def append_children(parent_id):
            for group_id in self.child_group_ids(parent_id):
                ordered.append(dict(self._group_nodes[group_id]))
                append_children(group_id)

        append_children(None)
        return ordered

    def group(self, group_id):
        if group_id not in self._group_nodes:
            return None
        return dict(self._group_nodes[group_id])

    def has_group(self, group_id):
        return group_id in self._group_nodes

    def create_group(self, name='New group', parent_id=None):
        if parent_id not in self._group_nodes:
            parent_id = None
        if parent_id is None:
            colour = self.next_available_top_level_colour()
        else:
            colour = self._group_nodes[parent_id]['colour']
        group_id = self._generate_group_id()
        self._group_nodes[group_id] = {
            'id': group_id,
            'name': str(name).strip() or 'New group',
            'parent_id': parent_id,
            'colour': colour,
            'sort_index': self._next_sort_index(parent_id),
            'expanded': True,
        }
        return group_id

    def delete_group(self, group_id):
        node = self._group_nodes.get(group_id)
        if node is None:
            return
        parent_id = node['parent_id']
        for child_group_id in self.child_group_ids(group_id):
            self._group_nodes[child_group_id]['parent_id'] = parent_id
        self._grid_group_ids = [
            parent_id if value == group_id else value
            for value in self._grid_group_ids
        ]
        self._ov_group_ids = [
            parent_id if value == group_id else value
            for value in self._ov_group_ids
        ]
        del self._group_nodes[group_id]
        self._normalize_all_sort_indices()

    def rename_group(self, group_id, name):
        if group_id in self._group_nodes:
            self._group_nodes[group_id]['name'] = str(name).strip() or 'Group'

    def set_group_colour(self, group_id, colour):
        if group_id not in self._group_nodes:
            return
        try:
            colour = int(colour)
        except Exception:
            colour = self._group_nodes[group_id]['colour']
        self._group_nodes[group_id]['colour'] = min(9, max(0, colour))

    def set_group_expanded(self, group_id, expanded):
        if group_id in self._group_nodes:
            self._group_nodes[group_id]['expanded'] = bool(expanded)

    def next_available_top_level_colour(self):
        used = {
            self._group_nodes[group_id]['colour']
            for group_id in self.child_group_ids(None)
        }
        for colour in range(10):
            if colour not in used:
                return colour
        return 0

    def apply_group_tree_order(self, ordered_pairs):
        """Update parent/order from a flattened [(group_id, parent_id), ...] list."""
        sibling_order = {}
        for group_id, parent_id in ordered_pairs:
            if group_id not in self._group_nodes:
                continue
            if parent_id not in self._group_nodes:
                parent_id = None
            if self._would_create_cycle(group_id, parent_id):
                parent_id = None
            self._group_nodes[group_id]['parent_id'] = parent_id
            sibling_order.setdefault(parent_id, []).append(group_id)
        for parent_id, group_ids in sibling_order.items():
            for sort_index, group_id in enumerate(group_ids):
                self._group_nodes[group_id]['sort_index'] = sort_index
        self._normalize_all_sort_indices()

    def assign_grid(self, grid_index, group_id):
        self.sync_inventory()
        if not (0 <= grid_index < self.gm.number_grids):
            return
        self._grid_group_ids[grid_index] = group_id if group_id in self._group_nodes else None

    def assign_overview(self, ov_index, group_id):
        self.sync_inventory()
        if not (0 <= ov_index < self.ovm.number_ov):
            return
        self._ov_group_ids[ov_index] = group_id if group_id in self._group_nodes else None

    def grid_group_id(self, grid_index):
        self.sync_inventory()
        if 0 <= grid_index < len(self._grid_group_ids):
            return self._grid_group_ids[grid_index]
        return None

    def overview_group_id(self, ov_index):
        self.sync_inventory()
        if 0 <= ov_index < len(self._ov_group_ids):
            return self._ov_group_ids[ov_index]
        return None

    def group_path_ids(self, group_id):
        if group_id not in self._group_nodes:
            return []
        path = []
        while group_id is not None and group_id in self._group_nodes:
            path.append(group_id)
            group_id = self._group_nodes[group_id]['parent_id']
        path.reverse()
        return path

    def group_path_text(self, group_id):
        path = self.group_path_ids(group_id)
        if not path:
            return 'Ungrouped'
        return ' / '.join(self._group_nodes[path_id]['name'] for path_id in path)

    def grid_group_path_text(self, grid_index):
        return self.group_path_text(self.grid_group_id(grid_index))

    def overview_group_path_text(self, ov_index):
        return self.group_path_text(self.overview_group_id(ov_index))

    def descendant_group_ids(self, group_id):
        descendants = []
        stack = [group_id]
        while stack:
            current = stack.pop()
            for child_group_id in self.child_group_ids(current):
                descendants.append(child_group_id)
                stack.append(child_group_id)
        return descendants

    def grouped_grid_indices(self, group_id, include_descendants=True):
        if include_descendants:
            group_ids = {group_id, *self.descendant_group_ids(group_id)}
        else:
            group_ids = {group_id}
        return [
            grid_index for grid_index, assigned_group_id in enumerate(self._grid_group_ids)
            if assigned_group_id in group_ids
        ]

    def grouped_overview_indices(self, group_id, include_descendants=True):
        if include_descendants:
            group_ids = {group_id, *self.descendant_group_ids(group_id)}
        else:
            group_ids = {group_id}
        return [
            ov_index for ov_index, assigned_group_id in enumerate(self._ov_group_ids)
            if assigned_group_id in group_ids
        ]

    def group_summary(self, group_id, slice_counter):
        self.sync_inventory()
        ov_indices = self.grouped_overview_indices(group_id)
        grid_indices = self.grouped_grid_indices(group_id)
        active_ov = 0
        active_grids = 0
        active_tiles = 0
        locked_items = 0
        acquired_items = 0
        intervallic_items = 0
        slice_ready_ov = 0
        slice_ready_grids = 0
        slice_ready_tiles = 0

        for ov_index in ov_indices:
            overview = self.ovm[ov_index]
            if overview.active:
                active_ov += 1
                if overview.slice_active(slice_counter):
                    slice_ready_ov += 1
            if overview.locked:
                locked_items += 1
            if overview.acquired:
                acquired_items += 1
            if overview.active and overview.acq_interval > 1:
                intervallic_items += 1

        for grid_index in grid_indices:
            grid = self.gm[grid_index]
            if grid.active:
                active_grids += 1
                active_tiles += grid.number_active_tiles()
                if grid.slice_active(slice_counter):
                    slice_ready_grids += 1
                    slice_ready_tiles += grid.number_active_tiles()
            if grid.locked:
                locked_items += 1
            if grid.acquired:
                acquired_items += 1
            if grid.active and grid.acq_interval > 1:
                intervallic_items += 1

        current_slice_note = (
            f'Current slice {slice_counter}: '
            f'{slice_ready_ov} overview(s), '
            f'{slice_ready_grids} grid(s), '
            f'{slice_ready_tiles} active tile(s) are eligible.'
        )
        return {
            'active_overviews': active_ov,
            'active_grids': active_grids,
            'active_tiles': active_tiles,
            'locked_items': locked_items,
            'acquired_items': acquired_items,
            'intervallic_items': intervallic_items,
            'current_slice_note': current_slice_note,
        }

    def effective_grid_display_colour(self, grid_index):
        self.sync_inventory()
        if not (0 <= grid_index < self.gm.number_grids):
            return 0
        raw_colour = self.gm[grid_index].display_colour
        if raw_colour == 13:
            return 13
        group_id = self.grid_group_id(grid_index)
        if group_id in self._group_nodes:
            return self._group_nodes[group_id]['colour']
        return raw_colour

    def effective_grid_colour_rgb(self, grid_index):
        colour_index = self.effective_grid_display_colour(grid_index)
        if 0 <= colour_index < len(constants.COLOUR_SELECTOR):
            return constants.COLOUR_SELECTOR[colour_index]
        return constants.COLOUR_SELECTOR[0]

    def overview_accent_colour(self, ov_index):
        group_id = self.overview_group_id(ov_index)
        if group_id not in self._group_nodes:
            return None
        colour_index = self._group_nodes[group_id]['colour']
        if 0 <= colour_index < len(constants.COLOUR_SELECTOR):
            return constants.COLOUR_SELECTOR[colour_index]
        return None

    def save_to_cfg(self):
        self.sync_inventory()
        self.cfg[self.SECTION]['group_nodes'] = json.dumps(self.groups())
        self.cfg[self.SECTION]['grid_group_ids'] = json.dumps(self._grid_group_ids)
        self.cfg[self.SECTION]['ov_group_ids'] = json.dumps(self._ov_group_ids)

    def load_ui_state(self):
        section = self.cfg[self.SECTION]
        return {
            'view_preset': section.get(
                'ui_view_preset', self.UI_DEFAULTS['ui_view_preset']),
            'filter_active_only': (
                section.get(
                    'ui_filter_active_only',
                    self.UI_DEFAULTS['ui_filter_active_only']).lower()
                == 'true'),
            'filter_locked_only': (
                section.get(
                    'ui_filter_locked_only',
                    self.UI_DEFAULTS['ui_filter_locked_only']).lower()
                == 'true'),
            'filter_failed_only': (
                section.get(
                    'ui_filter_failed_only',
                    self.UI_DEFAULTS['ui_filter_failed_only']).lower()
                == 'true'),
            'filter_current_group_only': (
                section.get(
                    'ui_filter_current_group_only',
                    self.UI_DEFAULTS['ui_filter_current_group_only']).lower()
                == 'true'),
        }

    def save_ui_state(self, state):
        section = self.cfg[self.SECTION]
        section['ui_view_preset'] = str(
            state.get('view_preset', self.UI_DEFAULTS['ui_view_preset']))
        section['ui_filter_active_only'] = str(bool(
            state.get('filter_active_only', False)))
        section['ui_filter_locked_only'] = str(bool(
            state.get('filter_locked_only', False)))
        section['ui_filter_failed_only'] = str(bool(
            state.get('filter_failed_only', False)))
        section['ui_filter_current_group_only'] = str(bool(
            state.get('filter_current_group_only', False)))
