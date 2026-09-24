"""Role groups shared by HTTP boundaries and staff workflows."""
from utils.response import ApiError

USER = "user"
ADMIN = "admin"
FRONTDESK = "frontdesk"
MAINTENANCE = "maintenance"
ROLES = frozenset({USER, ADMIN, FRONTDESK, MAINTENANCE})
CUSTOMER_ROLES = frozenset({USER, ADMIN})
FRONTDESK_ROLES = frozenset({FRONTDESK, ADMIN})
MAINTENANCE_ROLES = frozenset({MAINTENANCE, ADMIN})


def require_role(user, allowed):
    if user.get("role") not in allowed:
        raise ApiError(403, "当前角色无权执行此操作", 403)
    return user
