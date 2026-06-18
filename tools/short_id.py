import re
import secrets
import string

OPPORTUNITY_ID_ALPHABET = string.ascii_lowercase + string.digits
OPPORTUNITY_ID_LENGTH = 8
COMPASS_USER_ID_PATTERN = re.compile(r"^cu_(\d+)$")


def generate_opportunity_id(length: int = OPPORTUNITY_ID_LENGTH) -> str:
    return "".join(secrets.choice(OPPORTUNITY_ID_ALPHABET) for _ in range(length))


def normalize_opportunity_id(value: str) -> str:
    opportunity_id = value.strip().lower()
    if not opportunity_id or len(opportunity_id) > OPPORTUNITY_ID_LENGTH:
        raise ValueError(f"Opportunity id must be 1-{OPPORTUNITY_ID_LENGTH} characters.")
    if any(char not in OPPORTUNITY_ID_ALPHABET for char in opportunity_id):
        raise ValueError("Opportunity id must use lowercase letters and digits only.")
    return opportunity_id


def format_compass_user_id(number: int) -> str:
    if number < 1:
        raise ValueError("Compass user number must be positive.")
    return f"cu_{number}"


def normalize_compass_user_id(value: str) -> str:
    compass_user_id = value.strip().lower()
    if not COMPASS_USER_ID_PATTERN.fullmatch(compass_user_id):
        raise ValueError("Compass user id must look like cu_1, cu_2, ...")
    return compass_user_id


def parse_compass_user_number(compass_user_id: str) -> int | None:
    match = COMPASS_USER_ID_PATTERN.fullmatch(compass_user_id.strip().lower())
    if not match:
        return None
    return int(match.group(1))
