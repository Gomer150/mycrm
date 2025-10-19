import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from deals.models import Company, Contact, Deal, Stage


User = get_user_model()


class DealContactViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass-12345")
        self.stage = Stage.objects.create(name="Заявка", order_index=1)
        self.client_company = Company.objects.create(name="Клиент", type="client")
        self.extra_company = Company.objects.create(name="Партнёр", type="partner")
        self.deal = Deal.objects.create(
            title="Сделка",
            owner=self.owner,
            stage=self.stage,
            client=self.client_company,
        )
        self.client.force_login(self.owner)

    def _post(self, url_name, *args, payload):
        return self.client.post(
            reverse(url_name, args=args),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_create_contact_with_multiple_companies(self):
        response = self._post(
            "deal_contact_create",
            self.deal.pk,
            payload={
                "name": "Иван",
                "company_ids": [self.client_company.id, self.extra_company.id],
            },
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()["contact"]
        self.assertEqual(data["name"], "Иван")
        self.assertCountEqual(data["company_ids"], [self.client_company.id, self.extra_company.id])
        contact = Contact.objects.get(pk=data["id"])
        self.assertCountEqual(contact.companies.values_list("id", flat=True), [self.client_company.id, self.extra_company.id])
        # Клиент сделки остаётся основной компанией, если явный primary не указан
        self.assertEqual(data["company_id"], self.client_company.id)

    def test_create_for_existing_contact_extends_companies(self):
        contact = Contact.objects.create(owner=self.owner, name="Пётр")
        contact.companies.add(self.extra_company)

        response = self._post(
            "deal_contact_create",
            self.deal.pk,
            payload={
                "contact_id": contact.id,
                "company_ids": [self.client_company.id, self.extra_company.id],
            },
        )

        self.assertEqual(response.status_code, 201)
        contact.refresh_from_db()
        self.assertCountEqual(contact.companies.values_list("id", flat=True), [self.client_company.id, self.extra_company.id])

    def test_update_contact_replaces_company_set(self):
        contact = Contact.objects.create(owner=self.owner, name="Мария")
        contact.companies.set([self.client_company, self.extra_company])

        response = self._post(
            "deal_contact_update",
            self.deal.pk,
            contact.pk,
            payload={
                "name": "Мария",
                "company_ids": [self.extra_company.id],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["contact"]
        self.assertEqual(data["name"], "Мария")
        self.assertEqual(data["company_ids"], [self.extra_company.id])
        contact.refresh_from_db()
        self.assertCountEqual(contact.companies.values_list("id", flat=True), [self.extra_company.id])

    def test_create_contact_without_companies_defaults_to_client(self):
        response = self._post(
            "deal_contact_create",
            self.deal.pk,
            payload={"name": "Без компании", "company_ids": []},
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()["contact"]
        self.assertEqual(data["company_ids"], [self.client_company.id])
        contact = Contact.objects.get(pk=data["id"])
        self.assertEqual(list(contact.companies.values_list("id", flat=True)), [self.client_company.id])
