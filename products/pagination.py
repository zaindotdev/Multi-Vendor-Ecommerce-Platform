from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Default pagination used across most endpoints.
    """
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProductPagination(PageNumberPagination):
    """
    Optimized pagination for product grids.
    """
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 48