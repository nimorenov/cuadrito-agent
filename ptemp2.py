from django.shortcuts import get_object_or_404, render
from django.db.transaction import atomic
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from apps.accounts.models import Account
from apps.authentication.authentication import (
    UserOrAccountAuthentication,
)
from apps.currency_balances.utils import (
    purchase_currency,
    purchase_currency_delete,
    block_for_race_condition,
)
from apps.base.utils import (
    get_local_datetime_str,
    get_local_date_str,
    get_absolute_url,
    get_aware_datetime_range,
)
from apps.cashiers.utils import verify_and_create_movement
from apps.cashiers.models import Movement
from apps.purchases.models import Purchase
from apps.purchases.api.serializers.purchase_serializers import (
    PurchaseSerializer,
    UserPurchaseSerializer,
    PurchaseCalculateSerializer,
    UserPurchaseCalculateSerializer,
)


class PurchaseViewSet(UserOrAccountAuthentication, GenericViewSet):
    serializer_class = PurchaseSerializer
    user_serializer_class = UserPurchaseSerializer
    calculate_serializer_class = PurchaseCalculateSerializer
    user_calculate_serializer_class = UserPurchaseCalculateSerializer
    model = Purchase

    def get_queryset(self, ordering=None):
        ordering = self.request.query_params.get("ordering", None)
        consecutive = self.request.query_params.get("consecutive", "")
        document = self.request.query_params.get("document", "")
        submitted = self.request.query_params.get("submitted", None)
        created_at_range = get_aware_datetime_range(self.request)
        user = (
            self.authenticated_user
            if self.authenticated_user
            else self.authenticated_account.establishment.user
        )
        account_id = (
            self.request.query_params.get("account", None)
            if self.authenticated_user
            else self.authenticated_account.id
        )
        if self.authenticated_user and not account_id:
            queryset = self.model.objects.filter(
                state=True,
                account__establishment__user=user,
                consecutive__contains=consecutive,
                client__document__contains=document,
                created_at__range=created_at_range,
            )
        else:
            queryset = self.model.objects.filter(
                state=True,
                account__establishment__user=user,
                account__id=account_id,
                consecutive__contains=consecutive,
                client__document__contains=document,
                created_at__range=created_at_range,
            )
        if submitted == "true":
            queryset = queryset.filter(submitted=True)
        elif submitted == "false":
            queryset = queryset.filter(submitted=False)

        if ordering:
            return queryset.order_by(ordering)
        else:
            return queryset

    def get_object(self, pk=None):
        if self.authenticated_user:
            return get_object_or_404(
                self.model,
                pk=pk,
                state=True,
                account__establishment__user=self.authenticated_user,
            )
        else:
            return get_object_or_404(
                self.model,
                pk=pk,
                state=True,
                account=self.authenticated_account,
            )

    def has_permissions(self, permissions: list):
        if self.authenticated_user:
            return True
        for permission in permissions:
            if not self.authenticated_account.permissions.filter(
                codename=f"{permission}_purchase"
            ).exists():
                return False
        return True

    def list(self, request, *args, **kwargs):
        if not self.has_permissions(["view"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        no_pagination = self.request.query_params.get("no_pagination", None)
        queryset = self.filter_queryset(self.get_queryset())
        if no_pagination == "true":
            purchase_serializer = self.get_serializer(queryset, many=True)
            return Response(
                {
                    "count": len(purchase_serializer.data),
                    "next": None,
                    "previous": None,
                    "results": purchase_serializer.data,
                }
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            purchase_serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(purchase_serializer.data)

        purchase_serializer = self.get_serializer(queryset, many=True)
        return Response(purchase_serializer.data)

    def retrieve(self, request, pk=None, *args, **kwargs):
        if not self.has_permissions(["view"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        purchase = self.get_object(pk)
        purchase_serializer = self.get_serializer(purchase)
        return Response(purchase_serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        if not self.has_permissions(["add"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        purchase_serializer = (
            self.user_serializer_class(
                data=request.data,
                context={"user": self.authenticated_user, "no_validate_client": True},
            )
            if self.authenticated_user
            else self.get_serializer(
                data=request.data,
                context={
                    "account": self.authenticated_account,
                    "no_validate_client": True,
                },
            )
        )

        with atomic():
            block_for_race_condition(
                request.data.get("account")
                if self.authenticated_user
                else self.authenticated_account
            )
            purchase_serializer.is_valid(raise_exception=True)
            purchase = purchase_serializer.save()
            movement = verify_and_create_movement(
                user=self.authenticated_user,
                account=purchase_serializer.instance.account,
                token=request.data.get("cashier_token"),
                type="purchase",
                request_type="create",
                object_id=purchase_serializer.instance.id,
            )
            purchase_currency(purchase, movement)

        return Response(purchase_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
        if not self.has_permissions(["change"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        purchase = self.get_object(pk)
        purchase_serializer = (
            self.user_serializer_class(
                purchase,
                data=request.data,
                context={"user": self.authenticated_user, "purchase": purchase},
                partial=True,
            )
            if self.authenticated_user
            else self.get_serializer(
                purchase,
                data=request.data,
                context={"account": self.authenticated_account, "purchase": purchase},
                partial=True,
            )
        )
        purchase_serializer.is_valid(raise_exception=True)

        currency, amount, rate, iva, total, account, created_date = (
            purchase_serializer.validated_data.get("currency"),
            purchase_serializer.validated_data.get("amount"),
            purchase_serializer.validated_data.get("rate"),
            purchase_serializer.validated_data.get("iva"),
            purchase_serializer.validated_data.get("total"),
            purchase_serializer.validated_data.get("account"),
            purchase_serializer.validated_data.get("created_date"),
        )
        with atomic():
            if (
                currency
                or amount != None
                or rate != None
                or iva != None
                or account
                or created_date
            ):
                pass
            purchase_serializer.save()
            verify_and_create_movement(
                user=self.authenticated_user,
                account=account if account else purchase.account,
                token=request.data.get("cashier_token"),
                type="purchase",
                request_type="update",
                object_id=purchase_serializer.instance.id,
            )

        return Response(purchase_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None, *args, **kwargs):
        if not self.has_permissions(["delete"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        with atomic():
            purchase = self.get_object(pk)
            block_for_race_condition(purchase.account)
            purchase = self.get_object(pk)
            if purchase.submitted:
                return Response(
                    {
                        "detail": "This purchase has already been reported to the DIAN. It cannot be deleted."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            verify_and_create_movement(
                user=self.authenticated_user,
                account=purchase.account,
                token=request.data.get("cashier_token"),
                type="purchase",
                request_type="delete",
                object_id=purchase.id,
            )
            purchase_currency_delete(purchase)
            purchase.state = False
            purchase.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="last-consecutive")
    def last_consecutive(self, request, *args, **kwargs):
        if not self.has_permissions(["view"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if self.authenticated_user:
            account_id = self.request.query_params.get("account", None)
            if account_id:
                account = get_object_or_404(
                    Account, pk=account_id, establishment__user=self.authenticated_user
                )
                last_consecutive = self.model.objects.get_last_consecutive(
                    account=account
                )
                return Response(
                    {"consecutive": last_consecutive}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "Account is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            last_consecutive = self.model.objects.get_last_consecutive(
                account=self.authenticated_account
            )
            return Response(
                {"consecutive": last_consecutive}, status=status.HTTP_200_OK
            )

    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, pk=None, *args, **kwargs):
        if not self.has_permissions(["view"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        purchase = self.get_object(pk)
        purchase.account.prefix = f"{purchase.account.prefix}C"  # TODO: Dinamic prefix
        purchase.consecutive = str(purchase.consecutive).zfill(6)
        purchase.created_date, purchase.created_time = get_local_datetime_str(
            purchase.created_at
        )
        purchase.client.birthdate = get_local_date_str(purchase.client.birthdate)
        purchase.client.is_pep = "Sí" if purchase.client.is_pep else "No"
        purchase.client.is_relative_pep = (
            "Sí" if purchase.client.is_relative_pep else "No"
        )
        purchase.client.pep_entity = purchase.client.pep_entity or "N/A"
        purchase.client.pep_position = purchase.client.pep_position or "N/A"
        purchase.client.pep_relative_name = purchase.client.pep_relative_name or "N/A"
        purchase.client.pep_relative_relationship = (
            purchase.client.pep_relative_relationship or "N/A"
        )
        purchase.amount = (
            int(purchase.amount) if purchase.amount.is_integer() else purchase.amount
        )
        purchase.rate = (
            int(purchase.rate) if purchase.rate.is_integer() else purchase.rate
        )
        purchase.total = (
            int(purchase.total) if purchase.total.is_integer() else purchase.total
        )
        purchase.total_dollars = (
            int(purchase.total_dollars)
            if purchase.total_dollars.is_integer()
            else round(purchase.total_dollars, 2)
        )
        client_full_name = purchase.client.get_full_name()
        purchase.logo = get_absolute_url(request, purchase.account.establishment.logo)
        purchase.business_nit = (
            purchase.account.establishment.user.settings.get_business_nit_formatted()
        )

        movement = Movement.objects.get(object_id=purchase.id, type="purchase")
        if movement.cashier:
            purchase.cashier = (
                movement.cashier.names + " " + movement.cashier.last_names
            )
        else:
            purchase.cashier = "Administrador"

        return render(
            request,
            "invoice.html",
            {
                "transaction": purchase,
                "client_full_name": client_full_name,
                "title": "COMPRA",
                "cod": 15,
                "transaction_type": "purchase",
            },
        )

    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate(self, request, *args, **kwargs):
        if not self.has_permissions(["add"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        calculate_serializer = (
            self.user_calculate_serializer_class(
                data=request.data,
                context={
                    "user": self.authenticated_user,
                    "client_id": request.data.get("client"),
                },
            )
            if self.authenticated_user
            else self.calculate_serializer_class(
                data=request.data,
                context={
                    "account": self.authenticated_account,
                    "client_id": request.data.get("client"),
                },
            )
        )
        calculate_serializer.is_valid(raise_exception=True)
        return Response(calculate_serializer.calculate(), status=status.HTTP_200_OK)
