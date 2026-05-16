from datetime import datetime
from typing import Any

from config.settings import Settings
from repositories import notification_repository
from utils.query import clean_text
from utils.response import ApiError


VALID_CATEGORIES = {"system", "reservation", "member", "announcement", "shop", "event", "community"}


def _parse_is_read(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        is_read = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "通知状态参数格式错误", 400) from exc
    if is_read not in (0, 1):
        raise ApiError(400, "通知状态只能是0或1", 400)
    return is_read


def _validate_message(title: Any, content: Any) -> tuple[str, str]:
    title_text = clean_text(title)
    content_text = clean_text(content)
    if not title_text:
        raise ApiError(400, "通知标题不能为空", 400)
    if len(title_text) > 100:
        raise ApiError(400, "通知标题不能超过100个字符", 400)
    if not content_text:
        raise ApiError(400, "通知内容不能为空", 400)
    if len(content_text) > 2000:
        raise ApiError(400, "通知内容不能超过2000个字符", 400)
    return title_text, content_text


def _validate_category(value: str) -> str:
    category = clean_text(value) or "system"
    if category not in VALID_CATEGORIES:
        return "system"
    return category


def _public_notification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "category": row["category"],
        "source_type": row.get("source_type"),
        "source_id": row.get("source_id"),
        "is_read": bool(row.get("is_read")),
        "read_at": row.get("read_at"),
        "created_at": row.get("created_at"),
    }


