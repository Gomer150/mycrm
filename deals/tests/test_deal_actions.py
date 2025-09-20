import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deals.models import Deal, DealAction, Stage


User = get_user_model()


class DealActionViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="test-pass-123")
        self.other_user = User.objects.create_user(username="other", password="test-pass-456")
        self.stage = Stage.objects.create(name="Заявка", order_index=1)
        self.deal = Deal.objects.create(title="Тестовая сделка", owner=self.owner, stage=self.stage)

    def test_owner_can_create_action(self):
        self.client.force_login(self.owner)
        url = reverse("deal_action_create", args=[self.deal.pk])
        remind_at = timezone.now().replace(microsecond=0)
        payload = {
            "description": "Позвонить клиенту",
            "recurrence": DealAction.Recurrence.CUSTOM,
            "custom_interval_days": 3,
            "remind_at": remind_at.strftime("%Y-%m-%dT%H:%M"),
        }

        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertIn("action", data)
        action = DealAction.objects.get(pk=data["action"]["id"])
        self.assertEqual(action.deal, self.deal)
        self.assertEqual(action.description, "Позвонить клиенту")
        self.assertEqual(action.recurrence, DealAction.Recurrence.CUSTOM)
        self.assertEqual(action.custom_interval_days, 3)
        self.assertIsNotNone(action.starts_at)

    def test_owner_can_update_action(self):
        action = DealAction.objects.create(
            deal=self.deal,
            description="Первичная задача",
            recurrence=DealAction.Recurrence.NONE,
        )

        self.client.force_login(self.owner)
        url = reverse("deal_action_update", args=[self.deal.pk, action.pk])
        payload = {
            "description": "Обновлённая задача",
            "recurrence": DealAction.Recurrence.DAILY,
            "remind_at": "",
            "custom_interval_days": "",
        }

        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

        action.refresh_from_db()
        self.assertEqual(action.description, "Обновлённая задача")
        self.assertEqual(action.recurrence, DealAction.Recurrence.DAILY)
        self.assertIsNone(action.remind_at)
        self.assertIsNone(action.custom_interval_days)

    def test_owner_can_delete_action(self):
        action = DealAction.objects.create(
            deal=self.deal,
            description="Удалить задачу",
            recurrence=DealAction.Recurrence.NONE,
        )

        self.client.force_login(self.owner)
        url = reverse("deal_action_delete", args=[self.deal.pk, action.pk])
        response = self.client.post(url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DealAction.objects.filter(pk=action.pk).exists())

    def test_custom_recurrence_requires_interval(self):
        self.client.force_login(self.owner)
        url = reverse("deal_action_create", args=[self.deal.pk])
        payload = {
            "description": "Без интервала",
            "recurrence": DealAction.Recurrence.CUSTOM,
            "custom_interval_days": "",
            "remind_at": "",
        }

        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("errors", data)
        self.assertIn("custom_interval_days", data["errors"])
        self.assertEqual(DealAction.objects.count(), 0)

    def test_non_owner_cannot_manage_actions(self):
        action = DealAction.objects.create(
            deal=self.deal,
            description="Чужое действие",
            recurrence=DealAction.Recurrence.NONE,
        )

        self.client.force_login(self.other_user)
        create_url = reverse("deal_action_create", args=[self.deal.pk])
        response = self.client.post(
            create_url,
            data=json.dumps({"description": "Попытка", "recurrence": DealAction.Recurrence.NONE}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        update_url = reverse("deal_action_update", args=[self.deal.pk, action.pk])
        response = self.client.post(
            update_url,
            data=json.dumps({"description": "Попытка", "recurrence": DealAction.Recurrence.NONE}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        delete_url = reverse("deal_action_delete", args=[self.deal.pk, action.pk])
        response = self.client.post(delete_url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(DealAction.objects.filter(pk=action.pk).exists())
