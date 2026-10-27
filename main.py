"""Single entry point for the packaged app.

    NaukriProfileBot.exe              -> open the desktop UI
    NaukriProfileBot.exe --run-task   -> one scheduled profile update (used by Task Scheduler)
    NaukriProfileBot.exe --uninstall  -> remove the scheduled task (used by the uninstaller)
"""
import sys


def main() -> int:
    if "--run-task" in sys.argv:
        import run_task
        return run_task.main()
    if "--uninstall" in sys.argv:
        import task_scheduler
        try:
            task_scheduler.unregister()
        except Exception:
            pass
        return 0
    import app
    app.launch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
