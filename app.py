"""Naukri Profile Bot - desktop UI."""
import threading
from datetime import date, datetime, timedelta
from tkinter import messagebox

import customtkinter as ctk

import bot
import task_scheduler as ts
from config import (
    LOG_FILE, Settings, resource_path, append_log, delete_password, get_password, load_status,
    set_password, update_status,
)
from run_task import perform

try:
    from tkcalendar import Calendar
except ImportError:  # optional dependency
    Calendar = None

ICON = resource_path("assets/icon.ico")
ACCENT = "#275DF5"
ACCENT_HOVER = "#1C47C9"
DANGER = "#E5484D"
DANGER_HOVER = "#C93C40"
SUCCESS = "#2E9E5B"
MUTED = ("gray45", "gray65")
CARD = ("#FFFFFF", "#24262B")
BG = ("#F2F4F8", "#17181C")
BORDER = ("#E3E6EC", "#32353C")

METHOD_LABELS = {"manual": "Google / OTP", "password": "Email & Password"}
HOURS = [f"{h:02d}" for h in range(1, 13)]
MINUTES = [f"{m:02d}" for m in range(0, 60, 5)]


def to_display(t24: str) -> str:
    return datetime.strptime(t24, "%H:%M").strftime("%I:%M %p").lstrip("0")


def fmt_dt(dt: datetime) -> str:
    day = "Today" if dt.date() == date.today() else (
        "Tomorrow" if dt.date() == date.today() + timedelta(days=1) else dt.strftime("%a, %d %b"))
    return f"{day}, {dt.strftime('%I:%M %p').lstrip('0')}"


