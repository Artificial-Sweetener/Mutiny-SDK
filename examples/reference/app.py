#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Minimal reference host that stays on Mutiny's public API."""

from __future__ import annotations

import asyncio
import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mutiny import Config, JobSnapshot, Mutiny, ProgressUpdate

from .async_utils import AsyncTaskHandler


class GuiTokenProvider:
    """Provide the Discord token entered through the GUI."""

    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self) -> str:
        return self._token


class MutinyReferenceApp(tk.Tk):
    """Small Tkinter host that demonstrates public-only Mutiny usage."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Mutiny Reference")
        self.geometry("900x700")

        self._loop = asyncio.new_event_loop()
        self._async = AsyncTaskHandler(self._loop)
        self._async.start()

        self._client: Mutiny | None = None
        self._event_future = None

        self._token = tk.StringVar()
        self._guild = tk.StringVar()
        self._channel = tk.StringVar()
        self._prompt = tk.StringVar()
        self._image_path = tk.StringVar()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        connection = ttk.LabelFrame(self, text="Connection", padding=12)
        connection.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        connection.columnconfigure(1, weight=1)

        ttk.Label(connection, text="Discord Token").grid(row=0, column=0, sticky="w")
        ttk.Entry(connection, textvariable=self._token, show="*").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(connection, text="Guild Id").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(connection, textvariable=self._guild).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )
        ttk.Label(connection, text="Channel Id").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(connection, textvariable=self._channel).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )
        ttk.Button(connection, text="Connect", command=self._connect).grid(
            row=3, column=1, sticky="e", pady=(10, 0)
        )

        actions = ttk.LabelFrame(self, text="Actions", padding=12)
        actions.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        actions.columnconfigure(1, weight=1)

        ttk.Label(actions, text="Prompt").grid(row=0, column=0, sticky="w")
        ttk.Entry(actions, textvariable=self._prompt).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(actions, text="Image / Video Path").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(actions, textvariable=self._image_path).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )
        ttk.Button(actions, text="Browse", command=self._browse).grid(
            row=1, column=2, padx=(8, 0), pady=(8, 0)
        )

        button_row = ttk.Frame(actions)
        button_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Button(button_row, text="Imagine", command=self._submit_imagine).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Describe", command=self._submit_describe).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(button_row, text="Resolve Image", command=self._resolve_image).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        log_frame = ttk.LabelFrame(self, text="Log", padding=12)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(6, 12))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self._log = tk.Text(log_frame, wrap="word", state="disabled")
        self._log.grid(row=0, column=0, sticky="nsew")

    def _append_log(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _browse(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=str(pathlib.Path.cwd()),
            filetypes=[("Media", "*.png;*.jpg;*.jpeg;*.webp;*.mp4;*.mov"), ("All files", "*.*")],
        )
        if selected:
            self._image_path.set(selected)

    def _connect(self) -> None:
        if self._client is not None:
            self._append_log("Client is already connected.")
            return
        try:
            config = Config.create(
                token_provider=GuiTokenProvider(self._token.get().strip()),
                guild_id=self._guild.get().strip(),
                channel_id=self._channel.get().strip(),
            )
            client = Mutiny(config)
        except Exception as exc:
            messagebox.showerror("Mutiny", str(exc))
            return

        async def _connect_and_listen() -> None:
            await client.start()
            ready = await client.wait_ready(timeout_s=60)
            if not ready:
                raise RuntimeError("Gateway not ready within 60 seconds.")
            self._client = client
            self._append_log("Connected.")
            async for update in client.events():
                if isinstance(update, ProgressUpdate):
                    self._append_log(f"[progress] {update.job_id}: {update.status_text}")
                elif isinstance(update, JobSnapshot):
                    self._append_log(f"[job] {update.id}: {update.status.name} ({update.kind})")

        self._event_future = self._async.run_coro(_connect_and_listen(), self._handle_async_result)

    def _submit_imagine(self) -> None:
        if self._client is None:
            self._append_log("Connect first.")
            return
        prompt = self._prompt.get().strip()
        image_path = self._image_path.get().strip()
        self._async.run_coro(
            self._client.imagine(
                prompt,
                omni_reference=image_path or None,
            ),
            lambda handle, error: self._handle_submission("imagine", handle, error),
        )

    def _submit_describe(self) -> None:
        if self._client is None:
            self._append_log("Connect first.")
            return
        image_path = self._image_path.get().strip()
        if not image_path:
            self._append_log("Select an image first.")
            return
        self._async.run_coro(
            self._client.describe(image_path),
            lambda handle, error: self._handle_submission("describe", handle, error),
        )

    def _resolve_image(self) -> None:
        if self._client is None:
            self._append_log("Connect first.")
            return
        image_path = self._image_path.get().strip()
        if not image_path:
            self._append_log("Select an image first.")
            return
        try:
            resolution = self._client.resolve_image(image_path)
        except Exception as exc:
            self._append_log(f"resolve_image failed: {exc}")
            return
        if resolution is None:
            self._append_log("No cached image resolution was found.")
            return
        self._append_log(f"Resolved image -> job_id={resolution.job_id} index={resolution.index}")

    def _handle_submission(self, label: str, handle, error: Exception | None) -> None:
        if error is not None:
            self._append_log(f"{label} failed: {error}")
            return
        self._append_log(f"{label} submitted: {handle.id}")

    def _handle_async_result(self, _result, error: Exception | None) -> None:
        if error is not None:
            self._append_log(f"background task failed: {error}")

    def on_close(self) -> None:
        if self._client is not None:
            self._async.run_coro(self._client.close())
            self._client = None
        self._async.stop()
        self.destroy()


__all__ = ["GuiTokenProvider", "MutinyReferenceApp"]
