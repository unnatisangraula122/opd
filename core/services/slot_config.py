from datetime import datetime, time, timedelta

from django.utils import timezone

from core.models import ConsultationSlot, SlotTypeConfig

SLOT_TYPES = ('morning', 'afternoon', 'evening')

DEFAULT_SLOT_CONFIGS = {
    'morning': {
        'start_time': time(9, 0),
        'end_time': time(11, 0),
        'avg_consultation_minutes': 10,
        'checkin_opens_minutes_before': 15,
    },
    'afternoon': {
        'start_time': time(12, 0),
        'end_time': time(14, 0),
        'avg_consultation_minutes': 10,
        'checkin_opens_minutes_before': 15,
    },
    'evening': {
        'start_time': time(15, 0),
        'end_time': time(17, 0),
        'avg_consultation_minutes': 10,
        'checkin_opens_minutes_before': 15,
    },
}


def _format_clock(value):
    return value.strftime('%H:%M')


def _format_time_range(start, end):
    def label(t):
        return t.strftime('%I:%M %p').lstrip('0')
    return f"{label(start)} - {label(end)}"


def ensure_slot_type_configs():
    for slot_type, defaults in DEFAULT_SLOT_CONFIGS.items():
        SlotTypeConfig.objects.get_or_create(
            slot_type=slot_type,
            defaults=defaults,
        )


def get_slot_type_config(slot_type):
    ensure_slot_type_configs()
    try:
        return SlotTypeConfig.objects.get(slot_type=slot_type)
    except SlotTypeConfig.DoesNotExist:
        defaults = DEFAULT_SLOT_CONFIGS.get(slot_type, DEFAULT_SLOT_CONFIGS['morning'])
        return SlotTypeConfig(slot_type=slot_type, **defaults)


def serialize_slot_type_config(config):
    doctor = getattr(config, 'assigned_doctor', None)
    return {
        'slot_type': config.slot_type,
        'label': dict(ConsultationSlot.SLOT_TYPE).get(config.slot_type, config.slot_type.title()),
        'start_time': _format_clock(config.start_time),
        'end_time': _format_clock(config.end_time),
        'duration_minutes': config.duration_minutes,
        'avg_consultation_minutes': config.avg_consultation_minutes,
        'max_tokens': config.max_tokens,
        'checkin_opens_minutes_before': config.checkin_opens_minutes_before,
        'time_range': _format_time_range(config.start_time, config.end_time),
        'assigned_doctor_id': doctor.id if doctor else None,
        'assigned_doctor_name': str(doctor) if doctor else '',
    }


def get_all_slot_configs_serialized():
    ensure_slot_type_configs()
    configs = SlotTypeConfig.objects.filter(
        slot_type__in=SLOT_TYPES,
    ).select_related('assigned_doctor__user').order_by('slot_type')
    by_type = {cfg.slot_type: serialize_slot_type_config(cfg) for cfg in configs}
    for slot_type in SLOT_TYPES:
        by_type.setdefault(slot_type, serialize_slot_type_config(get_slot_type_config(slot_type)))
    return by_type


def refresh_consultation_slot_capacities():
    ensure_slot_type_configs()
    for slot_type in SLOT_TYPES:
        max_tokens = get_slot_type_config(slot_type).max_tokens
        ConsultationSlot.objects.filter(slot_type=slot_type).update(max_tokens=max_tokens)


def is_slot_ended(slot, now=None):
    """True when the slot's calendar day is past, or today's slot window has ended."""
    now = now or timezone.localtime()
    today = timezone.localdate()
    if slot.date < today:
        return True
    if slot.date > today:
        return False
    cfg = get_slot_type_config(slot.slot_type)
    return now.time() >= cfg.end_time


def is_slot_bookable(slot, now=None):
    """Slot can accept a new booking (not full, not passed)."""
    if slot.is_full:
        return False
    return not is_slot_ended(slot, now)


def get_active_slot_type(now=None):
    now = now or timezone.localtime()
    current = now.time()
    ensure_slot_type_configs()
    for cfg in SlotTypeConfig.objects.filter(slot_type__in=SLOT_TYPES):
        if cfg.start_time <= current < cfg.end_time:
            return cfg.slot_type
    return 'morning'


def parse_time_value(value):
    if isinstance(value, time):
        return value
    return datetime.strptime(str(value), '%H:%M').time()
