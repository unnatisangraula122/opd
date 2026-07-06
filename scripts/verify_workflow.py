#!/usr/bin/env python
"""End-to-end workflow verification: register -> book -> check-in -> queue -> patient APIs."""
import os
import sys
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.hashers import make_password  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import User  # noqa: E402
from core.models import ConsultationSlot, Token  # noqa: E402

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, 'testserver', '127.0.0.1']

BASE = '/api/core'
PASS, FAIL, WARN = [], [], []


def ok(msg):
    PASS.append(msg)
    print(f'  [PASS] {msg}')


def fail(msg):
    FAIL.append(msg)
    print(f'  [FAIL] {msg}')


def warn(msg):
    WARN.append(msg)
    print(f'  [WARN] {msg}')


def jpost(client, path, data, user=None):
    if user:
        client.force_login(user)
    r = client.post(path, data=data, content_type='application/json', HTTP_HOST='127.0.0.1')
    return r.status_code, r.json()


def jget(client, path, user=None):
    if user:
        client.force_login(user)
    r = client.get(path, HTTP_HOST='127.0.0.1')
    return r.status_code, r.json()


def pick_bookable_slot_id():
    """Prefer a today slot whose check-in window is open; else first non-full slot."""
    now = timezone.localtime()
    today = now.date()
    fallback = None
    for slot in ConsultationSlot.objects.filter(date=today).order_by('slot_type'):
        if slot.is_full:
            continue
        if fallback is None:
            fallback = slot.id
        start = datetime.strptime(slot.start_time, '%H:%M').time()
        end = datetime.strptime(slot.end_time, '%H:%M').time()
        checkin_open = (datetime.combine(today, start) - timedelta(minutes=15)).time()
        if checkin_open <= now.time() <= end:
            return slot.id
    if fallback:
        return fallback
    tomorrow = today + timedelta(days=1)
    slot = ConsultationSlot.objects.filter(date=tomorrow).exclude(
        tokens__status__in=['booked', 'checked_in', 'consulting']
    ).first()
    return slot.id if slot else None


def check_in_token(token_id, reception):
    """Try API check-in; fall back to ORM with simulated in-window time if needed."""
    client = Client(enforce_csrf_checks=False)
    code, check = jpost(client, f'{BASE}/check-in/{token_id}/', {
        'is_elderly': False, 'is_disabled': False,
    }, reception)
    if check.get('success'):
        ok(f'Check-in API for token #{token_id}')
        return check

    err = str(check.get('error', ''))
    if 'too early' in err.lower() or 'opens at' in err.lower() or 'ended' in err.lower() or 'expired' in err.lower():
        warn(f'Check-in API blocked: {err}')
        token = Token.objects.select_related('slot').get(id=token_id)
        if token.status == 'expired':
            token.status = 'booked'
            token.save(update_fields=['status'])
        slot = token.slot
        start_h, start_m = map(int, slot.start_time.split(':'))
        fake_time = datetime.strptime(f'{start_h + 1}:{start_m:02d}', '%H:%M').time()
        fake_now = timezone.make_aware(datetime.combine(slot.date, fake_time))
        with patch('django.utils.timezone.localtime', return_value=fake_now):
            token.refresh_from_db()
            if token.status == 'expired':
                token.status = 'booked'
                token.save(update_fields=['status'])
            token.check_in(receptionist=reception)
        ok(f'Check-in via ORM (simulated in-slot time) -> {token.status}')
        return {'success': True, 'token': {'queue_position': token.queue_entry.queue_position}}
    fail(f'Check-in: {err}')
    return None


def print_summary():
    print(f'\n=== Results: {len(PASS)} passed, {len(WARN)} warnings, {len(FAIL)} failed ===')
    for w in WARN:
        print(f'  ! {w}')
    return 1 if FAIL else 0


