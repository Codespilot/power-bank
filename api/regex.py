import re

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{4,32}$")
MOBILE_REGEX = re.compile(r"^\d{10,22}$")
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
