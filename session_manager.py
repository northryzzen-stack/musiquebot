import os

class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.lang = "ru"
        self.original_file = None
        self.current_file = None
        self.preview_file = None
        self.history = []  # Список прошлых версий для Undo

    def set_new_track(self, file_path: str):
        """Загрузка нового трека: сброс старой сессии"""
        self.original_file = file_path
        self.current_file = file_path
        self.preview_file = None
        self.history = []

    def set_preview(self, preview_path: str):
        """Создание временного предпросмотра"""
        self.preview_file = preview_path

    def apply_preview(self) -> bool:
        """Подтверждение изменений: preview становится current"""
        if self.preview_file and os.path.exists(self.preview_file):
            if self.current_file:
                self.history.append(self.current_file)
            self.current_file = self.preview_file
            self.preview_file = None
            return True
        return False

    def cancel_preview(self):
        """Отмена предпросмотра: удаление временного файла"""
        if self.preview_file and os.path.exists(self.preview_file):
            try:
                os.remove(self.preview_file)
            except OSError:
                pass
        self.preview_file = None

    def undo(self) -> bool:
        """Откат к предыдущей сохраненной версии"""
        if self.history:
            prev_file = self.history.pop()
            if self.current_file and self.current_file != self.original_file:
                try:
                    os.remove(self.current_file)
                except OSError:
                    pass
            self.current_file = prev_file
            return True
        return False

    def reset_to_original(self):
        """Сброс к исходнику"""
        self.current_file = self.original_file
        self.preview_file = None
        self.history = []

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_session(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id)
        return self.sessions[user_id]

session_mgr = SessionManager()
