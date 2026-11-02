"""Stop native status watch, then close/reap the separately scoped observer."""
def finalize(guard,watcher,stop_event,lock,collect,deadline,h,directory,case_already_failed=False):
    stop_event.set()
    if watcher is not None:watcher.join(timeout=20)
    if watcher is not None and watcher.is_alive():
        return dict(report=None,failure=None,errors=['Original observer status-watch completion unknown'],watch_stopped=False,writer_stopped=False,scope_complete=False,statuses=[])
    result=guard.finish(case_already_failed=case_already_failed);result['watch_stopped']=True
    return result
