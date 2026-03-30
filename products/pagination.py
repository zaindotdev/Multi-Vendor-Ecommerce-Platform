from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProductPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 48