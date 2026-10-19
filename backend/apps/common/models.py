"""全局抽象基类模型。

所有业务表统一包含：id、created_at、updated_at、created_by、is_deleted（软删除）。
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """默认过滤已删除记录；需要全量时用 all_objects。"""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("创建时间", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField("已删除", default=False, db_index=True)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, using=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"] if hasattr(self, "updated_at") else ["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class BaseModel(SoftDeleteModel, TimeStampedModel):
    """业务模型统一基类。"""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
        db_index=True,
    )

    class Meta:
        abstract = True
