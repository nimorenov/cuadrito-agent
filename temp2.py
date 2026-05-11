from math import sqrt
from rest_framework import serializers
from apps.clients.models import Client
from apps.clients.api.serializers.client_serializers import ClientSerializer
from apps.accounts.api.serializers.account_serializers import AccountSerializer
from apps.currency_balances.api.serializers.currencies_serializers import (
    CurrencySerializer,
)
from apps.currency_balances.models import Currency, CurrencyBalance
from apps.currency_balances.utils import (
    calculate_subtotal_and_total,
    get_client_dollars_sumatory,
)
from apps.purchases.models import Purchase
from apps.sales.models import Sale


class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = (
            "client",
            "currency",
            "amount",
            "rate",
            "iva",
            "funds_origin",
            "funds_destination",
        )

    def validate_client(self, value):
        if (
            value.user.id != self.context["account"].establishment.user.id
        ) or value.state == False:
            raise serializers.ValidationError(
                f'Invalid pk "{value.id}" - object does not exist.'
            )
        return value

    def validate_currency(self, value):
        if value == Currency.objects.get_default_currency():
            raise serializers.ValidationError("Default currency cannot be used.")
        if value.state == False:
            raise serializers.ValidationError(
                f'Invalid pk "{value.id}" - object does not exist.'
            )
        return value

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate_rate(self, value):
        if value < 0:
            raise serializers.ValidationError("Rate must be greater than 0.")
        return value

    def validate_iva(self, value):
        if value < 0:
            raise serializers.ValidationError("IVA must be greater than 0.")
        return value

    def validate(self, data):
        amount = data.get("amount")
        rate = data.get("rate")
        iva = data.get("iva")
        currency = data.get("currency")
        client = data.get("client")
        instance = self.context.get("sale")
        no_validate_funds = self.context.get("no_validate_funds")
        no_validate_client = self.context.get("no_validate_client")
        if (
            amount == None
            and rate == None
            and iva == None
            and currency == None
            and client == None
        ):
            return data
        if instance:
            amount = amount if amount != None else instance.amount
            rate = rate if rate != None else instance.rate
            iva = iva if iva != None else instance.iva
            currency = currency if currency else instance.currency
            client = client if client else instance.client

        data["subtotal"], data["total"] = calculate_subtotal_and_total(
            amount, rate, iva
        )

        if not no_validate_funds:
            currency_balance = CurrencyBalance.objects.filter(
                state=True,
                account=self.context["account"],
                currency=currency,
            ).first()
            if (
                not currency_balance
                or (not instance and (data["amount"] > currency_balance.balance))
                or (instance and (amount > currency_balance.balance + instance.amount))
            ):
                raise serializers.ValidationError("Insufficient funds.")

        if currency == Currency.objects.get_dollars_currency():
            data["total_dollars"] = amount
            data["rate_dollars"] = rate
        else:
            rate_dollars = Purchase.objects.get_rate_dollars(
                self.context["account"].establishment.user
            )
            data["total_dollars"] = data["total"] / rate_dollars
            data["rate_dollars"] = rate_dollars

        if not no_validate_client:
            if get_client_dollars_sumatory(client) + data["total_dollars"] >= 10000:
                raise serializers.ValidationError(
                    "The client cannot exceed 10000 dollars."
                )

        return data

    def create(self, validated_data):
        validated_data["account"] = self.context["account"]
        validated_data["import_log"] = self.context.get("import_log")
        return super().create(validated_data)

    def to_representation(self, instance):
        client = ClientSerializer(instance.client).data
        currency = CurrencySerializer(instance.currency).data
        account = AccountSerializer(instance.account).data
        return {
            "id": instance.id,
            "consecutive": instance.consecutive,
            "account": account,
            "client": client,
            "currency": currency,
            "amount": instance.amount,
            "rate": instance.rate,
            "iva": instance.iva,
            "subtotal": instance.subtotal,
            "total": instance.total,
            "total_dollars": instance.total_dollars,
            "rate_dollars": instance.rate_dollars,
            "submitted": instance.submitted,
            "submitted_date": instance.submitted_date,
            "funds_origin": instance.funds_origin,
            "funds_destination": instance.funds_destination,
            "created_at": instance.created_at,
            "modified_at": instance.modified_at,
            "deleted_at": instance.deleted_at,
        }


