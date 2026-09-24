import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
import aiomysql
from repositories import transaction as boundary
from utils.response import ApiError


class TransactionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def run_transaction(self, failure=None):
        connection=MagicMock()
        for method in ('autocommit','begin','commit','rollback'):
            setattr(connection,method,AsyncMock())
        @asynccontextmanager
        async def cursor_scope(): yield object()
        @asynccontextmanager
        async def acquire(): yield connection
        connection.cursor.side_effect=lambda *_:cursor_scope()
        pool=MagicMock();pool.acquire.side_effect=acquire
        with patch.object(boundary,'get_pool',AsyncMock(return_value=pool)):
            try:
                async with boundary.transaction(None):
                    if failure: raise failure
            except BaseException as exc:
                return connection,exc
        return connection,None

    async def test_success_commits_once_and_resets_pooled_connection(self):
        connection,error=await self.run_transaction()
        self.assertIsNone(error);connection.commit.assert_awaited_once();connection.rollback.assert_not_awaited()
        self.assertEqual([x.args for x in connection.autocommit.await_args_list],[(False,),(True,)])

    async def test_failure_and_task_cancellation_roll_back_before_reusing_connection(self):
        for failure in (RuntimeError('fault after writes'),asyncio.CancelledError()):
            connection,error=await self.run_transaction(failure)
            self.assertIs(error,failure);connection.rollback.assert_awaited_once();connection.commit.assert_not_awaited()
            self.assertEqual(connection.autocommit.await_args.args,(True,))

    async def test_lock_conflicts_return_retryable_error_after_rollback(self):
        for code in (1205,1213):
            connection,error=await self.run_transaction(aiomysql.OperationalError(code,'lock conflict'))
            self.assertIsInstance(error,ApiError);self.assertEqual(error.status_code,409)
            connection.rollback.assert_awaited_once();connection.commit.assert_not_awaited()
