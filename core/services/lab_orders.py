"""Lab order helpers — repair corrupt rows and group reception payments."""
from decimal import Decimal

from django.db import transaction

from core.models import LabOrder, LabQueueEntry, Token
from core.services.lab_catalog import resolve_lab_test


def _is_corrupt_name(name):
    return len((name or '').strip()) <= 2


@transaction.atomic
def repair_corrupt_lab_orders(token_id=None):
    """
    Fix orders created when a test name string was split character-by-character.
    Merges fragments into one catalog test and removes bogus rows/queue entries.
    """
    qs = LabOrder.objects.filter(
        status__in=('ordered', 'fee_pending', 'in_queue'),
    ).select_related('token')
    if token_id is not None:
        qs = qs.filter(token_id=token_id)

    by_token = {}
    for order in qs:
        if _is_corrupt_name(order.test_name):
            by_token.setdefault(order.token_id, []).append(order)

    repaired = 0
    for tid, corrupt_list in by_token.items():
        corrupt_list.sort(key=lambda o: (o.ordered_at, o.id))

        if len(corrupt_list) < 3:
            for order in corrupt_list:
                LabQueueEntry.objects.filter(lab_order=order).delete()
                order.delete()
            continue

        joined = ''.join(o.test_name for o in corrupt_list)
        resolved = resolve_lab_test(joined)

        for order in corrupt_list:
            LabQueueEntry.objects.filter(lab_order=order).delete()
            order.delete()

        token = Token.objects.select_related('consultation').get(id=tid)
        if not token.lab_orders.filter(status__in=('ordered', 'fee_pending')).exists():
            LabOrder.objects.create(
                consultation=token.consultation,
                token=token,
                test_name=resolved['name'],
                fee=resolved['fee'],
                status='fee_pending',
            )
        repaired += 1

    return repaired


def normalize_pending_lab_order_names():
    """Fix test names/fees on unpaid orders using the catalog."""
    updated = 0
    for order in LabOrder.objects.filter(status__in=('ordered', 'fee_pending')):
        resolved = resolve_lab_test(order.test_name)
        changes = []
        if order.test_name != resolved['name']:
            order.test_name = resolved['name']
            changes.append('test_name')
        if order.fee != resolved['fee']:
            order.fee = resolved['fee']
            changes.append('fee')
        if changes:
            order.save(update_fields=changes)
            updated += 1
    return updated


def group_pending_lab_payments(orders_qs):
    """One reception row per patient/token with correct test list and total fee."""
    from core.utils import patient_id_for_token

    grouped = {}
    for order in orders_qs:
        key = order.token_id
        if key not in grouped:
            grouped[key] = {
                'token_id': order.token_id,
                'token_number': order.token.token_number,
                'patient_id': patient_id_for_token(order.token),
                'patient_name': order.token.patient_name,
                'tests': [],
                'orders': [],
                'amount': Decimal('0'),
            }
        row = grouped[key]
        name = order.test_name
        if name and name not in row['tests']:
            row['tests'].append(name)
        row['orders'].append({
            'order_id': order.id,
            'test_name': name,
            'amount': float(order.fee),
        })
        row['amount'] += order.fee

    data = []
    for row in grouped.values():
        tests = row['tests']
        amount = float(row['amount'])
        data.append({
            'token_id': row['token_id'],
            'token_number': row['token_number'],
            'patient_id': row['patient_id'],
            'patient_name': row['patient_name'],
            'test_name': ', '.join(tests),
            'tests': tests,
            'orders': row['orders'],
            'amount': amount,
            'order_id': row['orders'][0]['order_id'] if row['orders'] else None,
        })
    return data
