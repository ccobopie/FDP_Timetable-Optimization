import requests


class CanvasAPI:
    def __init__(self, token, base_url):
        self.token = token
        self.base_url = base_url

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get_courses(self):
        url = f"{self.base_url}/courses"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 200:
            return response.json()
        return []

    def get_assignments(self, course_id):
        url = f"{self.base_url}/courses/{course_id}/assignments"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 200:
            return response.json()
        return []

    def get_course(self, course_id):
        url = f"{self.base_url}/courses/{course_id}"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 200:
            return response.json()
        return None
