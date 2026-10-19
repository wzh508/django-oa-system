"""文档中心域模型。"""
from django.db import models

from apps.common.models import BaseModel


class Document(BaseModel):
    """文档 / 文件夹。文件夹 is_folder=True，file 为空。"""

    class ShareType(models.TextChoices):
        PRIVATE = "private", "私有"
        DEPT = "dept", "部门共享"
        ALL = "all", "全员共享"

    class Category(models.TextChoices):
        DOC = "doc", "文档"
        IMAGE = "image", "图片"
        VIDEO = "video", "视频"
        OTHER = "other", "其他"

    name = models.CharField("名称", max_length=255)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="children", verbose_name="父文件夹")
    is_folder = models.BooleanField("是否文件夹", default=False)
    category = models.CharField("类别", max_length=20, choices=Category.choices, default=Category.DOC)
    owner = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                              related_name="documents", verbose_name="上传人")
    dept = models.ForeignKey("accounts.Department", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="documents", verbose_name="所属部门")
    file = models.CharField("存储相对路径", max_length=500, blank=True, default="")
    original_name = models.CharField("原始文件名", max_length=255, blank=True, default="")
    mime = models.CharField("MIME", max_length=100, blank=True, default="")
    size = models.BigIntegerField("字节大小", default=0)
    version = models.IntegerField("版本号", default=1)
    share_type = models.CharField("共享范围", max_length=20, choices=ShareType.choices, default=ShareType.PRIVATE)
    tags = models.CharField("标签", max_length=255, blank=True, default="")
    description = models.TextField("描述", blank=True, default="")
    download_count = models.IntegerField("下载次数", default=0)

    class Meta:
        db_table = "document"
        verbose_name = "文档"
        verbose_name_plural = "文档"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
