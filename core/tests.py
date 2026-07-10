from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core import constants as C
from core.models import (
    ConsultationSlot,
    DoctorProfile,
    LabOrder,
    LabQueueEntry,
    PharmacyQueueEntry,
    Token,
)
from core.services.workflow import after_lab_report_uploaded, complete_consultation
from core.views.lab import lab_queue
from core.views.reception import pay_lab_fee
from rest_framework.test import APIRequestFactory, force_authenticate


class LabPaymentQueueFlowTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.today = timezone.localdate()

        self.receptionist = User.objects.create_user(
            username='reception_lab',
            password='pass',
            role='receptionist',
        )
        self.lab_tech = User.objects.create_user(
            username='labtech1',
            password='pass',
            role='lab_tech',
        )
        doctor_user = User.objects.create_user(
            username='doctor_lab',
            password='pass',
            role='doctor',
            first_name='Test',
            last_name='Doctor',
        )
        self.doctor = DoctorProfile.objects.create(
            user=doctor_user,
            specialization='General Physician',
        )
        self.slot = ConsultationSlot.objects.create(
            doctor=self.doctor,
            date=self.today,
            slot_type='morning',
            start_time='08:00',
            end_time='11:00',
            max_tokens=20,
        )
        self.token = Token.objects.create(
            slot=self.slot,
            patient_name='Lab Patient',
            patient_age=30,
            patient_phone='9800000001',
            token_number='T1',
            status=C.CONSULTING,
        )

    def test_lab_fee_payment_sends_order_to_lab_dashboard(self):
        complete_consultation(
            self.token,
            symptoms='fever',
            diagnosis='malaria screen',
            lab_tests=['Complete Blood Count (CBC)'],
        )
        order = LabOrder.objects.get(token=self.token)
        self.assertEqual(order.status, 'fee_pending')

        pay_request = self.factory.post(
            f'/api/core/reception/lab-pay/{order.id}/',
            {'amount': float(order.fee)},
            format='json',
        )
        force_authenticate(pay_request, user=self.receptionist)
        pay_response = pay_lab_fee(pay_request, order.id)
        self.assertTrue(pay_response.data['success'])

        order.refresh_from_db()
        self.assertEqual(order.status, 'in_queue')
        entry = LabQueueEntry.objects.get(lab_order=order)
        self.assertTrue(entry.lab_fee_paid)

        queue_request = self.factory.get('/api/core/lab/queue/')
        force_authenticate(queue_request, user=self.lab_tech)
        queue_response = lab_queue(queue_request)
        self.assertTrue(queue_response.data['success'])
        pending_ids = [item['order_id'] for item in queue_response.data['pending']]
        self.assertIn(order.id, pending_ids)

    def test_paid_lab_queue_visible_regardless_of_appointment_date(self):
        """Older appointments stay on the lab queue until completed."""
        complete_consultation(
            self.token,
            symptoms='fever',
            diagnosis='screen',
            lab_tests=['Complete Blood Count (CBC)'],
        )
        order = LabOrder.objects.get(token=self.token)
        pay_request = self.factory.post(
            f'/api/core/reception/lab-pay/{order.id}/',
            {'amount': float(order.fee)},
            format='json',
        )
        force_authenticate(pay_request, user=self.receptionist)
        pay_lab_fee(pay_request, order.id)

        # Simulate an order from a previous visit day
        self.slot.date = self.today - timezone.timedelta(days=3)
        self.slot.save(update_fields=['date'])

        queue_request = self.factory.get('/api/core/lab/queue/')
        force_authenticate(queue_request, user=self.lab_tech)
        queue_response = lab_queue(queue_request)
        pending_ids = [item['order_id'] for item in queue_response.data['pending']]
        self.assertIn(order.id, pending_ids)

    def test_lab_and_pharmacy_run_in_parallel(self):
        """Patients with Rx enter pharmacy immediately even if labs are pending."""
        result = complete_consultation(
            self.token,
            symptoms='fever',
            diagnosis='infection',
            medicines=[{'name': 'Amoxicillin', 'dosage': '500mg', 'frequency': 'TID'}],
            lab_tests=['Complete Blood Count (CBC)'],
        )
        self.token.refresh_from_db()

        self.assertTrue(result['requires_lab'])
        self.assertTrue(result['requires_pharmacy'])
        self.assertEqual(self.token.status, C.PENDING_LAB)
        self.assertTrue(
            PharmacyQueueEntry.objects.filter(token=self.token, status=C.PHARMACY_WAITING).exists()
        )

        # Completing pharmacy while labs pending keeps visit on lab
        pharmacy = PharmacyQueueEntry.objects.get(token=self.token)
        pharmacy.complete()
        self.token.refresh_from_db()
        self.assertEqual(pharmacy.status, C.PHARMACY_DONE)
        self.assertEqual(self.token.status, C.PENDING_LAB)

        # Finishing labs after pharmacy completes the visit
        order = LabOrder.objects.get(token=self.token)
        order.status = 'completed'
        order.save(update_fields=['status'])
        after_lab_report_uploaded(order)
        self.token.refresh_from_db()
        self.assertEqual(self.token.status, C.COMPLETED)
