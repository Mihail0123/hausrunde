from rest_framework.pagination import PageNumberPagination

class AdPagination(PageNumberPagination):
    """Page-number pagination for ads."""
    page_size = 10                      # default items per page
    page_size_query_param = 'page_size' # allow ?page_size=
    max_page_size = 50                  # safety cap
