"""人事域序列化器。"""
from rest_framework import serializers

from apps.accounts.serializers import MaskedField

from .models import Contract, StaffProfile, Training, Transfer


class StaffProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    real_name = serializers.CharField(source="user.first_name", read_only=True)
    dept_name = serializers.CharField(source="user.dept.name", read_only=True, default="")
    bank_card = MaskedField(mask_kind="bank_card", required=False, allow_blank=True)
    id_card = MaskedField(mask_kind="id_card", required=False, allow_blank=True)

    class Meta:
        model = StaffProfile
        fields = ["id", "user", "username", "real_name", "dept_name", "education", "major",
                  "emergency_contact", "emergency_phone", "marital_status", "native_place",
                  "probation_end", "regularized_at", "salary", "bank_card", "id_card", "created_at"]
        read_only_fields = ["created_at", "username", "real_name", "dept_name"]


class TransferSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.first_name", read_only=True, default="")
    from_dept_name = serializers.CharField(source="from_dept.name", read_only=True, default="")
    to_dept_name = serializers.CharField(source="to_dept.name", read_only=True, default="")
    handler_name = serializers.CharField(source="handler.first_name", read_only=True, default="")

    class Meta:
        model = Transfer
        fields = ["id", "employee", "employee_name", "type", "from_dept", "from_dept_name",
                  "to_dept", "to_dept_name", "from_position", "to_position", "effective_date",
                  "status", "handler", "handler_name", "remark", "created_at"]
        read_only_fields = ["created_at", "employee_name", "from_dept_name", "to_dept_name", "handler_name"]


class ContractSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.first_name", read_only=True, default="")

    class Meta:
        model = Contract
        fields = ["id", "employee", "employee_name", "contract_type", "sign_date", "start_date",
                  "end_date", "status", "salary", "attachment", "remark", "created_at"]
        read_only_fields = ["created_at", "employee_name"]


class TrainingSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.first_name", read_only=True, default="")

    class Meta:
        model = Training
        fields = ["id", "employee", "employee_name", "title", "organization", "start_date",
                  "hours", "score", "certificate", "remark", "created_at"]
        read_only_fields = ["created_at", "employee_name"]
