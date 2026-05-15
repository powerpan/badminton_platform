from handlers.admin import (
    AdminAnnouncementDetailHandler,
    AdminAnnouncementStatusHandler,
    AdminAnnouncementsHandler,
    AdminConfigDetailHandler,
    AdminConfigsHandler,
    AdminCourtDetailHandler,
    AdminCourtStatusHandler,
    AdminCourtsHandler,
    AdminReservationCancelHandler,
    AdminReservationDetailHandler,
    AdminReservationsHandler,
    AdminOperationLogsHandler,
    AdminStatisticsCourtsHandler,
    AdminStatisticsOverviewHandler,
    AdminStatisticsTimeSlotsHandler,
    AdminStatisticsUsersHandler,
    AdminUserRoleHandler,
    AdminUserStatusHandler,
    AdminUsersHandler,
)
from handlers.announcements import AnnouncementDetailHandler, AnnouncementsHandler
from handlers.auth import LoginHandler, PasswordHandler, ProfileHandler, RegisterHandler
from handlers.courts import CourtsHandler, CourtSlotsHandler
from handlers.health import HealthHandler
from handlers.reservations import CancelReservationHandler, MyReservationsHandler, ReservationsHandler


def build_routes() -> list[tuple[str, object]]:
    return [
        (r"/api/health", HealthHandler),
        (r"/api/admin/health", HealthHandler),
        (r"/api/auth/register", RegisterHandler),
        (r"/api/auth/login", LoginHandler),
        (r"/api/auth/profile", ProfileHandler),
        (r"/api/auth/password", PasswordHandler),
        (r"/api/announcements", AnnouncementsHandler),
        (r"/api/announcements/([0-9]+)", AnnouncementDetailHandler),
        (r"/api/courts", CourtsHandler),
        (r"/api/courts/([0-9]+)/slots", CourtSlotsHandler),
        (r"/api/reservations", ReservationsHandler),
        (r"/api/reservations/my", MyReservationsHandler),
        (r"/api/reservations/([0-9]+)/cancel", CancelReservationHandler),
        (r"/api/admin/users", AdminUsersHandler),
        (r"/api/admin/users/([0-9]+)/status", AdminUserStatusHandler),
        (r"/api/admin/users/([0-9]+)/role", AdminUserRoleHandler),
        (r"/api/admin/courts", AdminCourtsHandler),
        (r"/api/admin/courts/([0-9]+)/status", AdminCourtStatusHandler),
        (r"/api/admin/courts/([0-9]+)", AdminCourtDetailHandler),
        (r"/api/admin/reservations", AdminReservationsHandler),
        (r"/api/admin/reservations/([0-9]+)/cancel", AdminReservationCancelHandler),
        (r"/api/admin/reservations/([0-9]+)", AdminReservationDetailHandler),
        (r"/api/admin/statistics/overview", AdminStatisticsOverviewHandler),
        (r"/api/admin/statistics/courts", AdminStatisticsCourtsHandler),
        (r"/api/admin/statistics/time-slots", AdminStatisticsTimeSlotsHandler),
        (r"/api/admin/statistics/users", AdminStatisticsUsersHandler),
        (r"/api/admin/logs", AdminOperationLogsHandler),
        (r"/api/admin/announcements", AdminAnnouncementsHandler),
        (r"/api/admin/announcements/([0-9]+)/status", AdminAnnouncementStatusHandler),
        (r"/api/admin/announcements/([0-9]+)", AdminAnnouncementDetailHandler),
        (r"/api/admin/configs", AdminConfigsHandler),
        (r"/api/admin/configs/([A-Za-z0-9_]+)", AdminConfigDetailHandler),
    ]
