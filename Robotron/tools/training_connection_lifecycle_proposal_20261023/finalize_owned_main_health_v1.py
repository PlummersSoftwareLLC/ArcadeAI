"""Unselected native health-watch shutdown; no import-time actions.

Keep capture running through private cleanup, atomically stop after a complete
original proof, join the watch, then drain/close its writer. Never close or hash
as successful while the original watch can still run. Never signal main actors.
"""
import time


def finalize(guard,watcher,stop_event,lock,collect,deadline,h,directory,case_already_failed=False):
    result=dict(report=None,failure=None,errors=[],watch_stopped=False,writer_stopped=False)
    if guard is None:
        stop_event.set()
        if watcher is not None:watcher.join(timeout=20)
        result['watch_stopped']=watcher is None or not watcher.is_alive()
        if not result['watch_stopped']:result['errors'].append('Original health watcher completion unknown')
        return result
    try:
        if not case_already_failed:
            while True:
                if time.monotonic()>=deadline:raise ValueError('Original native deadline reached before final health proof; no extension')
                with lock:
                    record=collect()
                    if not record['phase']['overlap_pending']:
                        stop_event.set();break  # no new watch sample can intervene
                time.sleep(.2)
    except Exception as error:result['errors'].append('Original final main-health capture: '+repr(error))
    finally:stop_event.set()
    if watcher is not None:watcher.join(timeout=20)
    result['watch_stopped']=watcher is None or not watcher.is_alive()
    if not result['watch_stopped']:
        result['errors'].append('Original health watcher completion unknown; no guard/writer success inferred')
        return result  # guard lock/writer may still be in use: no close or hashing
    try:result['report']=h.put(directory/'closed-full-health-report.json',guard.close())
    except Exception as error:
        result['errors'].append('Original main-health closure: '+repr(error))
        try:result['failure']=h.put(directory/'failed-full-health-report.json',guard.preserve_failure(error))
        except Exception as failure:result['errors'].append('Original raw health-failure preservation: '+repr(failure))
    result['writer_stopped']=not guard.collector.writer.thread.is_alive()
    if not result['writer_stopped']:result['errors'].append('Original health evidence writer completion unknown')
    return result
