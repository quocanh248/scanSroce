from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from exam_token.constants import ROLE_CHOICES


class Command(BaseCommand):
    help = 'Tạo các group phân quyền cho hệ thống coi thi/chấm điểm.'

    def handle(self, *args, **options):
        for name, label in ROLE_CHOICES:
            Group.objects.get_or_create(name=name)
            self.stdout.write(self.style.SUCCESS(f'OK group {name} - {label}'))
