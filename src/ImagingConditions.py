import datetime
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field

import utils


class ImagingConditionError(Exception):
    """Base exception for imaging-condition preset handling."""


class ImagingConditionDuplicateNameError(ImagingConditionError):
    """Raised when a preset name already exists."""


class ImagingConditionNotFoundError(ImagingConditionError):
    """Raised when a preset id could not be found."""


class ImagingConditionCompatibilityError(ImagingConditionError):
    """Raised when a preset cannot be applied in the current environment."""


@dataclass
class ImagingConditionPreset:
    schema_version: int = 1
    preset_id: str = ''
    name: str = ''
    created_at: str = ''
    updated_at: str = ''
    source_dialog: str = ''
    source_sem_device: str = ''
    frame_size_px: list = field(default_factory=list)
    pixel_size_nm: float = 0.0
    dwell_time_us: float = 0.0

    @classmethod
    def from_dict(cls, data):
        frame_size_px = data.get('frame_size_px', [])
        if (not isinstance(frame_size_px, (list, tuple))
                or len(frame_size_px) != 2):
            raise ValueError('frame_size_px must contain [width, height].')
        return cls(
            schema_version=int(data.get('schema_version', 1)),
            preset_id=str(data.get('preset_id', '')),
            name=str(data.get('name', '')).strip(),
            created_at=str(data.get('created_at', '')),
            updated_at=str(data.get('updated_at', '')),
            source_dialog=str(data.get('source_dialog', '')),
            source_sem_device=str(data.get('source_sem_device', '')),
            frame_size_px=[
                int(frame_size_px[0]),
                int(frame_size_px[1]),
            ],
            pixel_size_nm=float(data.get('pixel_size_nm', 0.0)),
            dwell_time_us=float(data.get('dwell_time_us', 0.0)),
        )

    def to_dict(self):
        return {
            'schema_version': int(self.schema_version),
            'preset_id': str(self.preset_id),
            'name': str(self.name),
            'created_at': str(self.created_at),
            'updated_at': str(self.updated_at),
            'source_dialog': str(self.source_dialog),
            'source_sem_device': str(self.source_sem_device),
            'frame_size_px': [
                int(self.frame_size_px[0]),
                int(self.frame_size_px[1]),
            ],
            'pixel_size_nm': float(self.pixel_size_nm),
            'dwell_time_us': float(self.dwell_time_us),
        }


class ImagingConditionStore:
    SCHEMA_VERSION = 1

    def __init__(self, storage_dir=None):
        self.storage_dir = storage_dir or os.path.join(
            'cfg', 'imaging_conditions')
        utils.validate_output_path(self.storage_dir)

    def _log_warning(self, message):
        try:
            utils.log_warning('CTRL', message)
        except Exception:
            print(message)

    def _preset_path(self, preset_id):
        return os.path.join(self.storage_dir, f'{preset_id}.json')

    def _timestamp(self):
        return datetime.datetime.now(datetime.timezone.utc).replace(
            microsecond=0).isoformat().replace('+00:00', 'Z')

    def _coerce_preset(self, preset):
        if isinstance(preset, ImagingConditionPreset):
            coerced = ImagingConditionPreset.from_dict(preset.to_dict())
        else:
            coerced = ImagingConditionPreset.from_dict(preset)
        if not coerced.name:
            raise ValueError('Preset name must not be empty.')
        if coerced.frame_size_px[0] <= 0 or coerced.frame_size_px[1] <= 0:
            raise ValueError('Frame size must be positive.')
        if coerced.pixel_size_nm <= 0:
            raise ValueError('Pixel size must be positive.')
        if coerced.dwell_time_us <= 0:
            raise ValueError('Dwell time must be positive.')
        return coerced

    def _write_preset(self, preset):
        utils.validate_output_path(self.storage_dir)
        path = self._preset_path(preset.preset_id)
        fd, tmp_path = tempfile.mkstemp(
            prefix='imaging_condition_',
            suffix='.tmp',
            dir=self.storage_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(
                    preset.to_dict(),
                    handle,
                    indent=2,
                    sort_keys=True)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _read_preset_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            preset = ImagingConditionPreset.from_dict(data)
            if preset.schema_version != self.SCHEMA_VERSION:
                raise ValueError(
                    f'Unsupported preset schema version {preset.schema_version}.')
            if not preset.preset_id:
                raise ValueError('Preset id missing.')
            return preset
        except Exception as exc:
            self._log_warning(
                f'CTRL: Ignoring invalid imaging-condition preset file '
                f'{os.path.basename(path)} ({exc}).')
            return None

    def list_presets(self):
        utils.validate_output_path(self.storage_dir)
        presets = []
        for file_name in os.listdir(self.storage_dir):
            if not file_name.lower().endswith('.json'):
                continue
            preset = self._read_preset_file(
                os.path.join(self.storage_dir, file_name))
            if preset is not None:
                presets.append(preset)
        return sorted(presets, key=lambda preset: preset.name.lower())

    def get_preset(self, preset_id):
        path = self._preset_path(preset_id)
        if not os.path.isfile(path):
            raise ImagingConditionNotFoundError(
                f'Preset {preset_id} not found.')
        preset = self._read_preset_file(path)
        if preset is None:
            raise ImagingConditionNotFoundError(
                f'Preset {preset_id} could not be loaded.')
        return preset

    def find_preset_by_name(self, name):
        name_key = name.strip().lower()
        for preset in self.list_presets():
            if preset.name.lower() == name_key:
                return preset
        return None

    def save_new_preset(self, name, preset):
        clean_name = name.strip()
        if not clean_name:
            raise ValueError('Preset name must not be empty.')
        if self.find_preset_by_name(clean_name) is not None:
            raise ImagingConditionDuplicateNameError(
                f'A preset named "{clean_name}" already exists.')
        if isinstance(preset, ImagingConditionPreset):
            preset.name = clean_name
        elif isinstance(preset, dict):
            preset = dict(preset)
            preset['name'] = clean_name
        preset = self._coerce_preset(preset)
        timestamp = self._timestamp()
        preset.schema_version = self.SCHEMA_VERSION
        preset.preset_id = uuid.uuid4().hex
        preset.name = clean_name
        preset.created_at = timestamp
        preset.updated_at = timestamp
        self._write_preset(preset)
        return preset

    def update_preset(self, preset_id, preset):
        existing = self.get_preset(preset_id)
        preset = self._coerce_preset(preset)
        colliding = self.find_preset_by_name(preset.name)
        if colliding is not None and colliding.preset_id != preset_id:
            raise ImagingConditionDuplicateNameError(
                f'A preset named "{preset.name}" already exists.')
        preset.schema_version = self.SCHEMA_VERSION
        preset.preset_id = existing.preset_id
        preset.created_at = existing.created_at
        preset.updated_at = self._timestamp()
        self._write_preset(preset)
        return preset

    def delete_preset(self, preset_id):
        path = self._preset_path(preset_id)
        if not os.path.isfile(path):
            raise ImagingConditionNotFoundError(
                f'Preset {preset_id} not found.')
        os.remove(path)

    def duplicate_preset(self, preset_id, new_name):
        preset = self.get_preset(preset_id)
        preset.name = new_name.strip()
        preset.preset_id = ''
        preset.created_at = ''
        preset.updated_at = ''
        return self.save_new_preset(new_name, preset)
