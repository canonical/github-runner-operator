# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for threads."""

import logging
from queue import Queue
from threading import Thread

logger = logging.getLogger(__name__)


def _add_err_queue(function: callable, err_queue: Queue):
    def func_with_err_queue():
        try:
            function()
        except Exception as err:
            logger.exception("Caught exception in thread")
            err_queue.put(err, block=True, timeout=None)
    return func_with_err_queue

class ThreadManager:
    
    def __init__(self):
        self.err_queue = Queue()
        self.threads = []
    
    def add_thread(self, target: callable, **kwargs):
        func_with_err_handling = _add_err_queue(target, self.err_queue)
        thread = Thread(target=func_with_err_handling, **kwargs)
        self.threads.append(thread)
        
    def start(self):
        for thread in self.threads:
            thread.start()
    
    def raise_on_error(self):
        err: Exception =  self.err_queue.get(block=True, timeout=None)
        raise err.with_traceback(err.__traceback__)