async def list_my_notifications(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    is_read_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    is_read = _parse_is_read(is_read_arg)
    rows = await notification_repository.list_notifications(
        settings,
        user_id=current_user["id"],
        is_read=is_read,
        offset=offset,
        limit=page_size,
    )
    total = await notification_repository.count_notifications(
        settings,
        user_id=current_user["id"],
        is_read=is_read,
    )
    return {
        "items": [_public_notification(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_unread_count(settings: Settings, *, current_user: dict[str, Any]) -> dict[str, int]:
    count = await notification_repository.count_unread_notifications(settings, user_id=current_user["id"])
    return {"unread_count": count}


async def mark_notification_read(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    notification_id: int,
) -> dict[str, Any]:
    notification = await notification_repository.get_notification(
        settings,
        user_id=current_user["id"],
        notification_id=notification_id,
    )
    if notification is None:
        raise ApiError(404, "通知不存在", 404)
    await notification_repository.mark_notification_read(
        settings,
        user_id=current_user["id"],
        notification_id=notification_id,
    )
    updated = await notification_repository.get_notification(
        settings,
        user_id=current_user["id"],
        notification_id=notification_id,
    )
    if updated is None:
        raise ApiError(404, "通知不存在", 404)
    return _public_notification(updated)


async def mark_all_read(settings: Settings, *, current_user: dict[str, Any]) -> dict[str, int]:
    updated_count = await notification_repository.mark_all_read(settings, user_id=current_user["id"])
    return {"updated_count": updated_count}


async def create_user_notification(
    settings: Settings,
    *,
    user_id: int,
    title: str,
    content: str,
    category: str = "system",
    source_type: str | None = None,
    source_id: int | None = None,
    created_by: int | None = None,
) -> dict[str, Any]:
    title_text, content_text = _validate_message(title, content)
    notification_id = await notification_repository.create_notification(
        settings,
        user_id=user_id,
        title=title_text,
        content=content_text,
        category=_validate_category(category),
        source_type=source_type,
        source_id=source_id,
        created_by=created_by,
    )
    notification = await notification_repository.get_notification(
        settings,
        user_id=user_id,
        notification_id=notification_id,
    )
    if notification is None:
        raise ApiError(500, "创建通知后读取失败", 500)
    return _public_notification(notification)


async def broadcast_to_enabled_users(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    title, content = _validate_message(body.get("title"), body.get("content"))
    user_ids = await notification_repository.list_enabled_user_ids(settings)
    created_at = datetime.now()
    sent_count = await notification_repository.create_notifications_for_users(
        settings,
        user_ids=user_ids,
        title=title,
        content=content,
        category="system",
        source_type="broadcast",
        source_id=None,
        created_by=current_user["id"],
        created_at=created_at,
    )
    return {"sent_count": sent_count, "created_at": created_at}


async def safe_create_user_notification(
    settings: Settings,
    *,
    user_id: int,
    title: str,
    content: str,
    category: str = "system",
    source_type: str | None = None,
    source_id: int | None = None,
    created_by: int | None = None,
) -> None:
    try:
        await create_user_notification(
            settings,
            user_id=user_id,
            title=title,
            content=content,
            category=category,
            source_type=source_type,
            source_id=source_id,
            created_by=created_by,
        )
    except Exception:
        return


async def safe_broadcast_announcement(settings: Settings, *, announcement: dict[str, Any], created_by: int) -> None:
    try:
        user_ids = await notification_repository.list_enabled_user_ids(settings)
        await notification_repository.create_notifications_for_users(
            settings,
            user_ids=user_ids,
            title=f"新公告：{announcement['title']}",
            content=clean_text(announcement.get("content"))[:200],
            category="announcement",
            source_type="announcement",
            source_id=int(announcement["id"]),
            created_by=created_by,
            created_at=datetime.now(),
        )
    except Exception:
        return


async def notify_reservation_created(settings: Settings, *, reservation: dict[str, Any]) -> None:
    content = (
        f"您已成功预约 {reservation.get('court_name')}，"
        f"时间为 {reservation.get('reserve_date')} {reservation.get('start_time')}-{reservation.get('end_time')}，"
        f"本次扣费 {(int(reservation.get('payable_amount_cents') or 0) / 100):.2f} 元。"
    )
    await safe_create_user_notification(
        settings,
        user_id=int(reservation["user_id"]),
        title="预约成功",
        content=content,
        category="reservation",
        source_type="reservation",
        source_id=int(reservation["id"]),
        created_by=int(reservation["user_id"]),
    )


async def notify_reservation_canceled(
    settings: Settings,
    *,
    reservation: dict[str, Any],
    by_admin: bool,
    operator_id: int | None = None,
) -> None:
    refund_cents = int(reservation.get("refund_cents") or 0)
    amount = refund_cents / 100
    title = "管理员已取消预约" if by_admin else "预约已取消"
    refund_text = f"已按规则退回 {amount:.2f} 元。" if refund_cents > 0 else "该预约尚未支付，无需退款。"
    content = (
        f"预约 {reservation.get('reservation_no')} 已取消，"
        f"场地为 {reservation.get('court_name')}，"
        f"时间为 {reservation.get('reserve_date')} {reservation.get('start_time')}-{reservation.get('end_time')}，"
        f"{refund_text}"
    )
    await safe_create_user_notification(
        settings,
        user_id=int(reservation["user_id"]),
        title=title,
        content=content,
        category="reservation",
        source_type="reservation",
        source_id=int(reservation["id"]),
        created_by=operator_id,
    )


async def notify_member_adjusted(
    settings: Settings,
    *,
    user: dict[str, Any],
    balance_change_cents: int,
    points_change: int,
    operator_id: int | None,
) -> None:
    member = user["member"]
    balance_text = f"{balance_change_cents / 100:+.2f} 元"
    points_text = f"{points_change:+d} 分"
    content = (
        f"您的会员账户已调整，当前等级为 {member['level_label']}，"
        f"余额变动 {balance_text}，积分变动 {points_text}，"
        f"当前余额 {(int(member['balance_cents']) / 100):.2f} 元，当前积分 {member['points']}。"
    )
    await safe_create_user_notification(
        settings,
        user_id=int(user["id"]),
        title="会员账户已调整",
        content=content,
        category="member",
        source_type="member",
        source_id=int(user["id"]),
        created_by=operator_id,
    )


async def notify_shop_order_paid(settings: Settings, *, order: dict[str, Any]) -> None:
    amount = int(order.get("total_amount_cents") or 0) / 100
    await safe_create_user_notification(
        settings,
        user_id=int(order["user_id"]),
        title="商城订单已支付",
        content=f"订单 {order.get('order_no')} 已使用会员余额支付 {amount:.2f} 元，请到店领取或等待管理员处理。",
        category="shop",
        source_type="shop_order",
        source_id=int(order["id"]),
        created_by=int(order["user_id"]),
    )


async def notify_shop_order_canceled(
    settings: Settings,
    *,
    order: dict[str, Any],
    by_admin: bool,
    operator_id: int | None,
) -> None:
    amount = int(order.get("total_amount_cents") or 0) / 100
    title = "商城订单已退款" if by_admin else "商城订单已取消"
    content = f"订单 {order.get('order_no')} 已取消，已退回会员余额 {amount:.2f} 元。"
    await safe_create_user_notification(
        settings,
        user_id=int(order["user_id"]),
        title=title,
        content=content,
        category="shop",
        source_type="shop_order",
        source_id=int(order["id"]),
        created_by=operator_id,
    )


async def notify_shop_order_completed(settings: Settings, *, order: dict[str, Any], operator_id: int | None) -> None:
    await safe_create_user_notification(
        settings,
        user_id=int(order["user_id"]),
        title="商城订单已完成",
        content=f"订单 {order.get('order_no')} 已确认完成。",
        category="shop",
        source_type="shop_order",
        source_id=int(order["id"]),
        created_by=operator_id,
    )


async def notify_event_registered(settings: Settings, *, event: dict[str, Any], user_id: int) -> None:
    await safe_create_user_notification(
        settings,
        user_id=user_id,
        title="活动报名成功",
        content=f"您已报名活动《{event.get('title')}》，活动地点：{event.get('location')}。",
        category="event",
        source_type="event",
        source_id=int(event["id"]),
        created_by=user_id,
    )


async def notify_event_registration_canceled(settings: Settings, *, event: dict[str, Any], user_id: int) -> None:
    await safe_create_user_notification(
        settings,
        user_id=user_id,
        title="活动报名已取消",
        content=f"您已取消活动《{event.get('title')}》的报名。",
        category="event",
        source_type="event",
        source_id=int(event["id"]),
        created_by=user_id,
    )


async def notify_event_hidden(
    settings: Settings,
    *,
    event: dict[str, Any],
    user_ids: list[int],
    operator_id: int | None,
) -> None:
    for user_id in user_ids:
        await safe_create_user_notification(
            settings,
            user_id=user_id,
            title="活动状态变更",
            content=f"活动《{event.get('title')}》已由管理员隐藏，请关注后续安排。",
            category="event",
            source_type="event",
            source_id=int(event["id"]),
            created_by=operator_id,
        )