class Card(ctk.CTkFrame):
    def __init__(self, master, title: str, subtitle: str = ""):
        super().__init__(master, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=16, weight="bold"),
                     anchor="w").pack(fill="x", padx=18, pady=(12, 0))
        if subtitle:
            ctk.CTkLabel(self, text=subtitle, text_color=MUTED, anchor="w",
                         font=ctk.CTkFont(size=12)).pack(fill="x", padx=18)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=(8, 14))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Naukri Profile Bot")
        self.minsize(940, 600)
        if self.winfo_screenheight() < 820:  # small laptop screens: use the whole screen
            self.geometry("1060x640+0+0")
            self.after(0, lambda: self.state("zoomed"))
        else:
            self.geometry("1060x700")
        self.configure(fg_color=BG)
        if ICON.exists():  # CustomTkinter sets its own icon shortly after start; override it after
            self.after(250, lambda: self.iconbitmap(str(ICON)))

        self.settings = Settings.load()
        self.task_active = False
        self.busy = False
        self._log_pos = 0

        self.grid_columnconfigure(0, weight=5, uniform="col")
        self.grid_columnconfigure(1, weight=4, uniform="col")
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 16))
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 16))
        self._build_account(left)
        self._build_schedule(left)
        self._build_status(right)
        self._build_log(right)

        self._render_times()
        self._load_log_tail()
        self.after(1000, self._tick)
        self._in_thread(self._check_system_state)

    # ================= layout =================
    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(12, 10))
        logo = ctk.CTkLabel(bar, text="N", width=40, height=40, corner_radius=12, fg_color=ACCENT,
                            text_color="white", font=ctk.CTkFont(size=22, weight="bold"))
        logo.pack(side="left")
        titles = ctk.CTkFrame(bar, fg_color="transparent")
        titles.pack(side="left", padx=12)
        ctk.CTkLabel(titles, text="Naukri Profile Bot", font=ctk.CTkFont(size=22, weight="bold"),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(titles, text="Keeps your profile fresh so it stays on top of recruiter searches",
                     text_color=MUTED, anchor="w").pack(anchor="w")

        self.theme = ctk.CTkSegmentedButton(bar, values=["Light", "Dark"], command=self._set_theme,
                                            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER)
        self.theme.set("Light")
        self.theme.pack(side="right")

    def _build_account(self, parent):
        card = Card(parent, "Naukri account")
        card.pack(fill="x", pady=(0, 12))
        b = card.body

        self.method = ctk.CTkSegmentedButton(
            b, values=list(METHOD_LABELS.values()), command=self._on_method_change,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER)
        self.method.set(METHOD_LABELS.get(self.settings.login_method, "Google / OTP"))
        self.method.pack(fill="x")

        self.method_panel = ctk.CTkFrame(b, fg_color="transparent")
        self.method_panel.pack(fill="x", pady=(10, 0))

        # Google / OTP panel
        self.manual_panel = ctk.CTkFrame(self.method_panel, fg_color="transparent")
        ctk.CTkLabel(self.manual_panel, justify="left", anchor="w", text_color=MUTED, wraplength=480,
                     text="Sign in once in the browser window using Google, OTP or password. "
                          "The session is remembered for all scheduled updates.").pack(fill="x")
        row = ctk.CTkFrame(self.manual_panel, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(row, text="Log in with browser", height=36, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self.manual_login).pack(side="left")
        self._logout_button(row).pack(side="left", padx=(10, 0))

        # Email & Password panel
        self.password_panel = ctk.CTkFrame(self.method_panel, fg_color="transparent")
        self.password_panel.grid_columnconfigure((0, 1), weight=1, uniform="pw")
        self.username = ctk.CTkEntry(self.password_panel, height=36,
                                     placeholder_text="Email ID / Username")
        self.username.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.password = ctk.CTkEntry(self.password_panel, height=36, show="•",
                                     placeholder_text="Password")
        self.password.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        row = ctk.CTkFrame(self.password_panel, fg_color="transparent")
        row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ctk.CTkButton(row, text="Save credentials", height=36, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self.save_credentials).pack(side="left")
        self._logout_button(row).pack(side="left", padx=(10, 0))
        self.show_pw = ctk.CTkCheckBox(row, text="Show password", command=self._toggle_pw,
                                       fg_color=ACCENT)
        self.show_pw.pack(side="right")
        if self.settings.username:
            self.username.insert(0, self.settings.username)
            pw = get_password(self.settings.username)
            if pw:
                self.password.insert(0, pw)

        self._on_method_change(self.method.get(), save=False)

    def _logout_button(self, parent):
        return ctk.CTkButton(parent, text="Log out", width=90, height=36, fg_color="transparent",
                             border_width=1, border_color=BORDER, text_color=("gray20", "gray85"),
                             hover_color=BORDER, command=self.clear_session)

    def _build_schedule(self, parent):
        card = Card(parent, "Schedule", "Your profile is refreshed every day at these times")
        card.pack(fill="both", expand=True)
        b = card.body

        picker = ctk.CTkFrame(b, fg_color="transparent")
        picker.pack(fill="x")
        self.hour = ctk.CTkComboBox(picker, values=HOURS, width=72, height=34, justify="center")
        self.hour.set("10")
        self.hour.pack(side="left")
        ctk.CTkLabel(picker, text=":", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=4)
        self.minute = ctk.CTkComboBox(picker, values=MINUTES, width=72, height=34, justify="center")
        self.minute.set("00")
        self.minute.pack(side="left")
        self.ampm = ctk.CTkSegmentedButton(picker, values=["AM", "PM"], height=34,
                                           selected_color=ACCENT, selected_hover_color=ACCENT_HOVER)
        self.ampm.set("AM")
        self.ampm.pack(side="left", padx=10)
        ctk.CTkButton(picker, text="+ Add time", width=100, height=34, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=self.add_time).pack(side="left")

        self.chips = ctk.CTkFrame(b, fg_color="transparent")
        self.chips.pack(fill="x", pady=(8, 2))

        until = ctk.CTkFrame(b, fg_color="transparent")
        until.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(until, text="Run until", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.end_date = ctk.CTkEntry(until, width=120, height=34, justify="center",
                                     placeholder_text="YYYY-MM-DD")
        self.end_date.insert(0, self.settings.end_date
                             or (date.today() + timedelta(days=30)).isoformat())
        self.end_date.pack(side="left", padx=(10, 4))
        self.end_date.bind("<FocusOut>", lambda _e: self._schedule_changed())
        if Calendar:
            ctk.CTkButton(until, text="📅", width=36, height=34, fg_color="transparent",
                          border_width=1, border_color=BORDER, text_color=("gray20", "gray85"),
                          hover_color=BORDER, command=self._pick_date).pack(side="left")
        for label, days in (("+1 week", 7), ("+1 month", 30), ("+3 months", 90)):
            ctk.CTkButton(until, text=label, width=74, height=28, fg_color="transparent",
                          text_color=ACCENT, hover_color=BORDER,
                          command=lambda d=days: self._set_end(date.today() + timedelta(days=d))
                          ).pack(side="left", padx=(6, 0))

        self.hidden = ctk.CTkSwitch(b, text="Run the browser hidden during scheduled updates",
                                    progress_color=ACCENT, command=self._save_settings)
        if self.settings.headless:
            self.hidden.select()
        self.hidden.pack(anchor="w", pady=(12, 0))

        actions = ctk.CTkFrame(b, fg_color="transparent")
        actions.pack(fill="x", side="bottom", pady=(12, 0))
        self.activate_btn = ctk.CTkButton(actions, text="Activate schedule", height=42,
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                          command=self.toggle_schedule)
        self.activate_btn.pack(side="left", fill="x", expand=True)
        self.run_btn = ctk.CTkButton(actions, text="Update now", height=42, width=130,
                                     fg_color="transparent", border_width=1, border_color=ACCENT,
                                     text_color=ACCENT, hover_color=BORDER, command=self.run_now)
        self.run_btn.pack(side="left", padx=(10, 0))

    def _build_status(self, parent):
        card = Card(parent, "Status")
        card.pack(fill="x", pady=(0, 14))
        grid = card.body
        grid.grid_columnconfigure(1, weight=1)
        self.status_values = {}
        for row, key in enumerate(("Schedule", "Next update", "Last update", "Session", "Wake from sleep")):
            ctk.CTkLabel(grid, text=key, text_color=MUTED, anchor="w").grid(
                row=row, column=0, sticky="w", pady=3)
            val = ctk.CTkLabel(grid, text="…", anchor="w", font=ctk.CTkFont(weight="bold"))
            val.grid(row=row, column=1, sticky="w", padx=(14, 0), pady=3)
            self.status_values[key] = val
        self.wake_btn = ctk.CTkButton(grid, text="Enable", width=70, height=26, fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER, command=self.enable_wake)
        self.wake_note = ctk.CTkLabel(
            grid, text_color=MUTED, anchor="w", justify="left", wraplength=520,
            font=ctk.CTkFont(size=11),
            text="Updates run while the laptop is locked or asleep (it wakes up for them) "
                 "as long as you stay signed in to Windows. The app itself can stay closed.")
        self.wake_note.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_log(self, parent):
        card = Card(parent, "Activity")
        card.pack(fill="both", expand=True)
        self.log_box = ctk.CTkTextbox(card.body, font=ctk.CTkFont(family="Consolas", size=12),
                                      fg_color=BG, corner_radius=10, wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    # ================= account =================
    def _method_key(self) -> str:
        return next(k for k, v in METHOD_LABELS.items() if v == self.method.get())

    def _on_method_change(self, _value=None, save=True):
        self.manual_panel.pack_forget()
        self.password_panel.pack_forget()
        panel = self.manual_panel if self._method_key() == "manual" else self.password_panel
        panel.pack(fill="x")
        if save:
            self._save_settings()

    def _toggle_pw(self):
        self.password.configure(show="" if self.show_pw.get() else "•")

    def save_credentials(self):
        user, pw = self.username.get().strip(), self.password.get()
        if not user or not pw:
            messagebox.showwarning("Missing details", "Enter both email/username and password.")
            return
        if self.settings.username and self.settings.username != user:
            delete_password(self.settings.username)
        set_password(user, pw)
        self._save_settings()
        append_log("Credentials saved to Windows Credential Manager.")

    def manual_login(self):
        self._save_settings()

        def work():
            if bot.manual_login(append_log):
                update_status(logged_in=True)
        self._in_thread(work)

    def clear_session(self):
        if not messagebox.askyesno("Log out", "Log out of Naukri and delete the saved session?"):
            return
        try:
            bot.clear_session()
            update_status(logged_in=False)
            append_log("Logged out; saved browser session deleted.")
        except Exception as e:
            append_log(f"Could not log out: {e}")

    # ================= schedule =================
    def add_time(self):
        try:
            h, m = int(self.hour.get()), int(self.minute.get())
            if not (1 <= h <= 12 and 0 <= m <= 59):
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid time", "Hour must be 1-12 and minute 0-59.")
            return
        t24 = datetime.strptime(f"{h}:{m:02d} {self.ampm.get()}", "%I:%M %p").strftime("%H:%M")
        if t24 not in self.settings.times:
            self.settings.times = sorted([*self.settings.times, t24])
            self._render_times()
            self._schedule_changed()

    def remove_time(self, t24: str):
        self.settings.times = [t for t in self.settings.times if t != t24]
        self._render_times()
        self._schedule_changed()

    def _render_times(self):
        for w in self.chips.winfo_children():
            w.destroy()
        if not self.settings.times:
            ctk.CTkLabel(self.chips, text="No times yet. Add at least one above.",
                         text_color=MUTED).grid(row=0, column=0, sticky="w")
            return
        for i, t in enumerate(sorted(self.settings.times)):
            chip = ctk.CTkFrame(self.chips, fg_color=("#E8EEFF", "#2A3350"), corner_radius=16)
            chip.grid(row=i // 4, column=i % 4, padx=(0, 8), pady=4, sticky="w")
            ctk.CTkLabel(chip, text=to_display(t), text_color=(ACCENT, "#9DB5FF"),
                         font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(12, 2))
            ctk.CTkButton(chip, text="✕", width=24, height=24, corner_radius=12,
                          fg_color="transparent", hover_color=("#D3DEFF", "#3A4670"),
                          text_color=(ACCENT, "#9DB5FF"),
                          command=lambda x=t: self.remove_time(x)).pack(side="left", padx=(0, 4))

    def _set_end(self, d: date):
        self.end_date.delete(0, "end")
        self.end_date.insert(0, d.isoformat())
        self._schedule_changed()

    def _pick_date(self):
        top = ctk.CTkToplevel(self)
        top.title("Run until")
        top.resizable(False, False)
        top.transient(self)
        try:
            current = ts.parse_end_date(self.end_date.get().strip()) or date.today()
        except ValueError:
            current = date.today()
        cal = Calendar(top, selectmode="day", mindate=date.today(), year=current.year,
                       month=current.month, day=current.day, date_pattern="yyyy-mm-dd",
                       background=ACCENT, headersbackground="#E8EEFF", selectbackground=ACCENT,
                       normalbackground="white", weekendbackground="white", borderwidth=0,
                       font=("Segoe UI", 11), headersforeground=ACCENT)
        cal.pack(padx=12, pady=12)

        def chosen(_e=None):
            self._set_end(cal.selection_get())
            top.destroy()
        cal.bind("<<CalendarSelected>>", chosen)
        top.after(100, top.grab_set)

    def _validate(self) -> bool:
        try:
            end = ts.parse_end_date(self.end_date.get().strip())
        except ValueError:
            messagebox.showerror("Invalid date", "'Run until' must be a date like 2026-12-31.")
            return False
        if not end or end < date.today():
            messagebox.showerror("Invalid date", "'Run until' must be today or later.")
            return False
        if not self.settings.times:
            messagebox.showwarning("No times", "Add at least one time first.")
            return False
        return True

    def _save_settings(self):
        s = self.settings
        s.login_method = self._method_key()
        s.username = self.username.get().strip()
        s.end_date = self.end_date.get().strip()
        s.headless = bool(self.hidden.get())
        s.save()

    def _schedule_changed(self):
        self._save_settings()
        if self.task_active:  # keep the Windows task in sync with edits
            if self.settings.times and self._valid_end_silent():
                self._in_thread(lambda: self._activate_task(quiet=True))
            else:
                self._in_thread(self._deactivate_task)

    def _valid_end_silent(self) -> bool:
        try:
            end = ts.parse_end_date(self.settings.end_date)
        except ValueError:
            return False
        return bool(end and end >= date.today())

    def toggle_schedule(self):
        if self.task_active:
            self._in_thread(self._deactivate_task)
        elif self._validate():
            self._save_settings()
            self._in_thread(self._activate_task)

    def _activate_task(self, quiet=False):
        ts.register(self.settings.times, self.settings.end_date)
        self.task_active = True
        if not quiet:
            times = ", ".join(to_display(t) for t in self.settings.times)
            append_log(f"Schedule activated: daily at {times} until {self.settings.end_date}.")
        else:
            append_log("Schedule updated.")

    def _deactivate_task(self):
        ts.unregister()
        self.task_active = False
        append_log("Schedule deactivated.")

    def run_now(self):
        if self.busy:
            return
        self._save_settings()

        def work():
            self.busy = True
            try:
                append_log("Manual update started.")
                perform(self.settings, attempts=1)
            finally:
                self.busy = False
        self._in_thread(work)

    # ================= system =================
    def _check_system_state(self):
        self.task_active = ts.is_registered()
        if self.task_active and self._valid_end_silent() and self.settings.times:
            # Re-register so an existing task picks up any changes to the task definition.
            ts.register(self.settings.times, self.settings.end_date)
        self.wake_ok = ts.wake_timers_enabled()

    def enable_wake(self):
        try:
            ts.enable_wake_timers()
            self.wake_ok = ts.wake_timers_enabled()
            append_log("Wake timers enabled in the power plan.")
        except Exception as e:
            messagebox.showerror(
                "Could not enable",
                f"{e}\n\nEnable it manually: Control Panel > Power Options > Change plan settings > "
                "Change advanced power settings > Sleep > Allow wake timers > Enable.")

    def _set_theme(self, value):
        ctk.set_appearance_mode(value.lower())

    # ================= periodic refresh =================
    def _tick(self):
        self._refresh_status()
        self._load_log_tail()
        self.after(1000, self._tick)

    def _refresh_status(self):
        st = load_status()
        v = self.status_values

        if self.task_active:
            v["Schedule"].configure(text=f"● Active until {self.settings.end_date}", text_color=SUCCESS)
            self.activate_btn.configure(text="Deactivate schedule", fg_color=DANGER,
                                        hover_color=DANGER_HOVER)
            nxt = ts.next_run(self.settings.times, self.settings.end_date)
            v["Next update"].configure(text=fmt_dt(nxt) if nxt else "None (end date reached)")
        else:
            v["Schedule"].configure(text="● Inactive", text_color=MUTED)
            self.activate_btn.configure(text="Activate schedule", fg_color=ACCENT,
                                        hover_color=ACCENT_HOVER)
            v["Next update"].configure(text="—")

        if self.busy:
            v["Last update"].configure(text="Running now…", text_color=ACCENT)
        elif st.get("last_run"):
            ok = st.get("last_ok")
            when = fmt_dt(datetime.fromisoformat(st["last_run"]))
            v["Last update"].configure(text=f"{'✓' if ok else '✕'} {when}  ·  {st.get('last_message', '')}",
                                       text_color=SUCCESS if ok else DANGER)
        else:
            v["Last update"].configure(text="Never", text_color=MUTED)

        logged_in = st.get("logged_in")
        if logged_in:
            text, color = "● Logged in", SUCCESS
        elif logged_in is False:
            text, color = "● Not logged in", DANGER
        else:
            text, color = "● Unknown (run 'Update now' to check)", MUTED
        v["Session"].configure(text=text, text_color=color)

        wake = getattr(self, "wake_ok", None)
        if wake:
            v["Wake from sleep"].configure(text="● Enabled", text_color=SUCCESS)
            self.wake_btn.grid_forget()
        elif wake is False:
            v["Wake from sleep"].configure(text="● Disabled in power plan", text_color=DANGER)
            self.wake_btn.grid(row=4, column=2, sticky="e")
        else:
            v["Wake from sleep"].configure(text="…", text_color=MUTED)

        self.run_btn.configure(state="disabled" if self.busy else "normal")

    def _load_log_tail(self):
        try:
            size = LOG_FILE.stat().st_size
        except OSError:
            return
        if size < self._log_pos:  # file was truncated
            self._log_pos = 0
        if size == self._log_pos:
            return
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            if self._log_pos == 0 and size > 20000:
                f.seek(size - 20000)
                f.readline()
            else:
                f.seek(self._log_pos)
            new = f.read()
            self._log_pos = f.tell()
        self.log_box.configure(state="normal")
        self.log_box.insert("end", new)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ================= helpers =================
    def _in_thread(self, fn):
        def wrapper():
            try:
                fn()
            except Exception as e:
                append_log(f"ERROR: {e}")
        threading.Thread(target=wrapper, daemon=True).start()


def launch():
    ctk.set_appearance_mode("light")
    App().mainloop()


if __name__ == "__main__":
    launch()