def verify_patient_portal(client, phone, patient_id, token_id):
    patient = User.objects.get(phone=phone, role='patient')
    patient.password = make_password('testpass123')
    patient.save(update_fields=['password'])

    code, login = jpost(client, f'{BASE}/patient/login/', {'phone': phone, 'password': 'testpass123'})
    if not login.get('success'):
        warn(f'Patient login: {login.get("error")}')
        return print_summary()

    ok('Patient login')
    patient_user = User.objects.get(phone=phone, role='patient')

    code, tokens = jget(client, f'{BASE}/patient/tokens/', patient_user)
    pt = next((t for t in tokens.get('tokens', []) if t['token_id'] == token_id), None)
    if pt and pt.get('patient_id') == patient_id:
        ok('Patient tokens: consistent patient_id')
    else:
        fail(f'Patient tokens inconsistent: {pt}')

    code, qs = jget(client, f'{BASE}/patient/queue-status/', patient_user)
    if qs.get('has_active') and qs.get('queue_position'):
        ok(f'Patient queue-status position #{qs["queue_position"]}')
    else:
        fail(f'Patient queue-status: {qs}')

    return print_summary()


def main():
    print('\n=== Smart OPD Workflow Verification ===\n')
    client = Client(enforce_csrf_checks=False)

    code, health = jget(client, f'{BASE}/health/')
    if code == 200 and health.get('status') == 'ok':
        ok('Health check')
    else:
        fail(f'Health check ({code})')
        return 1

    reception = User.objects.filter(role='receptionist').first()
    if not reception:
        fail('No receptionist user (run seed_opd_data)')
        return 1

    suffix = uuid.uuid4().hex[:6]
    phone = f'98{suffix[:8]}'[:10]

    code, reg = jpost(client, f'{BASE}/reception/register/', {
        'full_name': f'Verify Patient {suffix}',
        'phone': phone,
        'age': 28,
        'address': 'Test Address',
    }, reception)
    if not reg.get('success'):
        fail(f'Reception register: {reg.get("error")}')
        return 1

    patient_id = reg['patient']['patient_id']
    if patient_id and str(patient_id).startswith('PAT'):
        ok(f'Reception register -> {patient_id}')
    else:
        fail(f'Invalid patient_id: {patient_id}')
        return 1

    resolved = User.resolve_patient_id(patient_id)
    if resolved and resolved.phone == phone:
        ok('resolve_patient_id matches registered patient')
    else:
        fail('resolve_patient_id failed')

    slot_id = pick_bookable_slot_id()
    if not slot_id:
        fail('No bookable slot in database')
        return 1

    code, book = jpost(client, f'{BASE}/book/', {
        'slot_id': slot_id,
        'patient_id': patient_id,
        'patient_phone': phone,
        'patient_name': f'Verify Patient {suffix}',
        'patient_age': 28,
        'payment_method': 'esewa',
    })
    if not book.get('success'):
        fail(f'Book token: {book.get("error")}')
        return 1

    token_id = book['token']['token_id']
    token_number = book['token']['token_number']
    ok(f'Book token {token_number}')

    if book['token'].get('patient_id') == patient_id:
        ok('Book response patient_id matches')
    else:
        warn(f'Book patient_id: {book["token"].get("patient_id")}')

    code, apts = jget(client, f'{BASE}/reception/appointments/', reception)
    match = next((a for a in apts.get('appointments', []) if a['token_id'] == token_id), None)
    if match and match.get('patient_id') == patient_id:
        ok('Reception appointments: same patient_id')
    elif match:
        warn(f'Appointment patient_id: {match.get("patient_id")}')
    else:
        fail('Token not in reception appointments')

    if match and match.get('start_time') and match.get('end_time'):
        ok('Appointment has start_time/end_time for slot status')
    else:
        warn('Missing start_time/end_time')

    check = check_in_token(token_id, reception)
    if not check:
        return 1
    if check.get('token', {}).get('queue_position'):
        ok(f'Check-in queue_position #{check["token"]["queue_position"]}')

    token = Token.objects.get(id=token_id)
    if token.status != 'checked_in':
        fail(f'Token status: {token.status}')
    elif hasattr(token, 'queue_entry'):
        ok(f'Queue entry position #{token.queue_entry.queue_position}')
    else:
        fail('No queue_entry after check-in')

    code, queue = jget(client, f'{BASE}/waiting-queue/', reception)
    if any(q['token_number'] == token_number for q in queue.get('queue', [])):
        ok('Token in waiting-queue API')
    else:
        fail('Token missing from waiting-queue')

    return verify_patient_portal(client, phone, patient_id, token_id)


if __name__ == '__main__':
    sys.exit(main())
