# Copyright 2014 MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities for testing Motor with asyncio."""

import asyncio
import functools
import inspect
import os
import unittest
from asyncio import events, tasks

from motor import motor_asyncio


class _TestMethodWrapper(object):
    """Wraps a test method to raise an error if it returns a value.

    This is mainly used to detect undecorated generators (if a test
    method yields it must use a decorator to consume the generator),
    but will also detect other kinds of return values (these are not
    necessarily errors, but we alert anyway since there is no good
    reason to return a value from a test).

    Adapted from Tornado's test framework.
    """
    def __init__(self, orig_method):
        self.orig_method = orig_method

    def __call__(self):
        result = self.orig_method()
        if inspect.isgenerator(result):
            raise TypeError("Generator test methods should be decorated with "
                            "@asyncio_test")
        elif result is not None:
            raise ValueError("Return value from test method ignored: %r" %
                             result)

    def __getattr__(self, name):
        """Proxy all unknown attributes to the original method.

        This is important for some of the decorators in the `unittest`
        module, such as `unittest.skipIf`.
        """
        return getattr(self.orig_method, name)


class AsyncIOTestCase(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)

        # It's easy to forget the @asyncio_test decorator, but if you do
        # the test will silently be ignored because nothing will consume
        # the generator. Replace the test method with a wrapper that will
        # make sure it's not an undecorated generator.
        # (Adapted from Tornado's AsyncTestCase.)
        setattr(self, methodName, _TestMethodWrapper(getattr(self, methodName)))

    def setUp(self):
        # Ensure that the event loop is passed explicitly in Motor.
        events.set_event_loop(None)
        self.loop = asyncio.new_event_loop()

    def asyncio_client(self, uri=None, *args, **kwargs):
        """Get an AsyncIOMotorClient.

        Ignores self.ssl, you must pass 'ssl' argument.
        """
        return motor_asyncio.AsyncIOMotorClient(
            uri or 'mongodb://localhost', *args, io_loop=self.loop, **kwargs)

    def tearDown(self):
        self.loop.close()


def get_async_test_timeout():
    """Get the global timeout setting for async tests.

    Returns a float, the timeout in seconds.
    """
    try:
        return float(os.environ.get('ASYNC_TEST_TIMEOUT'))
    except (ValueError, TypeError):
        return 5


# TODO: doc. Spin off to a PyPI package.
def asyncio_test(func=None, timeout=None):
    """Decorator like Tornado's gen_test."""
    def wrap(f):
        @functools.wraps(f)
        def wrapped(self, *args, **kwargs):
            actual_timeout = timeout
            if actual_timeout is None:
                actual_timeout = get_async_test_timeout()

            def on_timeout():
                if inspect.isgenerator(coro):
                    # Simply doing task.cancel() raises an unhelpful traceback.
                    # We want to include the coroutine's stack, so throw into
                    # the generator and record its traceback in exc_handler().
                    msg = 'timed out after %s seconds' % actual_timeout
                    coro.throw(asyncio.CancelledError(msg))

            coro_exc = None

            def exc_handler(loop, context):
                nonlocal coro_exc
                coro_exc = context['exception']

                # Raise CancelledError from run_until_complete below.
                task.cancel()

            self.loop.set_exception_handler(exc_handler)
            coro = asyncio.coroutine(f)(self, *args, **kwargs)
            timeout_handle = self.loop.call_later(actual_timeout, on_timeout)
            task = tasks.Task(coro, loop=self.loop)
            try:
                self.loop.run_until_complete(task)
            except:
                if coro_exc:
                    # Raise the error thrown in on_timeout, with only the
                    # traceback from the coroutine itself, not from
                    # run_until_complete.
                    raise coro_exc from None

                raise

            # self.loop.run_until_complete(coro)
            timeout_handle.cancel()

        return wrapped

    if func is not None:
        # Used like:
        #     @gen_test
        #     def f(self):
        #         pass
        return wrap(func)
    else:
        # Used like @gen_test(timeout=10)
        return wrap
