from rest_framework import serializers

from mutuelles.models import Mutuelle, MutuelleMembership


class MutuelleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mutuelle
        fields = "__all__"


class MutuelleMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = MutuelleMembership
        fields = "__all__"
