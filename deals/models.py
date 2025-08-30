from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User


User = get_user_model()

class Stage(models.Model):
    name = models.CharField(max_length=120)
    order_index = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class Company(models.Model):
    TYPE_CHOICES = [
        ("client", "Клиент"),
        ("partner", "Партнёр"),
        ("supplier", "Поставщик"),
    ]
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="client")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Contact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    messengers = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.name:  
            # Считаем количество сделок
            count = Deal.objects.filter(owner=self.owner).count() + 1
            self.name = f"Сделка {count}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

class Deal(models.Model):
    title = models.CharField(max_length=255)
    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True)
    companies = models.ManyToManyField(Company, through="DealCompany", related_name="deals")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Автогенерация имени сделки
        if not self.title:
            count = Deal.objects.filter(owner=self.owner).count() + 1
            self.title = f"Сделка {count}"
        # Автоматический этап для новых сделок
        if not self.stage:
            # Получаем объект Stage с названием "Заявка"
            stage_obj = Stage.objects.filter(name="Заявка").first()
            self.stage = stage_obj
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class DealCompany(models.Model):
    ROLE_CHOICES = [
        ("client", "Клиент"),
        ("partner", "Партнёр"),
        ("supplier", "Поставщик"),
    ]
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("deal", "company", "role")

class Document(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="documents")
    filename = models.CharField(max_length=512)
    content_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    data = models.BinaryField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.filename} ({self.size} bytes)"