from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from deals.models import Stage, Company, Contact, Deal, DealCompany, Document
import base64

User = get_user_model()

TEST_PDF = b"%PDF-1.4\n%Test PDF\n"  # tiny placeholder
TEST_DOCX = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"  # tiny docx header placeholder

class Command(BaseCommand):
    help = "Create initial test data (admin/admin)"

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser("admin", "admin@example.com", "admin")
            self.stdout.write("Created superuser admin/admin")
        else:
            admin = User.objects.get(username="admin")
            self.stdout.write("Superuser admin already exists")

        # stages
        Stage.objects.all().delete()
        s_contact = Stage.objects.create(name="Контакт", order_index=1)
        s_offer = Stage.objects.create(name="Предложение", order_index=2)
        s_contract = Stage.objects.create(name="Договор", order_index=3)
        s_execution = Stage.objects.create(name="Выполнение", order_index=4)
        s_closed = Stage.objects.create(name="Закрыто", order_index=5)
        s_lost = Stage.objects.create(name="Сделка сорвана", order_index=99)

        # companies
        Company.objects.all().delete()
        c1 = Company.objects.create(name="ООО \"СтройИнвест\"", type="client")
        c2 = Company.objects.create(name="ИП \"Иванов\"", type="client")
        p1 = Company.objects.create(name="Поставщик Техно", type="supplier")
        partner = Company.objects.create(name="Партнёр Сервис", type="partner")

        # contacts
        Contact.objects.all().delete()
        Contact.objects.create(company=c1, name="Петров Петр", position="Директор", phone="+7-900-111-222", email="petrov@example.com")
        Contact.objects.create(company=c1, name="Смирнова Анна", position="Бухгалтер", phone="+7-900-333-444", email="smirnova@example.com")
        Contact.objects.create(company=c2, name="Иванов Иван", position="Владелец", phone="+7-901-555-666", email="ivanov@example.com")

        # deals
        Deal.objects.all().delete()
        d1 = Deal.objects.create(title="Поставка оборудования", stage=s_offer, owner=admin)
        d2 = Deal.objects.create(title="Строительство склада", stage=s_execution, owner=admin)

        DealCompany.objects.create(deal=d1, company=c1, role="client")
        DealCompany.objects.create(deal=d1, company=p1, role="supplier")
        DealCompany.objects.create(deal=d2, company=c2, role="client")
        DealCompany.objects.create(deal=d2, company=partner, role="partner")

        # documents (small placeholders)
        Document.objects.all().delete()
        Document.objects.create(deal=d1, filename="offer.pdf", content_type="application/pdf", size=len(TEST_PDF), data=TEST_PDF, uploader=admin)
        Document.objects.create(deal=d1, filename="contract.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", size=len(TEST_DOCX), data=TEST_DOCX, uploader=admin)

        self.stdout.write("Initial data created.")
