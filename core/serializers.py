from rest_framework import serializers


class TenantModelSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        request = self.context.get("request")
        if request and getattr(request, "mutuelle", None) and "mutuelle" not in validated_data:
            validated_data["mutuelle"] = request.mutuelle
        return super().create(validated_data)