class UserSaleSerializer(SaleSerializer):
    class Meta:
        model = Sale
        fields = (
            "client",
            "currency",
            "amount",
            "rate",
            "iva",
            "funds_origin",
            "funds_destination",
            "account",
        )

    def validate_client(self, value):
        if (value.user.id != self.context["user"].id) or value.state == False:
            raise serializers.ValidationError(
                f'Invalid pk "{value.id}" - object does not exist.'
            )
        return value

    def validate_account(self, value):
        if (
            value.establishment.user.id != self.context["user"].id
        ) or value.is_active == False:
            raise serializers.ValidationError(
                f'Invalid pk "{value.id}" - object does not exist.'
            )
        return value

    def validate(self, data):
        instance = self.context.get("sale")
        self.context["account"] = data.get("account") or instance.account
        return super().validate(data)


class SaleCalculateSerializer(SaleSerializer):
    class Meta:
        model = Sale
        fields = ("currency", "amount", "rate", "iva")

    def validate(self, data):
        return data

    def calculate_is_suspicious_rate(self):
        n = 50
        last_n_sales = Sale.objects.filter(
            state=True,
            account=self.context["account"],
            currency=self.validated_data["currency"],
        )[:n]
        n = len(last_n_sales)
        if n == 0:
            return False
        elif n == 1:
            mean = last_n_sales[0].rate
            standard_deviation = 1
        else:
            total_weight = sum([(s.amount) for s in last_n_sales])
            total_weight = total_weight if total_weight > 0 else 1
            mean = sum(s.rate * s.amount for s in last_n_sales) / total_weight
            variance = sum(s.amount * ((s.rate - mean) ** 2) for s in last_n_sales) / (
                total_weight
            )
            standard_deviation = sqrt(variance) if variance > 1 else 1

        z_score = (self.validated_data["rate"] - mean) / standard_deviation
        return abs(z_score) > 2.5

    def calculate(self):
        subtotal, total = calculate_subtotal_and_total(
            self.validated_data["amount"],
            self.validated_data["rate"],
            self.validated_data["iva"],
        )

        available_funds = True
        currency_balance = CurrencyBalance.objects.filter(
            state=True,
            account=self.context["account"],
            currency=self.validated_data["currency"],
        ).first()
        if (
            not currency_balance
            or self.validated_data["amount"] > currency_balance.balance
        ):
            available_funds = False

        if self.validated_data["currency"] == Currency.objects.get_dollars_currency():
            total_dollars = self.validated_data["amount"]
            rate_dollars = self.validated_data["rate"]
        else:
            rate_dollars = Purchase.objects.get_rate_dollars(
                self.context["account"].establishment.user
            )
            total_dollars = total / rate_dollars

        client = Client.objects.filter(
            state=True,
            pk=self.context["client_id"],
            user=self.context["account"].establishment.user,
        ).first()
        exceeds_10000_dollars = False
        if client:
            if get_client_dollars_sumatory(client) + total_dollars >= 10000:
                exceeds_10000_dollars = True
        else:
            if total_dollars >= 10000:
                exceeds_10000_dollars = True

        exceeds_1000_dollars = False
        if total_dollars >= 1000:
            exceeds_1000_dollars = True

        total_taxes = total - subtotal
        suspicious_rate = self.calculate_is_suspicious_rate()

        return {
            "subtotal": subtotal,
            "total": total,
            "total_dollars": total_dollars,
            "total_taxes": total_taxes,
            "rate_dollars": rate_dollars,
            "exceeds_10000_dollars": False,
            "exceeds_1000_dollars": exceeds_1000_dollars,
            "available_funds": available_funds,
            "suspicious_rate": suspicious_rate,
        }


class UserSaleCalculateSerializer(SaleCalculateSerializer):
    class Meta:
        model = Sale
        fields = ("currency", "amount", "rate", "iva", "account")

    def validate_account(self, value):
        if (
            value.establishment.user.id != self.context["user"].id
        ) or value.is_active == False:
            raise serializers.ValidationError(
                f'Invalid pk "{value.id}" - object does not exist.'
            )
        return value

    def validate(self, data):
        self.context["account"] = data.get("account")
        return data
