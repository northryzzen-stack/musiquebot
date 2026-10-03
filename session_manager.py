import os
import shutil
import uuid


class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id

        # Язык
        self.lang = "ru"
        self.lang_selected = False

        # Файлы
        self.original_file = None
        self.current_file = None
        self.preview_file = None

        # История изменений
        self.history = []

    def _file_exists(self, path):
        return bool(path and os.path.exists(path))

    def create_version_path(self, suffix=".mp3"):
        """
        Создаёт уникальное имя для новой версии файла.
        Это предотвращает перезапись preview/current файлов.
        """
        os.makedirs("downloads", exist_ok=True)

        unique_id = uuid.uuid4().hex[:10]

        return os.path.join(
            "downloads",
            f"{self.user_id}_{unique_id}{suffix}"
        )

    def set_new_track(self, file_path: str):
        """
        Устанавливает новый исходный трек
        и полностью сбрасывает историю редактирования.
        """

        self.cleanup_edits()

        self.original_file = file_path
        self.current_file = file_path
        self.preview_file = None
        self.history = []

    def set_preview(self, preview_path: str):
        """
        Устанавливает временную preview-версию.
        Старый preview удаляется.
        """

        if (
            self.preview_file
            and self.preview_file != preview_path
            and self._file_exists(self.preview_file)
        ):
            try:
                os.remove(self.preview_file)
            except OSError:
                pass

        self.preview_file = preview_path

    def apply_preview(self) -> bool:
        """
        Применяет preview.

        Текущая версия сохраняется в history,
        чтобы пользователь мог сделать Undo.
        """

        if not self._file_exists(self.preview_file):
            return False

        if self.current_file and self._file_exists(self.current_file):
            self.history.append(self.current_file)

        self.current_file = self.preview_file
        self.preview_file = None

        return True

    def cancel_preview(self):
        """
        Отменяет preview и удаляет временный файл.
        """

        if self._file_exists(self.preview_file):
            try:
                os.remove(self.preview_file)
            except OSError:
                pass

        self.preview_file = None

    def undo(self) -> bool:
        """
        Возвращает предыдущую применённую версию.
        """

        if not self.history:
            return False

        previous_file = self.history.pop()

        if not self._file_exists(previous_file):
            return False

        current = self.current_file

        self.current_file = previous_file
        self.preview_file = None

        # Удаляем отменённую обработанную версию,
        # но никогда не удаляем оригинал.
        if (
            current
            and current != self.original_file
            and current not in self.history
            and self._file_exists(current)
        ):
            try:
                os.remove(current)
            except OSError:
                pass

        return True

    def reset_to_original(self) -> bool:
        """
        Возвращает исходный загруженный файл.
        """

        if not self._file_exists(self.original_file):
            return False

        self.cancel_preview()

        self.current_file = self.original_file
        self.history = []

        return True

    def copy_current_to_preview(self, suffix=".mp3"):
        """
        Создаёт отдельную копию current_file для обработки.
        Все изменения делаем только над этой копией.
        """

        if not self._file_exists(self.current_file):
            return None

        preview_path = self.create_version_path(suffix)

        shutil.copy2(
            self.current_file,
            preview_path
        )

        self.set_preview(preview_path)

        return preview_path

    def has_track(self) -> bool:
        return self._file_exists(self.current_file)

    def cleanup_edits(self):
        """
        Удаляет временные версии предыдущего трека.
        Оригинальный файл здесь не удаляется.
        """

        files = set(self.history)

        if self.preview_file:
            files.add(self.preview_file)

        if (
            self.current_file
            and self.current_file != self.original_file
        ):
            files.add(self.current_file)

        for file_path in files:
            if (
                file_path
                and file_path != self.original_file
                and os.path.exists(file_path)
            ):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

        self.preview_file = None
        self.history = []


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_session(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id)

        return self.sessions[user_id]

    def remove_session(self, user_id: int):
        """
        Удаляет пользовательскую сессию и временные файлы.
        """

        session = self.sessions.get(user_id)

        if not session:
            return

        session.cleanup_edits()

        del self.sessions[user_id]


session_mgr = SessionManager()
