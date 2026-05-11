from django.shortcuts import get_object_or_404, render
from django.db.transaction import atomic
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from apps.authentication.authentication import UserOrAccountAuthentication
from apps.accounts.models import Account
from apps.currency_balances.utils import (
    sell_currency,
    sell_currency_delete,
    block_for_race_condition,
)
from apps.base.utils import (
    get_local_date_str,
    get_local_datetime_str,
    get_absolute_url,
    get_aware_datetime_range,
)
from apps.cashiers.utils import verify_and_create_movement
from apps.cashiers.models import Movement
from apps.sales.models import Sale
from apps.sales.api.serializers.sale_serializers import (
    SaleSerializer,
    UserSaleSerializer,
    SaleCalculateSerializer,
    UserSaleCalculateSerializer,
)


class SaleViewSet(UserOrAccountAuthentication, GenericViewSet):
    serializer_class = SaleSerializer
    user_serializer_class = UserSaleSerializer
    calculate_serializer_class = SaleCalculateSerializer
    user_calculate_serializer_class = UserSaleCalculateSerializer
    model = Sale

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
                codename=f"{permission}_sale"
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
            sales_serializer = self.get_serializer(queryset, many=True)
            return Response(
                {
                    "count": len(sales_serializer.data),
                    "next": None,
                    "previous": None,
                    "results": sales_serializer.data,
                }
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            sale_serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(sale_serializer.data)

        sale_serializer = self.get_serializer(queryset, many=True)
        return Response(sale_serializer.data)

    def retrieve(self, request, pk=None, *args, **kwargs):
        if not self.has_permissions(["view"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        sale = self.get_object(pk)
        sale_serializer = self.get_serializer(sale)
        return Response(sale_serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        if not self.has_permissions(["add"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        sale_serializer = (
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
            sale_serializer.is_valid(raise_exception=True)
            sale = sale_serializer.save()
            movement = verify_and_create_movement(
                user=self.authenticated_user,
                account=sale_serializer.instance.account,
                token=request.data.get("cashier_token"),
                type="sale",
                request_type="create",
                object_id=sale_serializer.instance.id,
            )
            sell_currency(sale, movement)

        return Response(sale_serializer.data, status=status.HTTP_201_CREATED)

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
        sale = self.get_object(pk)
        sale_serializer = (
            self.user_serializer_class(
                sale,
                data=request.data,
                context={"user": self.authenticated_user, "sale": sale},
                partial=True,
            )
            if self.authenticated_user
            else self.get_serializer(
                sale,
                data=request.data,
                context={"account": self.authenticated_account, "sale": sale},
                partial=True,
            )
        )
        sale_serializer.is_valid(raise_exception=True)

        currency, amount, rate, iva, total, account, created_date = (
            sale_serializer.validated_data.get("currency"),
            sale_serializer.validated_data.get("amount"),
            sale_serializer.validated_data.get("rate"),
            sale_serializer.validated_data.get("iva"),
            sale_serializer.validated_data.get("total"),
            sale_serializer.validated_data.get("account"),
            sale_serializer.validated_data.get("created_date"),
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
            sale_serializer.save()
            if self.authenticated_account:
                verify_and_create_movement(
                    user=self.authenticated_user,
                    account=account if account else sale.account,
                    token=request.data.get("cashier_token"),
                    type="sale",
                    request_type="update",
                    object_id=sale_serializer.instance.id,
                )

        return Response(sale_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None, *args, **kwargs):
        if not self.has_permissions(["delete"]):
            return Response(
                {
                    "detail": "The account does not have permission to perform this action."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        with atomic():
            sale = self.get_object(pk)
            block_for_race_condition(sale.account)
            sale = self.get_object(pk)
            if sale.submitted:
                return Response(
                    {
                        "detail": "This sale has already been reported to the DIAN. It cannot be deleted."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            verify_and_create_movement(
                user=self.authenticated_user,
                account=sale.account,
                token=request.data.get("cashier_token"),
                type="sale",
                request_type="delete",
                object_id=sale.id,
            )
            sell_currency_delete(sale)
            sale.state = False
            sale.save()

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
        sale = self.get_object(pk)
        sale.account.prefix = f"{sale.account.prefix}V"  # TODO: Dinamic prefix
        sale.consecutive = str(sale.consecutive).zfill(6)
        sale.created_date, sale.created_time = get_local_datetime_str(sale.created_at)
        sale.client.birthdate = get_local_date_str(sale.client.birthdate)
        sale.client.is_pep = "Sí" if sale.client.is_pep else "No"
        sale.client.is_relative_pep = "Sí" if sale.client.is_relative_pep else "No"
        sale.client.pep_entity = sale.client.pep_entity or "N/A"
        sale.client.pep_position = sale.client.pep_position or "N/A"
        sale.client.pep_relative_name = sale.client.pep_relative_name or "N/A"
        sale.client.pep_relative_relationship = (
            sale.client.pep_relative_relationship or "N/A"
        )
        sale.amount = int(sale.amount) if sale.amount.is_integer() else sale.amount
        sale.rate = int(sale.rate) if sale.rate.is_integer() else sale.rate
        sale.total = int(sale.total) if sale.total.is_integer() else sale.total
        sale.total_dollars = (
            int(sale.total_dollars)
            if sale.total_dollars.is_integer()
            else round(sale.total_dollars, 2)
        )
        client_full_name = sale.client.get_full_name()
        sale.logo = get_absolute_url(request, sale.account.establishment.logo)
        sale.business_nit = (
            sale.account.establishment.user.settings.get_business_nit_formatted()
        )

        movement = Movement.objects.get(object_id=sale.id, type="sale")
        if movement.cashier:
            sale.cashier = movement.cashier.names + " " + movement.cashier.last_names
        else:
            sale.cashier = "Administrador"

        return render(
            request,
            "invoice.html",
            {
                "transaction": sale,
                "client_full_name": client_full_name,
                "title": "VENTA",
                "cod": 16,
                "transaction_type": "sale",
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
